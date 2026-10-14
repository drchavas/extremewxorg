# Monthly means from hourly ERA5 without a CDS account

How we built ERA5 monthly means for Jan 2023 – May 2026 from **hourly** ERA5. It took about 20–30 s
per variable per month, on a 2-CPU cloud box with no special hardware. The trick is Google's public
cloud copy of ERA5 ("ARCO-ERA5"). It is a Zarr store, one global hourly field per file, and needs no
account and no API key. Fetch the files directly over HTTPS in parallel and keep a running sum.

## The data

- Store: `https://storage.googleapis.com/gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3`
  - Equivalent: `gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3`
  - Public bucket; anonymous HTTPS GET works.
- Coverage: 1940 → present. The store's `.zattrs` gives `valid_time_stop` (final ERA5) and
  `valid_time_stop_era5t` (preliminary ERA5T, replaced later). Check before using recent months.
- Layout: one array per variable, `<store>/<variable>/`.
  - Shape `(time, 721, 1440)`, float32.
  - **Chunks `(1, 721, 1440)`**: one chunk = one hour, whole globe, about 2 MB compressed.
  - Compression: Blosc/LZ4 (`numcodecs.Blosc().decode(...)`).
- Chunk file name: `<store>/<variable>/<t>.0.0`, where
  `t = hours since 1900-01-01 00:00 UTC` (from `time/.zattrs`).
- Grid:
  - Latitude runs 90 → −90 (721 points); longitude runs 0 → 359.75 (1440 points).
  - Note the descending latitude.
- Variable names are long CF-style names, e.g. `2m_temperature`, `total_precipitation`,
  `mean_total_precipitation_rate`, `mean_snowfall_rate`, `10m_u_component_of_wind`,
  `sea_surface_temperature`. The full list is in `<store>/.zmetadata`.
- Units are ERA5's own: temperatures in K, `mean_*_rate` in kg m⁻² s⁻¹ (×86400 = mm/day),
  `total_precipitation` in m per hour.

## Why it is fast (and why "hourly is too big" is the wrong mental model)

- **Size of the job.** A month of one variable is about 744 chunks × 2 MB ≈ 1.5 GB to *stream*, but
  nothing needs to be *stored*. Decode each hour and add it into a float64 running sum
  (721 × 1440 × 8 bytes ≈ 8 MB). Divide by the count at the end.
- **Parallel download.** Use 24 concurrent HTTPS GETs with a persistent session. That gave
  60–100 MB/s, so about 20–30 s per variable-month.
- **No bulk tooling.** Don't use `xarray.open_zarr(...).resample(time='1MS').mean()` over dask for
  this. It works, but it is much slower and memory-hungry. Raw chunk GETs plus a running sum are
  simpler and faster.
- **No spatial shortcut.** Each chunk is the whole globe, so a regional subset does not reduce the
  download. Download the global hour and crop after decoding.

## Getting the averaging right

- **Instantaneous fields** (`2m_temperature`, winds, SST, …):
  - Average all hours whose valid time is in the month: 00:00 on day 1 through 23:00 on the last
    day.
  - That is how ECMWF's "monthly averaged reanalysis" is defined.
- **Mean-rate fields** (`mean_total_precipitation_rate`, `mean_snowfall_rate`, …):
  - Each hourly value is the mean over the hour *ending* at its valid time.
  - So use valid times 01:00 on day 1 through 00:00 on day 1 of the *next* month. Those are the
    accumulation hours inside the month.
- **Accumulated fields** (`total_precipitation`, in m per hour):
  - Use the same hour window as the mean rates.
  - The **sum** is the monthly total; the mean × 24 × 1000 is mm/day.
- **Validation (do this):**
  - Build one month that also exists in an official monthly product and compare the two.
  - We built Dec 2022 from hourly data and compared it with NCAR GDEX ds633.1 monthly means
    (`https://data.gdex.ucar.edu/d633001/`, open, no key, 1979–2022).
  - Max difference in every 1° box: 0.001 K for 2 m temperature, 0.001 mm/day for precipitation.
  - Global-mean 2 m temperatures for 2023–2025 also matched Copernicus's published monthly values
    to 0.003 °C.
  - A one-hour error in the rate window shows up as about 0.1 mm/day of local precipitation
    differences, so this check catches it.

