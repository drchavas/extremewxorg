# ENSO page sources

The three ENSO pages in `enso/` are built from this folder. **Edit here, then build**; don't edit the built pages by hand, or the next build will overwrite the change.

| Built page | Template letter | What it is |
|---|---|---|
| `enso/ensogrid.html` | C | Composite maps. This is the public page, served at https://elninolanina.org/ |
| `enso/ensoreg.html` | R | Regression on RONI with a strength slider. Hidden (noindex) |
| `enso/ensofcst.html` | F | Month-by-month maps at CPC's forecast strength. Hidden (noindex) |

- **`ensogrid.tmpl.html`** is the HTML and CSS of all three pages.
  - Text inside `<!--X-->…<!--/X-->` goes only on the pages whose letter is in `X`, e.g. `<!--C-->` ensogrid only, `<!--RF-->` both hidden pages.
  - Unmarked text goes on all three.
- **`enso.js`** is the page script. It is inlined at `/*__SCRIPT__*/`, with `REG` (regression) and `FCST` (forecast) set per page.
- **`build.py`** builds the pages. It keeps the "Data last updated …" stamp that `update_stamps.py` wrote into each page.
  - `python3 enso/src/build.py` writes the three pages.
  - `python3 enso/src/build.py --check` reports whether they match the sources.
- **`check_seo.py`** checks two things the search-engine data depends on:
  - the FAQPage structured data in the `<head>` (JSON-LD) says exactly what the visible "Quick answers" box says;
  - every paper in the "Foundations: published research" box is listed as a `citation`.

  So if you edit a Quick answer or add or remove a paper, edit both places, then run the check.

## The location page (`enso/ensolocal.html`, hidden)
"How will El Niño & La Niña affect where you are?": type a place (Open-Meteo geocoding, or the browser's location), get a
table of hazards × the coming months, as % change (default) or expected amount, colored like the maps, pale where the
box's own fit has p ≥ 0.05. It is a hand-written page (no template), `noindex` and linked from nowhere yet.
- Its numbers come from **`build_local.js`** (`node enso/src/build_local.js`), which runs `enso.js` itself in a sandbox
  with the forecast page's settings (REG and FCST on, trend removed, count fields smoothed) and stores, per box and
  calendar month, the regression on the Dec–Feb RONI: climatology, the two slopes, and their p-values. Output:
  `enso/local/meta.json` (fields, grids, per-month color scales) and `enso/local/t/<lat>_<lon>.json` (10° tiles that
  touch land, ~11 MB). The page reads the fit at the Dec–Feb RONI of each month's ENSO year (observed, else CPC's
  median from `data/roni_fcst.json`), so a new CPC outlook needs no rebuild; rerun the builder when the ENSO data change
  (and it is cheap to run monthly). Checked 2026-11-12: 61 box-month values at 9 places match the forecast map page to
  the stored 3 significant figures.
- Rows: temperature (°C change), precipitation and snowfall (%), tropical-storm days (5° box), and for U.S. places
  tornado, hail and thunderstorm-wind days (2° box, all reports). A count or rain change is capped at −100%.
- **Redesign, 2026-11-13.** The page now leads with plain language; the table is behind "Detailed outlook →".
  - Headline "How is *El Niño* expected to change the weather where you are?" (the phase word follows the outlook);
    a large sentence "We are in the midst of a *very strong El Niño* … through mid-{Y+1} (NOAA)" (static in the
    HTML, rewritten by `fcStatement`).
  - Search: type-ahead suggestions (`suggest`, 220 ms debounce, Open-Meteo prefix match, cached per query), text
    after a comma filters by state/region/country (US state abbreviations mapped), postal codes work, a typo falls
    back to the name with its last letters dropped ("Did you mean"). Airports, parks, PPLX/historical places and
    ADM3+ are dropped.
  - Result card: `seasonSummary` for Dec–Feb and Mar–May (named Winter/Spring north of 23.5°N, Summer/Autumn south
    of 23.5°S, month names in the tropics) from the same cells as the table. Sizes: temperature <0.5 °C near normal,
    <1.5 °C a little, else a lot; precipitation/snow <10% / <25% / else; one step lower if fewer than 2 of the 3
    months have p < 0.05 of the same sign. Snow only where the season averages ≥ 0.25 mm/day of water. `seasonLine`
    groups the near-normal items ("Near-normal temperature and precipitation."). Month tiles and the table round
    to the degree and to 10%.
  - "View maps →" opens `ensoreg#f=t2m&r=<outlook rounded to 0.5>&m=djf&c=<lat,lon>`.
  - Look: Instrument Serif + DM Sans from Google Fonts; `.sky` layer (sun, rain streaks, drops); no banner.
  - `<meta name="version">` identifies the copy (`ensolocal-2026-11-13-v8` when it was deployed by hand).
