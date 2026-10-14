"""Monthly climatologies for earthvis.html from the 1 deg per-year files written by
fetch_era5_sfc.py, fetch_era5_pl.py and fetch_wb2_shear.py.

    python3 build_climo.py OUT_DATA_DIR SFC_DIR PL_DIR WB2_DIR [var,...]

For every variable and period writes data/era5_<var>_<period>.bin.gz:
  gzip( Int16 LE [12 months][180 rows S->N][360 cols from 0 deg E] ), each row
  delta-coded along longitude (d[0]=q[0], d[i]=q[i]-q[i-1] mod 2^16; decode = running sum mod 2^16),
  value = q*scale + offset, q = -32768 = missing (no ocean for SST / sea ice).
Delta coding the smooth fields roughly halves the gzip size; it is exact (modular arithmetic).
Monthly climatology = plain mean of that calendar month over the period's years.
Also writes data/index.json (grid, periods, per-variable scale/offset/unit and checks)."""
import os, sys, gzip, json, numpy as np
# One period for now (present-day climate); add tuples here and to PERIODS in the page for more.
PERIODS = [('p9625', '1996–2025', 1996, 2025)]
# shear (s06, s200) comes from WeatherBench2 through 2022 and from the CDS for 2023 on
K0 = 273.15; DAY = 86400.0; G0 = 9.80665
# var: (dir key, file stem, convert fn, scale, offset, unit, long name)
V = {
 't2m': ('sfc', 't2m', lambda a: a - K0, .02, 0, '°C', '2 m air temperature'),
 'd2m': ('sfc', 'd2m', lambda a: a - K0, .02, 0, '°C', '2 m dewpoint temperature'),
 'sst': ('sfc', 'sst', lambda a: a - K0, .02, 0, '°C', 'Sea surface temperature'),
 'ci':  ('sfc', 'ci', lambda a: a * 100, .1, 0, '%', 'Sea-ice concentration'),
 'msl': ('sfc', 'msl', lambda a: a / 100, .02, 1000, 'hPa', 'Mean sea-level pressure'),
 'tcc': ('sfc', 'tcc', lambda a: a * 100, .1, 0, '%', 'Total cloud cover'),
 'tcwv': ('sfc', 'tcwv', lambda a: a, .02, 0, 'mm', 'Total column water vapour'),
 'cape': ('sfc', 'cape', lambda a: a, .5, 0, 'J/kg', 'CAPE (monthly mean)'),
 'u10': ('sfc', 'u10', lambda a: a, .02, 0, 'm/s', '10 m zonal wind'),
 'v10': ('sfc', 'v10', lambda a: a, .02, 0, 'm/s', '10 m meridional wind'),
 'sd':  ('sfc', 'sd', lambda a: a * 1000, .5, 0, 'mm', 'Snow depth (water equivalent)'),
 'mtpr': ('sfc', 'mtpr', lambda a: a * DAY, .004, 0, 'mm/day', 'Precipitation'),
 'msr':  ('sfc', 'msr', lambda a: a * DAY, .004, 0, 'mm/day', 'Snowfall (water equivalent)'),
 'mcpr': ('sfc', 'mcpr', lambda a: a * DAY, .004, 0, 'mm/day', 'Convective precipitation'),
 'mer':  ('sfc', 'mer', lambda a: a * DAY, .004, 0, 'mm/day', 'Evaporation rate (negative = evaporation)'),
 'mtnlwrf': ('sfc', 'mtnlwrf', lambda a: a, .1, 0, 'W/m²', 'TOA net longwave (negative = outgoing)'),
 'mtnswrf': ('sfc', 'mtnswrf', lambda a: a, .1, 0, 'W/m²', 'TOA net shortwave (absorbed solar)'),
 'mtdwswrf': ('sfc', 'mtdwswrf', lambda a: a, .1, 0, 'W/m²', 'TOA incoming solar'),
 'mslhf': ('sfc', 'mslhf', lambda a: a, .1, 0, 'W/m²', 'Surface latent heat flux (negative = upward)'),
 'msshf': ('sfc', 'msshf', lambda a: a, .1, 0, 'W/m²', 'Surface sensible heat flux (negative = upward)'),
 't850': ('pl', 't850', lambda a: a - K0, .02, 0, '°C', '850 hPa temperature'),
 'q850': ('pl', 'q850', lambda a: a * 1000, .002, 0, 'g/kg', '850 hPa specific humidity'),
 'z500': ('pl', 'z500', lambda a: a / G0, .2, 5500, 'm', '500 hPa geopotential height'),
 'w500': ('pl', 'w500', lambda a: a, 2e-4, 0, 'Pa/s', '500 hPa vertical velocity (omega)'),
}
for lev in (850, 500, 250):          # 200 hPa winds/heights are fetched (they feed nothing yet) but not served
    V[f'u{lev}'] = ('pl', f'u{lev}', lambda a: a, .02, 0, 'm/s', f'{lev} hPa zonal wind')
    V[f'v{lev}'] = ('pl', f'v{lev}', lambda a: a, .02, 0, 'm/s', f'{lev} hPa meridional wind')
