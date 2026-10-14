"""ERA5 monthly-mean pressure-level fields via the NCAR GDEX THREDDS NetCDF Subset Service
(server-side subsetting of ds633.1 e5.moda.an.pl, so only the levels we need are sent).

    python3 fetch_era5_pl.py COARSE_DIR Y0 Y1

Writes COARSE_DIR/<var><level>_<year>.npy, float32 (12, 180, 360), Jan..Dec, rows S->N
(same 1 deg box grid as era5_coarsen.py). One request per (month, level), ~4 MB per field."""
import os, sys, subprocess, tempfile, threading, datetime as dt, numpy as np, netCDF4
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from era5_coarsen import coarsen
NCSS = 'https://thredds.rda.ucar.edu/thredds/ncss/grid/aggregations/g/d633001/1/TP'
NAME = {'u': 'U_component_of_wind_isobaric_Average', 'v': 'V_component_of_wind_isobaric_Average',
        'z': 'Geopotential_isobaric_Average', 'w': 'Vertical_velocity_isobaric_Average',
        't': 'Temperature_isobaric_Average', 'q': 'Specific_humidity_isobaric_Average'}
LEVELS = {850: 'uvtq', 500: 'uvzw', 250: 'uv', 200: 'uvz'}
LOCK = threading.Lock()

def one(job):
    out, y, m, lev, vs = job
    parts = f'{out}/part_{y}_{m:02d}_{lev}.npz'
    if os.path.exists(parts): return
    q = '&'.join(f'var={NAME[v]}' for v in vs)
    u = f'{NCSS}?{q}&vertCoord={lev}&time={y}-{m:02d}-15T00:00:00Z&accept=netcdf3'
    fd, tmp = tempfile.mkstemp(suffix='.nc', dir=out); os.close(fd)
    try:
        for a in range(8):
            r = subprocess.run(['curl', '-sf', '--retry', '3', '-m', '300', '-o', tmp, u])
            if r.returncode == 0 and os.path.getsize(tmp) > 1e6:
                with open(tmp, 'rb') as fh:
                    if fh.read(3) == b'CDF': break      # a netCDF-3 file, not an error page
            import time; time.sleep(5 * (a + 1))
        else:
            print('FAILED', y, m, lev, flush=True); return
        res = {}
        with LOCK, netCDF4.Dataset(tmp) as d:
            t = netCDF4.num2date(d.variables['time'][:], d.variables['time'].units)[0]
            assert (t.year, t.month) == (y, m), (t, y, m)
            assert abs(float(d.variables['latitude'][0]) - 90) < 1e-3
            assert float(d.variables['isobaric'][0]) == lev
            for v in vs:
                x = d.variables[NAME[v]][:]
                res[v] = np.ma.filled(x.astype(np.float64), np.nan).reshape(721, 1440)
        np.savez(parts, **{v: coarsen(a) for v, a in res.items()})
    finally:
        if os.path.exists(tmp): os.remove(tmp)

def assemble(out, y):
    for lev, vs in LEVELS.items():
        for v in vs:
            dst = f'{out}/{v}{lev}_{y}.npy'
            if os.path.exists(dst): continue
            fs = [f'{out}/part_{y}_{m:02d}_{lev}.npz' for m in range(1, 13)]
            if not all(os.path.exists(f) for f in fs): print('incomplete', y, lev); return
            np.save(dst, np.stack([np.load(f)[v] for f in fs]))
    for lev in LEVELS:
        for m in range(1, 13): os.remove(f'{out}/part_{y}_{m:02d}_{lev}.npz')
    print(y, 'assembled', flush=True)

if __name__ == '__main__':
    out, y0, y1 = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    os.makedirs(out, exist_ok=True)
    for y in range(y0, y1 + 1):
        if all(os.path.exists(f'{out}/{v}{lev}_{y}.npy') for lev, vs in LEVELS.items() for v in vs): continue
        jobs = [(out, y, m, lev, vs) for m in range(1, 13) for lev, vs in LEVELS.items()]
        with ThreadPoolExecutor(int(os.environ.get('NTHREADS', 4))) as ex:
            list(ex.map(one, jobs))
        assemble(out, y)
