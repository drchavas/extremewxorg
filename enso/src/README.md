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

## Where things are in the template
- **Header text** (title, intro lines, NOAA links, feedback and email line): the `<header>` near the top of `<body>`.
- **"Quick answers"** (`id="faqBox"`) and **"Foundations: published research"** (`id="papersBox"`): collapsed boxes at the bottom. Both are ensogrid only.
- **Structured data:** `<script type="application/ld+json">` in the ensogrid `<head>`.
- **Methods, "How to read these maps", tooltips and panel text:** written by `enso.js` (`methodsHtml`, `guideHtml`, `writeTitles`, `boxPanel`, …).

## History
These sources first lived only in a cloud workspace, which was reset on 2026-11-12. They were rebuilt from the deployed pages, and `build.py --check` confirmed all three come out byte-identical. The earlier split of the script into `src_part1-5.js` and the generators for the papers box and Quick answers did not survive. The content they produced is now edited directly in the template.
