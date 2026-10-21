"""County <- PRISM 4 km cell overlap weights, and 2 deg box <- PRISM cells.

PRISM (ACIS grid 21) is land-only: water and anything outside the lower 48 is
missing, so no land mask is needed -- a cell counts if it has data in every
month of the record (VALID, from cells/*.npz). County weight = area of (county
polygon intersect cell) x cos(lat). A county with no valid cell takes the
nearest valid one. 2 deg boxes (24-50 N, 126-66 W) average the valid cells
whose centres lie inside a lower-48 county.
Run in the rain directory:  python3 build_rain_weights.py  -> geo/weights.json
"""
import json, math, glob
import numpy as np
import shapely
from shapely.geometry import shape, Point
from shapely.strtree import STRtree

z = np.load(sorted(glob.glob("cells/*.npz"))[-1])
LAT0, LON0, STEP = float(z["lat0"]), float(z["lon0"]), float(z["step"])
NY, NX = z["c"].shape[2:]
valid = np.ones((NY, NX), bool)
for f in sorted(glob.glob("cells/*.npz")):
    c = np.load(f)["c"]
    valid &= (c != 255).all(axis=(0, 1))
print("cells valid in every month:", int(valid.sum()))
np.save("geo/valid.npy", valid)
lat = LAT0 + STEP * np.arange(NY); lon = LON0 + STEP * np.arange(NX)
vi, vj = np.nonzero(valid)
vpts = np.c_[lon[vj], lat[vi]]

gj = json.load(open("geo/counties.geojson"))
out, skipped, nearest = {}, [], []
for f in gj["features"]:
    g = f["properties"]["GEOID"]
    geom = shape(f["geometry"])
    if not geom.is_valid:
        geom = geom.buffer(0)
    minx, miny, maxx, maxy = geom.bounds
    if maxx < -125.2 or minx > -65.8 or maxy < 23.8 or miny > 50.2:
        skipped.append(g); continue
    i0 = max(0, int(math.floor((miny - LAT0) / STEP)) - 1); i1 = min(NY, int(math.ceil((maxy - LAT0) / STEP)) + 2)
    j0 = max(0, int(math.floor((minx - LON0) / STEP)) - 1); j1 = min(NX, int(math.ceil((maxx - LON0) / STEP)) + 2)
    ii, jj = np.meshgrid(np.arange(i0, i1), np.arange(j0, j1), indexing="ij")
    ii = ii.ravel(); jj = jj.ravel()
    keep = valid[ii, jj]; ii = ii[keep]; jj = jj[keep]
    idx, w = [], []
    if len(ii):
        boxes = shapely.box(lon[jj] - STEP / 2, lat[ii] - STEP / 2, lon[jj] + STEP / 2, lat[ii] + STEP / 2)
        a = shapely.area(shapely.intersection(boxes, geom))
        m = a > 0
        idx = (ii[m] * NX + jj[m]).tolist()
        w = (a[m] * np.cos(np.radians(lat[ii[m]]))).tolist()
    if not idx:
        p = geom.representative_point()
        d = (vpts[:, 0] - p.x) ** 2 * math.cos(math.radians(p.y)) ** 2 + (vpts[:, 1] - p.y) ** 2
        k = int(np.argmin(d)); idx, w = [int(vi[k] * NX + vj[k])], [1.0]
        nearest.append(g)
    s = sum(w)
    out[g] = [idx, [x / s for x in w]]

polys = [shape(f["geometry"]) for f in gj["features"] if f["properties"]["GEOID"] in out]
polys = [p if p.is_valid else p.buffer(0) for p in polys]
us = shapely.union_all(polys)
shapely.prepare(us)
inside = shapely.contains_xy(us, vpts[:, 0], vpts[:, 1])
GRID, BLAT0, BLON0, NLAT, NLON = 2.0, 24.0, -126.0, 13, 30
boxes = {}
for k in np.nonzero(inside)[0]:
    la, lo = vpts[k, 1], vpts[k, 0]
    bi, bj = int((la - BLAT0) // GRID), int((lo - BLON0) // GRID)
    if 0 <= bi < NLAT and 0 <= bj < NLON:
        boxes.setdefault(bi * NLON + bj, []).append(int(vi[k] * NX + vj[k]))
json.dump({"counties": out, "boxes": {str(k): v for k, v in boxes.items()},
           "grid": [GRID, BLAT0, BLON0, NLAT, NLON], "prism": [LAT0, LON0, STEP, int(NY), int(NX)],
           "skipped": skipped, "nearest": nearest}, open("geo/weights.json", "w"))
n = [len(v[0]) for v in out.values()]
print(f"counties {len(out)} (skipped {len(skipped)}, nearest-cell {len(nearest)} {nearest}); "
      f"cells/county min {min(n)} median {int(np.median(n))} max {max(n)}; boxes {len(boxes)} "
      f"cells/box min {min(map(len, boxes.values()))}; US cells {int(inside.sum())}")
