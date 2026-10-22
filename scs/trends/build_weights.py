"""County <- ERA5 cell overlap weights, and 2 deg box <- ERA5 land cells.

County weight of a 0.25 deg ERA5 cell = area of (county polygon intersect cell)
on the sphere (degrees^2 x cos(lat)) x the cell's LAND FRACTION (ERA5 land-sea
mask), over land cells only (mask >= 0.5). Sea and lake cells carry marine
temperatures, and letting them in pulled coastal counties far down (Galveston
54 -> 31 days/yr >= 90 F). Partly-land cells (mask 0.5-0.9) still run cooler than
the land beside them, so they count in proportion to their land (review of
2026-10-22: Miami-Dade 58 -> 66, Monroe 52 -> 65 days/yr >= 90 F, 2015-24).
A county that overlaps no land cell at all (Nantucket, Dukes, San Juan WA, ...)
takes the land cell nearest to it.

2 deg boxes follow the grid page (24-50 N, 126-66 W, 2 deg): a box's value is the
land-fraction-weighted mean over the ERA5 land cells (mask >= 0.5) whose centres
fall inside a U.S. county and in the box, so coastal boxes are not diluted by sea
points and border boxes carry no Canadian or Mexican land. Each box also gets a
weight (its cells' summed land area, cos(lat) x land fraction) for area-weighted
national means on the grid page.
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
LSM = xr.open_dataset("geo/lsm.nc")["LSM"].isel(time=0).values[160:265, 940:1177]
LAND = LSM >= 0.5
landpts = np.array([(lo, la) for i, la in enumerate(LAT) for j, lo in enumerate(LON) if LAND[i, j]])
landidx = np.array([i * len(LON) + j for i in range(len(LAT)) for j in range(len(LON)) if LAND[i, j]])
cells = []
for i, la in enumerate(LAT):
    for j, lo in enumerate(LON):
        cells.append(box(lo - 0.125, la - 0.125, lo + 0.125, la + 0.125))
tree = STRtree(cells)

out = {}
skipped = []
nearest = []
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
        i, j = divmod(int(k), NJ)
        if not LAND[i, j]:
            continue
        a = geom.intersection(cells[k]).area
        if a > 0:
            idx.append(int(k)); w.append(a * math.cos(math.radians(LAT[i])) * float(LSM[i, j]))
    if not idx:                                         # island or spit: nearest land cell
        p = geom.representative_point()
        d = (landpts[:, 0] - p.x) ** 2 * math.cos(math.radians(p.y)) ** 2 + (landpts[:, 1] - p.y) ** 2
        idx, w = [int(landidx[int(np.argmin(d))])], [1.0]
        nearest.append(g)
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
        if not LAND[i, j]:
            continue
        pt = Point(lo, la)
        if not any(polys[k].contains(pt) for k in ptree.query(pt)):
            continue
        nus += 1
        bi, bj = int((la - LAT0) // GRID), int((lo - LON0) // GRID)
        if 0 <= bi < NLAT and 0 <= bj < NLON:
            boxes.setdefault(bi * NLON + bj, []).append((i * NJ + j, float(LSM[i, j]) * math.cos(math.radians(la))))
print(f"US land cells: {nus}")
# [cell ids, normalised land weights, box land weight (deg^2-equivalent)]
boxes = {k: [[c for c, _ in v], [w / sum(x for _, x in v) for _, w in v],
             round(sum(x for _, x in v) * 0.0625, 5)] for k, v in boxes.items()}

json.dump({"counties": out, "boxes": {str(k): v for k, v in boxes.items()},
           "grid": [GRID, LAT0, LON0, NLAT, NLON], "skipped": skipped, "nearest": nearest},
          open("geo/weights.json", "w"))
print(f"counties with weights: {len(out)}  skipped (outside lower 48): {len(skipped)} "
      f"e.g. {sorted(skipped)[:3]}..{sorted(skipped)[-3:]}")
print(f"2-deg boxes with land: {len(boxes)}  cells per box: "
      f"min {min(len(v[0]) for v in boxes.values())} median {int(np.median([len(v[0]) for v in boxes.values()]))}")
print(f"counties on no land cell (nearest land cell used): {len(nearest)} {nearest}")
n = [len(v[0]) for v in out.values()]
print(f"cells per county: min {min(n)} median {int(np.median(n))} max {max(n)}")
