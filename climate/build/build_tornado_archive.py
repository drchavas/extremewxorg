#!/usr/bin/env python3
"""Tornado Archive (Maas et al. 2024, BAMS) -> 2-degree global tornado-day grid for EarthVis.

Input : tornadoes-noESWD.json from https://github.com/malcolmmaas/tornadoarchive-pub
        (GeoJSON FeatureCollection; ESWD/Europe is not in the public file).
Output: ../data/ta_tornado.json.gz, same sparse layout as ../../scs/trends/data/grid_*.json.gz:
        meta, ci (cell = row*nlon+col, rows S->N from lat0, cols from lon0), yi (year-year0),
        mi (month 1-12), v[threshold][k] = days in that box-year-month with >= 1 tornado at or
        above the threshold rating (UTC calendar day of the start time).

A tornado counts in every 2-degree box its path touches (paths sampled every 0.05 deg; points
fall in one box). The rating is the highest (E)F value given (DAT tracks list one per segment);
unrated tornadoes (-9) count only in "Any tornado".

    python3 -I build_tornado_archive.py tornadoes-noESWD.json ../data/ta_tornado.json.gz
"""
import sys, json, gzip, math, collections

G, LAT0, LON0, NLAT, NLON = 2.0, -90.0, -180.0, 90, 180
THR = [dict(k='any', label='Any tornado (incl. unrated)', min=-1),
       dict(k='ef1', label='(E)F1+', min=1),
       dict(k='ef2', label='(E)F2+ (significant)', min=2),
       dict(k='ef3', label='(E)F3+ (intense)', min=3)]


def rating(x):
    vals = x if isinstance(x, list) else [x]
    best = -9
    for v in vals:
        try:
            best = max(best, int(float(v)))
        except (TypeError, ValueError):
            pass
    return best


def lines(geom):
    if not geom:
        return []
    t = geom['type']
    if t == 'Point':
        return [[geom['coordinates']]]
    if t == 'LineString':
        return [geom['coordinates']]
    if t == 'MultiLineString':
        return geom['coordinates']
    if t == 'MultiPoint':
        return [[c] for c in geom['coordinates']]
    if t == 'GeometryCollection':
        return [l for g in geom['geometries'] for l in lines(g)]
    if t == 'Polygon':   # damage swaths; stored here as a bare ring (depth 2) or as GeoJSON rings (depth 3)
        co = geom['coordinates']
        return [co] if co and isinstance(co[0][0], (int, float)) else [co[0]]
    return []


def cell(lon, lat):
    lon = (lon - LON0) % 360.0
    r = min(NLAT - 1, max(0, int((lat - LAT0) // G)))
    c = int(lon // G) % NLON
    return r * NLON + c


def cells(geom):
    out = set()
    for ln in lines(geom):
        pts = [p[:2] for p in ln if p and len(p) >= 2]
        if len(pts) == 1:
            out.add(cell(*pts[0]))
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            dx = ((x1 - x0 + 180) % 360) - 180
            n = max(1, int(math.ceil(max(abs(dx), abs(y1 - y0)) / 0.05)))
            for i in range(n + 1):
                out.add(cell(x0 + dx * i / n, y0 + (y1 - y0) * i / n))
    return out


def main(src, dst):
    feats = json.load(open(src))['features']
    days = collections.defaultdict(lambda: [set() for _ in THR])   # (cell, y, m) -> per threshold set of days
    y0, y1, last = 9999, 0, ''
    cc = collections.Counter()
    for f in feats:
        p = f['properties']
        t = p.get('datetime-start') or ''
        if len(t) < 10:
            continue
        Y, M, D = int(t[:4]), int(t[5:7]), int(t[8:10])
        if Y < 1950:
            continue
        r = rating(p.get('f-scale'))
        cs = cells(f.get('geometry'))
        if not cs:
            continue
        y0, y1, last = min(y0, Y), max(y1, Y), max(last, t[:10])
        for c in p.get('countries') or []:
            cc[c] += 1
        for c in cs:
            slot = days[(c, Y, M)]
            for i, th in enumerate(THR):
                if r >= th['min'] or th['min'] < 0:
                    slot[i].add(D)
    keys = sorted(days, key=lambda k: (k[1], k[2], k[0]))
    out = dict(
        meta=dict(hazard='tornado', label='Tornado (Tornado Archive, worldwide)', unit='(E)F',
                  thresholds=THR, year0=y0, year1=y1, through=last[:7], grid=G, lat0=LAT0, lon0=LON0,
                  nlat=NLAT, nlon=NLON, gaps=[],
                  source='The Tornado Archive (Maas et al. 2024, BAMS, doi:10.1175/BAMS-D-23-0123.1), '
                         'public file without ESWD (Europe)',
                  countries=dict(cc.most_common())),
        ci=[k[0] for k in keys], yi=[k[1] - y0 for k in keys], mi=[k[2] for k in keys],
        v=[[len(days[k][i]) for k in keys] for i in range(len(THR))])
    with gzip.open(dst, 'wt', compresslevel=9) as fh:
        json.dump(out, fh, separators=(',', ':'))
    print(dst, len(keys), 'box-months', y0, y1, last)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
