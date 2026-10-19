#!/usr/bin/env python3
"""
era5_daily_max.py YEAR [YEAR ...]

Daily maximum 2 m temperature and daily maximum NWS heat index over the lower 48
(24-50 N, 125-66 W, ERA5 0.25 deg = 105 x 237 points), from hourly ERA5 2 m T
and dewpoint (NCAR ds633.0 copy on AWS, nsf-ncar-era5).

Days are LOCAL STANDARD days by longitude: a point at longitude L uses the
offset round(L/15) h (-8 on the Pacific coast ... -4 in far-eastern Maine), so
the 24 hours that make a day run midnight to midnight local standard time and
the afternoon maximum never straddles a day boundary. (The Indiana card used UTC
days; that choice was validated separately and is not used here.)

Output: daily/<YEAR>.npz with
  tmax_f10, hi_f10   int16 [ndays, 105, 237]  tenths of deg F (-32768 = missing)
  lat, lon           grid centres
A local day is missing only if some of its hours are not yet published (the end
of the record).
"""
import calendar, os, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from heatcalc import read_month, rh_pct, heat_index_f, k_to_f

I0, I1 = 160, 265            # 50.0 .. 24.0 N
J0, J1 = 940, 1177           # 235.0 .. 294.0 E
LAT = 90.0 - 0.25 * np.arange(I0, I1)
LON = 0.25 * np.arange(J0, J1) - 360.0
OFF = np.round(LON / 15.0).astype(int)          # -8 .. -4
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "daily")
MISS = -32768


def fields(y, m, h0=None, h1=None):
    T = read_month("t", y, m, I0, I1, J0, J1) if h0 is None else _part("t", y, m, h0, h1)
    D = read_month("d", y, m, I0, I1, J0, J1) if h0 is None else _part("d", y, m, h0, h1)
    hi = heat_index_f(k_to_f(T), rh_pct(T - 273.15, D - 273.15)).astype(np.float32)
    return k_to_f(T).astype(np.float32), hi


def _part(var, y, m, h0, h1):
    return read_month(var, y, m, I0, I1, J0, J1, h0, h1)


def next_month(y, m):
    return (y + 1, 1) if m == 12 else (y, m + 1)


def do_year(y):
    os.makedirs(OUT, exist_ok=True)
    dest = os.path.join(OUT, f"{y}.npz")
    if os.path.exists(dest):
        print(f"{y}: exists"); return
    t0 = time.time()
    tmax_all, hi_all = [], []
    for m in range(1, 13):
        nd = calendar.monthrange(y, m)[1]
        try:
            T, H = fields(y, m)
        except FileNotFoundError:
            break                                   # past the end of the record
        ny, nm = next_month(y, m)
        try:
            Tn, Hn = fields(ny, nm, 0, 8)            # the 4-8 h a local day borrows
        except FileNotFoundError:
            Tn = np.full((8,) + T.shape[1:], np.nan, np.float32); Hn = Tn.copy()
        T = np.concatenate([T, Tn]); H = np.concatenate([H, Hn])
        tm = np.full((nd,) + T.shape[1:], np.nan, np.float32); hm = tm.copy()
        for o in np.unique(OFF):
            cols = np.where(OFF == o)[0]
            s = -o                                   # local midnight in UTC hours
            blk = slice(s, s + 24 * nd)
            tb = T[blk][:, :, cols].reshape(nd, 24, T.shape[1], len(cols))
            hb = H[blk][:, :, cols].reshape(nd, 24, H.shape[1], len(cols))
            # At the end of the record the last local day lacks its final 4-8
            # night-time hours; the afternoon maximum is there, so keep the day
            # when at least 16 of its 24 hours exist.
            ok = np.isfinite(tb).sum(axis=1) >= 16
            with np.errstate(all="ignore"):
                tm[:, :, cols] = np.where(ok, np.nanmax(np.where(np.isfinite(tb), tb, -np.inf), axis=1), np.nan)
                hm[:, :, cols] = np.where(ok, np.nanmax(np.where(np.isfinite(hb), hb, -np.inf), axis=1), np.nan)
        tmax_all.append(tm); hi_all.append(hm)
        print(f"  {y}-{m:02d} done ({time.time()-t0:.0f}s)", flush=True)
    if not tmax_all:
        print(f"{y}: no data"); return
    tm = np.concatenate(tmax_all); hm = np.concatenate(hi_all)
    def q(a):
        o = np.round(a * 10).astype(np.int32)
        o[~np.isfinite(a)] = MISS
        return o.astype(np.int16)
    tmp = dest + ".tmp.npz"
    np.savez_compressed(tmp, tmax_f10=q(tm), hi_f10=q(hm), lat=LAT, lon=LON)
    os.replace(tmp, dest)
    print(f"{y}: wrote {tm.shape[0]} days in {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    for a in sys.argv[1:]:
        do_year(int(a))
