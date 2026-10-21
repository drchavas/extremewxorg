# U.S. Severe Convective Storm Climatology, Trends and Events

Three live pages over the same NOAA/NCEI Storm Events record, plus the SPC derecho archive.

**`scstrend.html`** — climatology and trend side by side on one shared, pannable map: drag
or zoom either and both follow, so the pair is always over the same ground. Click a *new* state
to center on it; clicking inside the state you are already on leaves the view where you put it,
so your own zoom survives. Pick a county from the County menu to pin it, with an annual series
(95% confidence band) and all twelve months as small multiples below. Covers hail, tornado,
thunderstorm wind, derecho, freezing rain and peak wind.

**`scstrend_grid.html`** — the same two maps on a 2° × 2° grid instead of counties. States
and counties are drawn as geographic reference only; every number is per grid box.

**`scsevents.html`** — individual storms rather than the climatology. The SPC derecho
archive (184 wind swaths, 1956–2025) and the biggest days on record for hail, tornado and
thunderstorm wind: top 50 for any state, top 100 nationally, or type any date as `YYYYMMDD`.

(The earlier deprecated pages — `scstrend_state.html`, `scstrend_map.html`, `scscard.html` — and
their `old/` test folder are no longer in this repo.)

## What a "hazard day" is

A hazard day is a **(county, calendar date)** pair with at least one report meeting the
selected magnitude threshold. Counting days rather than reports removes most of the
duplicate-report inflation you get when one storm generates a dozen calls to the same
office.

Two hazards do not use that definition, on purpose:

- **Derecho** is counted in **events per year**, not hazard days. A derecho is one coherent
  storm, and it is dated by its swath's start rather than by each report's local date —
  half these swaths cross a date boundary, and dating by report counted one storm twice in
  any county hit either side of midnight.
- **Station hazards** (freezing rain, peak wind) are per station, and a station-year below
  90% complete is dropped as *no observation* rather than counted as zero. That is the
  opposite of the county rule, and both are right: every county exists every year, a
  station does not.

## Data

| Hazard | Source | Record | Thresholds |
|---|---|---|---|
| Hail | NOAA/NCEI Storm Events | 1955–latest | any, ≥1″, ≥2″, ≥3″ |
| Tornado | NOAA/NCEI Storm Events | 1950–latest | EF0+, EF1+, EF2+, EF3+ |
| Thunderstorm wind | NOAA/NCEI Storm Events | 1955–latest | any, ≥50 kt, ≥65 kt, ≥80 kt |
| Derecho | SPC archive + Storm Events | 1996–end of archive | ≥50 kt, ≥64 kt, ≥74 kt |
| Freezing rain | NOAA ISD hourly | 2000–2025 season (ISD frozen) | ≥1 h, ≥3 h, ≥6 h |
| Peak wind | NOAA ISD hourly | 2000–2024 (ISD frozen) | ≥40 kt, ≥50 kt, ≥60 kt |

"latest" is whatever `update_storm_events.py` last fetched; `data/*.json.gz` `meta.year1` is
the authority. The newest year is usually only partly published — see *Updating* below.

Only `CZ_TYPE == "C"` (county) records are used; the county GEOID is built from
`STATE_FIPS` + `CZ_FIPS` rather than by matching county names, which avoids the
name-collision and independent-city problems.

### County days vs. state days

The build emits two different things, and they are not interchangeable:

- **County days** (`ci`/`yi`/`mi`/`v`) — per county, used for the maps.
- **State and national days** (`rri`/`ryi`/`rmi`/`rv`) — calendar dates on which
  *anywhere* in the state (or country) qualified. This is what the lower panels plot, and
  it is deliberately **not** the sum of county days: one storm can hit twenty counties on
  the same afternoon. Indiana averages 28 statewide hail days a year but 125 county-days.

Note also that the original per-county scripts divided each county's total by the number
of years *present in the data* rather than by the length of the period, which inflates
counties that had quiet years. Everything here divides by the full period: Marion County
was 3.60 mean annual hail days for 2000–2024 (3.58 for 2000–2025), not 3.91.

