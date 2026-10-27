# ENSO composites — `ensogrid.html`

**El Niño and La Niña: Climatology and Impacts — global grid.** Built 2026-10-10.

**Layout (Oct 2026, simplified for a general audience):** one Leaflet map. Above it are two main
controls: **Show** (El Niño · La Niña · Climatology; the El Niño − La Niña button appears only when
"Compare El Niño with La Niña directly" is ticked under Advanced) and **Variable**, a single menu
with every field at every intensity ("Hail — ≥ 1 inch", "Tornadoes — EF2+", …; values `field:thr`).
The averaging strip sits under them. Everything else (strength, period, trend, units, smoothing,
dots, compare, view/theme/PNG/link buttons) is in a collapsed **Advanced settings** box below the
map. Below that come the panels, the year lists, Methods and the guidance box. A title bubble in
the map's top-left corner names the variable. The top bar also holds "Show difference as" (Percentage / Absolute;
grayed for Climatology, % disabled for temperature) and "Reload default". Hash: `ph=en|ln|enln|clim`.
**Compare with** (Advanced, hash `b=neu`): the baseline for the El Niño / La Niña maps. *All years*
(default) = minus climatology. Because departures from the all-year mean sum to zero
(nEN·EN + nLN·LN + nN·N = 0), the La Niña map is largely forced to ≈ −(nEN/nLN)·El Niño and EN−LN ≈
(1+nEN/nLN)·EN (checked: ratio 1.62 predicted and observed for 2000–2025; pattern correlation
EN vs −LN 0.77–0.95). *Neutral years* = phase minus the neutral-year mean, Welch test phase vs neutral,
cluster shuffles within phase ∪ neutral; EN and LN maps then independent (corr EN vs −LN −0.3…+0.4)
but share the noise of a small baseline (12 neutral years 1979–2025, 5 for 2000–2025). EN−LN unchanged.
Neutral is always *truly* neutral (no event even at the 0.5 level, `classify(0.5)`), whatever the
strength: at strength > 0.5 the weaker events get class `W` in `windowYears()` and sit in neither
composite nor the neutral baseline (they stay in the all-years climatology). Counts in the tooltip
and Methods are computed (`nNeutral`), not hard-coded.
**Climatology contours** (Advanced, off by default; hash `ct=1`): marching squares on the box
centers of the displayed climatology (smoothed/masked like the map), drawn over whichever view is
showing. Levels: temperature every 10 °C (nice steps in °F), precipitation 0.5–16 mm/day doubling,
snowfall 0.1–4, count fields ~5 nice steps between the 2nd and 98th percentiles. Labels: one per
level per 45°×60° block (8°×12° on the U.S. grid), on the segment nearest the block center and only
where the contour has ≥ 4 segments there.

1. **Climatology** — the chosen average over every ENSO year of the period: the **whole ENSO
   year (default)**, a season (Jun–Aug, Sep–Nov, Dec–Feb, Mar–May) or a single month.
2. **El Niño / La Niña** (default El Niño) — minus climatology, or El Niño − La Niña; dots on
   significant patches (cluster permutation test, below).
3. **Averaging strip** — ENSO year / four seasons / Month; in Month mode a slider June (year 0) →
   May (year +1) with step buttons.
4. **RONI panel** — every season since 1950, period shaded, one marker per ENSO year on its DJF
   season; the years actually used are filled and labeled with the ENSO year ("1997–1998"). The year lists are also printed in
   the footer as text.
5. **Box panel** — one bar per year for the clicked box (or the field aggregate: ERA5 global
   area-weighted mean, TC global total, U.S. mean over boxes), colored by phase, with both
   composite means and their p-values.

Everything statistical is computed **in the browser** from per-year fields, so strength, period,
trend option, phase and units are all live controls, and the box panel is the same arithmetic as
the map. Verified against an independent numpy/scipy implementation (max disagreement ~1e-6),
against IBTrACS and the Storm Events grids directly, and by a six-reviewer independent review of
the whole site on 2026-10-10 (data rebuilt from raw GDEX files, C3S global means, CPC's RONI table,
per-pixel map geolocation). Fixes from that review are noted below.

## Regression version — `ensoreg.html` (Oct 22, 2026; separate page, not linked from ensogrid yet)

