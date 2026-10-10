# ENSO composites — `ensogrid.html`

**El Niño and La Niña: Climatology and Impacts — global grid.** Built 2026-10-10.

Laid out like `../scs/trends/scstrend_grid.html` (two linked Leaflet maps stacked, controls in the
header, SVG panels below, Methods at the bottom) but global like `../tc/trends/tctrend.html`, and
the lower map answers a different question: not "how has this changed" but "how is this month
different in El Niño (or La Niña) years".

1. **Climatology map** — the chosen month, mean over every ENSO year of the period.
2. **Difference map** — El Niño minus climatology, La Niña minus climatology, or El Niño − La Niña
   (segmented control), dotted where p < 0.05.
3. **Month strip** — June (year 0) → May (year +1), all twelve months of the ENSO year; slider + step + Play.
4. **RONI panel** — every season since 1950, period shaded, one marker per ENSO year on its DJF
   season; the years actually used are filled and labelled. The year lists are also printed in
   the footer as text.
5. **Box panel** — one bar per year for the clicked box (or the field aggregate: ERA5 global
   area-weighted mean, TC global total, U.S. mean over boxes), coloured by phase, with both
   composite means and their p-values.

Everything statistical is computed **in the browser** from per-year fields, so strength, period,
trend option, phase and units are all live controls, and the box panel is the same arithmetic as
the map. Verified against an independent numpy/scipy implementation (5 cases, max disagreement
8e-7) and against IBTrACS / the Storm Events grids directly.

## Fields

| Family | Fields | Grid | Source on disk |
|---|---|---|---|
| ERA5 | 2 m temperature, precipitation | 2° global | `data/era5_<var>_<MM>.bin.gz` (one per variable per month, 24 files, ~1 MB each) |
| Tropical cyclones | track density (TS+/Cat1+/Cat3+), ACE, genesis | 5° global, ±60° | `data/tc_month.json.gz` (80 KB) |
| U.S. severe weather | hail, tornado, thunderstorm wind, derecho (+ their thresholds) | 2° lower 48 | **`../scs/trends/data/grid_*.json.gz` — read in place** |

The U.S. fields read the 2° page's own data files (and `../scs/trends/geo/states.topo.json.gz` for
state lines) via relative paths. That keeps one copy of the data, but it couples the pages: **if
`build_scs_grid.py`'s wire format changes (`meta`, `ci`/`yi`/`mi`/`v`, `meta.gaps`, `meta.through`),
check this page too.**

## Method decisions (don't change silently)

- **ENSO year** = the twelve months June Y → May Y+1 (extended from Jun–Feb on 2026-10-10 at Dan's request). Classified by the **Dec–Feb RONI**: El Niño if ≥ strength
  (default +0.5 °C), La Niña if ≤ −strength, *and* that DJF lies in a run of ≥ 5 consecutive
  overlapping seasons beyond ±0.5 °C (CPC's episode rule). Strength menu: 0.5 / 1.0 / 1.5.
  1979–2025 at 0.5 gives 13 El Niño, 19 La Niña. RONI finds more La Niña and fewer El Niño years
  than the old ONI (it removes the tropical-mean warming) — e.g. 1987–88 is *not* El Niño here
  (DJF 1988 RONI 0.45).
- **Index = RONI**, not ONI: CPC's operational index since 2025. `build_enso_roni.py` refetches it.
- **Trend removed by default**: each box's least-squares line through the period is subtracted
  before compositing, so recent warming (or Storm Events' reporting growth) doesn't leak into
  whichever phase dominated recent years. "Trend: Kept" uses the period mean instead.
- **Tests**: one phase → one-sample t-test of the mean anomaly vs 0 (n−1 df); El Niño − La Niña →
  Welch. No field-significance correction; the guidance box says so.
- **Count fields**: a box below 2% of the field's 98th-percentile monthly climatology is blank; below
  5% it is drawn but not dotted (a t-test on an almost-all-zero series calls a fraction of a
  storm-day "significant"). `% of climatology` is blanked below 5% (counts) / 0.1 mm/day (precip).
- **Colour scales**: fixed for ERA5 (T clim −30…30 °C, diff ±3 °C, ±5 for EN−LN; precip 0–12 mm/day,
  ±3 / ±5, ±80% / ±100%), so the slider never re-scales. Count fields follow the month on screen
  (their seasonal cycle is too strong for one scale).
- **Smoothing** (count fields only): Gaussian, sigma one box, applied to each *year's* map before
  compositing so dots and colours describe the same field; panels are never smoothed.
- **Default periods**: ERA5 1979–2025, TC 1980–2025, Storm Events **2000**–2025 (reporting).
- **Projection**: EPSG:4326 (equirectangular), Pacific-centred, with Natural Earth 110m coastlines
  (`geo/countries-110m.json`, from `world-atlas@2.0.2`) drawn in three copies at ±360°. The
  field is painted per pixel into canvas tiles (`FieldLayer`), no basemap tiles. Russia/Fiji arcs
  that jump ±180° are split (`splitJumps`) or they draw lines across the globe.
- **TC conventions** follow `build_tc_trends.py` (main/provisional tracks, synoptic 6-hourly,
  `USA_WIND`) except: **NATURE TS/SS only** and ≥ 34 kt only. tctrend's default also keeps ET.

## Rebuilding the data

```sh
cd enso
python3 build_enso_roni.py data                                   # RONI (seconds)
python3 build_enso_tc.py /path/to/ibtracs.ALL.list.v04r01.csv data # TC (~10 s)
# ERA5: 1 deg box means into a scratch dir, then the 2 deg per-month files
python3 fetch_era5_gdex.py /tmp/coarse 1979 2022                   # ~2 GB streamed, ~5 min
python3 fetch_era5_arco.py /tmp/coarse                             # ~90 GB streamed, ~25 min
python3 build_enso_era5.py /tmp/coarse data --y0 1979 --y1 2025
```

- NCAR GDEX ds633.1 (monthly means) currently **ends Dec 2022**, hence the ARCO-ERA5 (Google
  public bucket, hourly) splice from Jan 2023. Dec 2022 was built both ways: agreement 0.001 K /
  0.001 mm/day in every 1° box. Neither source needs a key; no CDS account is involved.
- To add the 2026–27 ENSO year: extend the `months` list in `fetch_era5_arco.py` through May 2027,
  rerun it and `build_enso_era5.py --y1 2026` (once May 2027 is in the final ERA5, ~3 months later),
  and the RONI/TC builders. TC/Storm Events ENSO years end automatically at the last one whose May
  is published (`lastEnsoYear()`).
- `data/era5_*.bin.gz` layout: gzip of Int16 LE `[clim(cell) | anom(year0,cell) | …]`, ×100,
  cell = row·180 + col, row 0 = 90–88°S, col 0 = 0–2°E. See `data/era5_index.json`.

## Not done yet / ideas

- Seasonal (e.g. DJF) means; SST / 500 hPa height fields; a scatter of DJF RONI vs the box value.
- No `test_*.js` yet; the checks above were run ad hoc with Playwright + numpy.
