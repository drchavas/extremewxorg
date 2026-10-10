"""Shared 0.25 deg -> 1 deg box-mean coarsening for ERA5 global fields.

Input grid: 721 x 1440, latitude 90 -> -90 (or ascending), longitude 0 -> 359.75.
Output grid: 180 x 360 boxes, row r spans [-90+r, -89+r] deg N (south -> north),
column c spans [c, c+1] deg E (0 -> 360). Each box mean is a trapezoid-rule average
over the 5 x 5 grid points on and inside its edges (edge points half weight, corner
points quarter weight), cos(lat) area-weighted in latitude. Edge points are shared
with the neighbouring box, so the boxes tile the sphere exactly.
"""
import numpy as np

LAT = np.linspace(-90, 90, 721)          # ascending
W5 = np.array([.5, 1, 1, 1, .5])

# latitude weights: (180, 5) incl. cos(lat)
_ilat = (np.arange(180)[:, None] * 4 + np.arange(5)[None, :])
_wlat = W5[None, :] * np.cos(np.deg2rad(LAT[_ilat]))
_wlat = np.where(_wlat < 0, 0, _wlat)
_wlat /= _wlat.sum(1, keepdims=True)
_ilon = (np.arange(360)[:, None] * 4 + np.arange(5)[None, :]) % 1440
_wlon = np.tile(W5 / W5.sum(), (360, 1))

def coarsen(a, lat_descending=True):
    """a: (..., 721, 1440) -> (..., 180, 360) float32"""
    a = np.asarray(a, dtype=np.float64)
    if lat_descending:
        a = a[..., ::-1, :]
    # latitude
    b = np.einsum('...rkx,rk->...rx', a[..., _ilat, :], _wlat)
    # longitude
    c = np.einsum('...rck,ck->...rc', b[..., :, _ilon], _wlon)
    return c.astype(np.float32)
