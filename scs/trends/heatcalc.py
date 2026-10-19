"""
heatcalc.py -- heat index and ERA5 reading for the extremewx.org heat hazards.

Heat index follows the NWS procedure as published by NOAA/WPC
(https://www.wpc.ncep.noaa.gov/html/heatindex_equation.shtml):
  * simple formula HI = 0.5 [T + 61 + 1.2 (T - 68) + 0.094 RH];
  * if the average of that and T is >= 80 F, use the Rothfusz regression,
    with the low-RH (RH < 13 %, 80 <= T <= 112) and high-RH
    (RH > 85 %, 80 <= T <= 87) adjustments.
Relative humidity comes from 2 m T and 2 m dewpoint with the Magnus form
e_s = 6.112 exp(17.67 T / (T + 243.5)) hPa, the same one the Indiana card used.
Written from the NWS description, independently of the Indiana card's code, so
that reproducing that card is a real check of both.
"""
import numpy as np
import fsspec
import h5py

BASE = "https://nsf-ncar-era5.s3.amazonaws.com/e5.oper.an.sfc"
VARS = {"t": ("128_167_2t", "VAR_2T"), "d": ("128_168_2d", "VAR_2D")}


def month_url(var, y, m):
    import calendar
    code = VARS[var][0]
    last = calendar.monthrange(y, m)[1]
    return (f"{BASE}/{y}{m:02d}/e5.oper.an.sfc.{code}.ll025sc."
            f"{y}{m:02d}0100_{y}{m:02d}{last}23.nc")


def read_month(var, y, m, i0, i1, j0, j1, h0=None, h1=None, tries=6):
    """Hourly field [hour, lat, lon] for rows i0:i1, cols j0:j1 of the global
    0.25 deg grid (lat 90 -> -90, lon 0 -> 359.75). Kelvin, float32.
    Retries dropped connections; a month that does not exist raises
    FileNotFoundError at once."""
    import time
    url = month_url(var, y, m)
    for k in range(tries):
        try:
            with fsspec.open(url, "rb", block_size=2 ** 22,
                             client_kwargs={"trust_env": True}) as f:
                with h5py.File(f, "r") as h:
                    return h[VARS[var][1]][slice(h0, h1), i0:i1, j0:j1]
        except FileNotFoundError:
            raise
        except Exception as e:
            if k == tries - 1:
                raise
            time.sleep(10 * (k + 1))


def rh_pct(t_c, td_c):
    es = 6.112 * np.exp(17.67 * t_c / (t_c + 243.5))
    e = 6.112 * np.exp(17.67 * td_c / (td_c + 243.5))
    return np.clip(100.0 * e / es, 0.0, 100.0)


def heat_index_f(t_f, rh):
    t_f = np.asarray(t_f, dtype=np.float64)
    rh = np.asarray(rh, dtype=np.float64)
    simple = 0.5 * (t_f + 61.0 + (t_f - 68.0) * 1.2 + rh * 0.094)
    use_full = 0.5 * (simple + t_f) >= 80.0
    T, R = t_f, rh
    full = (-42.379 + 2.04901523 * T + 10.14333127 * R - 0.22475541 * T * R
            - 6.83783e-3 * T * T - 5.481717e-2 * R * R + 1.22874e-3 * T * T * R
            + 8.5282e-4 * T * R * R - 1.99e-6 * T * T * R * R)
    lo = (R < 13.0) & (T >= 80.0) & (T <= 112.0)
    full = np.where(lo, full - ((13.0 - R) / 4.0) *
                    np.sqrt(np.clip((17.0 - np.abs(T - 95.0)) / 17.0, 0, None)), full)
    hi = (R > 85.0) & (T >= 80.0) & (T <= 87.0)
    full = np.where(hi, full + ((R - 85.0) / 10.0) * ((87.0 - T) / 5.0), full)
    return np.where(use_full, full, simple)


def k_to_f(k):
    return (k - 273.15) * 9.0 / 5.0 + 32.0
