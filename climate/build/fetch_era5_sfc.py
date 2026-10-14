"""ERA5 monthly means (NCAR GDEX ds633.1, open, no key) -> 1 deg box means, one file per var-year.

    python3 fetch_era5_sfc.py COARSE_DIR Y0 Y1 [var,var,...]

Writes COARSE_DIR/<var>_<year>.npy, float32 (12, 180, 360), months Jan..Dec, rows S->N.
The 0.25 deg netCDF (~2-30 MB) is streamed to a temp file and deleted after coarsening."""
import os, sys, subprocess, tempfile, numpy as np, netCDF4
from concurrent.futures import ThreadPoolExecutor
import threading
LOCK = threading.Lock()   # netCDF4/HDF5 is not thread-safe
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from era5_coarsen import coarsen
B = 'https://data.gdex.ucar.edu/d633001'
# key: (stream, GRIB code+short name)
SRC = {
 't2m': ('e5.moda.an.sfc', '128_167_2t'), 'd2m': ('e5.moda.an.sfc', '128_168_2d'),
 'sst': ('e5.moda.an.sfc', '128_034_sstk'), 'ci': ('e5.moda.an.sfc', '128_031_ci'),
 'msl': ('e5.moda.an.sfc', '128_151_msl'), 'tcc': ('e5.moda.an.sfc', '128_164_tcc'),
 'tcwv': ('e5.moda.an.sfc', '128_137_tcwv'), 'cape': ('e5.moda.an.sfc', '128_059_cape'),
 'u10': ('e5.moda.an.sfc', '128_165_10u'), 'v10': ('e5.moda.an.sfc', '128_166_10v'),
 'sd': ('e5.moda.an.sfc', '128_141_sd'),
 'mtpr': ('e5.moda.fc.sfc.meanflux', '235_055_mtpr'), 'msr': ('e5.moda.fc.sfc.meanflux', '235_031_msr'),
 'mcpr': ('e5.moda.fc.sfc.meanflux', '235_030_mcpr'), 'mtnlwrf': ('e5.moda.fc.sfc.meanflux', '235_040_mtnlwrf'),
 'mtnswrf': ('e5.moda.fc.sfc.meanflux', '235_039_mtnswrf'), 'mtdwswrf': ('e5.moda.fc.sfc.meanflux', '235_053_mtdwswrf'),
 'mer': ('e5.moda.fc.sfc.meanflux', '235_043_mer'), 'mslhf': ('e5.moda.fc.sfc.meanflux', '235_034_mslhf'),
 'msshf': ('e5.moda.fc.sfc.meanflux', '235_033_msshf'),
}
def url(v, y):
    s, c = SRC[v]
    return f'{B}/{s}/{y}/{s}.{c}.ll025sc.{y}010100_{y}120100.nc'

def one(job):
    v, y, out = job
    dst = f'{out}/{v}_{y}.npy'
    if os.path.exists(dst): return
    fd, tmp = tempfile.mkstemp(suffix='.nc', dir=out); os.close(fd)
    try:
        for a in range(5):
            r = subprocess.run(['curl', '-sf', '--retry', '3', '-m', '600', '-o', tmp, url(v, y)])
            if r.returncode == 0: break
        else:
            print('FAILED', v, y, url(v, y), flush=True); return
        with LOCK, netCDF4.Dataset(tmp) as d:
            names = [k for k, x in d.variables.items() if x.ndim == 3]
            assert len(names) == 1, names
            x = d.variables[names[0]]; x.set_auto_maskandscale(True)
            a = np.ma.filled(x[:].astype(np.float64), np.nan)
            assert a.shape == (12, 721, 1440), a.shape
            assert abs(float(d.variables['latitude'][0]) - 90) < 1e-6
        np.save(dst, coarsen(a))
        print(v, y, 'ok', flush=True)
    finally:
        if os.path.exists(tmp): os.remove(tmp)

if __name__ == '__main__':
    out, y0, y1 = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    vs = sys.argv[4].split(',') if len(sys.argv) > 4 else list(SRC)
    os.makedirs(out, exist_ok=True)
    jobs = [(v, y, out) for y in range(y0, y1 + 1) for v in vs]
    with ThreadPoolExecutor(int(os.environ.get('NTHREADS', 3))) as ex:
        list(ex.map(one, jobs))