Geometry is the Census `cb_2023_us_county_500k` cartographic boundary file, simplified
to 4% with mapshaper: 3,221 counties across 50 states + DC + Puerto Rico (the Pacific
territories are dropped). Aleutians West is shifted across the antimeridian so it draws
contiguously. State outlines are the same file dissolved by `STATEFP`.

## Three things about the source that bite

**June and July 1993 do not exist.** Not sparse — absent. NCEI's own documentation: *"A best
effort was made to import these files into the original Storm Events Database in FoxPro 3.0
format. (June & July 1993 were misplaced and are not included)."* Verified against all three
files: zero rows in those two months, non-zero in every other month of 1993. Unrecoverable,
so it is masked (`NODATA` in the builders, `meta.gaps` on the wire). Left unmasked, 1993 read
40% low for hail, 46% for tornado and 53% for wind, which looks like a quiet year rather
than a partial one.

**Tornado rows are county segments, not tornadoes.** Storm Events splits a tornado at every
county line: 3 April 1974 holds 239 segments for 148 tornadoes. County-based quantities are
unaffected and in fact *want* segments — each of those counties genuinely had a tornado —
which is why `scsevents.html` ranks days by counties. Segments cannot be collapsed back into
tornadoes across the record: `TOR_OTHER_CZ_FIPS` is empty for every row before ~1990 and
populated on only 13% of rows since 2010. So the column is labeled *Segments*, not *Reports*.

**1993–1995 carries no coordinates.** Report lat/lon is ~100% present 1955–1992 and 1996 on,
and 0% in between. Anything needing a position (the 2° grid, the derecho swaths) falls back
to the county centroid for those years.

## Updating to newer NOAA data

```sh
BC="/path/to/Baseball Cards"
python3 update_storm_events.py "$BC" --isd "$BC/Freezing Rain Baseball Card/global_hourly_downloads"
```

This compares NCEI's yearly Storm Events "details" files with what was used last time
(`storm_events_coverage.json` in the Baseball Cards folder), downloads any year that is new
or re-issued (the three most recent years are watched; `--full` refreshes all), and splices
the hail, tornado and thunderstorm-wind rows into the Baseball Cards CSVs. `--dry-run` only
reports. Exit status 0 means something changed, 3 means already current. Network access to
`www.ncei.noaa.gov` and `noaa-global-hourly-pds.s3.amazonaws.com` is required.

**The newest year is usually partial.** NCEI publishes a year piecemeal and finishes it
some eight months later. Complete years go into `<hazard>_events_complete_years.csv`
as before; the incomplete one goes into `<hazard>_events_partial_year.csv`, with its last
published month recorded as `partial_through`. The builders (via `storm_coverage.py`) add
the unpublished months to `meta.gaps`, exactly like June/July 1993, so the pages drop that
year from means, trends and annual plots but still show its published months in the
monthly panels. Every page opens on the latest *complete* year; the partial year is
reachable from the To box.

**ISD is frozen.** NOAA stopped updating ISD Global Hourly on 24 Aug 2025 and, from
31 Jul 2026, serves the CSVs only from the NODD bucket
`noaa-global-hourly-pds.s3.amazonaws.com`. `--isd` fills in missing station-years up to 2025
from there. That extends freezing rain (Jul–Jun seasons) through the 2025 season; peak wind
(calendar years) cannot pass 2024 because 2025 fails the 90% completeness screen. Going
further means moving the station builder to GHCNh, NOAA's successor product.

## Rebuilding

Order matters: the county builder owns `index.json` and the others merge into it, and the
derecho builder reads the grid definition from `grid_index.json`.

```sh
python3 build_hazard_data.py   "/path/to/Baseball Cards" data   # hail, tornado, wind
python3 build_station_data.py  "/path/to/ISD csvs"        data   # fzra, pkwnd
python3 extract_derecho_archive.py SquitieriWadeJirak2026_supp.pdf   # only if the archive changes
python3 build_scs_grid.py      "/path/to/Baseball Cards" data   # 2 deg grid
python3 build_derecho_data.py  "/path/to/Baseball Cards" data   # derecho swaths + county + grid
python3 build_events_data.py   "/path/to/Baseball Cards" data   # biggest-days lists
```

(`build_scs_grid.py` keeps any Derecho entry already in `grid_index.json`, so running it
after the derecho builder no longer drops Derecho from the grid page.)

