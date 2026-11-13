#!/usr/bin/env python3
"""Radius-based event climatologies for EarthVis: "days per year with an event within R km".

Why: counting events per latitude-longitude box makes a box's number depend on its area, which shrinks toward the
poles (a 5 deg box at 60N is half the size of one at the equator) and changes with the grid. Counting, for each point,
the days on which an event came within a fixed radius keeps the human meaning ("about 5 days a year") and is the same
everywhere on the globe (Dan, 2026-11-13: option (c)).

    python3 -I build_radius_counts.py OUTDIR --scs ../../scs/trends --ibtracs ib.csv --ta tornadoes-noESWD.json \
            --etc etc_points.csv etc_tracks.csv [--only tc,etc,us,derecho,ta]

Fields (key, radius, grid, years):
  tcd     500 km  global 1 deg   1996-2025  days with a tropical cyclone (TS+ / Cat1+ / Cat3+) centre within R
  tcace   500 km  global 1 deg   1996-2025  ACE of storm positions within R, 10^4 kt^2 per year
  tcgen   500 km  global 1 deg   1996-2025  storms whose first TS+ position is within R
  etc     500 km  global 1 deg   1996-2025  days with an extratropical-cyclone centre within R (filtered / deep / all lows)
  hail, tornado, wind  80 km  CONUS 0.25 deg  1996-2025  days with a Storm Events report at/above threshold within R
  derechoday 100 km CONUS 0.25 deg  1996-2025  days with a core report of a definitive derecho within R
  tatorn  80 km   global 0.5 deg 1992-2021  days with a tornado path (Tornado Archive) within R

Conventions copied from the builders that feed the old box grids, so the two agree in what counts as an event:
  * TCs: ../../enso/build_enso_tc.py (IBTrACS main/provisional tracks, synoptic 6-hourly, USA_WIND >= 34 kt,
    NATURE not ET/DS). Day = UTC date.
  * Storm Events: ../../scs/trends/build_scs_grid.py (day = local BEGIN date; BEGIN_LAT/LON, county centroid when
    missing or outside the domain), read from events_<hz>_pts.json.gz + events_<hz>.json.gz (county-type rows only).
  * Derechos: ../../scs/trends/build_derecho_data.py grid_days (tier 'definitive', core reports, dated by swath start).
  * Tornado Archive: build_tornado_archive.py (UTC start date, highest rating, waterspouts dropped; path sampled
    every ~0.05 deg).
  * ETCs: Chavas-lab global ETC tracks (draft 2026-11-13; TempestExtremes, Gore et al. 2023 settings, hourly infill).
    Day = UTC date; points every 3 h. "ETC" = not IBTrACS-matched, track reaches 30 deg, point below 1500 m terrain.

Output: OUTDIR/rad_<key>.bin.gz  Int16 LE [threshold][12 months][nlat rows S->N][nlon], rows delta-coded along
longitude mod 2^16 (like era5_*.bin.gz); value = q * scale; q = -32768 = outside the domain.
Values are the mean per year of that calendar month, so months sum to a yearly total.
OUTDIR/rad_index.json carries grids, thresholds, scales, radii and years.
"""
import sys, os, json, gzip, math, argparse, collections, datetime as dt
import numpy as np
from sklearn.neighbors import BallTree

RE = 6371.0
GRIDS = {
    'g1':  dict(lat0=-90.0, lon0=0.0, g=1.0, nlat=180, nlon=360, glob=True),
    'r05': dict(lat0=-90.0, lon0=0.0, g=0.5, nlat=360, nlon=720, glob=True),
    'rus': dict(lat0=24.0, lon0=-126.0, g=0.25, nlat=104, nlon=240, glob=False),
}
_TREES = {}


def centers(gk):
    G = GRIDS[gk]
    la = G['lat0'] + (np.arange(G['nlat']) + 0.5) * G['g']
    lo = G['lon0'] + (np.arange(G['nlon']) + 0.5) * G['g']
    return np.meshgrid(la, lo, indexing='ij')


