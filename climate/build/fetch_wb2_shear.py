"""Monthly-mean bulk wind shear from 6-hourly ERA5 (WeatherBench2 copy, 1.5 deg conservative,
gs://weatherbench2/datasets/era5/1959-2023_01_10-6h-240x121_equiangular_with_poles_conservative.zarr).

    python3 fetch_wb2_shear.py OUT_DIR Y0 Y1 [STRIDE]

Shear is computed at every 6-hourly time *before* averaging (mean of |dV|, not |dV| of the mean
winds, which would be much smaller). Two layers:
  s06  = |V(500 hPa) - V(10 m)|   ~ 0-6 km deep-layer shear (severe storms)
  s200 = |V(200 hPa) - V(850 hPa)|   tropical-cyclone vertical wind shear
Each zarr chunk holds 8 consecutive 6-hourly times (2 days). To keep the download
manageable (~10 MB per chunk per wind component) only every STRIDE-th chunk is read
(default 4: 2 days in every 8; the served climatology used STRIDE=2: 2 days in every 4, ~60 samples per month-year).
Writes OUT_DIR/<s06|s200>_<year>.npy  float32 (12, 121, 240): lat -90..90 (1.5 deg), lon 0..358.5."""
import os, sys, time, datetime as dt, numpy as np, requests
from numcodecs import Blosc
from concurrent.futures import ThreadPoolExecutor
Z = 'https://storage.googleapis.com/weatherbench2/datasets/era5/1959-2023_01_10-6h-240x121_equiangular_with_poles_conservative.zarr'
LEV = [50, 100, 150, 200, 250, 300, 400, 500, 600, 700, 850, 925, 1000]
S = requests.Session(); S.mount('https://', requests.adapters.HTTPAdapter(pool_connections=16, pool_maxsize=16))
C = Blosc()
T0 = dt.datetime(1959, 1, 1)

def get(path, shape):
    for a in range(6):
        try:
            r = S.get(f'{Z}/{path}', timeout=120)
            if r.status_code == 200:
                return np.frombuffer(C.decode(r.content), '<f4').reshape(shape)
        except Exception:
            pass
        time.sleep(2 * (a + 1))
    raise RuntimeError(path)

def chunk(k):
    u = get(f'u_component_of_wind/{k}.0.0.0', (8, 13, 240, 121))
    v = get(f'v_component_of_wind/{k}.0.0.0', (8, 13, 240, 121))
    u10 = get(f'10m_u_component_of_wind/{k}.0.0', (8, 240, 121))
    v10 = get(f'10m_v_component_of_wind/{k}.0.0', (8, 240, 121))
    i5, i2, i8 = LEV.index(500), LEV.index(200), LEV.index(850)
    s06 = np.hypot(u[:, i5] - u10, v[:, i5] - v10)
    s200 = np.hypot(u[:, i2] - u[:, i8], v[:, i2] - v[:, i8])
    return k, s06, s200

if __name__ == '__main__':
    out, y0, y1 = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    stride = int(sys.argv[4]) if len(sys.argv) > 4 else 4
    os.makedirs(out, exist_ok=True)
    for y in range(y0, y1 + 1):
        if os.path.exists(f'{out}/s200_{y}.npy'): continue
        i0 = int((dt.datetime(y, 1, 1) - T0).total_seconds() // 21600)
        i1 = int((dt.datetime(y + 1, 1, 1) - T0).total_seconds() // 21600)
        ks = [k for k in range(i0 // 8, (i1 - 1) // 8 + 1) if k % stride == 0]
        acc = {n: np.zeros((12, 240, 121)) for n in ('s06', 's200')}; cnt = np.zeros(12)
        with ThreadPoolExecutor(int(os.environ.get('NTHREADS', 6))) as ex:
            for k, s06, s200 in ex.map(chunk, ks):
                for j in range(8):
                    i = 8 * k + j
                    if not (i0 <= i < i1): continue
                    m = (T0 + dt.timedelta(hours=6 * i)).month - 1
                    acc['s06'][m] += s06[j]; acc['s200'][m] += s200[j]; cnt[m] += 1
        assert (cnt > 0).all(), cnt
        for n in acc:
            a = acc[n] / cnt[:, None, None]                 # (12, lon, lat)
            np.save(f'{out}/{n}_{y}.npy', np.transpose(a, (0, 2, 1)).astype(np.float32))
        print(y, 'ok samples/month', cnt.astype(int).tolist(), flush=True)
