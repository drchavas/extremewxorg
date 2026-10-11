#!/usr/bin/env python3
"""
Write the ERA5 monthly fields that ensogrid.html composites by ENSO phase.

    python3 build_enso_era5.py COARSE_DIR data [--y0 1979] [--y1 2025]

Inputs are 1 deg box means of ERA5 monthly fields produced by the two fetch scripts
kept beside this one (fetch_era5_gdex.py, fetch_era5_arco.py, era5_coarsen.py):
  * 1979-2022  NCAR GDEX ds633.1 "ERA5 monthly means" (the ECMWF monthly-mean product)
  * 2023-on    ARCO-ERA5 hourly (gs://gcp-public-data-arco-era5), averaged here to
               monthly means.  Checked against ds633.1 for Dec 2022: max |diff| over
               all boxes 0.001 K for 2 m temperature and 0.001 mm/day for precipitation.
Variables: 2 m temperature (K -> deg C), mean total precipitation rate and mean snowfall
rate (kg m-2 s-1 -> mm/day, water equivalent).

The page needs, for each of the twelve months June..May of every ENSO year
Y = 1979..2025 (June-December of Y, January-May of Y+1), the field on a 2 deg
grid.  It does every statistic itself -- climatology, detrending, composites, t-tests
-- so the strength threshold, phase and period stay live controls.

Output, one file per variable per month, data/era5_<var>_<MM>.bin.gz, plus one per
multi-month average (<var>_yr = the ENSO year Jun-May, _jja, _son, _djf, _mam), gzip of a
little-endian Int16Array laid out
    [ clim(cell) | anom(year 0, cell) | anom(year 1, cell) | ... ]
with cell = row*180 + col, row 0 = 90S..88S, col 0 = 0..2E.  clim is the mean over
all years written; anom = value - clim.  Both are scaled by 100 (0.01 deg C, 0.01
mm/day).  data/era5_index.json carries the grid, years and scale.
"""
import sys, os, json, gzip, argparse
import numpy as np
ap = argparse.ArgumentParser(); ap.add_argument('coarse'); ap.add_argument('out')
ap.add_argument('--y0', type=int, default=1979); ap.add_argument('--y1', type=int, default=2025)
A = ap.parse_args()
MONTHS = [6, 7, 8, 9, 10, 11, 12, 1, 2, 3, 4, 5]
VARS = {'t2m': {'label': '2 m temperature', 'unit': '°C', 'conv': lambda a: a - 273.15},
        'pr':  {'label': 'Precipitation', 'unit': 'mm/day', 'conv': lambda a: a * 86400.0, 'src': 'mtpr'},
        'sf':  {'label': 'Snowfall (water equivalent)', 'unit': 'mm/day', 'conv': lambda a: a * 86400.0, 'src': 'msr'}}
# Averages over several months, written as their own files so the default view (the whole
# ENSO year) costs one ~1 MB download rather than twelve.  Each is the plain mean of the
# monthly means (months weighted equally, not by their length).
AVGS = {'yr': [6, 7, 8, 9, 10, 11, 12, 1, 2, 3, 4, 5], 'jja': [6, 7, 8], 'son': [9, 10, 11],
        'djf': [12, 1, 2], 'mam': [3, 4, 5]}
_rda = {}
def field(v, y, m):
    """1 deg monthly mean (180 x 360, south->north, 0->360E)."""
    src = VARS[v].get('src', v)
    f = f'{A.coarse}/arco_{src}_{y}_{m:02d}.npy'
    if os.path.exists(f) and y >= 2023: return np.load(f)
    k = (src, y)
    if k not in _rda: _rda[k] = np.load(f'{A.coarse}/rda_{src}_{y}.npy')
    return _rda[k][m - 1]
lat1 = -89.5 + np.arange(180)
w1 = np.cos(np.deg2rad(lat1))
def to2(a):
    """2x2 box mean of 1 deg boxes, cos(lat) weighted -> (90, 180)."""
    ww = np.broadcast_to(w1[:, None], a.shape)
    s = (a * ww).reshape(90, 2, 180, 2).sum((1, 3)); n = ww.reshape(90, 2, 180, 2).sum((1, 3))
    return s / n
years = list(range(A.y0, A.y1 + 1))
os.makedirs(A.out, exist_ok=True)
stats = {}
def write(v, tag, X):
    clim = X.mean(0)
    an = X - clim
    q = np.concatenate([np.round(clim * 100).ravel(), np.round(an * 100).ravel()])
    assert np.isfinite(q).all() and np.abs(q).max() < 32767, (v, tag)
    fn, raw = f'{A.out}/era5_{v}_{tag}.bin.gz', q.astype('<i2').tobytes()
    # rewrite only on a real change, and with no timestamp in the gzip header, so a
    # rebuild does not churn every file in git
    if not (os.path.exists(fn) and gzip.open(fn).read() == raw):
        with open(fn, 'wb') as fh, gzip.GzipFile(fileobj=fh, mode='wb', compresslevel=9, mtime=0) as f:
            f.write(raw)
    stats[f'{v}_{tag}'] = [round(float(clim.min()), 2), round(float(clim.max()), 2)]
    print(v, tag, 'clim range', stats[f'{v}_{tag}'], 'max|anom|', round(float(np.abs(an).max()), 2), flush=True)
only = os.environ.get('ENSO_VARS')            # e.g. ENSO_VARS=sf to rebuild one variable
for v, spec in VARS.items():
    if only and v not in only.split(','): continue
    Xm = {}
    for m in MONTHS:
        Xm[m] = np.stack([spec['conv'](to2(field(v, y if m >= 6 else y + 1, m).astype(np.float64))) for y in years])
        write(v, f'{m:02d}', Xm[m])
    for tag, ms in AVGS.items():
        write(v, tag, np.mean([Xm[m] for m in ms], axis=0))
old = {}
if only and os.path.exists(f'{A.out}/era5_index.json'):
    old = json.load(open(f'{A.out}/era5_index.json')).get('clim_range', {})
stats = {**old, **stats}
idx = {'grid': 2.0, 'lat0': -90.0, 'lon0': 0.0, 'nlat': 90, 'nlon': 180, 'scale': 100,
       'years': years, 'months': MONTHS, 'avgs': AVGS,
       'vars': [{'k': k, 'label': s['label'], 'unit': s['unit']} for k, s in VARS.items()],
       'source': 'ERA5 (ECMWF/Copernicus C3S): NCAR GDEX ds633.1 monthly means 1979-2022; '
                 'ARCO-ERA5 hourly averaged to monthly 2023 on',
       'clim_range': stats}
json.dump(idx, open(f'{A.out}/era5_index.json', 'w'), indent=1)
