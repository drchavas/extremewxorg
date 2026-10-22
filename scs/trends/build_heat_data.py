#!/usr/bin/env python3
"""
build_heat_data.py  counts  DAILY_DIR COUNTS_DIR WEIGHTS   [YEAR ...]
build_heat_data.py  site    COUNTS_DIR WEIGHTS COUNTIES_TOPO OUT_DIR

Two extreme-heat hazards for the county and 2 deg grid pages, from ERA5:

  heatindex  days whose daily maximum NWS heat index reached the threshold
  heat       days whose daily maximum 2 m air temperature reached the threshold

Stage 1 (counts): the 0.25 deg daily maxima (era5_daily_max.py) are put onto
counties and 2 deg boxes, and turned into monthly day counts per threshold.
  * every ERA5 cell gets its own day counts (its daily maximum reached the
    threshold, local standard days);
  * a COUNTY's count is the area-weighted mean of the counts of the cells it
    overlaps -- the days a typical place in the county saw, the statistic the
    Indiana card used for the state. (Averaging the daily highs first and then
    thresholding trims the hot tail by 2-10%.) Not a whole number: the counts
    files keep hundredths, the page files tenths (meta.vscale = 10; region
    series hundredths, meta.rscale = 100);
  * a BOX's count is the plain mean over the U.S. land cells in the box.
Stage 2 (site): writes heatindex.json.gz, heat.json.gz, grid_heatindex.json.gz,
grid_heat.json.gz in the pages' formats, and merges them into index.json and
grid_index.json. State and national series are AREA-WEIGHTED MEANS of county days
(the days a typical place in the state saw), not "any county" days -- heat is a
continuous field, not a scatter of reports, and that is the statistic the Indiana
card used.
"""
import glob, gzip, json, math, os, sys, datetime as dt
import numpy as np
from scipy import sparse

HAZ = {
    "heatindex": {
        "label": "Extreme Heat Index", "unit": "°F", "var": "hi_f10",
        "note": ("Days on which the daily maximum heat index (NWS formula, from hourly ERA5 2 m "
                 "temperature and dewpoint) reached the threshold. Heat index is what the "
                 "temperature feels like given the humidity."),
        "thr": [(90, "hi90", "Heat index ≥ 90°F (extreme caution)", "≥90°F"),
                (100, "hi100", "Heat index ≥ 100°F", "≥100°F"),
                (105, "hi105", "Heat index ≥ 105°F", "≥105°F"),
                (110, "hi110", "Heat index ≥ 110°F", "≥110°F"),
                (115, "hi115", "Heat index ≥ 115°F", "≥115°F")],
    },
    "heat": {
        "label": "Extreme Heat (temperature)", "unit": "°F", "var": "tmax_f10",
        "note": ("Days on which the daily maximum 2 m air temperature (hourly ERA5) reached the "
                 "threshold. Temperature only; see Extreme Heat Index for humidity."),
        "thr": [(90, "t90", "Max temperature ≥ 90°F", "≥90°F"),
                (95, "t95", "Max temperature ≥ 95°F", "≥95°F"),
                (100, "t100", "Max temperature ≥ 100°F", "≥100°F"),
                (105, "t105", "Max temperature ≥ 105°F", "≥105°F")],
    },
}
NCELL = 105 * 237
SOURCE = "ECMWF ERA5 reanalysis (hourly, 0.25°), NCAR ds633.0 copy"
SRCNAME = "ERA5"            # short source name the pages show (build_rain_data.py sets "PRISM")
BW = {}                     # box -> land area (deg^2 x cos lat x land fraction), set in stage_site


def matrices(W):
    geo = sorted(W["counties"])
    rows, cols, vals = [], [], []
    for r, g in enumerate(geo):
        idx, w = W["counties"][g]
        rows += [r] * len(idx); cols += idx; vals += w
    Mc = sparse.csr_matrix((vals, (rows, cols)), shape=(len(geo), NCELL))
    bx = sorted(int(k) for k in W["boxes"])
    rows, cols, vals = [], [], []
    for r, b in enumerate(bx):
        e = W["boxes"][str(b)]
        if e and isinstance(e[0], list):         # [ids, land weights, box land area]
            idx, w = e[0], e[1]
        else:                                    # older weights: plain mean over ids
            idx, w = e, [1.0 / len(e)] * len(e)
        rows += [r] * len(idx); cols += idx; vals += list(w)
    Mb = sparse.csr_matrix((vals, (rows, cols)), shape=(len(bx), NCELL))
    return geo, Mc, bx, Mb


