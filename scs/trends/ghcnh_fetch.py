#!/usr/bin/env python3
"""ghcnh_fetch.py -- download GHCNh station-year parquet files (NOAA NCEI, the
successor to ISD Global Hourly). Parquet, not PSV: ~1.2 MB vs 13 MB a station-year.

  python3 ghcnh_fetch.py OUTDIR YEAR[-YEAR] ID [ID ...]      (or IDs from a file with @file)
A file that already exists is kept unless --force; a 404 (no data that year) is
recorded as an empty marker OUTDIR/YEAR/ID.none so it is not asked again.
"""
import os, sys, time, concurrent.futures as cf
import requests
BASE = "https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/access/by-year"
S = requests.Session()


def url(sid, y):
    return f"{BASE}/{y}/parquet/GHCNh_{sid}_{y}.parquet"


def get(outdir, sid, y, force=False):
    d = os.path.join(outdir, str(y)); os.makedirs(d, exist_ok=True)
    p = os.path.join(d, sid + ".parquet"); none = os.path.join(d, sid + ".none")
    if not force and (os.path.exists(p) or os.path.exists(none)):
        return "cached"
    for k in range(4):
        try:
            r = S.get(url(sid, y), timeout=120)
            if r.status_code == 404:
                open(none, "w").close(); return "404"
            r.raise_for_status()
            with open(p + ".tmp", "wb") as fh:
                fh.write(r.content)
            os.replace(p + ".tmp", p); return "ok"
        except Exception as e:
            err = e; time.sleep(2 + 4 * k)
    return f"fail {err}"


def fetch(outdir, ids, years, workers=16, force=False):
    jobs = [(s, y) for s in ids for y in years]
    stat = {}
    with cf.ThreadPoolExecutor(workers) as ex:
        for (s, y), r in zip(jobs, ex.map(lambda j: get(outdir, j[0], j[1], force), jobs)):
            k = r.split()[0]; stat[k] = stat.get(k, 0) + 1
            if k == "fail":
                print(s, y, r, flush=True)
    return stat


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if x != "--force"]
    out, yr = a[0], a[1]
    y0, y1 = (int(yr), int(yr)) if "-" not in yr else map(int, yr.split("-"))
    ids = []
    for x in a[2:]:
        ids += open(x[1:]).read().split() if x.startswith("@") else [x]
    print(fetch(out, ids, range(y0, y1 + 1), force="--force" in sys.argv))
