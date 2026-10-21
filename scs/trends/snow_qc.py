#!/usr/bin/env python3
"""
snow_qc.py  DAILY_DIR CANDIDATES OUT_JSON_GZ [--report REPORT.json]

Heavy-snow days at quality-controlled COOP and first-order stations, after
Kunkel et al. (2009, JTECH 26, 33-44), automated. Seasons run July-June and are
labelled by their ending year (1951 = 1950-51 ... 2026 = 2025-26).

Day level
  * Trace counts as 0.
  * Zero-fill (Kunkel): a missing snowfall becomes 0 when that day's precipitation
    is 0, or when precipitation fell with a minimum temperature above 32 F.
    Observers often left the snowfall column blank on days that could not have
    had snow.
  * Accumulated multi-day values (A / S flags) cannot be put on one day: missing.
  * Suspect days are set to missing:
      - more than 60 in in a day;
      - 1 in or more of snow with exactly 0.00 in of precipitation;
      - 4 in or more at a snow-to-liquid ratio above 60:1;
      - 4 in or more equal to a snow depth that was already on the ground the day
        before and did not grow (snow depth keyed as snowfall).
Season level (a failed season is "no observation", never zero)
  * October-May at least 90% complete after zero-fill;
  * none of December, January, February entirely missing;
  * not an estimated season: if more than 10 days had both snow and precipitation
    and more than half of them read exactly 10:1, the snowfall was computed from
    the gauge, not measured (the EPA snowfall indicator's screen).
Station level
  * "all": at least 30 valid seasons.
  * "qc" (the page's QC set): at least 60 of 76 valid seasons, at least 5 valid in
    each of the first (1951-60) and last (2017-26) decades, and no significant
    break against its neighbours: the log ratio of the station's seasonal total
    to a neighbour reference (median of up to 10 stations within 200 km and
    500 m of elevation, each scaled to the station's mean) shows neither a
    Pettitt change point (p < 0.01, step > 20%) nor a linear drift (p < 0.01,
    > 5% per decade). This replaces Kunkel's seven-expert panel. Stations
    averaging under 3 in a season cannot be tested that way and are kept on
    length alone.
"""
import argparse, glob, gzip, json, math, os, sys
import datetime as dt
import numpy as np
from scipy import stats

MISS, ACC, TR = -9999, -9998, -1
D0 = dt.date(1950, 7, 1)
NDAY = (dt.date(2026, 6, 30) - D0).days + 1
DATES = [D0 + dt.timedelta(i) for i in range(NDAY)]
MON = np.array([d.month for d in DATES])
SEAS = np.array([d.year + (1 if d.month >= 7 else 0) for d in DATES])
Y0, Y1 = 1951, 2026
NS = Y1 - Y0 + 1
THR = [10, 40, 60, 120]                    # tenths of an inch: 1, 4, 6, 12 in
COLD = np.isin(MON, [10, 11, 12, 1, 2, 3, 4, 5])
LEN_ALL, LEN_QC = 30, 60


def clean(a):
    """a int16 [nday, 4] snow (0.1 in), snwd (in), pcpn (0.01 in), mint (F)."""
    snow = a[:, 0].astype(np.int32); snwd = a[:, 1].astype(np.int32)
    pcp = a[:, 2].astype(np.int32); tmin = a[:, 3].astype(np.int32)
    s = snow.astype(float)
    s[snow == TR] = 0.0
    s[(snow == MISS) | (snow == ACC)] = np.nan
    p = pcp.astype(float); p[pcp == TR] = 0.0; p[(pcp == MISS) | (pcp == ACC)] = np.nan
    t = tmin.astype(float); t[tmin == MISS] = np.nan
    d = snwd.astype(float); d[snwd == TR] = 0.0; d[(snwd == MISS) | (snwd == ACC)] = np.nan
    flags = {}
    # zero-fill: no snow possible
    zf = np.isnan(s) & (snow != ACC) & ((p == 0) | ((p > 0) & (t > 32)))
    s[zf] = 0.0; flags["zero_filled"] = int(zf.sum())
    # suspect days
    big = s > 600
    nopcp = (s >= 10) & (pcp == 0)                         # exactly 0.00, not trace or missing
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = (s >= 40) & (p > 0) & (s * 10 / p > 60)     # s tenths in / p hundredths in
    dprev = np.r_[np.nan, d[:-1]]
    sin = s / 10.0
    depth = (s >= 40) & (dprev >= np.round(sin)) & (d <= dprev) & (np.abs(d - np.round(sin)) <= 1)
    sus = big | nopcp | ratio | depth
    flags.update(big=int(big.sum()), snow_no_precip=int(nopcp.sum()), ratio60=int(ratio.sum()),
                 depth_as_snowfall=int(depth.sum()))
    s[sus] = np.nan
    return s, p, flags


