# EarthVis — `climate/earthvis.html`

> **How to cite.** Chavas, D. R., 2026: extremewx.org: Climatologies and trends of weather and
> climate extremes — data and code. Zenodo, https://doi.org/10.5281/zenodo.23839256 (concept DOI,
> always the latest version). To pin exact numbers cite the version DOI; v2026.10 is
> https://doi.org/10.5281/zenodo.23839257.

**EarthVis: Climate and Extremes Through the Year.** Built 2026-10-14. An interactive, animated
successor to the Purdue page `earthvis.html` (Climate Reanalyzer GIFs). It is a simple, quick way to
see **present-day climate**, the 1996–2025 average, and is meant as a teaching tool for students
and experts. Other periods were built and then dropped at Dan's request ("keep it simple"); the
data layout leaves room to add them back (see Rebuilding).

One map, one color bar and a time bar. Three panels sit underneath: the seasonal cycle at a
clicked place, the zonal mean, and a month × latitude Hovmöller of the zonal
mean. A side card says what to look for in each field.

## What it shows

- **Show:** Months (animated; steps month to month, see Method notes), Season (four buttons in the bar
  above the map), Annual, and under Advanced Range (largest monthly mean minus smallest) and Peak month
  (cyclic month palette). Outside Months the slider and Play are hidden, so a screenshot can't be read as one month.
- **Relative to:** nothing, the annual mean (seasonal anomaly) or the zonal mean (east–west
  departure). The zonal option is for global grids only.
- **Period:** 1996–2025 (the most recent 30 years). The incomplete worldwide tornado field uses 1992–2021.
- **Map:** Equal Earth, latitude–longitude, a draggable globe, and regional conic/azimuthal views
  (North America, CONUS, Europe, Asia, Africa, South America, Australia, Arctic, Antarctic).
  Drag pans the map or spins the globe; the wheel and the +/− buttons zoom.
- **Layout (2026-10-14, after the ENSO grid page):** a top bar with Variable, Show (Months/Season/Annual), Map and
  Reload default (Export sits in the bar above the map), plus a "Try these" tour row. Below it are the time bar and one map. Everything else is collapsed in
  **Advanced settings**: Range/Peak month, Relative to, units, wind, overlays, speed, theme and copy link. Under the map are
  "What to look for" and the clicked place's seasonal cycle. The zonal-mean and month × latitude panels, the reading guide
  and Methods are collapsed.