`build_station_data.py` needs the raw NOAA ISD Global Hourly station-year CSVs, which are
in `Freezing Rain Baseball Card/global_hourly_downloads/` (a copy also sits under Peak
Winds). It refuses to write an empty file if it finds none — an earlier version silently
overwrote good data with zero stations.

Geometry:

Two exceptions to the 2023 file, both because Storm Events codes counties differently:

- **Connecticut** uses its eight historical counties (09001–09015) from `cb_2021`. The 2023
  file has the nine planning regions (09110–09190) the Census adopted in 2022, which Storm
  Events does not use — with them, every Connecticut report was dropped.
- **Puerto Rico** is filed under state code 99, not 72. `storm_coverage.state_fips()` maps it
  to 72 from 2009 on; before 2009 PR rows carry forecast-zone numbers, not municipio codes,
  so they stay out.

```sh
M=mapshaper
$M cb_2023_us_county_500k.shp -filter '["60","66","68","69","78","09"].indexOf(STATEFP) === -1' \
   -filter-fields GEOID,NAME,STUSPS,ALAND,STATEFP -o rest.json format=geojson
$M cb_2021_us_county_500k.shp -filter 'STATEFP==="09"' \
   -filter-fields GEOID,NAME,STUSPS,ALAND,STATEFP -o ct.json format=geojson
# merge the two FeatureCollections, and move the part of Aleutians West (02016) east of
# 180 deg to negative longitudes (lon - 360) so it draws contiguously -> merged.json
$M merged.json -simplify 4% keep-shapes -each 'AREA = Math.round(ALAND/1e6)' \
   -filter-fields GEOID,NAME,STUSPS,AREA -rename-layers counties_raw \
   -o format=topojson geo/counties.topo.json
gzip -9 -k geo/counties.topo.json
```

The output is sparse and columnar — `ci` (county index), `yi` (year offset), `mi` (month),
and one count array per cumulative threshold — so the browser holds every county-year-month
cell in memory and recomputes means, trends and regressions on every control change.

`build_events_data.py` splits its output: the ranked lists plus a per-day county aggregate
(0.24–0.84 MB, always loaded) and the individual reports (0.6–3.9 MB, fetched only when the
reader switches to the points view).

Adding a hazard means adding an entry to `HAZARDS` in the relevant builder and re-running;
the pages read `data/index.json` and build their menus from whatever is there. Hazards carry
a `kind` (`station`, `event`, or absent for county) and the pages filter on it — filtering by
name broke twice as new hazards arrived.

## Caveat that matters

Storm Events is a **report** database, not a fixed observing network. National report counts
rose roughly 30-fold between 1955 and the late 1990s as population, spotter networks,
NEXRAD and NWS verification practice changed. Long-period trends therefore partly measure
the evolution of reporting. Trends from ~2000 on are much more defensible, and high
thresholds (≥2″ hail, EF2+ tornadoes) are far less sensitive to reporting practice than
"any report."

## Testing

Everything runs under node with jsdom (`npm i jsdom topojson-client`):

```sh
node test_scstrend.js        .        # climatology + trend page, Leaflet stubbed
node test_scstrend_grid.js   .        # 2 deg grid page
node test_scstrend_grid_audit.js .    # grid counts against an independent recomputation
node test_derecho.js         .        # the Derecho county climatology
node test_scsevents.js       .        # derecho archive + biggest-days lists
node test_scsdash.js         .        # county multi-hazard dashboard
```

What the suites are actually for, beyond "it renders": that the projection is not upside
down (it was once, and four visual checks missed it); that a zero-filled year is a real
zero while a masked month is not; that the smoother preserves NaN and does not change which
units are drawn; that switching hazard, threshold or state cannot strand the reader on a
selection that no longer exists; that the heavy per-report file is fetched only on demand;
and that a map is never built into a hidden container, which silently pins it at maximum
zoom.

## Extreme heat (ERA5)

Two hazards, both from the ECMWF **ERA5** reanalysis rather than reports:

| Key | What counts as a day | Thresholds |
|---|---|---|
| `heat` | daily maximum 2 m air temperature ≥ threshold | 90, 95, 100, 105 °F |
| `heatindex` | daily maximum NWS heat index ≥ threshold | 90, 100, 105, 110, 115 °F |

