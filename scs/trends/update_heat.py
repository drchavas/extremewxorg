#!/usr/bin/env python3
"""
update_heat.py COUNTS_DIR WEIGHTS [--dry-run] [--max N]

Bring the extreme-heat monthly counts up to date with NCAR's ERA5 copy, one
month at a time (each month is ~1 min: about 50 MB of hourly 2 m T and dewpoint
for the lower 48, read straight from the nsf-ncar-era5 bucket).

COUNTS_DIR holds one <YEAR>.npz per year (see build_heat_data.py, stage 1) with a
`complete` flag per month. This finds the first month after the last complete
one, processes it if NCAR has published it, and repeats (at most --max months
per run, default 1, so a time-limited shell can call it repeatedly).
Then rebuild the site files with:  build_heat_data.py site ...

Exit status: 0 = something changed, 3 = already current, other = error.
"""
import argparse, calendar, glob, json, os, sys
import datetime as dt
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import era5_daily_max as E
import build_heat_data as B
from heatcalc import month_url
import urllib.request


def published(y, m):
    try:
        req = urllib.request.Request(month_url("d", y, m), method="HEAD")
        urllib.request.urlopen(req, timeout=60)
        return True
    except Exception:
        return False


def next_needed(cdir):
    files = sorted(glob.glob(os.path.join(cdir, "[0-9][0-9][0-9][0-9].npz")))
    last = None
    for f in files:
        y = int(os.path.basename(f)[:4]); c = np.load(f)["complete"]
        for m in range(12):
            if c[m]:
                last = (y, m + 1)
    y, m = last
    return (y + 1, 1) if m == 12 else (y, m + 1)


def month_counts(y, m, W):
    """Counts for one month, in the per-year file's layout."""
    geo, Mc, bx, Mb = B.matrices(W)
    nd = calendar.monthrange(y, m)[1]
    T, H = E.fields(y, m)
    ny, nm = E.next_month(y, m)
    try:
        Tn, Hn = E.fields(ny, nm, 0, 8)
    except Exception:
        Tn = np.full((8,) + T.shape[1:], np.nan, np.float32); Hn = Tn.copy()
    T = np.concatenate([T, Tn]); H = np.concatenate([H, Hn])
    out = {}
    for hz, arr in (("heat", T), ("heatindex", H)):
        dm = np.full((nd,) + arr.shape[1:], np.nan, np.float32)
        for o in np.unique(E.OFF):
            cols = np.where(E.OFF == o)[0]; s = -o
            b = arr[s:s + 24 * nd][:, :, cols].reshape(nd, 24, arr.shape[1], len(cols))
            ok = np.isfinite(b).sum(axis=1) >= 16
            with np.errstate(all="ignore"):
                dm[:, :, cols] = np.where(ok, np.nanmax(np.where(np.isfinite(b), b, -np.inf), axis=1), np.nan)
        dm = np.round(dm * 10) / 10.0                    # same tenths as the archive
        a = dm.reshape(nd, B.NCELL)
        if np.isnan(a).any():
            raise SystemExit(f"{y}-{m:02d}: incomplete days; NCAR may still be publishing it")
        th = [t for t, *_ in B.HAZ[hz]["thr"]]
        pc = [(a >= t).sum(axis=0).astype(np.float64) for t in th]      # days per cell
        out[f"{hz}_county"] = np.stack([np.round(Mc @ p * 100) for p in pc], -1).astype(np.uint16)
        out[f"{hz}_box"] = np.stack([np.round(Mb @ p * 100) for p in pc], -1).astype(np.uint16)
    return geo, bx, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("counts"); ap.add_argument("weights")
    ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--max", type=int, default=1)
    a = ap.parse_args()
    W = json.load(open(a.weights))
    changed = False
    for _ in range(a.max):
        y, m = next_needed(a.counts)
        if not published(y, m):
            print(f"next month {y}-{m:02d} not yet published by NCAR"); break
        print(f"{y}-{m:02d}: published{' (dry run)' if a.dry_run else ''}", flush=True)
        if a.dry_run:
            changed = True; break
        geo, bx, mc = month_counts(y, m, W)
        p = os.path.join(a.counts, f"{y}.npz")
        if os.path.exists(p):
            z = dict(np.load(p))
        else:
            z = {"geo": np.array(geo), "boxes": np.array(bx), "ndays": 0,
                 "complete": np.zeros(12, int)}
            for hz in B.HAZ:
                n = len(B.HAZ[hz]["thr"])
                z[f"{hz}_county"] = np.zeros((len(geo), 12, n), np.uint16)
                z[f"{hz}_box"] = np.zeros((len(bx), 12, n), np.uint16)
        for k, v in mc.items():
            z[k][:, m - 1, :] = v
        z["complete"][m - 1] = 1
        tmp = p + ".tmp.npz"
        np.savez_compressed(tmp, **z); os.replace(tmp, p)
        print(f"{y}-{m:02d}: counts written", flush=True)
        changed = True
    print("changes found" if changed else "already current")
    sys.exit(0 if changed else 3)


if __name__ == "__main__":
    main()
