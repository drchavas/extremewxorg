#!/usr/bin/env python3
"""
build_fzra_data.py STATIONS_CSV DAILY_DIR OUT_DIR

Freezing rain, lower 48, from NOAA GHCNh (the successor to ISD Global Hourly,
which froze in Aug 2025). The method is the Indiana build's (build_station_data.py)
unchanged:

  * a day counts when any report that UTC day contains FZRA in its text (the
    METAR body or remarks; FZRANO, "freezing-rain sensor not operational", is not
    freezing rain); the higher levels count distinct UTC hours with such a report
  * July-June cold seasons labelled by the ending year
  * a season is kept only if >= 90% of its days have a report, and is otherwise
    NO OBSERVATION, not zero

Stations come from fzra_stations.py: every federal ASOS plus the other airfields
that had round-the-clock observers before automation. `dp` marks the QC set (the
page's "QC only" view): sites that had an overnight observer, DelPizzo et al.
(2025)'s criterion (`dpl` = on their own Great Lakes list). A site whose record
GHCNh splits across several ids (an old and a new WBAN) is read as the union.

The daily tables come from ghcnh_fetch.py + ghcnh_daily.py.
"""
import calendar, gzip, json, os, re, sys
import numpy as np, pandas as pd

COMPLETENESS = 0.90
Y0 = 2001                     # first season (Jul 2000 - Jun 2001), as before
EPOCH = pd.Timestamp("1970-01-01")
SPEC = {
    "label": "Freezing Rain", "unit": "h", "season": "JulJun",
    "note": ("Days with freezing rain (FZRA) in the hourly or special weather reports "
             "(METARs) of an airport weather station. Counted over a July–June cold season "
             "labeled by the ending year. Higher levels count hours of freezing rain in the "
             "day, a rough proxy for how much ice had a chance to accrete. The remark FZRANO "
             "(freezing-rain sensor not operational) is not counted."),
    "thresholds": [
        {"key": "any", "label": "Any freezing rain",  "short": "any",  "min": 1},
        {"key": "h3",  "label": "≥ 3 hours in a day", "short": "≥3 h", "min": 3},
        {"key": "h6",  "label": "≥ 6 hours in a day", "short": "≥6 h", "min": 6},
    ],
}
SOURCE = "NOAA/NCEI Global Historical Climatology Network-hourly (GHCNh)"
ABBR = [(r"\bAP\b", "Airport"), (r"\bARPT\b", "Airport"), (r"\bRGNL\b", "Regional"),
        (r"\bMUNI\b", "Municipal"), (r"\bINTL\b", "International"), (r"\bCO\b", "County"),
        (r"\bFLD\b", "Field"), (r"\bMEM\b", "Memorial")]
KEEP_UP = {"AFB", "AAF", "ANG", "NAS", "MCAS", "ASOS", "AWOS", "JRB", "NAF", "AFS", "ARB", "II", "III"}


def nice(name):
    s = name.upper()
    for a, b in ABBR:
        s = re.sub(a, b.upper(), s)
    return " ".join(w if w in KEEP_UP else w.title() for w in s.split())


# Mountain sites where "FZRA" is mostly ice from cloud or fog, not freezing rain
# (review of 2026-10-22: Sexton Summit 79% of its FZRA reports with no measurable
# precipitation, Mount Washington 92% with freezing fog). A site is left out when,
# over its whole record, at least half of its freezing-rain hours were reported
# together with freezing fog (FZFG), or at least half with visibility at or below
# 1/2 statute mile. Across the 676 sites with >= 20 FZRA hours the median shares are
# 0.7% and 1.3% (95th percentile 11% and 17%); the rule removes exactly the
# mountain and pass sites: Mount Washington, Sexton Summit, Blue Canyon, Stampede
# Pass, Mullan Pass, Guadalupe Mountains (Pine Springs) and Bryce Canyon.
# Shares from fewer than MIN_FZH freezing-rain hours are noise and never exclude a site.
FOG_SHARE, LOWVIS_SHARE, MIN_FZH = 0.50, 0.50, 20


def load_site(daily, ids):
    """daily FZRA-hour series for a site, and its fog / low-visibility shares"""
    parts = []
    for i in ids:
        p = os.path.join(daily, i + ".npz")
        if os.path.exists(p):
            z = np.load(p)
            n = len(z["day"])
            parts.append(pd.DataFrame({"day": z["day"], "fz": z["fz"],
                                       "fg": z["fg"] if "fg" in z else np.zeros(n, np.uint8),
                                       "lv": z["lv"] if "lv" in z else np.zeros(n, np.uint8)}))
    if not parts:
        return None, 0.0, 0.0, 0
    d = pd.concat(parts).groupby("day")[["fz", "fg", "lv"]].max()
    nfz = float(d.fz.sum())
    return d.fz, (d.fg.sum() / nfz if nfz else 0.0), (d.lv.sum() / nfz if nfz else 0.0), nfz


