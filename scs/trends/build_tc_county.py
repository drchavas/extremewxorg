#!/usr/bin/env python3
"""
County tropical-cyclone wind and rain records for the multi-hazard dashboard (scsdash.html),
taken from the tcviewer.org Storm Hazards & Impacts data.

    python3 build_tc_county.py [path/to/tcviewer/impacts/data]     # -> data/tc_county.json.gz

Default input: ../../../tcviewer/impacts/data (the tcviewer repo beside this one in Dan's
"Personal Website" folder). That repo refreshes itself on GitHub every 6 h, so `git pull` it
first, or point this script at a fresh checkout.

What a record is. tcviewer.org builds one file per Atlantic / East-Pacific storm since 2004 whose
34-kt wind radii touched a U.S. county. For every county the storm reached it stores
  w = [share of the county inside the 34-, 50-, 64-kt swath]   (IBTrACS USA wind radii)
  r = [county-average, county-highest storm-total rain, in]   (PRISM daily 4 km, CONUS only)
This script keeps, per (county, storm): the highest wind level reached anywhere in the county
(0 none, 1 = 34 kt/39 mph, 2 = 50 kt/58 mph, 3 = 64 kt/74 mph, i.e. w[k] > 0 -- the same rule
tcviewer's own wind map uses) and the county-highest rain (the same number tcviewer maps), in
tenths of an inch. The dashboard turns those into storms per year at each threshold.

Seasons. A storm belongs to its IBTrACS season. The newest season is left out of the rates until
it is over (Atlantic and East Pacific seasons end Nov 30), so `year1` is the last complete one; its
storms are still listed, flagged, so the county list is current.
"""
import datetime as dt, glob, gzip, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', '..', '..', 'tcviewer', 'impacts', 'data')
OUT = os.path.join(HERE, 'data', 'tc_county.json.gz')

idx = json.load(open(os.path.join(SRC, 'index.json')))
built = idx['built']                                   # 'YYYY-MM-DD HH:MM UTC'
bt = dt.datetime.strptime(built[:16], '%Y-%m-%d %H:%M')
year1 = bt.year if (bt.month, bt.day) >= (12, 1) else bt.year - 1   # last complete season

storms, recs = [], {}
counties = {}
for f in sorted(glob.glob(os.path.join(SRC, 'storms', '*.json'))):
    d = json.load(open(f))
    us = d.get('us') or d.get('t')
    mon = int(us[0][4:6])
    si = len(storms)
    storms.append([d['slug'], d['name'].title() if d['name'] != 'UNNAMED' else 'Unnamed', d['year'], mon])
    for g, c in d['counties'].items():
        w, r = c.get('w'), c.get('r')
        wl = (3 if w[2] > 0 else 2 if w[1] > 0 else 1 if w[0] > 0 else 0) if w else 0
        rr = int(round(r[1] * 10)) if r else -1
        if wl == 0 and rr < 0:
            continue
        ci = counties.setdefault(g, len(counties))
        recs[(ci, si)] = (wl, rr)

order = sorted(recs)
# distance to the sea coast for every county on the dashboard's map, for the coast-aware
# smoothing of these rows (see coast_dist.py)
sys.path.insert(0, HERE)
from coast_dist import county_coast_km
coast = county_coast_km()
obj = {
    'meta': {
        'source': 'tcviewer.org Storm Hazards & Impacts (IBTrACS USA wind radii; PRISM daily 4 km rain)',
        'built': built, 'year0': idx.get('year0', 2004), 'year1': year1,
        'n_storms': len(storms),
        'note': 'Atlantic/East-Pacific storms whose 34-kt winds reached a U.S. county. wl: highest wind '
                'level reached anywhere in the county (1=34 kt, 2=50 kt, 3=64 kt). rr: county-highest '
                'storm-total rain in tenths of an inch, -1 = no PRISM value (outside the lower 48).',
    },
    'storms': storms,                                  # [slug, name, season, month of U.S. arrival]
    'counties': list(counties),
    'ci': [k[0] for k in order], 'si': [k[1] for k in order],
    'wl': [recs[k][0] for k in order], 'rr': [recs[k][1] for k in order],
    'coast': coast,                                    # GEOID -> km from the sea coast (0 = on it)
}
with gzip.open(OUT, 'wt', compresslevel=9) as fh:
    json.dump(obj, fh, separators=(',', ':'))
print(f'{len(storms)} storms, {len(counties)} counties, {len(order)} records, seasons '
      f'{obj["meta"]["year0"]}-{year1} in the rates; wrote {OUT} ({os.path.getsize(OUT)/1e3:.0f} KB)')