def tree(gk):
    if gk not in _TREES:
        la, lo = centers(gk)
        _TREES[gk] = BallTree(np.radians(np.c_[la.ravel(), lo.ravel()]), metric='haversine')
    return _TREES[gk]


def hits(gk, la, lo, R):
    """list of cell-index arrays, one per point"""
    if len(la) == 0: return []
    return tree(gk).query_radius(np.radians(np.c_[la, lo]), r=R / RE)


class Acc:
    """monthly accumulators [nthr][12][N] for one field"""
    def __init__(self, gk, nthr):
        G = GRIDS[gk]; self.gk = gk; self.N = G['nlat'] * G['nlon']
        self.A = np.zeros((nthr, 12, self.N))

    def day(self, month, la, lo, lev, R):
        """one day: points (la, lo) with threshold level lev (highest threshold index met; -1 = none).
        Adds 1 to every cell within R of any point at or above each threshold."""
        la, lo, lev = np.asarray(la, float), np.asarray(lo, float), np.asarray(lev, int)
        ok = lev >= 0
        if not ok.any(): return
        la, lo, lev = la[ok], lo[ok], lev[ok]
        # positions repeated within a day add nothing: dedupe at ~1 km
        key = np.unique(np.c_[np.round(la, 2), np.round(lo, 2), lev], axis=0)
        H = hits(self.gk, key[:, 0], key[:, 1], R); L = key[:, 2].astype(int)
        for j in range(self.A.shape[0]):
            sel = [h for h, l in zip(H, L) if l >= j]
            if not sel: break
            self.A[j, month - 1, np.unique(np.concatenate(sel))] += 1


def write(out, key, acc, ny, mask, meta, IX):
    A = acc.A / ny
    G = GRIDS[acc.gk]
    mx = float(A.max()) if A.size else 0.0
    sc = 10 ** math.floor(math.log10(max(mx, 1e-9) / 2500))      # ~2500+ steps over the monthly range: plenty, and compresses well
    for m_ in (5, 2, 1):
        if mx / (sc * m_) >= 2500: sc *= m_; break
    q = np.round(A / sc).astype(np.int32)
    if mask is not None: q[:, :, ~mask.ravel()] = -32768
    q = q.astype(np.int16).reshape(-1, G['nlon']).astype(np.uint16)
    d = q.copy(); d[:, 1:] = (q[:, 1:].astype(np.int32) - q[:, :-1].astype(np.int32)) & 0xFFFF
    fn = f'rad_{key}.bin.gz'
    with gzip.open(os.path.join(out, fn), 'wb', compresslevel=9) as fh: fh.write(d.astype('<u2').tobytes())
    g = {k: G[k] for k in ('lat0', 'lon0', 'g', 'nlat', 'nlon')}; g['global'] = G['glob']; g['key'] = acc.gk
    yearly = A.sum(axis=1)                                         # [thr][N]
    if mask is not None: yearly = yearly[:, mask.ravel()]
    IX[key] = dict(meta, file=fn, grid=g, nthr=int(A.shape[0]), scale=sc,
                   max_month=[round(float(A[j].max()), 4) for j in range(A.shape[0])],
                   max_year=[round(float(yearly[j].max()), 3) for j in range(A.shape[0])],
                   kb=round(os.path.getsize(os.path.join(out, fn)) / 1024))
    print(f'  {fn}: {os.path.getsize(os.path.join(out, fn)) / 1e3:.0f} kB, scale {sc}, yearly max',
          IX[key]['max_year'], flush=True)


