#!/usr/bin/env python3
"""Fetch CPC's Relative Oceanic Nino Index and write data/roni.json for ensogrid.html.

    python3 build_enso_roni.py data

Source: https://www.cpc.ncep.noaa.gov/data/indices/RONI.ascii.txt  (3-month running
seasons DJF ... NDJ; the YR column is the year of the season's middle month, so
"DJF 1998" is Dec 1997 - Feb 1998).  The page does the classification itself so that
the strength threshold can change; this script prints the default classification
for reference.
"""
import sys, json, urllib.request, datetime
URL = 'https://www.cpc.ncep.noaa.gov/data/indices/RONI.ascii.txt'
SEAS = ['DJF', 'JFM', 'FMA', 'MAM', 'AMJ', 'MJJ', 'JJA', 'JAS', 'ASO', 'SON', 'OND', 'NDJ']
txt = urllib.request.urlopen(URL, timeout=60).read().decode()
rows = [l.split() for l in txt.splitlines()[1:] if l.strip()]
vals = {}
for s, y, v in rows:
    vals[(int(y), SEAS.index(s))] = float(v)
y0 = min(y for y, _ in vals); y1 = max(y for y, _ in vals)
series = []          # flat, one per month index (month = centre month of the season)
for y in range(y0, y1 + 1):
    for k in range(12):
        series.append(vals.get((y, k)))
while series and series[-1] is None: series.pop()
last = len(series) - 1
out = {'source': URL, 'retrieved': datetime.date.today().isoformat(), 'year0': y0,
       'note': 'v[i] is the 3-month season centred on month (i % 12) of year year0 + i//12; index 0 = DJF year0 (centre Jan)',
       'last': f'{SEAS[last % 12]} {y0 + last // 12}', 'v': series}
json.dump(out, open(sys.argv[1] + '/roni.json', 'w'), separators=(',', ':'))

def classify(thr=0.5):
    """ENSO year Y = Jun Y .. Feb Y+1, classified by DJF of Y+1 (centre Jan Y+1), which must
    lie in a run of >= 5 consecutive overlapping seasons beyond +/-0.5 (CPC's episode rule)."""
    res = {}
    for Y in range(y0, y0 + len(series) // 12):
        i = (Y + 1 - y0) * 12          # DJF Y+1
        if i >= len(series) or series[i] is None: continue
        v = series[i]
        for sgn, lab in ((1, 'EN'), (-1, 'LN')):
            if sgn * v >= thr:
                a = i
                while a - 1 >= 0 and series[a - 1] is not None and sgn * series[a - 1] >= 0.5: a -= 1
                b = i
                while b + 1 < len(series) and series[b + 1] is not None and sgn * series[b + 1] >= 0.5: b += 1
                if b - a + 1 >= 5: res[Y] = lab
    return res
c = classify()
print('last season', out['last'])
for lab in ('EN', 'LN'):
    ys = [y for y, l in c.items() if l == lab and 1979 <= y <= 2025]
    print(lab, len(ys), ys)
c1 = classify(1.0)
for lab in ('EN', 'LN'):
    ys = [y for y, l in c1.items() if l == lab and 1979 <= y <= 2025]
    print(lab, '>=1.0', len(ys), ys)