def build(stfile, daily):
    S = pd.read_csv(stfile, dtype=str).fillna("")
    mins = [t["min"] for t in SPEC["thresholds"]]; nlev = len(mins)
    stations, cells, valid, fogout = [], {}, {}, []
    for _, r in S.iterrows():
        fz, fgs, lvs, nfz = load_site(daily, [r.id] + r.also.split())
        if fz is None:
            continue
        if nfz >= MIN_FZH and (fgs >= FOG_SHARE or lvs >= LOWVIS_SHARE):
            fogout.append({"id": r.id, "name": nice(r["name"]), "state": r.state,
                           "fog_share": round(fgs, 3), "lowvis_share": round(lvs, 3)})
            continue
        date = EPOCH + pd.to_timedelta(fz.index.values, unit="D")
        season = np.where(date.month >= 7, date.year + 1, date.year)
        df = pd.DataFrame({"season": season, "mo": date.month, "fz": fz.values})
        nday = df.groupby("season").size()
        ok = [int(y) for y, n in nday.items()
              if y >= Y0 and n / (366 if calendar.isleap(y) else 365) >= COMPLETENESS]
        if not ok:
            continue
        si = len(stations)
        st = {"id": r.id, "name": nice(r["name"]), "state": r.state,
              "lat": float(r.lat), "lon": float(r.lon), "dp": int(r.qc), "icao": r.icao}
        if r.dp == "1":
            st["dpl"] = 1
        stations.append(st)
        valid[str(si)] = ok
        h = df[df.season.isin(ok) & (df.fz > 0)]
        for (y, m), g in h.groupby(["season", "mo"]):
            cells[(si, int(y), int(m))] = [int((g.fz >= k).sum()) for k in mins]
    obs = [y for v in valid.values() for y in v]
    y0, y1 = min(obs), max(obs)
    keys = sorted(cells)
    return {
        "meta": {"hazard": "fzra", "label": SPEC["label"], "unit": SPEC["unit"],
                 "note": SPEC["note"], "thresholds": SPEC["thresholds"],
                 "season": SPEC["season"], "year0": y0, "year1": y1, "kind": "station",
                 "completeness": COMPLETENESS, "source": SOURCE,
                 "nQC": sum(s["dp"] for s in stations),
                 "fogExcluded": fogout,
                 "nDelPizzo": sum(s.get("dpl", 0) for s in stations),
                 "ncell": len(keys)},
        "stations": stations,
        "validYears": valid,
        "si": [k[0] for k in keys], "yi": [k[1] - y0 for k in keys], "mi": [k[2] for k in keys],
        "v": [[cells[k][i] for k in keys] for i in range(nlev)],
    }


def main(stfile, daily, outdir):
    res = build(stfile, daily)
    if len(res["stations"]) < 100:
        raise SystemExit(f"!! only {len(res['stations'])} stations -- refusing to overwrite fzra.json.gz")
    p = os.path.join(outdir, "fzra.json.gz")
    with gzip.open(p, "wt", encoding="utf-8") as fh:
        json.dump(res, fh, separators=(",", ":"))
    m = res["meta"]
    print(f"wrote {p} ({os.path.getsize(p)/1e3:.0f} kB): {len(res['stations'])} stations, "
          f"{m['nQC']} QC ({m['nDelPizzo']} on DelPizzo's list), seasons {m['year0']}-{m['year1']}")
    ip = os.path.join(outdir, "index.json")
    idx = json.load(open(ip))
    ent = {"key": "fzra", "label": m["label"], "unit": m["unit"], "note": m["note"],
           "thresholds": m["thresholds"], "year0": m["year0"], "year1": m["year1"],
           "kind": "station", "season": m["season"], "file": "fzra.json.gz",
           "nDelPizzo": m["nDelPizzo"], "nQC": m["nQC"]}
    hz = idx["hazards"]
    k = next((i for i, h in enumerate(hz) if h["key"] == "fzra"), None)
    if k is None: hz.append(ent)
    else: hz[k] = ent                           # keep its place in the menu
    json.dump(idx, open(ip, "w"), indent=1)


if __name__ == "__main__":
    main(*sys.argv[1:4])
