#!/usr/bin/env python3
"""
fzra_update.py STATIONS_CSV DAILY_DIR OUT_DIR [--dry-run]

Monthly refresh of the national freezing-rain hazard. GHCNh rewrites its current-
year files daily (about three months behind real time) and still revises the
previous year, so this re-fetches those two calendar years for every station id,
re-reduces them into DAILY_DIR (ghcnh_daily.py replaces those years), and rebuilds
fzra.json.gz + its index entry (build_fzra_data.py). ~1 minute of download, a
few minutes of reduction.
Exit status: 0 = the page data changed, 3 = nothing new, other = error.
"""
import datetime as dt, gzip, hashlib, os, shutil, sys, tempfile
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import ghcnh_fetch as F, ghcnh_daily as D, build_fzra_data as B


def digest(p):
    if not os.path.exists(p): return None
    return hashlib.sha1(gzip.open(p).read()).hexdigest()


def main(stfile, daily, outdir, dry=False):
    s = pd.read_csv(stfile, dtype=str).fillna("")
    ids = sorted(set(s.id) | {x for a in s.also for x in a.split()})
    y = dt.date.today().year
    years = [y - 1, y]
    print(f"{len(ids)} ids, years {years}{' (dry run)' if dry else ''}", flush=True)
    if dry: sys.exit(0)
    tmp = tempfile.mkdtemp(prefix="ghcnh_")
    try:
        print(F.fetch(tmp, ids, years, force=True), flush=True)
        D.main(tmp, daily)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    p = os.path.join(outdir, "fzra.json.gz"); before = digest(p)
    B.main(stfile, daily, outdir)
    changed = digest(p) != before
    print("changes found" if changed else "nothing new")
    sys.exit(0 if changed else 3)


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if x != "--dry-run"]
    main(*a[:3], dry="--dry-run" in sys.argv)