**El Niño and La Niña by Strength.** Built from the *same sources* as ensogrid: `assemble.sh` writes both
pages, ensoreg with `const REG=true` and the template's `<!--R-->…<!--/R-->` blocks (ensogrid keeps
`<!--C-->…<!--/C-->`). All `REG` branches are no-ops on ensogrid.
- **Model (per box), revised Oct 22 after the independent review:** one-step OLS
  `y = y0 + a·(t − t̄) + b+·max(x,0) + b−·min(x,0)` (trend term only with Trend: removed), x = the
  year's two-decimal Dec–Feb RONI (no threshold, no episode rule; all years incl. neutral). Two lines
  meeting at RONI 0. Implemented by Frisch–Waugh (`regFit`: y residualized on [1,t], hinge terms with
  [1,t] projected out). **Map at slider v = fitted value at v minus climatology**
  = b+·(max(v,0) − mean max(x,0)) + b−·(min(v,0) − mean min(x,0)) (`mapAt`), the composite page's
  reference; % divides by climatology. At v = 0 the map is "fitted neutral minus climatology".
  - First version measured from the fitted point at RONI 0 (b·v). Reviewers showed the shared intercept
    leaks a curved El Niño response or intercept noise into La Niña with El Niño's sign (same-sign
    +1.5/−1.5 area 45–80% vs composites 16–26%; Peru DJF rain at −1.5 +102%, composite −5%; central
    Canada DJF t2m +0.93 °C). Now: same-sign area 21–33%; Peru +16%; Canada −0.31 °C. Synthetic
    El Niño-only convex response max(x−1,0): La Niña −1.5 map −0.06 (true −0.13) vs +0.24 before.
  - Two-step detrend (y only) was replaced: RONI trends toward La Niña (corr(year, min(x,0)) = −0.29),
    so it shrank La Niña slopes ~9–10%.
  - Both sides need ≥ 3 years (the map uses both slopes at any v).
- **p / dots (Dan: test the slope, option b):** t of the shown side's slope of the joint fit, df = n − 3
  (− 1 with trend). `regClusterTest` shuffles RONI across years and redoes the joint fit (time projected
  out of the shuffled hinge terms each shuffle). Dots identical for every v on a side, and in % vs
  absolute; none at RONI 0. Null any-patch rate (iid shuffles, 200 runs): 6.0% TC days yr, 5.5% hail
  DJF. Reviewer surrogate tests (ENSO's 2-year alternation) give ~6–9%: stated in Methods. ERA5 ~2–3 s.
- **Caveats on the page:** the El Niño line leans on the four RONI ≥ 2 years (1982–83, 1991–92
  Pinatubo, 1997–98, 2015–16; hat values 0.17–0.22) — named in the note; weak (±0.5) maps are the
  strong-event pattern scaled down and can overstate weak events (rain ~55–75%) — note at |v| = 0.5,
  guide and Methods; strength names follow RONI, not ONI.
- **UI:** slider −2.5…+2.5 step 0.5 (`#roRange`, ticks clickable), readout "Strong El Niño (RONI
  +1.5°C)" (weak 0.5, moderate 1.0, strong 1.5, very strong ≥2.0); Show = Difference | Climatology;
  strength, Compare with and El Niño − La Niña are not offered. Default +1.5. Values beyond the
  strongest year of the period on that side (1979–2025: +2.40 in 1982–83, −1.73 in 2007–08) are
  flagged "beyond the record" and in the note under the map. Hash `r=<v>` (`ph=clim` for climatology).
- **Panels:** RONI panel marks every year in the period by its DJF value (labels beyond ±0.5) with a
  dashed line at v; the box panel (Other advanced) is a scatter of each year's departure from
  climatology (joint trend removed) vs RONI with the two fitted lines measured from climatology
  (dashed beyond the strongest year), so the ring at v is exactly the map's value.
- **Other review fixes (Oct 22):** box/RONI panel text no longer clipped (two-line subtitle, shorter
  narrow captions); panel refuses a fit with < 3 years on either side; undefined p shows "p —";
  small % with one decimal, no "−0"; dots text/chip only when testable; slider aria-valuetext,
  live readout, dimmed in Climatology; REG tooltips/guide/Methods reworded (no composite wording);
  U.S. spring paragraph without the composite page's numbers; hash `r=` empty ignored, symmetric
  rounding, `c` range-checked. Shared with ensogrid: hash `v` written after a shared view is
  applied; Custom From/To ignores empty input and stores the normalized range; climatology colorbar
  uses "−"; hover omits p when undefined. Not done: pr/sf int16 at 0.01 (store at 0.001 in a data
  rebuild); borderline patches (p≈0.05) can flip with the seed; ensogrid's own two-step detrend.
