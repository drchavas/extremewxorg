"""ERA5 monthly means from the Copernicus CDS (needs ~/.cdsapirc) -> 1 deg box means.
Fills the years the open NCAR GDEX copy lacks (before 1979, after 2022); the two sources
are the same ECMWF product (checked: 1990 t2m, mtpr, mer, mtnlwrf, u250, w500 identical after coarsening).

    python3 fetch_era5_cds.py SFC_DIR PL_DIR YEARS [var,...]     YEARS like 1961-1978,2023-2025

One request per dataset and up to BATCH years, carrying every variable still missing (the CDS
caps queued requests per dataset, so few large requests beat many small ones). Variables are
identified in the returned netCDF by their GRIB parameter id, so the CDS's renaming of the
netCDF variables (avg_tprate, ...) does not matter. Writes <var>_<year>.npy (12, 180, 360)
float32, Jan..Dec, rows S->N, exactly as fetch_era5_sfc.py / fetch_era5_pl.py do."""
import os, sys, glob, time, zipfile, tempfile, shutil, threading, numpy as np, xarray as xr, cdsapi
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from era5_coarsen import coarsen
# key: (CDS name, GRIB paramId)
SFC = {'t2m': ('2m_temperature', 167), 'd2m': ('2m_dewpoint_temperature', 168), 'sst': ('sea_surface_temperature', 34),
       'ci': ('sea_ice_cover', 31), 'msl': ('mean_sea_level_pressure', 151), 'tcc': ('total_cloud_cover', 164),
       'tcwv': ('total_column_water_vapour', 137), 'cape': ('convective_available_potential_energy', 59),
       'u10': ('10m_u_component_of_wind', 165), 'v10': ('10m_v_component_of_wind', 166), 'sd': ('snow_depth', 141),
       'mtpr': ('mean_total_precipitation_rate', 235055), 'msr': ('mean_snowfall_rate', 235031),
       'mcpr': ('mean_convective_precipitation_rate', 235030), 'mer': ('mean_evaporation_rate', 235043),
       'mtnlwrf': ('mean_top_net_long_wave_radiation_flux', 235040), 'mtnswrf': ('mean_top_net_short_wave_radiation_flux', 235039),
       'mtdwswrf': ('mean_top_downward_short_wave_radiation_flux', 235053), 'mslhf': ('mean_surface_latent_heat_flux', 235034),
       'msshf': ('mean_surface_sensible_heat_flux', 235033)}
PL = {'u': ('u_component_of_wind', 131, [850, 500, 250, 200]), 'v': ('v_component_of_wind', 132, [850, 500, 250, 200]),
      't': ('temperature', 130, [850]), 'q': ('specific_humidity', 133, [850]),
      'z': ('geopotential', 129, [500, 200]), 'w': ('vertical_velocity', 135, [500])}
LEVELS = ['200', '250', '500', '850']
C = cdsapi.Client(quiet=True, progress=False); LOCK = threading.Lock()

def years_of(s):
    out = []
    for part in s.split(','):
        a, _, b = part.partition('-'); out += list(range(int(a), int(b or a) + 1))
    return out

def retrieve(ds, req, f):
    for a in range(60):          # the CDS limits queued requests per dataset: back off and retry
        try:
            return C.retrieve(ds, req, f)
        except Exception as e:
            print('retry', ds[-25:], req['year'], repr(e)[-80:].replace(chr(10), ' '), flush=True)
            time.sleep(60)
    raise RuntimeError('CDS kept refusing')

def open_all(path, work):
    """the CDS sends one netCDF, or a zip of several when analysis and forecast fields are mixed"""
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z: z.extractall(work)
        return sorted(glob.glob(f'{work}/*.nc'))
    return [path]

def one(job):
    kind, ys, vs, sfc, pl = job
    work = tempfile.mkdtemp(dir=sfc if kind == 'sfc' else pl); tmp = f'{work}/req.dat'
    req = {'product_type': ['monthly_averaged_reanalysis'], 'year': [str(y) for y in ys],
           'month': [f'{m:02d}' for m in range(1, 13)], 'time': ['00:00'],
           'data_format': 'netcdf', 'download_format': 'unarchived'}
    try:
        if kind == 'sfc':
            retrieve('reanalysis-era5-single-levels-monthly-means', dict(req, variable=[SFC[v][0] for v in vs]), tmp)
            pid2key = {SFC[v][1]: v for v in vs}
        else:
            retrieve('reanalysis-era5-pressure-levels-monthly-means',
                     dict(req, variable=[PL[v][0] for v in vs], pressure_level=LEVELS), tmp)
            pid2key = {PL[v][1]: v for v in vs}
        got = set()
        for fn in open_all(tmp, work):
            with LOCK:
                ds = xr.open_dataset(fn)
                t = ds['valid_time'].values.astype('datetime64[M]').astype(int)
                yr, mo = t // 12 + 1970, t % 12
                assert abs(float(ds.latitude[0]) - 90) < 1e-6 and ds.longitude.size == 1440
                lv = [int(l) for l in ds['pressure_level'].values] if kind == 'pl' else None
                names = [n for n in ds.data_vars if ds[n].ndim >= 3]
            for name in names:
                pid = int(ds[name].attrs.get('GRIB_paramId', -1))
                if pid not in pid2key: print('unexpected variable', name, pid, flush=True); continue
                k = pid2key[pid]
                for y in ys:
                    idx = np.where(yr == y)[0]
                    if len(idx) == 0: continue
                    assert mo[idx].tolist() == list(range(12)), (k, y, mo[idx])
                    with LOCK:
                        x = ds[name].isel(valid_time=idx)
                        if kind == 'sfc': out = {f'{sfc}/{k}_{y}.npy': x.values}
                        else: out = {f'{pl}/{k}{lev}_{y}.npy': x.isel(pressure_level=lv.index(lev)).values for lev in PL[k][2]}
                    for d, a in out.items():
                        a = np.asarray(a, dtype=np.float64); assert a.shape == (12, 721, 1440), (d, a.shape)
                        np.save(d, coarsen(a))
                got.add(k)
            ds.close()
        missing = set(vs) - got
        print(kind, ys, 'ok', sorted(got), ('MISSING ' + str(sorted(missing))) if missing else '', flush=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)

def todo(kind, y, sfc, pl, only):
    if kind == 'sfc':
        return [v for v in SFC if (not only or v in only) and not os.path.exists(f'{sfc}/{v}_{y}.npy')]
    return [v for v in PL if (not only or v in only) and not all(os.path.exists(f'{pl}/{v}{l}_{y}.npy') for l in PL[v][2])]

if __name__ == '__main__':
    sfc, pl, ys = sys.argv[1], sys.argv[2], years_of(sys.argv[3])
    only = sys.argv[4].split(',') if len(sys.argv) > 4 else None
    # group consecutive-in-list years that need the same variables into requests of up to BATCH years
    B = int(os.environ.get('BATCH', 6))
    jobs = []
    for kind in ('sfc', 'pl'):
        cur = None
        for y in ys:
            vs = todo(kind, y, sfc, pl, only)
            if not vs: continue
            if cur and cur[2] == vs and len(cur[1]) < B: cur[1].append(y)
            else:
                cur = (kind, [y], vs, sfc, pl); jobs.append(cur)
    print(len(jobs), 'requests', flush=True)
    with ThreadPoolExecutor(int(os.environ.get('NTHREADS', 3))) as ex:
        list(ex.map(one, jobs))
