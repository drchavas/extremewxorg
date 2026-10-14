"""Monthly-mean bulk shear for the months after the WeatherBench2 copy ends (Jan 2023 on),
from 6-hourly ERA5 on the Copernicus CDS, interpolated by the CDS to the same 1.5 deg grid.

    python3 fetch_cds_shear.py OUT_DIR YEAR[,YEAR...]
    python3 fetch_cds_shear.py OUT_DIR check        # Dec 2022 only -> check_<s06|s200>_202212.npy

Same definitions as fetch_wb2_shear.py (mean over 00/06/12/18 UTC of |V500-V10m| and |V200-V850|),
but every day of the month. One CDS request per dataset and two months (a whole year exceeds the CDS cost limit;
the CDS also caps queued requests, so requests go one at a time). Writes OUT_DIR/<s06|s200>_<year>.npy (12, 121, 240),
lat -90..90, lon 0..358.5. The check compares with WB2's value for Dec 2022 (conservative 1.5 deg
regridding there, CDS bilinear here)."""
import os, sys, time, tempfile, numpy as np, xarray as xr, cdsapi
C = cdsapi.Client(quiet=True, progress=False)
def get(ds, req, f):
    for a in range(60):
        try:
            return C.retrieve(ds, req, f)
        except Exception as e:
            print('retry', ds, req['year'], repr(e)[-120:].replace(chr(10), ' '), flush=True); time.sleep(60)
    raise RuntimeError('CDS kept refusing')
def period(y, months, out):
    base = {'product_type': ['reanalysis'], 'year': [str(y)], 'month': [f'{m:02d}' for m in months],
            'day': [f'{d:02d}' for d in range(1, 32)], 'time': ['00:00', '06:00', '12:00', '18:00'],
            'grid': ['1.5', '1.5'], 'data_format': 'netcdf', 'download_format': 'unarchived'}
    fp = tempfile.mktemp(suffix='.nc', dir=out); fs = tempfile.mktemp(suffix='.nc', dir=out)
    try:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(2) as ex:      # the two datasets queue separately at the CDS
            jobs = [ex.submit(get, 'reanalysis-era5-pressure-levels', dict(base, variable=['u_component_of_wind', 'v_component_of_wind'],
                                                                           pressure_level=['200', '500', '850']), fp),
                    ex.submit(get, 'reanalysis-era5-single-levels', dict(base, variable=['10m_u_component_of_wind', '10m_v_component_of_wind']), fs)]
            for j in jobs: j.result()
        p = xr.open_dataset(fp); s = xr.open_dataset(fs)
        assert float(p.latitude[0]) == 90 and p.u.shape[-2:] == (121, 240)
        lv = [int(l) for l in p.pressure_level.values]
        mo = p.valid_time.values.astype('datetime64[M]').astype(int) % 12 + 1
        assert (s.valid_time.values == p.valid_time.values).all()
        res = {}
        for m in months:
            idx = np.where(mo == m)[0]
            u = p.u.isel(valid_time=idx).values; v = p.v.isel(valid_time=idx).values
            u10 = s.u10.isel(valid_time=idx).values; v10 = s.v10.isel(valid_time=idx).values
            i5, i2, i8 = lv.index(500), lv.index(200), lv.index(850)
            s06 = np.hypot(u[:, i5] - u10, v[:, i5] - v10).mean(0)[::-1]
            s200 = np.hypot(u[:, i2] - u[:, i8], v[:, i2] - v[:, i8]).mean(0)[::-1]
            res[m] = (s06, s200)
            print(y, m, len(idx), 'times', flush=True)
        p.close(); s.close()
        return res
    finally:
        for f in (fp, fs):
            if os.path.exists(f): os.remove(f)
if __name__ == '__main__':
    out = sys.argv[1]; os.makedirs(out, exist_ok=True)
    if sys.argv[2] == 'check':
        r = period(2022, [12], out)[12]
        np.save(f'{out}/check_s06_202212.npy', r[0]); np.save(f'{out}/check_s200_202212.npy', r[1]); sys.exit()
    for y in map(int, sys.argv[2].split(',')):
        if os.path.exists(f'{out}/s200_{y}.npy'): continue
        r = {}
        for q in ([1, 2], [3, 4], [5, 6], [7, 8], [9, 10], [11, 12]):   # a whole year exceeds the CDS cost limit
            r.update(period(y, q, out))
        np.save(f'{out}/s06_{y}.npy', np.stack([r[m][0] for m in range(1, 13)]).astype(np.float32))
        np.save(f'{out}/s200_{y}.npy', np.stack([r[m][1] for m in range(1, 13)]).astype(np.float32))
