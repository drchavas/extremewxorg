"""0.25 deg -> 1 deg box means (same grid and weights as ../enso/era5_coarsen.py), NaN-aware.

Output grid: 180 x 360 boxes, row r spans [-90+r, -89+r] deg N (south -> north),
column c spans [c, c+1] deg E. Trapezoid weights over the 5 x 5 points on and inside
each box's edges, cos(lat) weighted. NaN points (e.g. SST/sea ice over land) are left out;
a box is NaN when less than `minfrac` of its weight is valid."""
import numpy as np
LAT = np.linspace(-90, 90, 721)
W5 = np.array([.5, 1, 1, 1, .5])
_ilat = (np.arange(180)[:, None] * 4 + np.arange(5)[None, :])
_wlat = W5[None, :] * np.cos(np.deg2rad(LAT[_ilat]))
_wlat = np.where(_wlat < 0, 0, _wlat)
_wlat /= _wlat.sum(1, keepdims=True)
_ilon = (np.arange(360)[:, None] * 4 + np.arange(5)[None, :]) % 1440
_wlon = np.tile(W5 / W5.sum(), (360, 1))

def _box(a):
    b = np.einsum('...rkx,rk->...rx', a[..., _ilat, :], _wlat)
    return np.einsum('...rck,ck->...rc', b[..., :, _ilon], _wlon)

def coarsen(a, lat_descending=True, minfrac=0.25):
    a = np.asarray(a, dtype=np.float64)
    if lat_descending:
        a = a[..., ::-1, :]
    ok = np.isfinite(a)
    if ok.all():
        return _box(a).astype(np.float32)
    w = _box(ok.astype(np.float64))
    s = _box(np.where(ok, a, 0.0))
    with np.errstate(invalid='ignore', divide='ignore'):
        out = s / w
    out[w < minfrac] = np.nan
    return out.astype(np.float32)
