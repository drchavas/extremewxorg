"""Monthly means from ARCO-ERA5 hourly (gs://gcp-public-data-arco-era5, full_37-1h-0p25deg-chunk-1.zarr-v3)
for months after the NCAR ds633.1 monthly archive ends (Dec 2022).
2m_temperature: mean over the 24 hourly analyses of every day in the month (valid 00..23 UTC).
mean_total_precipitation_rate: mean over the hourly rates whose accumulation hour lies inside the month
(valid 01 UTC on day 1 through 00 UTC on day 1 of the next month).

    python3 fetch_era5_arco.py COARSE_DIR

Public bucket, no key. ~2 MB per hourly global chunk, ~1,500 chunks per month for both
variables; nothing is written but the 1 deg monthly means. Took ~25 min for Dec 2022 (overlap
check against GDEX) + Jun-Feb of 2023-2026, ~10 min more for Mar-May. Extend `months` for later seasons."""
import os, sys, json, datetime as dt, numpy as np, requests, time
from concurrent.futures import ThreadPoolExecutor
from numcodecs import Blosc
sys.path.insert(0, os.path.dirname(__file__))
from era5_coarsen import coarsen
G = 'https://storage.googleapis.com/gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3'
OUT = sys.argv[1] if len(sys.argv) > 1 else 'coarse'
VAR = {'t2m': '2m_temperature', 'mtpr': 'mean_total_precipitation_rate'}
S = requests.Session(); S.mount('https://', requests.adapters.HTTPAdapter(pool_connections=32, pool_maxsize=32))
codec = Blosc()
def hidx(t): return int((t - dt.datetime(1900, 1, 1)).total_seconds() // 3600)
def fetch(args):
    v, i = args
    for a in range(6):
        try:
            r = S.get(f'{G}/{VAR[v]}/{i}.0.0', timeout=60)
            if r.status_code == 200:
                return np.frombuffer(codec.decode(r.content), dtype='<f4').reshape(721, 1440)
        except Exception as e:
            pass
        time.sleep(2 * (a + 1))
    raise RuntimeError(f'failed {v} {i}')
def month(v, y, m):
    out = f'{OUT}/arco_{v}_{y}_{m:02d}.npy'
    if os.path.exists(out): return
    t0 = dt.datetime(y, m, 1); t1 = dt.datetime(y + (m == 12), m % 12 + 1, 1)
    if v == 't2m': idx = list(range(hidx(t0), hidx(t1)))
    else: idx = list(range(hidx(t0) + 1, hidx(t1) + 1))
    acc = np.zeros((721, 1440)); n = 0
    with ThreadPoolExecutor(24) as ex:
        for b in range(0, len(idx), 48):
            for a in ex.map(fetch, [(v, i) for i in idx[b:b + 48]]):
                acc += a; n += 1
    assert n == len(idx)
    np.save(out, coarsen(acc / n))   # ARCO latitude is 90 -> -90, same as GDEX
    print(v, y, m, n, 'hours ok', flush=True)
if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    # Dec 2022 is the overlap check against GDEX; after that, every month the page uses
    # (June of year 0 through May of year +1) up to the last ENSO year built.
    months = [(2022, 12)]
    for y in (2023, 2024, 2025, 2026):
        for m in range(1, 13):
            if y == 2026 and m > 5: continue
            months.append((y, m))
    for (y, m) in months:
        for v in ('t2m', 'mtpr'):
            month(v, y, m)