V['s06'] = ('wb2', 's06', lambda a: a, .02, 0, 'm/s', 'Bulk shear 500 hPa − 10 m (mean of 6-hourly)')
V['s200'] = ('wb2', 's200', lambda a: a, .02, 0, 'm/s', 'Bulk shear 200 − 850 hPa (mean of 6-hourly)')

LATB = np.arange(-89.5, 90, 1.0); LONB = np.arange(0.5, 360, 1.0)
def wb2_to_1deg(a):
    """(12, 121 lat -90..90, 240 lon 0..358.5) -> (12, 180, 360) bilinear at 1 deg box centres"""
    la = np.arange(-90, 90.001, 1.5); lo = np.arange(0, 360, 1.5)
    fy = (LATB - la[0]) / 1.5; j0 = np.floor(fy).astype(int); wy = fy - j0
    fx = LONB / 1.5; i0 = np.floor(fx).astype(int); wx = fx - i0; i1 = (i0 + 1) % 240
    a0 = a[:, j0, :] * (1 - wy)[None, :, None] + a[:, j0 + 1, :] * wy[None, :, None]
    return a0[:, :, i0] * (1 - wx) + a0[:, :, i1] * wx

def load(dirs, v, y):
    d, stem = V[v][0], V[v][1]
    a = np.load(f'{dirs[d]}/{stem}_{y}.npy').astype(np.float64)
    if d == 'wb2': a = wb2_to_1deg(a)
    assert a.shape == (12, 180, 360), (v, y, a.shape)
    return a

def encode(c, sc, off):
    q = np.round((c - off) / sc)
    bad = ~np.isfinite(q)
    assert np.nanmax(np.abs(q)) < 32767, ('overflow', np.nanmin(q), np.nanmax(q))
    q = np.where(bad, -32768, q).astype(np.int64) & 0xFFFF
    d = q.copy(); d[..., 1:] = (q[..., 1:] - q[..., :-1]) & 0xFFFF
    return gzip.compress(d.astype('<u2').tobytes(), 9)

def decode(b):
    d = np.frombuffer(gzip.decompress(b), '<u2').reshape(12, 180, 360).astype(np.int64)
    q = np.cumsum(d, axis=-1) & 0xFFFF
    return np.where(q >= 32768, q - 65536, q)

W = np.cos(np.deg2rad(LATB))[:, None] * np.ones(360)
def gmean(a):
    ok = np.isfinite(a); return float((np.where(ok, a, 0) * W).sum() / (W * ok).sum())

if __name__ == '__main__':
    out, sfc, pl, wb2 = sys.argv[1:5]
    dirs = {'sfc': sfc, 'pl': pl, 'wb2': wb2}
    only = sys.argv[5].split(',') if len(sys.argv) > 5 else list(V)
    os.makedirs(out, exist_ok=True)
    ixf = f'{out}/index.json'
    ix = json.load(open(ixf)) if os.path.exists(ixf) else {}
    ix.update({'grid': {'lat0': -90, 'lon0': 0, 'g': 1, 'nlat': 180, 'nlon': 360},
               'periods': [{'k': k, 'label': l, 'y0': a, 'y1': b} for k, l, a, b in PERIODS],
               'encoding': 'gzip Int16 LE [12][180][360], rows delta-coded along longitude mod 2^16; value=q*scale+offset; q=-32768 missing',
               'source': 'ERA5 (ECMWF/Copernicus C3S) monthly means: NCAR GDEX ds633.1 for 1996-2022, Copernicus CDS for 2023-2025 (identical product); bulk shear from 6-hourly ERA5 (WeatherBench2 1.5 deg copy through 2022, CDS after)'})
    ix.setdefault('vars', {})
    for v in only:
        dk, stem, fn, sc, off, unit, name = V[v]
        ent = {'unit': unit, 'name': name, 'scale': sc, 'offset': off, 'periods': {}}
        for pk, pl_, y0, y1 in PERIODS:
            acc = np.zeros((12, 180, 360)); n = 0; got = []
            for y in range(y0, y1 + 1):
                if dk == 'wb2' and not os.path.exists(f'{dirs[dk]}/{stem}_{y}.npy'):
                    continue      # shear years not fetched yet: recorded below, shown on the page
                acc += fn(load(dirs, v, y)); n += 1; got.append(y)
            assert n >= 20, (v, pk, n)
            c = acc / n
            b = encode(c, sc, off)
            open(f'{out}/era5_{v}_{pk}.bin.gz', 'wb').write(b)
            r = decode(b).astype(float); r[r == -32768] = np.nan; r = r * sc + off
            err = np.nanmax(np.abs(r - c)); assert err <= sc * 0.5001, (v, pk, err)
            ann = c.mean(0)
            ent['periods'][pk] = {'n': n, 'y0': got[0], 'y1': got[-1], 'min': round(float(np.nanmin(c)), 3), 'max': round(float(np.nanmax(c)), 3),
                                  'gmean': round(gmean(ann), 4), 'kb': round(len(b) / 1024)}
        ix['vars'][v] = ent
        print(v, json.dumps(ent['periods']), flush=True)
        json.dump(ix, open(ixf, 'w'), indent=1, ensure_ascii=False)