def stage_counts(daily, cdir, wpath, years):
    W = json.load(open(wpath))
    geo, Mc, bx, Mb = matrices(W)
    os.makedirs(cdir, exist_ok=True)
    files = sorted(glob.glob(os.path.join(daily, "*.npz")))
    for f in files:
        y = int(os.path.basename(f)[:4])
        if years and y not in years:
            continue
        z = np.load(f)
        nd = z["tmax_f10"].shape[0]
        dates = [dt.date(y, 1, 1) + dt.timedelta(d) for d in range(nd)]
        mon = np.array([d.month for d in dates])
        out = {"ndays": nd}
        for hz, spec in HAZ.items():
            # integer tenths of deg F, truncated: ">= 10*t" is exactly "true value >= t"
            a = z[spec["var"]].reshape(nd, NCELL).astype(np.int32)
            dayok = ~(a == -32768).any(axis=1)        # a day is all-or-nothing
            th = [t for t, *_ in spec["thr"]]
            cc = np.zeros((len(geo), 12, len(th)), np.uint16)   # hundredths of a day
            cb = np.zeros((len(bx), 12, len(th)), np.uint16)
            for m in range(1, 13):
                sel = (mon == m) & dayok
                if not sel.any():
                    continue
                for k, t in enumerate(th):
                    pc = (a[sel] >= 10 * t).sum(axis=0).astype(np.float64)   # days per cell
                    cc[:, m - 1, k] = np.round(Mc @ pc * 100)
                    cb[:, m - 1, k] = np.round(Mb @ pc * 100)
            out[f"{hz}_county"] = cc; out[f"{hz}_box"] = cb
            # months whose days are all present
            out["complete"] = np.array([
                int(((mon == m) & dayok).sum() == sum(1 for d in dates if d.month == m)
                    and (mon == m).sum() == _mdays(y, m)) for m in range(1, 13)])
        # the last month of the record is provisional when its final local day
        # had to do without the next month's hours (see era5_daily_max.py)
        prov = np.zeros(12, int)
        if int(z["provisional"]) if "provisional" in z else 0:
            last = [m for m in range(12) if out["complete"][m]]
            if last:
                prov[last[-1]] = 1
        out["provisional"] = prov
        tmp = os.path.join(cdir, f"{y}.tmp.npz")
        np.savez_compressed(tmp, geo=np.array(geo), boxes=np.array(bx), **out)
        os.replace(tmp, os.path.join(cdir, f"{y}.npz"))
        print(f"counts {y}: {nd} days, complete months {out['complete'].tolist()}", flush=True)


def _mdays(y, m):
    import calendar
    return calendar.monthrange(y, m)[1]