- **Wind:** drawn by default as **static arrows** (length = speed, full length at 10/15/25/40 m/s for 10 m/850/500/250 hPa,
  with a key in the map's corner) at each field's default level. The arrows are part of the map, so PNG/GIF/MP4 exports
  include them. "Moving streaks" (particles, screen only) is an option under Advanced. The URL hash `ws=streaks` sets it.
- **Export:** MP4 (WebCodecs H.264 + `lib/mp4-muxer.js`; VP9 if the browser has no H.264
  encoder; WebM through MediaRecorder if it has no WebCodecs), animated GIF (`lib/gifenc.esm.js`,
  one palette for the whole loop) or PNG. Frames are drawn off-screen at 720p, 1080p or square
  sizes by a second `MapView`, with the same projection and zoom as the screen, plus a title,
  color bar, month label and credit.
- The URL hash keeps the whole view, so **Copy link** reproduces it.

## Fields

| Group | Fields | Source |
|---|---|---|
| Temperature | 2 m T, SST, T850, sea ice, snow depth | ERA5 monthly means, 1° |
| Water | precipitation, convective share, snowfall, P − E, TCWV, q850, cloud cover | ERA5 |
| Energy | TOA insolation, absorbed SW, planetary albedo, OLR, net TOA, latent and sensible heat flux | ERA5 |
| Circulation | MSLP, wind at 10 m / 850 / 500 / 250 hPa, Z500, ω500 (hPa/day) | ERA5 |
| Severe ingredients | CAPE, 500 hPa − 10 m bulk shear, 2 m dewpoint | ERA5 (shear from 6-hourly winds) |
| Tropical cyclones | 200 − 850 hPa shear; frequency (TS+/Cat1+/Cat3+), ACE, genesis, **within 500 km** | ERA5; IBTrACS (`data/rad_tc*.bin.gz`) |
| Extratropical cyclones | frequency within 500 km: ETCs / deep ETCs (< 990 hPa) / all closed lows | Chavas-lab ERA5 tracks, **draft** (`data/rad_etc.bin.gz`) |
| U.S. severe | hail, tornado, thunderstorm wind (with thresholds) **within 80 km**; derecho **within 100 km** | Storm Events (`data/rad_{hail,tornado,wind,derechoday}.bin.gz`) |
| Tornadoes worldwide | tornado days within 80 km, any / (E)F1+ / 2+ / 3+, **own period 1992–2021** (the data end in 2021) | The Tornado Archive (Maas et al. 2024, BAMS), `data/rad_tatorn.bin.gz` |

**Event maps count days within a radius (2026-11-13, Dan's choice).** For every grid point: the mean number of days
per year, by calendar month, with at least one event within R km (TC/ETC 500 km, Storm Events and the Tornado Archive
80 km, derechos 100 km; ACE sums Vmax² of positions within R, genesis counts storms). This replaced counts per 5° / 2°
latitude–longitude box, which depend on box area (a 5° box at 60° is half the area of one at the equator). Dividing by
area was rejected because it loses the plain meaning ("about 5 days a year here"); equal-area cells were the other
option. Values add up over months, so seasons and years are sums as before.

The event files are built by `build/build_radius_counts.py` from the raw events the other pages use (IBTrACS CSV,
`../scs/trends/data/events_*_pts.json.gz` + `events_*.json.gz`, `derecho.json.gz`, the Tornado Archive file, the ETC
track CSVs). The page no longer reads `../enso/data/tc_month.json.gz`, `../scs/trends/data/grid_*.json.gz` or
`data/ta_tornado.json.gz`; **rebuild the `rad_*` files when those sources are updated.** Basemaps still come from
the other pages: `../enso/geo/countries-110m.json`, `../enso/geo/admin1-10m.json.gz` (place
names) and `../scs/trends/geo/states.topo.json.gz`.

## Data files

`data/era5_<var>_p9625.bin.gz` (one period, 1996–2025; 32 variable files, about 16.5 MB). Each is a gzip of
Int16 LE `[12 months][180 rows S→N][360 cols from 0°E]` on 1° boxes (row 0 = 90–89°S).

- Each row is **delta-coded along longitude mod 2^16**: decode it with a running sum mod 65536.
  This is exact and roughly halves the gzip size.
- value = q·scale + offset. q = −32768 means missing (SST and sea ice over land).
- Scales and offsets are in `data/index.json`, which also records min, max and global mean per
  period as checks.
- Units are already display-ready: °C, hPa, mm/day, W/m², % and so on.

Derived fields (wind speed, albedo, OLR, P − E, convective share, ω in hPa/day, Z in dam) are
computed in the page from those variables.

`data/rad_<field>.bin.gz` (9 files, about 2.5 MB; `etc` alone 1.2 MB) are gzip Int16 LE
`[threshold][12 months][nlat rows S→N][nlon]`, delta-coded along longitude like the ERA5 files; value = q·scale;
q = −32768 is outside the domain. Grids, scales, thresholds, radius and years are in `data/rad_index.json`:
global 1° (`g1`, the ERA5 grid) for TC and ETC, global 0.5° (`r05`) for the Tornado Archive, 0.25° over the
U.S. (`rus`, 24–50°N, 126–66°W) for Storm Events and derechos.
- U.S. fields are masked to cells with any of 4×4 sub-points inside a state (`states.topo.json.gz`); the Tornado
  Archive to points within 80 km of any tornado in the archive (any year). Elsewhere global fields are 0, not blank.
- Storm Events conventions follow `build_scs_grid.py`: local BEGIN date, BEGIN lat/lon or the county centroid when
  missing or outside the domain (only county-type rows, which is what `events_*_pts` carries). TCs follow
  `../enso/build_enso_tc.py` (UTC day). Derechos follow `build_derecho_data.py` (`definitive`, core reports, dated by
  swath start). ETCs: positions every 3 h, default = not in the track's tropical phase (up to its last point within 3°/3 h
  of an IBTrACS position at any stage but ET: precursor, tropical stage, gaps), track reaches 30°, point below 1500 m.
- Checked by brute force: tornado days within 80 km of 35.5°N 97.5°W and TS+ days within 500 km of 25.5°N 80.5°W
  match a direct haversine count.

`data/ta_tornado.json.gz` (about 60 KB, **no longer read by the page**; kept for reference) has the same sparse layout
as the SCS grids, on a global 2° grid from 90°S, 180°W. It is built by `build/build_tornado_archive.py` (whose
waterspout filter and rating helpers `build_radius_counts.py` imports) from `tornadoes-noESWD.json`
in github.com/malcolmmaas/tornadoarchive-pub: a one-time snapshot with no license stated, no Europe
(ESWD), uneven national coverage and nothing after 2021 (2022 holds only 10 tornadoes, so the field
uses 1992–2021). Waterspouts are dropped: unrated records from NCEI alone (NCEI EVENT_TYPE Waterspout)
and unrated records lying entirely offshore (ocean codes NOA, EAA, OCA, SOA, SOF), 3,609 in all; kept, they made the
Florida Keys the world's top box. The field carries its own `per`, so it ignores the page's period.

## Rebuilding

Scripts are in `build/` (served like every repo file, but nothing links to them):

```sh
cd climate/build
python3 fetch_era5_sfc.py  /tmp/c   1996 2022                    # GDEX ds633.1 monthly means, open; 20 vars
python3 fetch_era5_pl.py   /tmp/cpl 1996 2022                    # GDEX THREDDS NCSS, server-side level subset
python3 fetch_era5_cds.py  /tmp/c /tmp/cpl 2023-2025             # Copernicus CDS (needs ~/.cdsapirc)
python3 fetch_wb2_shear.py /tmp/cw  1996 2022 2                  # WeatherBench2 6-hourly 1.5°, two days in every four
python3 fetch_cds_shear.py /tmp/cw  2023                         # 6-hourly from the CDS, all days; one process per year
python3 fetch_cds_shear.py /tmp/cw  check                        # optional: Dec 2022 both ways, to compare
python3 build_climo.py ../data /tmp/c /tmp/cpl /tmp/cw           # -> data/*.bin.gz + index.json
# event maps (about 2 minutes; needs numpy, pandas, scikit-learn, matplotlib):
python3 -I build_radius_counts.py ../data --scs ../../scs/trends --ibtracs ibtracs.since1980.list.v04r01.csv \
        --ta tornadoes-noESWD.json --etc etc_points.csv etc_tracks.csv [--only tc,etc,us,derecho,ta]
```

- All the per-year files are 1° box means (`era5_coarsen.py`: same grid and weights as
  `../enso/era5_coarsen.py`, made NaN-aware).
- GDEX and CDS are the same ECMWF product. Checked: 1990 t2m, mtpr, mer, mtnlwrf, u250 and w500
  agree exactly (0.0 difference) after coarsening.
- The CDS limits how many requests can be queued, and a whole year of 6-hourly winds exceeds its
  cost limit. `fetch_era5_cds.py` therefore batches several years and all variables per request,
  identifying variables by `GRIB_paramId`. `fetch_cds_shear.py` asks for two months at a time.
  Both back off on refusals.
  - Requests from killed scripts stay queued and block new ones. Delete them with
    `ecmwf.datastores.Client(url,key).get_jobs(status=['accepted'])` then `.delete(...)`.
- To move the period forward (e.g. 1997–2026), fetch the new year with `fetch_era5_cds.py` and
  `fetch_cds_shear.py`, change `PERIODS` in `build_climo.py` and at the top of the page's script,
  and rebuild.
- To add more periods, add them to both `PERIODS` lists. `monthly(f,p)` and the data file names
  are already per period; a period selector, change map and multi-period seasonal-cycle lines
  would need to be added back to the page.

## Method notes (don't change silently)

- Monthly climatology is the plain mean of that calendar month over the period's years.
  - Seasons and annual values are means of monthly means, with months weighted equally.
  - For counts they are sums: storm-days per season or per year.
- **Animation:** by default the map **steps through the 12 monthly means**, so every frame is data
  (Dan, 2026-10-14). An opt-in "Smooth between months (interpolated)" box under Advanced adds
  in-between frames: monthly means sit at mid-month, joined by a Catmull–Rom curve through four months
  and clamped to the two months that bracket it, so it never overshoots (no negative precipitation).
  Hash `sm=1` turns it on. With stepping, the export dialog defaults to one frame per month.
- **Color scales are fixed for the whole year** (all 12 months of whatever is shown), so the
  animation never rescales.
  - ERA5 values use preset levels per field (`lv` in `FIELDS`).
  - Counts use sqrt-spaced levels up to the 99.5th percentile.
  - Anomalies and changes are symmetric about zero, at the 98th percentile of |value|.
- Albedo and convective share are ratios: their seasons and annual values are the ratio of the summed parts
  (1 − ΣASR/ΣISR, Σmcpr/Σmtpr), not the mean of monthly ratios.
  - The "relative to the annual mean" baseline, the readout's annual mean and the panels' annual lines use the
    same ratio of summed parts (independent review, 2026-10-14). The global seasonal cycle is 1 − ΣASR/ΣISR.
- **Snow depth:** boxes that keep 20 mm or more in every month are blank (`glac` in `FIELDS`). ERA5 holds snow
  fixed at 10 m water equivalent on glaciers and ice sheets, and any glacier in a 1° box carries that into the mean.
- Diverging scales (anomalies, zonal departures) are at least ±2% of the field's preset range, so rounding noise
  is never stretched across the whole palette.
- Wind speed is the speed of the monthly-mean vector. Shear is the mean of 6-hourly magnitudes.
- Peak month is blank where the seasonal cycle (max − min month) is under 1% of the field's color
  range (ERA5), or under 3% of the 98th-percentile yearly total (counts).
- The Storm Events maps carry a note that reports follow population. The extremes need at least
  20 of the period's years; 1996–2025 has all of them (derechos start in 1996).
- Peak month is drawn as nearest boxes, never blended between neighbors. The event maps are smooth fields (counts
  within a radius) and are drawn bilinearly like ERA5. Their zero edge is drawn at half of one event in the period
  (0.5/30 per year), so it follows the interpolated field instead of grid steps; inside the U.S. and Tornado Archive
  domains the area below that is the faint "none reported" tint.
- The seasonal-cycle panel shows monthly values, so its unit always says "per month".

## Rendering

The page is one self-contained file (`earthvis.html`, script inline, about 170 KB). Edit it directly.

- `MapView` inverse-projects every pixel once per view into lon/lat, then into per-grid bilinear
  indices and weights. The globe and polar views use a cheap cos-distance visibility test; the
  flat maps use a round-trip check.
- Frames are drawn in one pass through a 2048-entry color LUT: about 15 ms for a 1056×514 map
  in headless Chromium. A full LUT rebuild takes about 0.2 s, and about 0.04 s at the 0.4×
  resolution used while dragging.
- Coastlines, borders and states are cached `Path2D` objects, drawn dark with a light halo.
- Contours are marching squares redrawn every frame.
- Flow streaks are dark or light depending on the mean luminance of the painted field.

## Not done yet / ideas

- **Shear status (2026-10-14):** `s06` and `s200` cover only **1996–2022** (WeatherBench2). The page
  says "1996–2025 uses 1996–2022" for them. The CDS download of 2023–2025 6-hourly winds did not
  finish, because the CDS queue was throttled. To complete it, on a machine with `~/.cdsapirc`, run
  `python3 build/fetch_cds_shear.py DIR 2023` (and 2024, 2025, one process each), then
  `python3 build/build_climo.py data C PL DIR s06,s200`, which rewrites the two files and `index.json`.
  Once all 30 years are present, the page's note disappears by itself.

- Contour labels; a land/ocean-only zonal mean; daily-data extremes (heat days, heavy-rain days).
- CAPE × shear joint frequency, which needs coincident 6-hourly CAPE.
- A "guided tour" mode for classes.