Hourly 2 m temperature and dewpoint, 0.25°, lower 48 (24–50 N, 125–66 W), 1950 onward, read
straight from NCAR's ERA5 copy on AWS (`nsf-ncar-era5`, ds633.0) with byte-range requests,
so only the chunks over the U.S. are downloaded (~50 MB per month). No account or key needed.

- **Heat index** follows the NWS procedure (simple formula; Rothfusz regression when the
  average of that and T is ≥ 80 °F; low- and high-humidity adjustments). RH from T and Td by
  the Magnus formula. `heatcalc.py`.
- **Days** run midnight to midnight local standard time, by longitude (UTC offset
  round(lon/15) h, halves rounded up). A day needs ≥ 16 of its 24 hours. Daily maxima are
  stored in tenths of °F **truncated**, so "stored ≥ threshold" is exactly "true value ≥
  threshold" (rounding had let 89.95 °F count as 90). UTC days, which the Indiana card used, end at 7 pm in Indiana and let one
  hot evening count on two days: about 4% more days at ≥90 °F, 10% more at ≥105 °F.
- **Counties**: each ERA5 cell gets its own day counts; a county's count is the
  area-weighted mean over the **land** cells it overlaps (ERA5 land–sea mask ≥ 0.5;
  `geo_heat/weights.json`, from the site's own county outlines and `geo_heat/lsm.nc`).
  Sea and lake cells carry marine temperatures; including them had pulled coastal counties
  far down (Galveston 54 → 31 days/yr ≥ 90 °F). The 4 counties on no land cell (Nantucket,
  Dukes, San Juan WA, Northampton VA) take the nearest land cell — the days a typical place in the county saw. State and national panels
  are the area-weighted mean over counties. Values are stored as integers: tenths
  of a day for counties and boxes (`meta.vscale` = 10), hundredths for state and national series
  (`meta.rscale` = 100); the pages divide them back out. Alaska, Hawaii and Puerto Rico are outside the domain and
  show as no data.
- **2° boxes**: the plain mean over the ERA5 land cells whose centres lie in a U.S. county in
  the box (252 boxes; six all-water boxes are not drawn).
- **Provisional last month.** Until the next month is published, the last local day of the
  newest month lacks its final 4–8 hours (from 16:00 LST on the Pacific coast), so that month
  is flagged `provisional` in `heat_counts/` and `meta.provisional`; `update_heat.py` redoes it
  once the next month is out.
- **No smoothing.** The heat maps are always drawn raw (the Smoothing control is hidden):
  ERA5 is already a continuous gridded field, so the 2° blur would only smear real contrasts
  such as desert against mountains.

**Validation.** Written independently of the Indiana heat-index card
(`Baseball Cards/Heat Index Baseball Card`), then run with that card's settings (UTC days,
May–Sep, its 21 × 21 box) for 2000, 2005, 2012 and 2024: day counts at every threshold agree
at all but 2 of ~86,000 point-days; daily maxima agree to 0.2 °F wherever HI ≥ 80 °F (the
two codes use different formulas below 80 °F, which no threshold reaches).

**Caveats** (on the pages too): ERA5's daily maximum is the warmest *hourly* value over a
~25 km cell, so counts run below single-station records, most in deserts and cities; trends
and geography are more trustworthy than the absolute numbers. Before ~1979 no satellite data
fed ERA5, so the earliest decades rest on fewer observations. **Heat index at 110/115 °F is
unreliable before ~1960**: early ERA5 has isolated one-hour dewpoint spikes (88 °F in Nebraska,
11 Jul 1954) that the heat index turns into 130–145 °F values; 1953–57 carry most of the
record's ≥ 130 °F cell-days. Not screened (the data are ERA5's own); flagged on the pages.
Credit: contains modified Copernicus Climate Change Service information; ERA5 is produced by
ECMWF.

**Independent audit (2026-10-19).** A separate reimplementation (own heat index, own
local-day grouping from raw hourly ERA5 at Phoenix, Houston/Gulf, 97.5 W, 82.5 W, a year end,
Nebraska 1954; own equal-area county weights; own box membership) reproduced the archive, the
counts, the boxes, the state/US series and the page JSON to within storage rounding, and
`update_heat.py` byte-for-byte. It found the coastal, rounding and truncated-last-day
problems fixed above.

