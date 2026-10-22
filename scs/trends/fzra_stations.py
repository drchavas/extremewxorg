#!/usr/bin/env python3
"""fzra_stations.py -- the station set for the national freezing-rain hazard.

Universe: every federal ASOS in the lower 48 (NCEI HOMR asos-stations.txt), plus
any other GHCNh airport station (USW) that had round-the-clock observers before
automation -- mostly military fields, which keep their own 24-h observers.

QC set ("24-h observer stations"): DelPizzo et al. (2025) kept only stations with
an overnight manual observer, because automated freezing-rain reports run high
where nobody is there to correct them.  Their list covers the Great Lakes only;
nationally we apply the same idea from the data: a site qualifies if, in one of
1985, 1987 or 1990 (before ASOS), it had an observation in the local small hours
(01-05 LST) on at least 90% of its observing days.  A site on DelPizzo's list
always qualifies.  The test is made per SITE (stations within 3 km pooled),
because GHCNh often files a site's pre-ASOS record under an older WBAN.

Inputs (cwd): asos-stations.txt, stl.csv (ghcnh-station-list.csv), inv.txt
(ghcnh-inventory.txt), overnight_best.csv (overnight.py over 1985/87/90),
stations_delpizzo2025.csv.  Output: fzra_stations.csv
"""
import numpy as np, pandas as pd
NONCONUS = ["AK", "HI", "PR", "VI", "GU", "AS", "MP"]
COLD = ["JAN", "FEB", "MAR", "APR", "MAY", "OCT", "NOV", "DEC"]

st = pd.read_csv("stl.csv", dtype=str)
st = st[st.GHCN_ID.str.startswith("USW") & st.STATE.notna() & ~st.STATE.isin(NONCONUS)].copy()
st["lat"] = st.LATITUDE.astype(float); st["lon"] = st.LONGITUDE.astype(float)
# the state field is not enough: GHCNh files Aruba (TNCA) and Curacao (TNCC) under
# "CA" -- keep the lower-48 box as well
st = st[st.lat.between(24.0, 49.6) & st.lon.between(-125.0, -66.8)].copy()
inv = pd.read_csv("inv.txt", sep=r"\s+"); inv = inv[inv.GHCNh_ID.str.startswith("USW")]
s = inv[inv.YEAR >= 2000]
# share of Oct-May months 2000-2026 with >= 500 reports: a rough "has the record" test;
# the builder applies the real per-season completeness screen
f01 = (s[COLD] >= 500).sum(axis=1).groupby(s.GHCNh_ID).sum() / (8 * 27)
st["f01"] = st.GHCN_ID.map(f01).fillna(0)

asos = pd.read_fwf("asos-stations.txt", skiprows=[1])
ICAO_FIX = {"USW00024018": "KCYS"}      # Cheyenne airport; GHCNh lists F.E. Warren's KFEW
asos = set(asos.GHCND.dropna().astype(str))
ov = pd.read_csv("overnight_best.csv").set_index("id")
st["night"] = st.GHCN_ID.map(ov.night).fillna(0)
dp = pd.read_csv("stations_delpizzo2025.csv", comment="#")
dp = dp[dp.icao.str.startswith("K")]


def km(la1, lo1, la2, lo2):
    return np.hypot((la2 - la1) * 111.2, (lo2 - lo1) * 111.2 * np.cos(np.radians(la1)))


# sites: cluster GHCNh ids within 3 km (or the same ICAO)
st = st.sort_values("f01", ascending=False).reset_index(drop=True)
site = -np.ones(len(st), int); n = 0
for i, r in st.iterrows():
    if site[i] >= 0: continue
    d = km(r.lat, r.lon, st.lat.values, st.lon.values)
    same = (d <= 3.0) | ((st.ICAO.values == r.ICAO) & pd.notna(r.ICAO))
    site[(site < 0) & same] = n; n += 1
st["site"] = site
g = st.groupby("site")
siteN = g.night.max()
rows = []
for k, grp in g:
    rep = grp.iloc[0]                       # the id with the most 2000-2026 data
    in_asos = grp.GHCN_ID.isin(asos).any()
    night = siteN[k]
    near_dp = dp.apply(lambda q: km(rep.lat, rep.lon, q.lat, q.lon), axis=1).min()
    is_dp = near_dp <= 3.0 or grp.ICAO.isin(dp.icao).any()
    h24 = night >= 0.9 or is_dp
    if rep.f01 < 0.5:                       # no usable modern record
        continue
    if not (in_asos or h24):
        continue
    # the representative id's ICAO, else any in the group; a few GHCNh entries are
    # wrong and are corrected by hand (NCEI's ASOS list is no better: it gives KDJT for
    # West Palm Beach and FAA codes such as 0J4 for Florala)
    icao = ICAO_FIX.get(rep.GHCN_ID) or \
        (rep.ICAO if isinstance(rep.ICAO, str) and rep.ICAO.strip() else "") or \
        next((x for x in grp.ICAO if isinstance(x, str) and x.strip()), "")
    rows.append(dict(id=rep.GHCN_ID, icao=icao, name=rep.NAME.title(), state=rep.STATE,
                     lat=round(rep.lat, 4), lon=round(rep.lon, 4), asos=int(in_asos),
                     night=round(night, 3), dp=int(is_dp), qc=int(h24),
                     also=" ".join(x for x in grp.GHCN_ID if x != rep.GHCN_ID)))
out = pd.DataFrame(rows).sort_values(["state", "name"])
out.to_csv("fzra_stations.csv", index=False)
print(len(out), "stations;", out.qc.sum(), "QC;", out.asos.sum(), "ASOS;", out.dp.sum(), "on DelPizzo's list")
print("QC not ASOS:", ((out.qc == 1) & (out.asos == 0)).sum())
print(out[out.state == "IN"][["id", "icao", "name", "qc", "dp", "night", "also"]].to_string())
