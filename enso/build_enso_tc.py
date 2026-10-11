#!/usr/bin/env python3
"""
Build the monthly tropical-cyclone grid for ensogrid.html.

    python3 build_enso_tc.py ibtracs.ALL.list.v04r01.csv data [--y0 1980] [--y1 2026]

tctrend.html's grid_usa.json.gz carries (cell, year) records only -- its month
dimension exists per basin, not per cell -- so an ENSO composite for "September
in El Nino years" cannot be read from it.  This builder keeps the month, and
nothing else that page needs: one record per (5 deg cell, calendar year, month,
intensity bin), plus a genesis table.

Conventions follow build_tc_trends.py so the two pages agree:
  * IBTrACS v04r01, TRACK_TYPE main / PROVISIONAL / US-PROVISIONAL (spurs dropped)
  * synoptic times only (00/06/12/18 UTC, minute 0) -> 4 positions = 1 storm-day
  * USA_WIND (1-minute sustained) only
  * 5 deg cells, 0-360 E, latitude -60..60 (the TC page's 2,592-cell grid, |lat|<60)
Differences, deliberate:
  * Extratropical (ET) and disturbance (DS) stages are dropped.  An ENSO composite of
    "tropical cyclone activity" should not count an extratropical remnant crossing the
    North Atlantic in October; tctrend's default also keeps ET positions.
    NR ("not reported") and MX ("mixture") are KEPT: NR is not a stage, it means the
    agency recorded none.  IBTrACS labels every North Indian position NR in 1990-95,
    all South Atlantic positions in 2010-11, and every provisional track (the latest
    season) NR -- an earlier TS/SS-only filter silently erased all of those (the 1991
    Bangladesh cyclone, most of 2026's West Pacific).
  * Positions without a wind report, or below 34 kt, are not kept: every field
    here starts at tropical-storm strength.

Output: data/tc_month.json.gz
  meta   grid / lat0 / nlat / nlon / year0 / year1 / through / bins / source
  ci,yi,mi,bi   parallel index arrays (cell, year offset, month 1-12, bin 0..2)
  n             6-hourly positions (storm-days x 4)
  a             sum of Vmax^2 over those positions, kt^2 / 100 (ACE x 100)
  gci,gyi,gmi   genesis: cell/year/month of each storm's first TS+ position
"""
import sys, json, gzip, argparse
import numpy as np, pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument('csv'); ap.add_argument('out')
ap.add_argument('--y0', type=int, default=1980)
ap.add_argument('--y1', type=int, default=None, help='last calendar year kept (default: all)')
ap.add_argument('--grid', type=float, default=5.0)
A = ap.parse_args()
G = A.grid; LAT0 = -60.0; NLAT = int(120 / G); NLON = int(360 / G)
EDGES = [34, 64, 96]
BINS = ['34–63 kt', '64–95 kt', '≥96 kt']

d = pd.read_csv(A.csv, usecols=['SID', 'BASIN', 'ISO_TIME', 'NATURE', 'LAT', 'LON', 'USA_WIND', 'TRACK_TYPE'],
                skiprows=[1], keep_default_na=False, low_memory=False)
d = d[d.TRACK_TYPE.isin(['main', 'PROVISIONAL', 'US-PROVISIONAL'])]
t = pd.to_datetime(d.ISO_TIME, errors='coerce')
d = d.assign(t=t)
d = d[(t.dt.hour.isin([0, 6, 12, 18]) & (t.dt.minute == 0)).fillna(False)]
for c in ['LAT', 'LON', 'USA_WIND']:
    d[c] = pd.to_numeric(d[c], errors='coerce')
d = d[d.LAT.notna() & d.LON.notna() & (d.USA_WIND >= 34) & ~d.NATURE.isin(['ET', 'DS'])]
d = d[(d.t.dt.year >= A.y0) & (d.LAT.abs() < 60)]
if A.y1 is not None: d = d[d.t.dt.year <= A.y1]
li = np.floor((d.LAT.to_numpy() - LAT0) / G).astype(int)
ki = np.floor((d.LON.to_numpy() % 360.0) / G).astype(int) % NLON
v = d.USA_WIND.to_numpy(float)
b = np.searchsorted(EDGES, v, side='right') - 1
d = d.assign(ci=li * NLON + ki, yi=d.t.dt.year.to_numpy() - A.y0, mi=d.t.dt.month.to_numpy(), bi=b, v2=v * v)
g = d.groupby(['ci', 'yi', 'mi', 'bi']).agg(n=('v2', 'size'), a=('v2', 'sum')).reset_index()
gen = d.sort_values('t').groupby('SID').first().reset_index()
through = str(d.t.max().date())
out = {
    'meta': {'grid': G, 'lat0': LAT0, 'lon0': 0.0, 'nlat': NLAT, 'nlon': NLON,
             'year0': A.y0, 'year1': int(d.t.dt.year.max()), 'through': through, 'bins': BINS,
             'source': 'IBTrACS v04r01 (NOAA NCEI), USA_WIND, synoptic 6-hourly, NATURE not ET/DS, Vmax >= 34 kt',
             'records': int(len(g)), 'storms': int(len(gen))},
    'ci': g.ci.tolist(), 'yi': g.yi.tolist(), 'mi': g.mi.tolist(), 'bi': g.bi.tolist(),
    'n': g.n.tolist(), 'a': [int(round(x / 100)) for x in g.a],
    'gci': gen.ci.tolist(), 'gyi': gen.yi.tolist(), 'gmi': gen.mi.tolist(),
}
with gzip.open(f'{A.out}/tc_month.json.gz', 'wt', compresslevel=9) as f:
    json.dump(out, f, separators=(',', ':'))
print(f'{len(d):,} positions, {len(gen):,} storms, {len(g):,} records, through {through}')
# Sanity: NA calendar-year ACE against the published season values (2005 245.3, 1994 32.0)
na = d[d.BASIN == 'NA']
print('NA ACE 2005:', round(na[na.t.dt.year == 2005].v2.sum() / 1e4, 1), ' 1994:', round(na[na.t.dt.year == 1994].v2.sum() / 1e4, 1))
ni = d[d.BASIN == 'NI']
print('NI ACE 1991:', round(ni[ni.t.dt.year == 1991].v2.sum() / 1e4, 1), '(was 0 under the TS/SS-only filter)')