- **Units (2026-11-13).** U.S. by default (°F, inches); the choice is shared with the map pages in `localStorage`
  key `ensoUnits` (`F`/`C`).

## Units on the map pages (2026-11-13)
`S.un` is `'F'` (U.S., default) or `'C'` (metric). `cvC`/`cvD` convert temperature to °F and the two water fluxes
(precipitation, snowfall) to in/month (× 30.44/25.4); `unitAbs` gives `in/month` or `mm/day`; `domains` swaps in round
in/month colour limits. The Units menu ("U.S. (°F, in)" / "Metric (°C, mm)") is shown for every ERA5 field. The choice
is saved in `localStorage` `ensoUnits` and read when a link has no `u=`; links carry `u=C` only for metric.

## extremewx.org → elninolanina.org (2026-11-13)
The template's first script sends a visit on `extremewx.org` (or `www.`) to the same page on elninolanina.org
(`/enso/`, `/enso/index`, `/enso/ensogrid` → `/`), keeping query and hash; `ensolocal.html` and `enso/index.html`
carry the same logic. Data files are not redirected (EarthVis reads them on extremewx.org).

## Where things are in the template
- **Header text** (title, intro lines, NOAA links, feedback and email line): the `<header>` near the top of `<body>`.
- **"Quick answers"** (`id="faqBox"`) and **"Foundations: published research"** (`id="papersBox"`): collapsed boxes at the bottom. Both are ensogrid only.
- **Structured data:** `<script type="application/ld+json">` in the ensogrid `<head>`.
- **Methods, "How to read these maps", tooltips and panel text:** written by `enso.js` (`methodsHtml`, `guideHtml`, `writeTitles`, `boxPanel`, …).

## History
These sources first lived only in a cloud workspace, which was reset on 2026-11-12. They were rebuilt from the deployed pages, and `build.py --check` confirmed all three come out byte-identical. The earlier split of the script into `src_part1-5.js` and the generators for the papers box and Quick answers did not survive. The content they produced is now edited directly in the template.

## The science page (`enso/ensoscience.html`, 2026-11-13, hidden)
"El Niño & La Niña Weather Effects: Science View": the composite and regression views on one page behind two
big tabs, **Composite view** and **Regression view** (Dan's names), with the Quick answers and Foundations boxes
under both. `ensogrid.html` and `ensoreg.html` stay as they were (Dan: keep the old pages).
- Built as a fourth page (`S`) by `build.py`. Template markers may now also carry `S` (kept on the science page as
  is) and `N` (dropped there). Other `C` / `R` blocks in the body are kept inside `<v-c>` / `<v-r>`; `C`/`R`/`F`
  blocks in the head and `F`-only blocks are left out.
- `REG` is decided at load: `#view=reg` is the regression view. At the top of `enso.js`, `SCI` (true only on this
  page) removes the other view's `<v-c>`/`<v-r>` blocks before anything reads the page and unwraps the rest.
- A tab click reloads the page in the other view, keeping the shared settings in the link (variable, threshold,
  season/month, period, units, smoothing, dots, contours, point, map view) and dropping the view-only ones
  (`ph`, `s`, `cp`, `b`, `r`). `writeHash` adds `view=reg`; "Reload default" keeps the view.
- The header is the composite page's and stays the same in both views (Dan): its intro block is marked `CS`, the
  regression intro `RN`; only what is below the tabs changes.
- `noindex` like the other hidden pages; `update_stamps.py` stamps it. The location page's "Deeper science view"
  opens its Regression tab.

## Background (2026-11-13)
In the light theme all four map pages use the location page's sky: a warm gradient (`html[data-theme="light"] body`),
and a `.sky` layer right after `<body>` with a sun at top left, rain streaks at right and drops toward the bottom
(`z-index:-1` inside the body's own stacking context, so it sits behind everything). The header is transparent there.
`applyTheme` leaves the light background to the stylesheet and sets the plain colour only in the dark theme.

## Forecast page: small outlook graph (2026-11-13)
Under the month buttons, `fcMiniSvg` draws CPC's most likely (50th percentile) RONI for each 3-month season of the
outlook (`data/roni_fcst.json`) as a small line graph, with the Dec–Feb value the maps use marked in red and labelled.
It follows the light/dark theme colours. The full fan chart (5–95%) stays in the panel further down.

