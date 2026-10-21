#!/usr/bin/env python3
"""
prism_fetch.py YEAR [LASTMONTH]

Monthly counts of heavy-rain days per PRISM 4 km cell over the lower 48, from
ACIS (grid 21 = PRISM daily precipitation), computed on the ACIS server with a
count reduction, so no daily data are downloaded.

Thresholds 1, 2 and 3 inches, on the daily total rounded to hundredths of an
inch (cnt_ge_0.995 etc.) -- the precision precipitation is reported in, and
what the Indiana card's daily download used (reproduced exactly).
A PRISM day is the 24 h ending 12 UTC (about 7 am EST), the observer day.

Output cells/<YEAR>.npz:
  c      uint8 [nmonth, 3, 621, 1405]  days per month (255 = missing: water,
         outside the grid, or any missing day in that month)
  lat0, lon0, step   grid: row 0 = 24.0833 N, col 0 = -125.0, 1/24 deg
  months list of 'YYYY-MM'
"""
import sys, json, time, os
import numpy as np, requests

THR = (1.0, 2.0, 3.0)
URL = "https://data.rcc-acis.org/GridData"
BBOX = "-125,24,-66,50"
HERE = os.path.dirname(os.path.abspath(__file__))


def fetch(y, m0=1, m1=12, out=None, tries=5):
    el = [{"name": "pcpn", "interval": "mly", "duration": "mly",
           "reduce": f"cnt_ge_{t - 0.005:.3f}", "maxmissing": 0} for t in THR]
    q = {"bbox": BBOX, "sdate": f"{y}-{m0:02d}", "edate": f"{y}-{m1:02d}", "grid": "21",
         "elems": el, "meta": "ll"}
    for k in range(tries):
        try:
            r = requests.post(URL, json=q, timeout=900)
            d = r.json()
            if "data" not in d:
                raise RuntimeError(str(d)[:200])
            break
        except Exception as e:
            if k == tries - 1:
                raise
            time.sleep(30 * (k + 1))
    lat = np.array(d["meta"]["lat"]); lon = np.array(d["meta"]["lon"])
    months = [x[0] for x in d["data"]]
    c = np.full((len(months), len(THR)) + lat.shape, 255, np.uint8)
    for i, x in enumerate(d["data"]):
        for k in range(len(THR)):
            a = np.array(x[k + 1], np.int16)
            c[i, k][a >= 0] = a[a >= 0]
    meta = dict(lat0=float(lat[0, 0]), lon0=float(lon[0, 0]), step=1 / 24.0)
    if out:
        tmp = out + f".{os.getpid()}.tmp.npz"
        np.savez_compressed(tmp, c=c, months=np.array(months), **meta)
        os.replace(tmp, out)
    return c, months, meta


if __name__ == "__main__":
    y = int(sys.argv[1]); m1 = int(sys.argv[2]) if len(sys.argv) > 2 else 12
    dest = os.path.join(HERE, "cells", f"{y}.npz")
    if os.path.exists(dest) and len(sys.argv) <= 2:
        print(f"{y}: exists"); sys.exit(0)
    t = time.time()
    c, months, meta = fetch(y, 1, m1, dest)
    print(f"{y}: {len(months)} months, {(c[0,0] != 255).sum()} valid cells, {time.time()-t:.0f}s", flush=True)