### Building

```sh
# 1. daily maxima, one year per call (~10 min/yr; several in parallel is fine)
python3 era5_daily_max.py 2024            # -> daily/2024.npz (0.25°, tenths of °F)
# 2. monthly counts per county and 2° box
python3 build_heat_data.py counts daily heat_counts geo_heat/weights.json
# 3. the page files, merged into index.json and grid_index.json
python3 build_heat_data.py site heat_counts geo_heat/weights.json geo/counties.topo.json.gz data
```

`build_weights.py` makes `weights.json` from the county outlines (rerun if they change). It reads
`geo/counties.geojson` (the site's `geo/counties.topo.json.gz` converted to GeoJSON) and
`geo/lsm.nc` (ERA5 land–sea mask, kept as `geo_heat/lsm.nc`) relative to where it runs, and
writes `geo/weights.json`; copy that to `geo_heat/`.

### Monthly update

Needs `pip install numpy scipy fsspec aiohttp h5py`. The 0.25° daily archive (`daily/`,
~1.5 GB) is not kept in the repo; `heat_counts/` (one small file per year) is all the
update needs.

`update_heat.py heat_counts geo_heat/weights.json` processes the next month NCAR has
published (about a minute; `--max N` for several) straight into the counts, without the
0.25° daily archive; then rerun step 3. NCAR's AWS copy runs a month or two behind real time.

## Heavy rain (PRISM)

One hazard, `rain`: days whose **PRISM** daily precipitation total reached 1, 2 or 3 inches,
on PRISM's 4 km grid (PRISM Group, Oregon State University), lower 48, **1981 onward**
(PRISM's daily record).

- **No daily data are downloaded.** ACIS (grid 21 = PRISM) counts the days on its own server:
  one `GridData` request per year with `"interval":"mly","reduce":"cnt_ge_0.995"` (and
  1.995, 2.995) returns monthly day counts for every cell of the lower 48 — about 175 MB of
  JSON and 2–3 minutes per year. The Indiana card instead downloaded every daily value
  (2.5 GB for one state). `prism_fetch.py`.
- **Thresholds** are on the daily total rounded to hundredths of an inch, the precision rain is
  reported in (so `≥ 0.995`). That is what the card's download did, and it reproduces the card
  **exactly**: all 8,002 Indiana cells × 3 thresholds, 2000–2007, cell by cell. Testing the
  unrounded value instead (≥ 25.4 mm) gives about 0.8% fewer ≥ 1″ days.
- **A day** is PRISM's: the 24 hours ending 12 UTC (about 7 am EST), the cooperative
  observers' day.
- **Counties**: each PRISM cell counts its own days; a county's value is the area-weighted mean
  of the cells it overlaps (`geo_rain/weights.json`); state and national panels are the
  area-weighted mean over counties — the days a typical place saw, the statistic of the card's
  maps. (The card's *statewide time series* counted days on which **any** cell in Indiana
  reached the threshold, ~130 days/yr at ≥ 1″; that is not shown here.) PRISM is land-only, so
  no land mask is needed; a cell is used only if it has data in every month of the record.
- **2° boxes**: the plain mean over the PRISM cells whose centres lie in a lower-48 county.
- **Provisional months**: PRISM revises about the last six months as late reports arrive; they
  are flagged `provisional` in `rain_counts/` and fetched again by every update.
- **Caveats** (on the pages): PRISM interpolates whichever gauges reported each day, and that
  network changes over time, so trends carry some network uncertainty; a 4 km cell smooths the
  most intense local downpours.

### Building

```sh
# 1. per-cell monthly counts, one request per year (2-3 min each; 3 at a time is fine)
python3 prism_fetch.py 2024                 # -> cells/2024.npz (kept outside the repo)
python3 prism_fetch.py 2026 9               # a partial year: through September
# 2. county/box weights (needs cells/, geo/counties.geojson); copy geo/weights.json to geo_rain/
python3 build_rain_weights.py
# 3. per-year county and box counts, then the page files (merged into index.json etc.)
python3 build_rain_data.py counts cells rain_counts geo_rain/weights.json
python3 build_rain_data.py site rain_counts geo_rain/weights.json geo/counties.topo.json.gz data
```

`build_rain_data.py site` reuses `build_heat_data.py`'s site stage (same file format).

### Monthly update

`prism_update.py rain_counts geo_rain/weights.json` re-fetches every month from the oldest
provisional one through last month (one request per calendar year in that window, a minute or
two), rewrites the affected `rain_counts/<YEAR>.npz`, and exits 0 if anything was new or
revised (3 otherwise); then rerun the `site` step. Needs `numpy scipy requests`.

## Snowfall (COOP / first-order stations)

Station hazard `snow` ("Snowfall"): days with at least **1, 4, 6 or 12 inches** of new snow, over
a **July–June season** labelled by its ending year (1951 = 1950–51 … 2026 = 2025–26), at NOAA
Cooperative Observer and first-order stations (GHCN-Daily, through ACIS). No gridded product
estimates daily snowfall well enough for trends (PRISM has none; NOAA's National Gridded
Snowfall Analysis starts in the late 2000s; Kluver et al.'s 1° grid ends in 2009), so this is
station-based. CoCoRaHS is left out: its records mostly begin after 2000.

**Quality control**, after Kunkel et al. (2009, *JTECH* 26, 33–44), automated (`snow_qc.py`):

- *Days.* Trace = 0. A blank snowfall becomes 0 when precipitation was 0, or fell with Tmin
  above 32 °F (Kunkel's zero-fill). Accumulated multi-day values (A/S) are missing. Set to
  missing as suspect: > 60 in; ≥ 1 in with exactly 0.00 in precipitation; ≥ 4 in at a ratio
  above 60:1; ≥ 4 in equal to a snow depth already on the ground and not growing (depth keyed
  as snowfall).
- *Seasons* (a failed season is no observation, never zero): October–May ≥ 90% complete after
  zero-fill; no empty December, January or February; not *estimated* — EPA's screen: more than
  10 days with snow and precipitation, over half of them exactly 10:1.
- *Stations.* Shown with ≥ 30 valid seasons (7,086). The default **QC set** (1,499) also needs
  ≥ 60 of 76 seasons, ≥ 5 valid in 1951–60 and in 2017–26, and no break or drift against its
  neighbours: log ratio of seasonal totals to the median of up to 10 neighbours (≤ 200 km,
  ≤ 500 m elevation difference, each scaled to the station's mean); inhomogeneous if a Pettitt
  change point has p < 0.01 and a step > 20%, or a linear drift has p < 0.01 and > 5%/decade.
  That replaces Kunkel's seven-expert panel. Stations averaging < 3 in a season (549, mostly
  the South, where the 1″ threshold matters) cannot be tested that way and are kept on length.
- Every station's verdict, test statistics and membership of Kunkel's own 420-station set
  (NCAR ds510.5) are in `snow_station_qc.txt` (CSV). Of Kunkel's 393 stations that still have
  ≥ 30 seasons here, 193 pass, 122 fail the length rules (many closed or degraded after 2007,
  where Kunkel's period ends), and 78 show a break against neighbours.

Sanity check (mean seasonal snowfall, all valid seasons): Buffalo 94″, Syracuse 107″,
Denver 57″, Minneapolis 52″, Boston 43″, Indianapolis 25″, Seattle 8″, Atlanta 2″. QC-set mean
days per season 1951–2026: 7.0 at ≥ 1″ (trend −0.13/decade, p = 0.03), 1.6 at ≥ 4″, 0.7 at
≥ 6″, 0.09 at ≥ 12″ (no significant trend at the higher thresholds).

The lower panels average stations observed in ≥ 90% of the window's seasons, each season over
those that reported it (other station hazards require every year).

### Building (about an hour, in the cloud)

```sh
python3 snow_candidates.py          # station list per state -> candidates.json (~8,600 with >= 30 yr)
python3 snow_fetch.py 6             # daily snow, depth, precip, Tmin per station -> daily/*.npz (~45 min)
python3 snow_qc.py daily candidates.json data/snow.json.gz --report snow_report.json
python3 snow_index.py data/snow.json.gz data/index.json
```

Rebuild once a year, after a season ends (e.g. in August): COOP reports arrive with a lag, and
the homogeneity tests use the whole record.