def seasons(s, p):
    """valid[NS] bool, total[NS] (in), monthly counts [NS, 12, nthr], est[NS]."""
    valid = np.zeros(NS, bool); total = np.full(NS, np.nan)
    cnt = np.zeros((NS, 12, len(THR)), np.int16); est = np.zeros(NS, bool)
    for k, y in enumerate(range(Y0, Y1 + 1)):
        m = SEAS == y
        cm = m & COLD
        if cm.sum() == 0:
            continue
        ss = s[m]; sc = s[cm]
        miss = np.isnan(sc).mean()
        ok = miss <= 0.10
        for mo in (12, 1, 2):
            mm = m & (MON == mo)
            if mm.any() and np.isnan(s[mm]).all():
                ok = False
        both = m & (s > 0) & (p > 0)
        if both.sum() > 10:
            tenone = np.isclose(s[both], p[both] / 1.0)       # tenths of snow == hundredths of liquid
            if tenone.mean() > 0.5:
                est[k] = True; ok = False
        valid[k] = ok
        if ok:
            total[k] = np.nansum(ss) / 10.0
            mons = MON[m]
            for j, t in enumerate(THR):
                hit = ss >= t
                for mo in range(1, 13):
                    cnt[k, mo - 1, j] = int((hit & (mons == mo)).sum())
    return valid, total, cnt, est


def pettitt(x):
    n = len(x)
    r = stats.rankdata(x)
    k = np.arange(1, n)
    U = 2 * np.cumsum(r)[:-1] - k * (n + 1)
    i = int(np.argmax(np.abs(U))); K = abs(U[i])
    p = 2 * math.exp(-6 * K * K / (n ** 3 + n ** 2))
    return i + 1, min(1.0, p)


