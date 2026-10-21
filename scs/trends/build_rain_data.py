#!/usr/bin/env python3
"""
build_rain_data.py  counts  CELLS_DIR COUNTS_DIR WEIGHTS   [YEAR ...]
build_rain_data.py  site    COUNTS_DIR WEIGHTS COUNTIES_TOPO OUT_DIR

Heavy rain days for the county and 2 deg grid pages, from PRISM daily
precipitation (4 km, 1981 on) via ACIS -- see prism_fetch.py.

  rain   days whose PRISM daily total (24 h ending 12 UTC, rounded to 0.01 in)
         reached 1, 2 or 3 inches

Stage 1 (counts): per-cell monthly counts (cells/<YEAR>.npz) -> per county the
area-weighted mean over its PRISM cells (the days a typical place in the county
saw -- the statistic of the Indiana card's maps), per 2 deg box the plain mean
over its cells. Hundredths of a day, as for heat.
Stage 2 (site): the page files and index entries, through build_heat_data.py's
site stage (same format: meta.kind "field", vscale 10, rscale 100; state and
national series are area-weighted means over counties).

PRISM revises recent months for about six months; those are flagged
`provisional` and prism_update.py fetches them again.
"""
import glob, json, os, sys
import numpy as np
import gzip


def load_json(p):
    """weights may be gzipped (geo_rain/weights.json.gz, ~5 MB instead of 21)"""
    return json.load(gzip.open(p, "rt") if p.endswith(".gz") else open(p))
from scipy import sparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_heat_data as B

RAIN = {
    "rain": {
        "label": "Heavy Rain", "unit": "in", "var": None,
        "note": ("Days on which the PRISM daily precipitation total (4 km grid, the 24 hours ending "
                 "12 UTC) reached the threshold."),
        "thr": [(1, "r1", "≥ 1.00″ in a day", "≥1″"),
                (2, "r2", "≥ 2.00″ in a day", "≥2″"),
                (3, "r3", "≥ 3.00″ in a day", "≥3″")],
    },
}
SOURCE = "PRISM daily precipitation (4 km), PRISM Group, Oregon State University, via ACIS (grid 21)"
PROVISIONAL_MONTHS = 6


def matrices(W):
    NY, NX = W["prism"][3], W["prism"][4]
    n = NY * NX
    geo = sorted(W["counties"])
    rows, cols, vals = [], [], []
    for r, g in enumerate(geo):
        idx, w = W["counties"][g]
        rows += [r] * len(idx); cols += idx; vals += w
    Mc = sparse.csr_matrix((vals, (rows, cols)), shape=(len(geo), n))
    bx = sorted(int(k) for k in W["boxes"])
    rows, cols, vals = [], [], []
    for r, b in enumerate(bx):
        idx = W["boxes"][str(b)]
        rows += [r] * len(idx); cols += idx; vals += [1.0 / len(idx)] * len(idx)
    Mb = sparse.csr_matrix((vals, (rows, cols)), shape=(len(bx), n))
    return geo, Mc, bx, Mb


def year_counts(c, months, Mc, Mb, nthr=3):
    """c uint8 [nmonth, nthr, NY, NX] -> county/box hundredths [n, 12, nthr], complete[12]."""
    cc = np.zeros((Mc.shape[0], 12, nthr), np.uint16)
    cb = np.zeros((Mb.shape[0], 12, nthr), np.uint16)
    complete = np.zeros(12, int)
    for i, mo in enumerate(months):
        m = int(str(mo)[5:7])
        for k in range(nthr):
            p = c[i, k].reshape(-1).astype(np.float64)
            p[p == 255] = 0.0                  # weights only reference cells valid all record
            cc[:, m - 1, k] = np.round(Mc @ p * 100)
            cb[:, m - 1, k] = np.round(Mb @ p * 100)
        complete[m - 1] = 1
    return cc, cb, complete


def provisional_flags(y, complete, last):
    """The last PROVISIONAL_MONTHS months of the record are still being revised by PRISM."""
    ly, lm = last
    prov = np.zeros(12, int)
    for m in range(1, 13):
        if complete[m - 1]:
            age = (ly - y) * 12 + (lm - m)
            if 0 <= age < PROVISIONAL_MONTHS:
                prov[m - 1] = 1
    return prov


def last_month(cells):
    y = max(int(os.path.basename(f)[:4]) for f in glob.glob(os.path.join(cells, "[0-9]" * 4 + ".npz")))
    ms = [str(x) for x in np.load(os.path.join(cells, f"{y}.npz"))["months"]]
    return y, int(ms[-1][5:7])


def stage_counts(cells, cdir, wpath, years):
    W = load_json(wpath)
    geo, Mc, bx, Mb = matrices(W)
    os.makedirs(cdir, exist_ok=True)
    last = last_month(cells)
    for f in sorted(glob.glob(os.path.join(cells, "[0-9]" * 4 + ".npz"))):
        y = int(os.path.basename(f)[:4])
        if years and y not in years:
            continue
        z = np.load(f)
        cc, cb, complete = year_counts(z["c"], [str(m) for m in z["months"]], Mc, Mb)
        prov = provisional_flags(y, complete, last)
        tmp = os.path.join(cdir, f"{y}.tmp.npz")
        np.savez_compressed(tmp, geo=np.array(geo), boxes=np.array(bx), ndays=0,
                            rain_county=cc, rain_box=cb, complete=complete, provisional=prov)
        os.replace(tmp, os.path.join(cdir, f"{y}.npz"))
        print(f"counts {y}: complete {complete.tolist()} provisional {prov.tolist()}", flush=True)


def stage_site(cdir, wpath, topo, outdir):
    B.HAZ = RAIN
    B.SOURCE = SOURCE
    B.SRCNAME = "PRISM"
    if wpath.endswith(".gz"):                  # the heat site stage reads plain JSON (only its "grid")
        import tempfile
        W = load_json(wpath)
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump({"grid": W["grid"]}, fh)
        wpath = fh.name
    B.stage_site(cdir, wpath, topo, outdir)


if __name__ == "__main__":
    if sys.argv[1] == "counts":
        stage_counts(sys.argv[2], sys.argv[3], sys.argv[4], [int(a) for a in sys.argv[5:]])
    elif sys.argv[1] == "site":
        stage_site(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
