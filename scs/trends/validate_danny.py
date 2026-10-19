"""Reproduce the Indiana card's daily maximum heat index (UTC days, May-Sep) and
compare point by point and day by day."""
import sys, os, time
import numpy as np, xarray as xr
sys.path.insert(0, os.path.dirname(__file__))
from heatcalc import read_month, rh_pct, heat_index_f, k_to_f

D = "/mnt/user-data/uploads/Baseball Cards/Heat Index Baseball Card/ERA5_heat_index/processed/daily"
I0, I1 = 192, 213          # 42.0 .. 37.0 N
J0, J1 = 1084, 1105        # 271.0 .. 276.0 E  (-89 .. -84)
THR = [90, 100, 105, 110, 115]

for y in [int(a) for a in sys.argv[1:]]:
    ref = xr.open_dataset(f"{D}/HI_daily_{y}.nc").daily_max_hi.values   # [153, 21, 21]
    mine = []
    t0 = time.time()
    for m in range(5, 10):
        T = read_month("t", y, m, I0, I1, J0, J1)
        Td = read_month("d", y, m, I0, I1, J0, J1)
        hi = heat_index_f(k_to_f(T), rh_pct(T - 273.15, Td - 273.15))
        nd = hi.shape[0] // 24
        mine.append(hi.reshape(nd, 24, *hi.shape[1:]).max(axis=1))
    mine = np.concatenate(mine)
    d = mine - ref
    print(f"{y}: {mine.shape} read {time.time()-t0:.0f}s | daily-max HI diff: "
          f"max|d| {np.abs(d).max():.4f} F, mean {d.mean():+.5f} | where Danny >= 80F: max|d| {np.abs(d[ref>=80]).max():.4f} F")
    for t in THR:
        a, b = (mine >= t), (ref >= t)
        print(f"   >= {t}F: days mine {a.sum():6d}  Danny {b.sum():6d}  disagree {np.sum(a != b)}")
