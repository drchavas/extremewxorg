# ENSO composites — `ensogrid.html`

**El Niño and La Niña: Climatology and Impacts — global grid.** Built 2026-10-10.

Laid out like `../scs/trends/scstrend_grid.html` (two linked Leaflet maps stacked, controls in the
header, SVG panels below, Methods at the bottom) but global like `../tc/trends/tctrend.html`, and
the lower map answers a different question: not "how has this changed" but "how is this year
(season, month) different in El Niño (or La Niña) years".

1. **Climatology map** — the chosen average over every ENSO year of the period: the **whole ENSO
   year (default)**, a season (Jun–Aug, Sep–Nov, Dec–Feb, Mar–May) or a single month.
2. **Difference map** — El Niño minus climatology, La Niña minus climatology, or El Niño − La Niña
   (segmented control), dotted where p < 0.05.
3. **Averaging strip** — ENSO year / four seasons / Month; in Month mode a slider June (year 0) →
   May (year +1) with step + Play.
4. **RONI panel** — every season since 1950, period shaded, one marker per ENSO year on its DJF
   season; the years actually used are filled and labelled with the ENSO year ("1997–1998"). The year lists are also printed in
   the footer as text.
5. **Box panel** — one bar per year for the clicked box (or the field aggregate: ERA5 global
   area-weighted mean, TC global total, U.S. mean over boxes), coloured by phase, with both
   composite means and their p-values.

Everything statistical is computed **in the browser** from per-year fields, so strength, period,
trend option, phase and units are all live controls, and the box panel is the same arithmetic as
the map. Verified against an independent numpy/scipy implementation (max disagreement ~1e-6),
against IBTrACS and the Storm Events grids directly, and by a six-reviewer independent review of
the whole site on 2026-10-10 (data rebuilt from raw GDEX files, C3S global means, CPC's RONI table,
per-pixel map geolocation). Fixes from that review are noted below.

## Fields

| Family | Fields | Grid | Source on disk |
|---|---|---|---|
| ERA5 | 2 m temperature, precipitation, snowfall (water equivalent) | 2° global | `data/era5_<var>_<MM\|yr\|jja\|son\|djf\|mam>.bin.gz` (17 per variable, ~1 MB each) |
| Tropical cyclones | track density (TS+/Cat1+/Cat3+), ACE, genesis | 5° global, ±60° | `data/tc_month.json.gz` (83 KB) |
| U.S. severe weather | hail, tornado, thunderstorm wind, derecho (+ their thresholds) | 2° lower 48 | **`../scs/trends/data/grid_*.json.gz` — read in place** |

The U.S. fields read the 2° page's own data files (and `../scs/trends/geo/states.topo.json.gz` for
state lines) via relative paths. That keeps one copy of the data, but it couples the pages: **if
`build_scs_grid.py`'s wire format changes (`meta`, `ci`/`yi`/`mi`/`v`, `meta.gaps`, `meta.through`),
check this page too.**

## Method decisions (don't change silently)

