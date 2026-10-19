"""County <- ERA5 cell overlap weights, and 2 deg box <- ERA5 land cells.

County weight of a 0.25 deg ERA5 cell = area of (county polygon intersect cell)
on the sphere (degrees^2 x cos(lat)). Every lower-48 county overlaps several
cells, so even the smallest independent city gets a value.

2 deg boxes follow the grid page (24-50 N, 126-66 W, 2 deg): a box's value is the
plain mean over the ERA5 cells whose centres fall inside a U.S. county and in
the box, so coastal boxes are not diluted by sea points and border boxes carry
no Canadian or Mexican land.
"""
import json, math, gzip
import numpy as np
import xarray as xr
from shapely.geometry import shape, box
from shapely.strtree import STRtree

LAT = 90.0 - 0.25 * np.arange(160, 265)       # 50 .. 24
LON = 0.25 * np.arange(940, 1177) - 360.0      # -125 .. -66
NI, NJ = len(LAT), len(LON)

gj = json.load(open("geo/counties.geojson"))
cells = []
for i, la in enumerate(LAT):
    for j, lo in enumerate(LON):
        cells.append(box(lo - 0.125, la - 0.125, lo + 0.125, la + 0.125))
tree = STRtree(cells)

out = {}
skipped = []
for f in gj["features"]:
    g = f["properties"]["GEOID"]
    geom = shape(f["geometry"])
    if not geom.is_valid:
        geom = geom.buffer(0)
    minx, miny, maxx, maxy = geom.bounds
    if maxx < -125.2 or minx > -65.8 or maxy < 23.8 or miny > 50.2:
        skipped.append(g); continue                     # AK, HI, PR: outside the domain
    idx, w = [], []
    for k in tree.query(geom):
        a = geom.intersection(cells[k]).area
        if a > 0:
            i, j = divmod(int(k), NJ)
            idx.append(int(k)); w.append(a * math.cos(math.radians(LAT[i])))
    if not idx:
        skipped.append(g); continue
    s = sum(w)
    out[g] = [idx, [x / s for x in w]]

# US land cells: the cell centre lies inside a lower-48 county polygon. This both
# drops sea points and keeps Canadian and Mexican land out of the border boxes.
from shapely.geometry import Point
polys = []
for f in gj["features"]:
    if f["properties"]["GEOID"] in out:
        p = shape(f["geometry"]); polys.append(p if p.is_valid else p.buffer(0))
ptree = STRtree(polys)
GRID, LAT0, LON0, NLAT, NLON = 2.0, 24.0, -126.0, 13, 30
boxes = {}
nus = 0
for i, la in enumerate(LAT):
    for j, lo in enumerate(LON):
        pt = Point(lo, la)
        if not any(polys[k].contains(pt) for k in ptree.query(pt)):
            continue
        nus += 1
        bi, bj = int((la - LAT0) // GRID), int((lo - LON0) // GRID)
        if 0 <= bi < NLAT and 0 <= bj < NLON:
            boxes.setdefault(bi * NLON + bj, []).append(i * NJ + j)
print(f"US land cells: {nus}")

json.dump({"counties": out, "boxes": {str(k): v for k, v in boxes.items()},
           "grid": [GRID, LAT0, LON0, NLAT, NLON], "skipped": skipped},
          open("geo/weights.json", "w"))
print(f"counties with weights: {len(out)}  skipped (outside lower 48): {len(skipped)} "
      f"e.g. {sorted(skipped)[:3]}..{sorted(skipped)[-3:]}")
print(f"2-deg boxes with land: {len(boxes)}  cells per box: "
      f"min {min(map(len, boxes.values()))} median {int(np.median(list(map(len, boxes.values()))))}")
n = [len(v[0]) for v in out.values()]
print(f"cells per county: min {min(n)} median {int(np.median(n))} max {max(n)}")