# ---------------------------------------------------------------- tropical cyclones
def build_tc(a, IX, Y0=1996, Y1=2025, R=500.0):
    import pandas as pd
    d = pd.read_csv(a.ibtracs, usecols=['SID', 'ISO_TIME', 'NATURE', 'LAT', 'LON', 'USA_WIND', 'TRACK_TYPE'],
                    skiprows=[1], keep_default_na=False, low_memory=False)
    d = d[d.TRACK_TYPE.isin(['main', 'PROVISIONAL', 'US-PROVISIONAL'])]
    t = pd.to_datetime(d.ISO_TIME, errors='coerce'); d = d.assign(t=t)
    d = d[(t.dt.hour.isin([0, 6, 12, 18]) & (t.dt.minute == 0)).fillna(False)]
    for c in ['LAT', 'LON', 'USA_WIND']: d[c] = pd.to_numeric(d[c], errors='coerce')
    d = d[d.LAT.notna() & d.LON.notna() & (d.USA_WIND >= 34) & ~d.NATURE.isin(['ET', 'DS'])]
    gen = d.sort_values('t').groupby('SID').first().reset_index()         # first TS+ position (any year)
    d = d[(d.t.dt.year >= Y0) & (d.t.dt.year <= Y1)]
    gen = gen[(gen.t.dt.year >= Y0) & (gen.t.dt.year <= Y1)]
    v = d.USA_WIND.to_numpy(float); lev = np.searchsorted([34, 64, 96], v, side='right') - 1
    print(f'TC: {len(d):,} positions, {len(gen):,} storms', flush=True)
    den = Acc('g1', 3); d = d.assign(lev=lev, day=d.t.dt.date)
    for day, g in d.groupby('day'):
        den.day(day.month, g.LAT.to_numpy(), g.LON.to_numpy() % 360, g.lev.to_numpy(), R)
    ace = Acc('g1', 1)
    H = hits('g1', d.LAT.to_numpy(), d.LON.to_numpy() % 360, R)
    for h, w, m in zip(H, v * v / 1e4, d.t.dt.month.to_numpy()): ace.A[0, m - 1, h] += w
    gn = Acc('g1', 1)
    H = hits('g1', gen.LAT.to_numpy(), gen.LON.to_numpy() % 360, R)
    for h, m in zip(H, gen.t.dt.month.to_numpy()): gn.A[0, m - 1, h] += 1
    src = 'IBTrACS v04r01 (NOAA NCEI), USA_WIND, synoptic 6-hourly, NATURE not ET/DS, Vmax >= 34 kt'
    ny = Y1 - Y0 + 1
    write(a.out, 'tcd', den, ny, None, dict(R_km=R, y0=Y0, y1=Y1, source=src, what='days with a tropical-cyclone centre within R',
          thresholds=['Vmax ≥ 34 kt (tropical storm+)', 'Vmax ≥ 64 kt (hurricane / Cat 1+)', 'Vmax ≥ 96 kt (major / Cat 3+)']), IX)
    write(a.out, 'tcace', ace, ny, None, dict(R_km=R, y0=Y0, y1=Y1, source=src, what='ACE (sum of Vmax² / 10⁴ kt²) of 6-hourly positions within R'), IX)
    write(a.out, 'tcgen', gn, ny, None, dict(R_km=R, y0=Y0, y1=Y1, source=src, what='storms whose first TS+ position lies within R'), IX)


