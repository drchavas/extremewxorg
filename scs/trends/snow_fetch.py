#!/usr/bin/env python3
"""snow_fetch.py [N_WORKERS] -> daily/<GHCNID>.npz for every station in candidates.json
Daily snowfall (tenths of in), snow depth (in), precipitation (hundredths of in) and
minimum temperature (F) from ACIS StnData, 1950-07-01 .. 2026-06-30.
Codes: -9999 missing; -9998 an accumulated multi-day value (A flag) or 'S' (part of
an accumulation), which cannot be put on one day; -1 trace."""
import json, os, sys, time, re
import numpy as np, requests
from concurrent.futures import ThreadPoolExecutor
MISS, ACC, TR = -9999, -9998, -1
SCALE = {"snow": 10, "snwd": 1, "pcpn": 100, "mint": 1}
NUM = re.compile(r"^(-?\d+(?:\.\d+)?)([A-Za-z]?)$")

def conv(v, sc):
    if v in ("M", "", None): return MISS
    if v == "T": return TR
    if v == "S": return ACC
    m = NUM.match(v)
    if not m: return MISS
    x, f = m.groups()
    if f == "A": return ACC
    return int(round(float(x) * sc))

def one(c):
    p = f"daily/{c['id']}.npz"
    if os.path.exists(p): return "skip"
    q = {"sid": c["id"], "sdate": "1950-07-01", "edate": "2026-06-30",
         "elems": [{"name": e} for e in SCALE]}
    for k in range(5):
        try:
            d = requests.post("https://data.rcc-acis.org/StnData", json=q, timeout=300).json()
            rows = d["data"]; break
        except Exception as e:
            if k == 4: return f"FAIL {c['id']} {e}"
            time.sleep(10 * (k + 1))
    a = np.array([[conv(r[i + 1], sc) for i, sc in enumerate(SCALE.values())] for r in rows], np.int16)
    np.savez_compressed(p + ".tmp.npz", a=a, d0=rows[0][0]); os.replace(p + ".tmp.npz", p)
    return "ok"

if __name__ == "__main__":
    C = json.load(open("candidates.json"))
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    t = time.time(); done = 0
    with ThreadPoolExecutor(n) as ex:
        for r in ex.map(one, C):
            done += 1
            if r.startswith("FAIL"): print(r, flush=True)
            if done % 200 == 0: print(f"{done}/{len(C)} {time.time()-t:.0f}s", flush=True)
    print("done", done)