- **Checked:** box values and p match numpy/scipy OLS for ERA5 T/precip, TC and hail boxes (to
  float precision); x = roni.json DJF exactly; map = fresh recompute; dots ⊂ p<0.05 boxes;
  dots same in % and absolute and across v on a side; drag sequence ends in a consistent state.

## Forecast version — `ensofcst.html` (Oct 22, 2026; separate page, linked only from itself)

**El Niño and La Niña Outlook: What to Expect, Month by Month.** Third build of the same sources
(`FCST=true`, template blocks `<!--F-->`; `REG` is also true, so it is the regression page without
the slider). Dan's choices: tie every month to the **Dec–Feb RONI of its ENSO year** (as on the
other pages), and use CPC's **median** as "most likely".
- **Forecast data:** `build_enso_fcst.py data` parses NOAA CPC's *Official RONI Outlook*
  (https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/roni/outlook/): 5/15/25/50/75/85/95th
  percentiles for 9 overlapping seasons, HTML table only. It writes `data/roni_fcst.json`
  (`issued`, `fetched`, `seasons[{code, center 'YYYY-MM', q}]`). First season's center month = issue
  month. Hard checks (9 consecutive seasons, increasing percentiles, plausible values); on any
  failure it exits without touching the file. **Run monthly after CPC's update (2nd Thursday)**,
  together with `build_enso_roni.py`.
- **Months offered:** from the current month (browser clock) to the center of CPC's last season,
  only in ENSO years whose Dec–Feb is observed or forecast (October 2026 issue: Oct 2026 – May 2027;
  the last season, MJJ 2027, belongs to the next ENSO year, whose Dec–Feb is not yet forecast).
  Default: next month. Each month: regression of the strength page at x = observed DJF RONI if in
  `roni.json`, else CPC's DJF median (Oct 2026: +2.36, 50% range +2.04…+2.68, 90% +1.58…+3.14 —
  just below the 1982–83 record +2.40). Map identical to ensoreg at that RONI and month (checked).
- **UI:** Show = Expected change | Climatology; Variable; Show difference as; month buttons with the
  forecast line (issue date, median, 50/90% ranges, stale warning from the month after the issue,
  after the 16th); no averaging bar. RONI panel = last two years observed + CPC outlook fan
  (`fcRoniPanel`) with the strongest Dec–Feb of the period. Note under the map says "a guide from
  history, not NOAA's forecast". Hash `mo=YYYY-MM` (`ph=clim`). If the forecast file is past its
  horizon the page says it is out of date.

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
  Every value is **rounded to 0.1 first, as CPC does** (half away from zero): CPC colors its RONI
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
  July derechos were that artifact. No dot where both groups have zero spread.
- **Dots (Oct 2026)**: cluster-based permutation test (Maris & Oostenveld 2007), `clusterTest` in
  the page. Boxes at p < 0.05 (Welch t vs the two-sided 5% point of its Welch df) join same-sign
  8-neighbors (longitude-wrapping on global grids) into patches; patch mass = Σ|t|·cos(lat). The
  phase labels are shuffled 1000× on the ERA5 grid and 2000× on the TC/U.S. grids (EN−LN: within
  EN∪LN years; EN or LN: across all years, or within phase ∪ neutral with Compare with: Neutral),
  seeded from the data-relevant settings only (field, threshold, phase, strength, period, trend,
  smoothing for counts, baseline, average — not %/absolute or °C/°F, so those never change the
  dots; before Oct 15 they did, flipping borderline patches); residuals are detrended once, before shuffling. A patch is dotted if
  < 5% of shuffles produced a heavier patch anywhere on the map (family-wise 5% for any spurious
  patch). It runs on the displayed field, smoothed when smoothing is on, so the shuffles share the
  smoothing. Cost: ~3–8 s for an ERA5 map on a slow 2-CPU machine (faster on a desktop),
  well under 1 s for TC/U.S.; the map draws at once and the dots follow. It is strict: U.S. 2° maps rarely pass (e.g. Dec–Feb tornado EN−LN: 16 boxes at
  p < 0.05, no significant patch), while ERA5/TC keep the main teleconnections. The hover p is
  still the box's own test.
