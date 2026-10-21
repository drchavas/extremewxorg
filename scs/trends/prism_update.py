#!/usr/bin/env python3
"""
prism_update.py COUNTS_DIR WEIGHTS [--dry-run]

Bring the heavy-rain monthly counts up to date from ACIS/PRISM. Fetches, in one
request, every month from the oldest still-provisional one (PRISM revises the
last ~6 months) through last calendar month, recomputes their county and box
counts, and rewrites the affected rain_counts/<YEAR>.npz. A month counts as
complete only when (nearly) every land cell has all its days.
Then rebuild the page files:  build_rain_data.py site ...
Exit status: 0 = something changed, 3 = nothing new, other = error.
"""
import argparse, datetime as dt, glob, json, os, sys
import numpy as np
import gzip


def load_json(p):
    """weights may be gzipped (geo_rain/weights.json.gz, ~5 MB instead of 21)"""
    return json.load(gzip.open(p, "rt") if p.endswith(".gz") else open(p))
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import prism_fetch as P
import build_rain_data as R


def months_between(a, b):
    (y, m), out = a, []
    while (y, m) <= b:
        out.append((y, m)); y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("counts"); ap.add_argument("weights"); ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    files = sorted(glob.glob(os.path.join(a.counts, "[0-9]" * 4 + ".npz")))
    Z = {int(os.path.basename(f)[:4]): np.load(f) for f in files}
    done = [(y, m + 1) for y in sorted(Z) for m in range(12) if Z[y]["complete"][m]]
    prov = [(y, m + 1) for y in sorted(Z) for m in range(12)
            if Z[y]["complete"][m] and Z[y]["provisional"][m]]
    last = done[-1]
    start = prov[0] if prov else months_between(last, (9999, 12))[1]
    today = dt.date.today()
    end = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
    if start > end:
        print("already current"); sys.exit(3)
    print(f"fetching {start[0]}-{start[1]:02d} .. {end[0]}-{end[1]:02d}"
          f"{' (dry run)' if a.dry_run else ''}", flush=True)
    if a.dry_run:
        sys.exit(0)
    W = R.load_json(a.weights)
    geo, Mc, bx, Mb = R.matrices(W)
    valid = np.zeros(W["prism"][3] * W["prism"][4], bool)
    for idx, _ in W["counties"].values():
        valid[idx] = True
    changed = False
    # one request per calendar year in the window (a request cannot span years usefully here)
    for y in sorted({y for y, _ in months_between(start, end)}):
        m0 = start[1] if y == start[0] else 1
        m1 = end[1] if y == end[0] else 12
        c, months, _ = P.fetch(y, m0, m1)
        ok = [((c[i, 0].reshape(-1)[valid] != 255).mean() >= 0.999) for i in range(len(months))]
        good = [months[i] for i in range(len(months)) if ok[i]]
        if not good:
            continue
        cg = c[[i for i in range(len(months)) if ok[i]]]
        cc, cb, comp = R.year_counts(cg, good, Mc, Mb)
        p = os.path.join(a.counts, f"{y}.npz")
        z = dict(np.load(p)) if os.path.exists(p) else {
            "geo": np.array(geo), "boxes": np.array(bx), "ndays": 0,
            "rain_county": np.zeros_like(cc), "rain_box": np.zeros_like(cb),
            "complete": np.zeros(12, int), "provisional": np.zeros(12, int)}
        diff = []
        for mo in good:
            m = int(mo[5:7])
            if (not z["complete"][m - 1] or not np.array_equal(z["rain_county"][:, m - 1], cc[:, m - 1])
                    or not np.array_equal(z["rain_box"][:, m - 1], cb[:, m - 1])):
                diff.append(mo)
            z["rain_county"][:, m - 1] = cc[:, m - 1]; z["rain_box"][:, m - 1] = cb[:, m - 1]
            z["complete"][m - 1] = 1
        if diff:                                   # new months, or PRISM revised a provisional one
            np.savez_compressed(p + ".tmp.npz", **z); os.replace(p + ".tmp.npz", p)
            print(f"{y}: new or revised {diff}", flush=True)
            changed = True
        else:
            print(f"{y}: {good} unchanged", flush=True)
    # re-flag provisional months relative to the new end of record
    Z = {int(os.path.basename(f)[:4]): dict(np.load(f))
         for f in sorted(glob.glob(os.path.join(a.counts, "[0-9]" * 4 + ".npz")))}
    last = [(y, m + 1) for y in sorted(Z) for m in range(12) if Z[y]["complete"][m]][-1]
    for y, z in Z.items():
        newp = R.provisional_flags(y, z["complete"], last)
        if not np.array_equal(newp, z["provisional"]):
            z["provisional"] = newp
            p = os.path.join(a.counts, f"{y}.npz")
            np.savez_compressed(p + ".tmp.npz", **z); os.replace(p + ".tmp.npz", p)
    print("changes found" if changed else "nothing new")
    sys.exit(0 if changed else 3)


if __name__ == "__main__":
    main()