# ---------------------------------------------------------------- extratropical cyclones
def build_etc(a, IX, Y0=1996, Y1=2025, R=500.0):
    import pandas as pd
    pts_f, trk_f = a.etc
    tr = pd.read_csv(trk_f, usecols=['track_id', 'lowlat'])
    low = set(tr.track_id[tr.lowlat == 1])
    keep = []
    for ch in pd.read_csv(pts_f, usecols=['track_id', 'iso_time', 'lat', 'lon', 'slp_hpa', 'elev_m', 'tc_sid'],
                          dtype={'tc_sid': str}, keep_default_na=False, chunksize=2_000_000):
        y = ch.iso_time.str[:4].astype(int); hr = ch.iso_time.str[11:13].astype(int)
        ch = ch[(y >= Y0) & (y <= Y1) & (hr % 3 == 0)]         # every 3 h: steps of ~100 km, well inside R
        etc = (~ch.track_id.isin(low)) & (ch.tc_sid == '') & (ch.elev_m < 1500)
        keep.append(pd.DataFrame(dict(day=ch.iso_time.str[:10], la=ch.lat.astype(float).round(2),
                                      lo=(ch.lon.astype(float) % 360).round(2), e=etc, dp=etc & (ch.slp_hpa < 990))))
    d = pd.concat(keep); del keep
    print(f'ETC: {len(d):,} 3-hourly points, {int(d.e.sum()):,} ETC', flush=True)
    # thresholds are not nested (0 = ETC, 1 = deep ETC, 2 = any closed low), so each is its own point set
    acc = Acc('g1', 3)
    for day, g in d.groupby('day', sort=False):
        m = int(day[5:7])
        key = g.groupby(['la', 'lo'], as_index=False)[['e', 'dp']].max()
        H = hits('g1', key.la.to_numpy(), key.lo.to_numpy(), R)
        for j, sel in enumerate((key.e.to_numpy(), key.dp.to_numpy(), np.ones(len(key), bool))):
            if sel.any(): acc.A[j, m - 1, np.unique(np.concatenate([h for h, s_ in zip(H, sel) if s_]))] += 1
    write(a.out, 'etc', acc, Y1 - Y0 + 1, None, dict(R_km=R, y0=Y0, y1=Y1,
          source='Global ERA5 surface-low tracks (TempestExtremes; Gore et al. 2023 settings, hourly infill), draft 2026-11-13',
          what='days with a cyclone centre within R',
          thresholds=['Extratropical cyclones (tropical, low-latitude and high-terrain lows removed)',
                      'Deep extratropical cyclones (central pressure < 990 hPa)',
                      'All closed surface lows (no filtering)']), IX)


# ---------------------------------------------------------------- U.S. Storm Events
def county_centroids(topo_path):
    topo = json.load(gzip.open(topo_path, 'rt'))
    obj = topo['objects'][list(topo['objects'])[0]]
    sx, sy = topo['transform']['scale']; tx, ty = topo['transform']['translate']
    dec = []
    for arc in topo['arcs']:
        x = y = 0; p = []
        for dx, dy in arc: x += dx; y += dy; p.append((x * sx + tx, y * sy + ty))
        dec.append(p)
    out = {}
    for g in obj['geometries']:
        ids = []
        def walk(z):
            for e in z:
                if isinstance(e, list): walk(e)
                else: ids.append(e)
        walk(g['arcs'])
        P = [q for i in ids for q in dec[i if i >= 0 else ~i]]
        if P: out[g['properties']['GEOID']] = (sum(q[1] for q in P) / len(P), sum(q[0] for q in P) / len(P))
    return out


def us_mask(states_topo):
    """0.25 deg cells with any of 4x4 sub-points inside a CONUS state polygon"""
    from matplotlib.path import Path
    topo = json.load(gzip.open(states_topo, 'rt'))
    obj = topo['objects'][list(topo['objects'])[0]]
    sx, sy = topo['transform']['scale']; tx, ty = topo['transform']['translate']
    dec = []
    for arc in topo['arcs']:
        x = y = 0; p = []
        for dx, dy in arc: x += dx; y += dy; p.append((x * sx + tx, y * sy + ty))
        dec.append(p)
    def ring(r):
        p = []
        for i in r:
            seg = dec[i] if i >= 0 else dec[~i][::-1]
            p.extend(seg if not p else seg[1:])
        return np.array(p)
    G = GRIDS['rus']; f = 4
    la = G['lat0'] + (np.arange(G['nlat'] * f) + 0.5) * G['g'] / f
    lo = G['lon0'] + (np.arange(G['nlon'] * f) + 0.5) * G['g'] / f
    LA, LO = np.meshgrid(la, lo, indexing='ij'); P = np.c_[LO.ravel(), LA.ravel()]
    inside = np.zeros(len(P), bool)
    for g in obj['geometries']:
        polys = g['arcs'] if g['type'] == 'MultiPolygon' else [g['arcs']] if g['type'] == 'Polygon' else []
        for poly in polys:
            r = ring(poly[0])
            if r[:, 0].max() < -126 or r[:, 0].min() > -66 or r[:, 1].min() > 50 or r[:, 1].max() < 24: continue
            bb = (P[:, 0] >= r[:, 0].min()) & (P[:, 0] <= r[:, 0].max()) & (P[:, 1] >= r[:, 1].min()) & (P[:, 1] <= r[:, 1].max())
            if bb.any(): inside[np.where(bb)[0][Path(r).contains_points(P[bb])]] = True
    return inside.reshape(G['nlat'], f, G['nlon'], f).any(axis=(1, 3))


