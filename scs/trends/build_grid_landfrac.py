#!/usr/bin/env python3
"""build_grid_landfrac.py COUNTIES_GEOJSON OUT_JSON -- U.S. land fraction of each 2-deg box
of the grid page (24-50 N, 126-66 W): the area of lower-48 county polygons inside the box over
the box's area. The grid page weights its smoothing and national panel by it, so mostly-sea,
lake or foreign boxes do not drag their neighbours or the national mean down. Boxes with no
U.S. land are left out (the page gives them a near-zero weight).
COUNTIES_GEOJSON: the site's geo/counties.topo.json.gz converted to GeoJSON (as for heat)."""
import json, sys
from shapely.geometry import shape, box
from shapely.strtree import STRtree
gj = json.load(open(sys.argv[1]))
polys = []
for f in gj["features"]:
    g = shape(f["geometry"]); g = g if g.is_valid else g.buffer(0)
    minx, miny, maxx, maxy = g.bounds
    if maxx < -126 or minx > -66 or maxy < 24 or miny > 50:
        continue
    polys.append(g)
tree = STRtree(polys)
G, LAT0, LON0, NLAT, NLON = 2.0, 24.0, -126.0, 13, 30
out = {}
for i in range(NLAT):
    for j in range(NLON):
        b = box(LON0 + j * G, LAT0 + i * G, LON0 + (j + 1) * G, LAT0 + (i + 1) * G)
        a = sum(polys[k].intersection(b).area for k in tree.query(b))
        if a > 0:
            out[str(i * NLON + j)] = round(min(1.0, a / b.area), 4)
json.dump(out, open(sys.argv[2], "w"))
print(len(out), "boxes with U.S. land")