def stage_site(cdir, wpath, topo, outdir):
    W = json.load(open(wpath))
    global BW
    BW = W.get("bw") or {k: e[2] for k, e in W.get("boxes", {}).items()
                         if e and isinstance(e[0], list) and len(e) > 2}
    t = json.load(gzip.open(topo))
    gm = t["objects"][list(t["objects"])[0]]["geometries"]
    props = {g["properties"]["GEOID"]: g["properties"] for g in gm}
    files = sorted(glob.glob(os.path.join(cdir, "[0-9][0-9][0-9][0-9].npz")))
    Z = {int(os.path.basename(f)[:4]): np.load(f) for f in files}
    years = sorted(Z)
    y0, y1 = years[0], years[-1]
    geo = [str(x) for x in Z[y0]["geo"]]; bx = [int(x) for x in Z[y0]["boxes"]]
    # coverage: the last month with every day present; later months are gaps
    gaps, through = [], None
    for y in years:
        for m in range(12):
            if not Z[y]["complete"][m]:
                gaps.append([y, m + 1])
    full = [(y, m + 1) for y in years for m in range(12) if Z[y]["complete"][m]]
    ly, lm = full[-1]
    if (ly, lm) != (y1, 12):
        through = f"{ly}-{lm:02d}"
    # a provisional last month: its last day lacks a few night hours (redone next update)
    provisional = None
    if "provisional" in Z[ly].files and Z[ly]["provisional"][lm - 1]:
        provisional = f"{ly}-{lm:02d}"
    # county area weights for the state/national means
    area = np.array([props[g].get("AREA", 1) or 1 for g in geo], float)
    st = [props[g]["STUSPS"] for g in geo]
    regions = sorted(set(st)) + ["US"]
    rmembers = {r: np.array([i for i, s in enumerate(st) if s == r or r == "US"]) for r in regions}
    idx_path = os.path.join(outdir, "index.json")
    gidx_path = os.path.join(outdir, "grid_index.json")
    index = json.load(open(idx_path)); gindex = json.load(open(gidx_path))
    for hz, spec in HAZ.items():
        nth = len(spec["thr"])
        ci, yi, mi, v = [], [], [], [[] for _ in range(nth)]
        rri, ryi, rmi, rv = [], [], [], [[] for _ in range(nth)]
        bci, byi, bmi, bv = [], [], [], [[] for _ in range(nth)]
        for y in years:
            cc = Z[y][f"{hz}_county"]; cb = Z[y][f"{hz}_box"]
            for m in range(12):
                if not Z[y]["complete"][m]:
                    continue
                nz = np.nonzero(cc[:, m, 0])[0]       # thresholds are nested
                ci += nz.tolist(); yi += [y - y0] * len(nz); mi += [m + 1] * len(nz)
                for k in range(nth):                  # tenths of a day on the wire
                    v[k] += np.round(cc[nz, m, k] / 10).astype(int).tolist()
                for r, mem in rmembers.items():
                    w = area[mem]
                    vals = [float((cc[mem, m, k] * w).sum() / w.sum()) for k in range(nth)]
                    if vals[0] > 0:                    # already in hundredths
                        rri.append(regions.index(r)); ryi.append(y - y0); rmi.append(m + 1)
                        for k in range(nth):
                            rv[k].append(int(round(vals[k])))
                nzb = np.nonzero(cb[:, m, 0])[0]
                bci += [bx[i] for i in nzb]; byi += [y - y0] * len(nzb); bmi += [m + 1] * len(nzb)
                for k in range(nth):
                    bv[k] += np.round(cb[nzb, m, k] / 10).astype(int).tolist()
        thr_c = [{"key": k, "label": lab, "short": sh, "min": t} for t, k, lab, sh in spec["thr"]]
        meta = {"hazard": hz, "label": spec["label"], "unit": spec["unit"], "note": spec["note"],
                "thresholds": thr_c, "year0": y0, "year1": y1, "gaps": gaps, "through": through,
                "provisional": provisional, "kind": "field", "vscale": 10, "rscale": 100, "source": SOURCE,
                "srcname": SRCNAME,
                "coverage": "lower 48", "ncounty": len(geo),
                "built": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
        county = {"regions": regions, "rri": rri, "ryi": ryi, "rmi": rmi, "rv": rv,
                  "meta": meta, "counties": geo, "ci": ci, "yi": yi, "mi": mi, "v": v}
        p = os.path.join(outdir, f"{hz}.json.gz")
        with gzip.open(p, "wt", encoding="utf-8") as fh:
            json.dump(county, fh, separators=(",", ":"))
        print(f"wrote {p} {os.path.getsize(p)/1e6:.2f} MB  {len(ci):,} cells")
        G, LAT0, LON0, NLAT, NLON = W["grid"]
        gmeta = {"hazard": hz, "label": spec["label"], "unit": spec["unit"],
                 "thresholds": [{"k": k, "label": lab, "min": t} for t, k, lab, sh in spec["thr"]],
                 "year0": y0, "year1": y1, "gaps": gaps, "through": through, "provisional": provisional, "kind": "field", "srcname": SRCNAME,
                 "vscale": 10, "grid": G, "lat0": LAT0, "lon0": LON0, "nlat": NLAT, "nlon": NLON,
                 "source": SOURCE, "boxes": bx, "ngrid": len(bx), "ncell": len(bci)}
        if BW:                                   # box land areas: area-weighted national means
            gmeta["bw"] = [BW.get(str(b), 0) for b in bx]
        grid = {"meta": gmeta, "ci": bci, "yi": byi, "mi": bmi, "v": bv}
        p = os.path.join(outdir, f"grid_{hz}.json.gz")
        with gzip.open(p, "wt", encoding="utf-8") as fh:
            json.dump(grid, fh, separators=(",", ":"))
        print(f"wrote {p} {os.path.getsize(p)/1e6:.2f} MB  {len(bci):,} cells")
        index["hazards"] = [h for h in index["hazards"] if h["key"] != hz]
        index["hazards"].append({"key": hz, "label": spec["label"], "unit": spec["unit"],
                                 "note": spec["note"], "thresholds": thr_c, "year0": y0,
                                 "year1": y1, "kind": "field", "file": f"{hz}.json.gz"})
        gindex["hazards"] = [h for h in gindex["hazards"] if h["k"] != hz]
        gindex["hazards"].append({"k": hz, "label": spec["label"], "unit": spec["unit"],
                                  "thresholds": gmeta["thresholds"], "y0": y0, "y1": y1,
                                  "kind": "field", "file": f"grid_{hz}.json.gz"})
    order = {k: i for i, k in enumerate(["hail", "tornado", "wind", "derechoday",
                                         "heatindex", "heat", "rain", "snow", "fzra", "pkwnd", "derecho"])}
    index["hazards"].sort(key=lambda h: order.get(h["key"], 99))
    gindex["hazards"].sort(key=lambda h: order.get(h["k"], 99))
    json.dump(index, open(idx_path, "w"), indent=1)
    json.dump(gindex, open(gidx_path, "w"), indent=1)
    print("updated index.json and grid_index.json")


if __name__ == "__main__":
    if sys.argv[1] == "counts":
        stage_counts(sys.argv[2], sys.argv[3], sys.argv[4], [int(a) for a in sys.argv[5:]])
    elif sys.argv[1] == "site":
        stage_site(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