def build_us(a, IX, Y0=1996, Y1=2025, R=80.0):
    D = os.path.join(a.scs, 'data')
    cents = county_centroids(os.path.join(a.scs, 'geo', 'counties.topo.json.gz'))
    mask = us_mask(os.path.join(a.scs, 'geo', 'states.topo.json.gz'))
    print('U.S. mask cells', int(mask.sum()), flush=True)
    LAT0, LAT1, LON0, LON1 = 24.0, 50.0, -126.0, -66.0
    for hz in ('hail', 'tornado', 'wind'):
        e = json.load(gzip.open(os.path.join(D, f'events_{hz}.json.gz')))
        p = json.load(gzip.open(os.path.join(D, f'events_{hz}_pts.json.gz')))
        mins = [t['min'] for t in e['meta']['thresholds']]; cty = e['counties']
        acc = Acc('rus', len(mins)); nfall = ndrop = nrep = 0
        for di, day in enumerate(e['days']):
            Y, M = int(day[:4]), int(day[5:7])
            if not Y0 <= Y <= Y1: continue
            la, lo, lv = [], [], []
            for k in range(p['off'][di], p['off'][di + 1]):
                x, y = p['lo'][k], p['la'][k]
                if y is None or x is None or not (LAT0 <= y <= LAT1 and LON0 <= x <= LON1):
                    c = cents.get(cty[p['ci'][k]])
                    if c is None or not (LAT0 <= c[0] <= LAT1 and LON0 <= c[1] <= LON1): ndrop += 1; continue
                    y, x = c; nfall += 1
                v = p['mag'][k]; L = 0
                if v is not None:
                    for j in range(1, len(mins)):
                        if v >= mins[j]: L = j
                la.append(y); lo.append(x); lv.append(L); nrep += 1
            acc.day(M, la, lo, lv, R)
        print(f'{hz}: {nrep:,} reports ({nfall:,} at county centroid, {ndrop:,} unplaceable)', flush=True)
        write(a.out, hz, acc, Y1 - Y0 + 1, mask, dict(R_km=R, y0=Y0, y1=Y1, source='NOAA/NCEI Storm Events Database',
              what='days with a report at or above the threshold within R (local calendar date)',
              thresholds=[t['label'] for t in e['meta']['thresholds']]), IX)


def build_derecho(a, IX, Y0=1996, Y1=2025, R=100.0):
    D = os.path.join(a.scs, 'data'); mask = us_mask(os.path.join(a.scs, 'geo', 'states.topo.json.gz'))
    g = json.load(gzip.open(os.path.join(D, 'grid_derechoday.json.gz')))['meta']
    mins = [t['min'] for t in g['thresholds']]
    ev = json.load(gzip.open(os.path.join(D, 'derecho.json.gz')))['events']
    byday = collections.defaultdict(list); nev = 0
    for e in ev:
        if e['tier'] != 'definitive': continue
        rep = e['reports']
        if isinstance(rep, str): import ast; rep = ast.literal_eval(rep)
        sd = dt.datetime.fromisoformat(e['start'])
        if not Y0 <= sd.year <= Y1: continue
        core = [r for r in rep if r['d']]; nev += bool(core)
        for r in core:
            L = 0
            for j in range(1, len(mins)):
                if r['kt'] >= mins[j]: L = j
            if r['kt'] < mins[0]: L = -1
            byday[sd.date()].append((r['la'], r['lo'], L))
    acc = Acc('rus', len(mins))
    for day, rr in byday.items(): acc.day(day.month, *zip(*rr), R)
    print(f'derecho: {nev} definitive events with core reports', flush=True)
    write(a.out, 'derechoday', acc, Y1 - Y0 + 1, mask, dict(R_km=R, y0=Y0, y1=Y1,
          source='Squitieri, Wade & Jirak (2026, BAMS) derecho archive; reports from NOAA/NCEI Storm Events',
          what='days with a core report of a definitive derecho within R (dated by the swath start)',
          thresholds=[t['label'] for t in g['thresholds']]), IX)