- **Fixes after the Oct 15 independent review**: tiles are repainted in place (`repaintTiles`)
  instead of `GridLayer.redraw()`, which at fractional zoom rebuilt tiles with the wrong longitude
  wrap (Pacific drawn over the Americas, e.g. on load at 1024 px); `.lmap{width:100%}` so the
  aspect-ratio + min-height no longer forced an 874 px-wide map on phones; La Niña subtitle reads
  RONI ≤ −X; footer neutral wording; box panel reports phase − neutral (and draws the neutral mean)
  with Compare with: Neutral; no hover readout while a new state loads (`BUSY`); a pasted link
  (hashchange) reloads the page. Oct 22: `fullView()` right after the map is made (shared links with a
  box selected opened blank: the outline layers were added to a map with no view); `lastRoniYear()`
  renamed (it had overridden the data loaders' `lastEnsoYear(last)`; same result today). Then (item 8): neutral = truly neutral (above); the note under the
  map adds "Note: no dotted areas = signal is weak in this domain" when dots are on and none are
  drawn (re-written when the patch test finishes); percent-mode floors raised (below); dots are drawn
  only on boxes the map colors.
- **Average**: switching variable never changes the average (ENSO year / season / month); every
  field opens on the ENSO year. (An automatic Dec–Feb default for U.S. fields was removed, Oct 2026.)
- **Count fields**: a box below 2% of the field's 98th-percentile monthly climatology is blank (5% in percent mode); below
  5% it is drawn but not dotted (a t-test on an almost-all-zero series calls a fraction of a
  storm-day "significant"). The same flux floors (0.1 mm/day precip, 0.05 snowfall) suppress dots
  (no Sahara dots).
- **Percent change (Oct 2026) is the default** for every field except temperature (always °C/°F;
  the control is disabled). Precip divides by max(clim, 0.1 mm/day), so deserts read as modest
  percentages rather than holes; in percent mode counts are blank below 5% of the 98th-percentile
  climatology and snowfall below 0.05 mm/day (`pctDenom`), i.e. exactly where those boxes cannot
  carry a dot, so the visible dots are the same in % and absolute. (10% was tried: it hid about a
  quarter of the dotted boxes on the TC maps, e.g. the El Niño typhoon increase near 160°E.) Scales saturate: ERA5 ±50% (EN−LN ±100%); counts 95th percentile of the
  map, capped at ±200%. Hash: `pc=abs` for absolute change; no `pc` = percent.
  Snowfall boxes below 0.01 mm/day climatology are blank on both maps.
- **Color scales**: fixed for ERA5 per averaging length, so the slider never re-scales
  (T clim −30…30 °C; T diff month ±3 / season ±2 / year ±1.5 °C, EN−LN ±5 / ±3 / ±2.5;
  precip 0–12 mm/day, diff ±3 / ±2.5 / ±1.5, EN−LN ±5 / ±4 / ±2.5; snowfall 0–4 mm/day,
  diff ±1 / ±0.8 / ±0.4; % ±80 / ±100). Count fields follow the map on screen.
- **Smoothing** (count fields only): Gaussian, sigma one box, applied to each *year's* map before
  compositing so dots and colors describe the same field; panels are never smoothed.
- **Period (Oct 2026)**: a three-way toggle — **1979–2025**, **2000–2025**, or **Custom…**, which
  reveals From/To boxes. Presets are clipped to each record (TC 1980–, derechos 1996–). Default:
  1979 for every field (the larger sample matters most for a public page). Storm Events reporting
  grew steeply into the late 1990s, but over 1979–2025 quadratic instead of linear per-box
  detrending changes the U.S. EN−LN maps by 3–13% RMS and flips ≤4% of boxes (hail, tornado,
  wind; every season). Hash: `p` omitted for the field's default, else `p=all|recent` or `p=YYYY-YYYY`
  (custom); old range links that equal a preset open as that preset.
- **Place names / state lines**: `geo/admin1-10m.json.gz` (Natural Earth 1:10m admin-1 states and
  provinces, `mapshaper -simplify 6% keep-shapes`, ~360 KB) is drawn as thin lines over both maps
  (canvas renderer, three copies; faded below zoom 1.75) and used to name the place under the cursor
  ("Indiana, United States") in the hover readout and the box panel title. Loaded after first render.
- **Projection**: EPSG:4326 (equirectangular), Pacific-centered, with Natural Earth 110m coastlines
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
- **Loading**: only the neighboring months are prefetched in Month mode (prefetching all twelve,
  ~12 MB, starved slow connections); a "Loading…" chip shows on both maps while data load.

## Rebuilding the data

```sh
cd enso
python3 build_enso_roni.py data                                   # RONI (seconds)
python3 build_enso_fcst.py data                                   # CPC RONI outlook for ensofcst.html (seconds; monthly)
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