def homogeneity(i, S, tot, valid, mean):
    """Neighbour-ratio tests for station i. Returns (verdict, detail)."""
    if mean[i] < 3:
        return "untestable", {"why": "mean seasonal snowfall under 3 in"}
    la, lo, el = S[i]["lat"], S[i]["lon"], S[i].get("elev") or 0
    cand = []
    for j, t in enumerate(S):
        if j == i or mean[j] < 3:
            continue
        dkm = 111.2 * math.hypot(t["lat"] - la, (t["lon"] - lo) * math.cos(math.radians(la)))
        if dkm > 200 or abs((t.get("elev") or 0) - el) > 500 * 3.281:
            continue
        common = valid[i] & valid[j]
        if common.sum() < 30:
            continue
        cand.append((dkm, j))
    cand = [j for _, j in sorted(cand)[:10]]
    if len(cand) < 3:
        return "untestable", {"why": f"only {len(cand)} usable neighbours"}
    ref = np.full((len(cand), NS), np.nan)
    for r, j in enumerate(cand):
        v = np.where(valid[j], tot[j], np.nan)
        ref[r] = v / mean[j] * mean[i]
    with np.errstate(all="ignore"):
        R = np.nanmedian(ref, axis=0)
    ok = valid[i] & np.isfinite(R)
    if ok.sum() < 30:
        return "untestable", {"why": "too few seasons in common with neighbours"}
    c = max(1.0, 0.1 * mean[i])
    q = np.log((tot[i][ok] + c) / (R[ok] + c))
    yrs = np.arange(Y0, Y1 + 1)[ok]
    k, pp = pettitt(q)
    step = abs(np.mean(q[k:]) - np.mean(q[:k]))
    lr = stats.linregress(yrs, q)
    drift = abs(lr.slope) * 10
    det = {"n_nb": len(cand), "pettitt_p": round(pp, 5), "break_year": int(yrs[k]) if k < len(yrs) else None,
           "step_pct": round((math.exp(step) - 1) * 100, 1), "drift_pct_per_decade": round((math.exp(drift) - 1) * 100, 1),
           "drift_p": round(lr.pvalue, 5)}
    bad = (pp < 0.01 and step > math.log(1.20)) or (lr.pvalue < 0.01 and drift > math.log(1.05))
    return ("inhomogeneous" if bad else "homogeneous"), det


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("daily"); ap.add_argument("cands"); ap.add_argument("out")
    ap.add_argument("--report", default=None)
    a = ap.parse_args()
    C = {c["id"]: c for c in json.load(open(a.cands))}
    S, V, T, N, F, E = [], [], [], [], [], []
    for f in sorted(glob.glob(os.path.join(a.daily, "*.npz"))):
        sid = os.path.basename(f)[:-4]
        if sid not in C:
            continue
        z = np.load(f)["a"]
        if z.shape[0] != NDAY:
            continue
        s, p, fl = clean(z)
        valid, total, cnt, est = seasons(s, p)
        if valid.sum() < LEN_ALL:
            continue
        S.append(C[sid]); V.append(valid); T.append(total); N.append(cnt); F.append(fl); E.append(int(est.sum()))
    V = np.array(V); T = np.array(T); N = np.array(N)
    mean = np.array([np.nanmean(t) for t in T])
    print(f"stations with >= {LEN_ALL} valid seasons: {len(S)}", flush=True)
    rep = []
    nqc = 0
    for i, st in enumerate(S):
        nv = int(V[i].sum())
        first = int(V[i][:10].sum()); last = int(V[i][-10:].sum())
        length_ok = nv >= LEN_QC and first >= 5 and last >= 5
        verdict, det = homogeneity(i, S, T, V, mean) if length_ok else ("short", {})
        qc = length_ok and verdict in ("homogeneous", "untestable")
        nqc += qc
        rep.append({"id": st["id"], "name": st["name"], "state": st["state"], "valid": nv,
                    "first10": first, "last10": last, "mean_in": round(float(mean[i]), 1),
                    "est_seasons": E[i], "flags": F[i], "verdict": verdict, "qc": bool(qc), **det})
    print(f"QC set: {nqc}", flush=True)
    keys = [(i, k, mo) for i in range(len(S)) for k in range(NS) if V[i][k]
            for mo in range(12) if N[i, k, mo, 0] > 0]
    out = {
        "meta": {
            "hazard": "snow", "label": "Snowfall", "unit": "in",
            "note": ("Days with at least the threshold of new snowfall in a day at a quality-controlled "
                     "NOAA Cooperative Observer or first-order station (GHCN-Daily, via ACIS), "
                     "counted over a July–June season labeled by its ending year."),
            "thresholds": [{"key": "s1", "label": "≥ 1″ of snow in a day", "short": "≥1″", "min": 1},
                           {"key": "s4", "label": "≥ 4″ of snow in a day", "short": "≥4″", "min": 4},
                           {"key": "s6", "label": "≥ 6″ of snow in a day", "short": "≥6″", "min": 6},
                           {"key": "s12", "label": "≥ 12″ of snow in a day", "short": "≥12″", "min": 12}],
            "season": "JulJun", "year0": Y0, "year1": Y1, "kind": "station",
            "completeness": 0.90, "nQC": nqc, "qcname": "Kunkel-style QC",
            "source": "NOAA GHCN-Daily COOP and first-order stations via ACIS; QC after Kunkel et al. (2009)",
            "ncell": len(keys),
        },
        "stations": [{"id": st["id"], "name": st["name"].title(), "state": st["state"],
                      "lat": round(st["lat"], 4), "lon": round(st["lon"], 4), "dp": int(r["qc"])}
                     for st, r in zip(S, rep)],
        "validYears": {str(i): [Y0 + k for k in range(NS) if V[i][k]] for i in range(len(S))},
        "si": [k[0] for k in keys], "yi": [k[1] for k in keys], "mi": [k[2] + 1 for k in keys],
        "v": [[int(N[k[0], k[1], k[2], j]) for k in keys] for j in range(len(THR))],
    }
    with gzip.open(a.out, "wt", encoding="utf-8") as fh:
        json.dump(out, fh, separators=(",", ":"))
    print(f"wrote {a.out} {os.path.getsize(a.out)/1e6:.2f} MB, {len(S)} stations, {len(keys):,} cells")
    if a.report:
        json.dump(rep, open(a.report, "w"), indent=0)


if __name__ == "__main__":
    main()
