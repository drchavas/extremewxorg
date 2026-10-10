"""Download ERA5 monthly means (NCAR GDEX ds633.1, 1979-2022) and coarsen to 1 deg.

    python3 fetch_era5_gdex.py COARSE_DIR 1979 2022

No account or key needed (data.gdex.ucar.edu is open). ~16-30 MB per variable-year, deleted after coarsening.
2 m temperature (128_167_2t, K) and mean total precipitation rate (235_055_mtpr, kg m-2 s-1)."""
import os, sys, subprocess, numpy as np, xarray as xr
sys.path.insert(0, os.path.dirname(__file__))
from era5_coarsen import coarsen
URL = {'t2m': 'https://data.gdex.ucar.edu/d633001/e5.moda.an.sfc/{y}/e5.moda.an.sfc.128_167_2t.ll025sc.{y}010100_{y}120100.nc',
       'mtpr': 'https://data.gdex.ucar.edu/d633001/e5.moda.fc.sfc.meanflux/{y}/e5.moda.fc.sfc.meanflux.235_055_mtpr.ll025sc.{y}010100_{y}120100.nc'}
VN = {'t2m': 'VAR_2T', 'mtpr': 'MTPR'}
OUT = sys.argv[1]; RAW = OUT
os.makedirs(OUT, exist_ok=True)
y0, y1 = int(sys.argv[2]), int(sys.argv[3])
for y in range(y0, y1 + 1):
    for v in ('t2m', 'mtpr'):
        out = f'{OUT}/rda_{v}_{y}.npy'
        if os.path.exists(out): continue
        f = f'{RAW}/{v}_{y}.nc'
        for attempt in range(4):
            r = subprocess.run(['curl', '-sf', '--retry', '3', '-o', f, URL[v].format(y=y)])
            if r.returncode == 0: break
        d = xr.open_dataset(f)
        a = d[VN[v]].values
        assert a.shape == (12, 721, 1440), a.shape
        assert float(d.latitude[0]) == 90.0
        np.save(out, coarsen(a))
        d.close(); os.remove(f)
        print(y, v, 'ok', flush=True)
