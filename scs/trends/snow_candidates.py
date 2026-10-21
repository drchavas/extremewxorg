#!/usr/bin/env python3
"""snow_candidates.py -> meta/<ST>.json and candidates.json
Every COOP (USC00...) and first-order (USW00...) station in the lower 48 that has
snowfall in ACIS, with its snowfall period of record. CoCoRaHS (US1...) is left
out: its records mostly begin after 2000. A candidate needs at least 30 years of
snowfall record inside 1950-07-01 .. 2026-06-30."""
import json, os, sys, time, datetime as dt
import requests
from concurrent.futures import ThreadPoolExecutor
STATES = ("AL AZ AR CA CO CT DE DC FL GA ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM "
          "NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY").split()
S0, S1 = dt.date(1950, 7, 1), dt.date(2026, 6, 30)

def get(st):
    p = f"meta/{st}.json"
    if os.path.exists(p):
        return json.load(open(p))
    q = {"state": st, "sdate": "1950-07-01", "edate": "2026-06-30",
         "elems": [{"name": "snow", "interval": "yly", "duration": "yly", "reduce": "sum", "maxmissing": 400}],
         "meta": "name,state,ll,elev,sids,valid_daterange,uid"}
    for k in range(5):
        try:
            d = requests.post("https://data.rcc-acis.org/MultiStnData", json=q, timeout=600).json()
            out = [s["meta"] for s in d["data"]]
            json.dump(out, open(p, "w")); print(st, len(out), flush=True); return out
        except Exception as e:
            print(st, "retry", e, flush=True); time.sleep(20 * (k + 1))
    raise SystemExit(st)

def years_in(rngs):
    n = 0
    for a, b in rngs:
        a = max(dt.date.fromisoformat(a), S0); b = min(dt.date.fromisoformat(b), S1)
        if b > a: n += (b - a).days
    return n / 365.25

with ThreadPoolExecutor(4) as ex:
    allm = [m for ms in ex.map(get, STATES) for m in ms]
cands = []
for m in allm:
    ghcn = [s.split()[0] for s in m.get("sids", []) if s.endswith(" 6")]
    ghcn = [g for g in ghcn if g.startswith(("USC00", "USW00"))]
    if not ghcn or "ll" not in m:
        continue
    yrs = years_in(m.get("valid_daterange", [[]])[0:1] and m["valid_daterange"][0:1] or [])
    if yrs >= 30:
        cands.append({"id": ghcn[0], "name": m["name"], "state": m.get("state", ""),
                      "lon": m["ll"][0], "lat": m["ll"][1], "elev": m.get("elev"),
                      "uid": m.get("uid"), "range": m["valid_daterange"][0], "years": round(yrs, 1)})
json.dump(cands, open("candidates.json", "w"))
print("stations", len(allm), "candidates", len(cands))