- **ENSO year** = the twelve months June Y → May Y+1 (extended from Jun–Feb on 2026-10-10 at Dan's request). Classified by the **Dec–Feb RONI**: El Niño if ≥ strength
  (default +0.5 °C), La Niña if ≤ −strength, *and* that DJF lies in a run of ≥ 5 consecutive
  overlapping seasons beyond ±0.5 °C (CPC's episode rule). Strength menu: 0.5 / 1.0 / 1.5.
  Every value is **rounded to 0.1 first, as CPC does** (half away from zero): CPC colours its RONI
  table from one-decimal values, so DJF 0.45 counts as +0.5. This reproduces every warm/cold season
  of CPC's RONI table. 1979–2025 at 0.5 gives **16 El Niño, 19 La Niña**. (Until the review the
  two-decimal values were tested, which made 1979–80, 1987–88 and 2014–15 neutral; an earlier note
  here blamed RONI-vs-ONI for 1987–88 — that was wrong.) DJF-only classification counts multi-year
  events only in their DJF years and can miss events peaking far from DJF; the Methods say so.
- **Index = RONI**, not ONI: CPC's operational index since 2025. `build_enso_roni.py` refetches it.
- **Trend removed by default**: each box's least-squares line through the period is subtracted
  before compositing, so recent warming (or Storm Events' reporting growth) doesn't leak into
  whichever phase dominated recent years. "Trend: Kept" uses the period mean instead.
- **Averages**: ENSO-year / seasonal ERA5 values are the plain mean of the monthly means (months
  weighted equally), served pre-built so the default view is one ~1 MB file. Count fields are the
  *sum* of the months (storm-days, hazard days per year or season), computed in the page; a year
  with any month missing (Storm Events Jun/Jul 1993) is dropped from that average.
- **Tests**: Welch's t, phase years vs **all other years** (EN−LN: EN vs LN). The first version
  used a one-sample t-test of the phase anomalies vs 0, which breaks for rare events: an all-zero
  El Niño group has residuals equal to the trend line, ~0 variance and p ≈ 0 — 25 of 25 dots on
  July derechos were that artefact. No dot where both groups have zero spread. No
  field-significance correction; the guidance box says so.
- **Count fields**: a box below 2% of the field's 98th-percentile monthly climatology is blank; below
  5% it is drawn but not dotted (a t-test on an almost-all-zero series calls a fraction of a
  storm-day "significant"). `% of climatology` is blanked below 5% (counts) / 0.1 mm/day (precip)
  / 0.05 mm/day (snowfall), and the same flux floors suppress dots in Amount mode (no Sahara dots).
  Snowfall boxes below 0.01 mm/day climatology are blank on both maps.
- **Colour scales**: fixed for ERA5 per averaging length, so the slider never re-scales
  (T clim −30…30 °C; T diff month ±3 / season ±2 / year ±1.5 °C, EN−LN ±5 / ±3 / ±2.5;
  precip 0–12 mm/day, diff ±3 / ±2.5 / ±1.5, EN−LN ±5 / ±4 / ±2.5; snowfall 0–4 mm/day,
  diff ±1 / ±0.8 / ±0.4; % ±80 / ±100). Count fields follow the map on screen.
- **Smoothing** (count fields only): Gaussian, sigma one box, applied to each *year's* map before
  compositing so dots and colours describe the same field; panels are never smoothed.
- **Default periods**: ERA5 1979–2025, TC 1980–2025, Storm Events **2000**–2025 (reporting).
- **Projection**: EPSG:4326 (equirectangular), Pacific-centred, with Natural Earth 110m coastlines
  (`geo/countries-110m.json`, from `world-atlas@2.0.2`) drawn in three copies at ±360°. The
  field is painted per pixel into canvas tiles (`FieldLayer`), no basemap tiles. Russia/Fiji arcs
  that jump ±180° are split (`splitJumps`) or they draw lines across the globe.
- **TC conventions** follow `build_tc_trends.py` (main/provisional tracks, synoptic 6-hourly,
  `USA_WIND`) except: ≥ 34 kt only, and **ET and DS stages dropped** (tctrend's default keeps ET).
  **NR ("not reported") and MX are kept** — a TS/SS-only filter erased the whole North Indian
  Ocean for 1990–95 (all NR in IBTrACS; e.g. the 1991 Bangladesh cyclone), South Atlantic 2010–11
  and nearly every provisional (latest-season) track. Fixed 2026-10-10.
- **Phones**: `FieldLayer` sets `minZoom:-2`. GridLayer's default of 0 drew nothing at the zoom a
  390-px screen needs to show the globe (−0.75), so both maps were blank on phones.
- **Loading**: only the neighbouring months are prefetched in Month mode (prefetching all twelve,
  ~12 MB, starved slow connections); a "Loading…" chip shows on both maps while data load.

## Rebuilding the data

```sh
cd enso
python3 build_enso_roni.py data                                   # RONI (seconds)
python3 build_enso_tc.py /path/to/ibtracs.ALL.list.v04r01.csv data # TC (~10 s)
# ERA5: 1 deg box means into a scratch dir, then the 2 deg per-month files
python3 fetch_era5_gdex.py /tmp/coarse 1979 2022 [t2m,mtpr,msr]   # ~3 GB streamed, ~8 min
python3 fetch_era5_arco.py /tmp/coarse [t2m,mtpr,msr]              # ~150 GB streamed, ~60 min
python3 build_enso_era5.py /tmp/coarse data --y0 1979 --y1 2025   # ENSO_VARS=sf to rebuild one var
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

- SST / 500 hPa height fields; a scatter of DJF RONI vs the box value.
- No `test_*.js` yet; the checks above were run ad hoc with Playwright + numpy.