# ---------------------------------------------------------------- Tornado Archive (worldwide)
def build_ta(a, IX, Y0=1992, Y1=2021, R=80.0):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import build_tornado_archive as TA
    feats = json.load(open(a.ta))['features']
    byday = collections.defaultdict(list); n = nws = 0
    allp = []
    for f in feats:
        p = f['properties']; t = p.get('datetime-start') or ''
        if len(t) < 10: continue
        Y = int(t[:4])
        if Y < 1950: continue
        r = TA.rating(p.get('f-scale'))
        if TA.waterspout(p, r): nws += 1; continue
        L = 3 if r >= 3 else 2 if r >= 2 else 1 if r >= 1 else 0
        pts = set()
        for ln in TA.lines(f.get('geometry')):
            P = [q[:2] for q in ln if q and len(q) >= 2]
            if len(P) == 1: pts.add((round(P[0][1], 2), round(P[0][0] % 360, 2)))
            for (x0, y0), (x1, y1) in zip(P, P[1:]):
                dx = ((x1 - x0 + 180) % 360) - 180
                k = max(1, int(math.ceil(max(abs(dx), abs(y1 - y0)) / 0.05)))
                for i in range(k + 1): pts.add((round(y0 + (y1 - y0) * i / k, 2), round((x0 + dx * i / k) % 360, 2)))
        if not pts: continue
        allp.extend(pts)
        if Y0 <= Y <= Y1:
            n += 1; byday[t[:10]].extend((y, x, L) for y, x in pts)
    acc = Acc('r05', 4)
    for day, rr in byday.items(): acc.day(int(day[5:7]), *zip(*rr), R)
    # domain: within R of any tornado in the whole archive (any year), so empty countries stay blank
    allp = np.array(sorted(set(allp)))
    m = np.zeros(acc.N, bool)
    for s in range(0, len(allp), 20000):
        H = hits('r05', allp[s:s + 20000, 0], allp[s:s + 20000, 1], R)
        if len(H): m[np.unique(np.concatenate(H))] = True
    print(f'Tornado Archive: {n:,} tornadoes {Y0}-{Y1} ({nws:,} waterspouts dropped, all years); domain cells {int(m.sum()):,}', flush=True)
    write(a.out, 'tatorn', acc, Y1 - Y0 + 1, m.reshape(360, 720), dict(R_km=R, y0=Y0, y1=Y1,
          source='The Tornado Archive (Maas et al. 2024, BAMS, doi:10.1175/BAMS-D-23-0123.1), public file without ESWD (Europe)',
          what='days with a tornado path within R (UTC date of the start time)',
          thresholds=[t['label'] for t in TA.THR]), IX)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('out'); ap.add_argument('--scs'); ap.add_argument('--ibtracs'); ap.add_argument('--ta')
    ap.add_argument('--etc', nargs=2); ap.add_argument('--only', default='tc,etc,us,derecho,ta')
    a = ap.parse_args(); only = set(a.only.split(','))
    ixf = os.path.join(a.out, 'rad_index.json')
    IX = json.load(open(ixf)) if os.path.exists(ixf) else {}
    F = IX.setdefault('fields', {})
    IX['encoding'] = ('gzip Int16 LE [threshold][12 months][nlat rows S->N][nlon], rows delta-coded along longitude '
                      'mod 2^16; value = q*scale; q = -32768 outside the domain; mean per year of each calendar month')
    IX['built'] = dt.date.today().isoformat()
    for k, fn in (('tc', build_tc), ('etc', build_etc), ('us', build_us), ('derecho', build_derecho), ('ta', build_ta)):
        if k in only:
            fn(a, F)
            json.dump(IX, open(ixf, 'w'), ensure_ascii=False, indent=1)