## Working script

```python
#!/usr/bin/env python3
"""Monthly means from ARCO-ERA5 hourly data.
    pip install numpy numcodecs requests
    python3 arco_monthly.py 2m_temperature 2024 1 2024 12 out_dir
Writes out_dir/<variable>_<YYYY>_<MM>.npy, each a (721, 1440) float32 monthly mean,
lat 90 -> -90, lon 0 -> 359.75."""
import sys, os, time, datetime as dt, numpy as np, requests
from concurrent.futures import ThreadPoolExecutor
from numcodecs import Blosc

STORE = 'https://storage.googleapis.com/gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3'
INSTANT = {'2m_temperature', '2m_dewpoint_temperature', 'sea_surface_temperature', 'skin_temperature',
           '10m_u_component_of_wind', '10m_v_component_of_wind', 'mean_sea_level_pressure',
           'surface_pressure', 'total_column_water_vapour', 'total_cloud_cover'}  # extend as needed
S = requests.Session()
S.mount('https://', requests.adapters.HTTPAdapter(pool_connections=32, pool_maxsize=32))
codec = Blosc()

def hidx(t):                       # chunk index = hours since 1900-01-01
    return int((t - dt.datetime(1900, 1, 1)).total_seconds() // 3600)

def fetch(var, i):
    for attempt in range(6):
        try:
            r = S.get(f'{STORE}/{var}/{i}.0.0', timeout=60)
            if r.status_code == 200:
                return np.frombuffer(codec.decode(r.content), dtype='<f4').reshape(721, 1440)
        except Exception:
            pass
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f'failed: {var} hour {i}')

def monthly_mean(var, y, m, workers=24, batch=48):
    t0 = dt.datetime(y, m, 1)
    t1 = dt.datetime(y + (m == 12), m % 12 + 1, 1)
    if var in INSTANT:             # analyses: valid 00..23 of every day in the month
        idx = range(hidx(t0), hidx(t1))
    else:                          # rates / accumulations: hours ending inside the month
        idx = range(hidx(t0) + 1, hidx(t1) + 1)
    idx = list(idx)
    acc = np.zeros((721, 1440)); n = 0
    with ThreadPoolExecutor(workers) as ex:
        for b in range(0, len(idx), batch):          # batches keep memory bounded
            for a in ex.map(lambda i: fetch(var, i), idx[b:b + batch]):
                acc += a; n += 1
    assert n == len(idx)
    return (acc / n).astype(np.float32)

if __name__ == '__main__':
    var, y0, m0, y1, m1, out = sys.argv[1], *map(int, sys.argv[2:6]), sys.argv[6]
    os.makedirs(out, exist_ok=True)
    y, m = y0, m0
    while (y, m) <= (y1, m1):
        f = f'{out}/{var}_{y}_{m:02d}.npy'
        if not os.path.exists(f):                    # re-runnable
            t = time.time(); np.save(f, monthly_mean(var, y, m))
            print(var, y, m, f'{time.time() - t:.0f}s', flush=True)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
```

Before trusting recent months, check the time origin and the end of final data:

```python
import requests, json
s = 'https://storage.googleapis.com/gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3'
print(json.loads(requests.get(s + '/time/.zattrs').text))   # units: hours since 1900-01-01
print(json.loads(requests.get(s + '/.zattrs').text))        # valid_time_stop (final), ..._era5t
```

## Gotchas we hit

- **Proxied sandboxes.** If the environment reaches the internet through a proxy, use `requests`,
  which honours `HTTPS_PROXY`. There is no need for `gsutil` or Google auth.
- **Descending latitude.** Flip it before any south-to-north gridding.
- **Coarsening.** To go from 0.25° to 1° box means, average the 5 × 5 points on and inside each box,
  with edge points at half weight (trapezoid rule) and cos(latitude) weights. Wrap longitude at the
  0/360 seam.
- **Overlap with official monthly files.** For years where an official monthly product exists
  (NCAR GDEX ds633.1, 1979–2022, open HTTPS), it is faster to download those, about 16–30 MB per
  variable-year. Keep the hourly route for months the monthly product doesn't have yet.
- **Disk.** None needed beyond the outputs: about 4 MB per variable-month at 0.25°, or far less once
  coarsened.
