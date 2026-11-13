"""
Distance from every county to the coast, for the dashboard's coast-aware smoothing of the
tropical-cyclone rows (imported by build_tc_county.py).

Coastline: the arcs of Natural Earth's 1:10m admin-1 topology (../../enso/geo/admin1-10m.json.gz)
that belong to only one polygon. Because that file holds every country's states and provinces,
land borders (U.S.-Mexico, U.S.-Canada, and the Great Lakes, which are split between states and
provinces) are shared arcs and drop out, leaving the sea coast.

Distance: shortest distance from the county polygon (../geo/counties.topo.json.gz, the same file
the dashboard draws) to that coastline, in km, on a local equirectangular projection centred on
the county. A county that touches the sea is 0.
"""
import gzip, json, math, os
import numpy as np
from shapely.geometry import LineString, MultiLineString, Polygon, MultiPolygon, box
from shapely.ops import unary_union
from shapely.strtree import STRtree

HERE = os.path.dirname(os.path.abspath(__file__))


def _arcs(topo):
    sx, sy = topo['transform']['scale']; tx, ty = topo['transform']['translate']
    out = []
    for arc in topo['arcs']:
        x = y = 0; pts = []
        for dx, dy in arc:
            x += dx; y += dy
            pts.append((x * sx + tx, y * sy + ty))
        out.append(pts)
    return out


def _rings(arcs, idxs):
    pts = []
    for i in idxs:
        a = arcs[i] if i >= 0 else arcs[~i][::-1]
        pts.extend(a if not pts else a[1:])
    return pts


def _walk(geom, fn):
    t = geom['type']
    if t == 'Polygon':
        for r in geom['arcs']: fn(r)
    elif t == 'MultiPolygon':
        for p in geom['arcs']:
            for r in p: fn(r)


def coastline():
    topo = json.load(gzip.open(os.path.join(HERE, '..', '..', 'enso', 'geo', 'admin1-10m.json.gz')))
    obj = list(topo['objects'].values())[0]
    use = {}
    def count(ring):
        for i in ring:
            k = i if i >= 0 else ~i
            use[k] = use.get(k, 0) + 1
    for g in obj['geometries']:
        _walk(g, count)
    arcs = _arcs(topo)
    region = box(-180, 10, -55, 75)                  # the U.S., its territories nearby, and neighbours
    lines = []
    for k, n in use.items():
        if n != 1: continue
        ls = LineString(arcs[k])
        if ls.intersects(region): lines.append(ls)
    return lines


def county_polys():
    topo = json.load(gzip.open(os.path.join(HERE, 'geo', 'counties.topo.json.gz')))
    obj = list(topo['objects'].values())[0]
    arcs = _arcs(topo)
    out = {}
    for g in obj['geometries']:
        polys = []
        if g['type'] == 'Polygon':
            polys.append(Polygon(_rings(arcs, g['arcs'][0]), [_rings(arcs, r) for r in g['arcs'][1:]]))
        elif g['type'] == 'MultiPolygon':
            for p in g['arcs']:
                polys.append(Polygon(_rings(arcs, p[0]), [_rings(arcs, r) for r in p[1:]]))
        else:
            continue
        out[g['properties']['GEOID']] = unary_union([p.buffer(0) for p in polys])
    return out


def county_coast_km(cap_km=1500):
    lines = coastline()
    tree = STRtree(lines)
    res = {}
    for geoid, poly in county_polys().items():
        cx, cy = poly.centroid.x, poly.centroid.y
        k = math.cos(math.radians(cy))
        # candidate coast within a generous box, then exact distance in a local projection
        for pad in (3, 8, 20):
            cand = tree.query(poly.buffer(pad))
            if len(cand): break
        if not len(cand):
            res[geoid] = cap_km; continue
        def proj(geom):
            from shapely import transform
            return transform(geom, lambda xy: np.c_[(xy[:, 0] - cx) * k * 111.32, (xy[:, 1] - cy) * 110.57])
        P = proj(poly)
        d = min(P.distance(proj(lines[i])) for i in cand)
        res[geoid] = int(round(min(d, cap_km)))
    return res


if __name__ == '__main__':
    d = county_coast_km()
    for g, nm in [('37019', 'Brunswick NC'), ('37129', 'New Hanover NC'), ('37047', 'Columbus NC'),
                  ('37183', 'Wake NC'), ('18157', 'Tippecanoe IN'), ('48061', 'Cameron TX'),
                  ('48427', 'Starr TX (Rio Grande)'), ('26163', 'Wayne MI (Great Lakes)'),
                  ('12086', 'Miami-Dade'), ('72127', 'San Juan PR'), ('15003', 'Honolulu')]:
        print(f'{nm:28s} {d.get(g)} km')
    print(len(d), 'counties;', sum(1 for v in d.values() if v == 0), 'touch the sea')
