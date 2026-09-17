# Extreme Weather: Maps and Trends — extremewx.org

The public site of interactive extreme-weather visualizations by
[Dan Chavas](https://web.ics.purdue.edu/~dchavas/) (Purdue University, EAPS).

**Live:** https://extremewx.org/

This repository is the *self-contained* source for the extremewx.org site. It holds only
the mature, public-facing tools (historical event viewers and climatology/trends). The
idealized-storm **research** tools and the **climate** animations are **not** here — they
live on the Purdue personal site (see "Relationship to other sites" below).

---

## Hosting & deployment

- **Repo:** `github.com/drchavas/extremewxorg`
- **Host:** Cloudflare Pages, connected to this repo (Build command: *none*; Build output
  directory: `/`). The custom domain `extremewx.org` is a `CNAME @ → extremewxorg.pages.dev`.
- **Deploy = git push.** Every push to `main` triggers an automatic Cloudflare Pages
  rebuild — live in a minute or two. No SFTP, no build step (it's a static site).

Convenience script (lives one level up, in the `Personal Website/` folder):

```
./deploy_extremewxorg.sh "commit message"   # commit + push → live
./deploy_extremewxorg.sh                     # auto-writes a commit message from the diff
./deploy_extremewxorg.sh --dry-run           # show what would change; touch nothing
```

Or plain git from inside this folder: `git add -A && git commit -m "…" && git push`.

---

## Structure

```
index.html            Landing page (the two sections below)
assets/               Purdue EAPS logo
skewt.js              Shared skew-T plotting helper
tc/                   Tropical cyclones
  ibtracs_viewer.html   (present but UNLINKED — the landing points to tcviewer.org instead)
  trends/
    tctrend.html        "Climatology & Trends — 5° grid" (linked from landing)
    tccard.html         redirect stub for the old filename → tctrend.html (unlinked)
    data/, geo/         pre-generated data + basemap (served)
    build_*.py, *.js    build/audit scripts (not served)
scs/                  Severe convective storms (+ other U.S. hazards)
  trends/
    scsevents.html      "Historical Severe Weather Events" (event viewer)
    scstrend.html       "Climatology & Trends — county level"
    scstrend_grid.html  "Climatology & Trends — 2° grid"
    data/, geo/         pre-generated data + basemaps (served)
    build_*.py, *.js    build/audit scripts (not served)
.gitignore            excludes raw source CSVs, .htaccess, OS junk
```

### The landing page (`index.html`) links to

**Tropical Cyclones**
- *Historical Event Viewer* → **[tcviewer.org](https://tcviewer.org/)** (external; the
  IBTrACS global track & wind-field viewer is its own site/repo — `drchavas/tcviewer`)
- *Historical Trends* → `tc/trends/tctrend.html` (the old `tccard.html` is a redirect stub
  that forwards to it, preserving query string and URL fragment)

**Severe Thunderstorms and Other Impactful Weather**
- *Historical Event Viewer* → `scs/trends/scsevents.html`
- *Historical Trends* → `scs/trends/scstrend.html` (county) and `scs/trends/scstrend_grid.html` (2° grid)

---

## Data

- Pages fetch small **pre-generated `data/*.json.gz`** files (committed here) plus basemaps
  in `geo/`. These are what the site serves.
- **Raw source CSVs** (NOAA/NCEI Storm Events, IBTrACS, etc.) are **git-ignored** — they
  exceed GitHub's 100 MB limit and aren't needed at runtime. Regenerate the `data/` files
  from raw sources with the `build_*.py` scripts in each `trends/` folder.
- The tropical-cyclone **event viewer** holds no local data — it links out to `tcviewer.org`,
  which serves the IBTrACS best-track data.

---

## What is intentionally NOT here

These stay on the Purdue site only (linked from `web.ics.purdue.edu/~dchavas/extremewx.html`):

- **Research (experimental) tools:** TC Wind Field Explorer, Idealized TC Track & Wind Swath,
  TC Ventilation Explorer, TC Potential Size, TC Potential Intensity Explorer (external, MIT-hosted,
  co-developed with Jonathan Lin, Cornell), Atlantic TC Landfall Risk Explorer, SCS Environmental
  Sounding Explorer, Sounding Plotter.
- **Climate:** Weather & Climate Data Visualization (earthvis — ERA5 seasonal-cycle animations).

If any of these should later move here, copy the page + its data into this repo and add a
link to `index.html`.

---

## Relationship to other sites

- **tcviewer.org** (`drchavas/tcviewer`) — the standalone TC track & wind-field viewer; this
  site links to it rather than hosting a copy.
- **web.ics.purdue.edu/~dchavas/extremewx.html** — the Purdue personal-site landing page. It
  points visitors here for maps & trends and keeps the research tools + climate animations.

---

## Updating

- **Content already here:** edit the file, then `./deploy_extremewxorg.sh "…"` (or `git push`).
- **New data:** run the relevant `build_*.py`, commit the updated `data/*.json.gz`, push.
- **New page:** add the `.html` (+ any `data/`), add a link in `index.html`, push.

## Notes

- `tc/ibtracs_viewer.html` is a leftover local copy and is currently unlinked (the landing
  uses tcviewer.org). It can be deleted.
- Local folder name is `extremewxorg/`; the GitHub repo and Cloudflare project are also
  `extremewxorg`; the public domain is `extremewx.org`.

---

## Handoff notes (for whoever — human or AI — works on this next)

**Where it lives:** `~/Dropbox/PurdueWebsite/Personal Website/extremewxorg/` on Dan's Mac.
This folder is its own git repo (`origin = github.com/drchavas/extremewxorg`).

**Publish workflow:** edit files here → `../deploy_extremewxorg.sh "message"` (or `git push`)
→ Cloudflare Pages auto-rebuilds → live at extremewx.org in ~1–2 min. There is **no build
step and no SFTP**; this is unlike the Purdue site.

**Landing-page style conventions** (`index.html`): dark theme via CSS variables
(`--bg/--panel/--line/--text/--accent/--accent2`); no top bar — the page opens straight
into a `.hero` with a gradient `h1`, a `.byline` (name + Purdue EAPS affiliation, text only,
no logo) and the `.subtitle`; then `<section>`s, each `<h2 class="sec-title">` (optional inline SVG `.ic`
icon) with `.cat` subheading labels and `ul.links > li > a.tool` + `span.desc`. Keep it
plain text — **no card/thumbnail artwork** (that was deliberately removed). External links
use `target="_blank" rel="noopener"` and a `<span class="ext">↗ external site</span>` marker.

**Editing cautions:**
- Use a normal text editor / file-edit tools. Do **not** run `perl` substitutions that
  introduce wide (non-ASCII) characters — an earlier edit double-encoded UTF-8 and turned
  `▾ • ©` into mojibake. After any edit that touches non-ASCII, verify the bytes look right.
- After edits, sanity-check that every `href` still resolves and that `<section>` open/close
  tags balance.
- Deleting files in this folder from an assistant sandbox may require enabling delete
  permission first.

**Scope reminder:** this site is non-research only. Research/experimental tools and the
climate animations deliberately stay on the Purdue site — don't add them here without a
reason. See the companion doc `Personal Website/README_extremewx_landing.md` for the Purdue
landing page.
