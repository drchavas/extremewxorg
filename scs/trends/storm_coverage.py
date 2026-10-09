"""
storm_coverage.py
-----------------
Shared by the Storm Events builders: how far the record runs, and the months of a
partly published final year that must be masked rather than read as zero.

update_storm_events.py keeps the Baseball Cards CSVs in two pieces per hazard:

  <hazard>_events_complete_years.csv   every year NOAA has published in full
  <hazard>_events_partial_year.csv     the current year so far (may be absent)

and writes storm_events_coverage.json next to them, e.g.

  {"complete_through": 2025, "partial_through": "2026-06", ...}

A month NOAA has not yet published is *no data*, exactly like June/July 1993, so it
goes into meta.gaps and the pages drop the year from means and trends while still
showing the months that do exist.
"""
import json
import os

import pandas as pd

COVERAGE = "storm_events_coverage.json"


def partial_path(path):
    return path.replace("_complete_years.csv", "_partial_year.csv")


def read_chunks(path, **kw):
    """Chunks of the complete-years CSV, then the partial-year CSV if present."""
    yield from pd.read_csv(path, **kw)
    extra = partial_path(path)
    if extra != path and os.path.exists(extra):
        yield from pd.read_csv(extra, **kw)


def coverage(root):
    """(year, last published month) of the partial year, or None."""
    p = os.path.join(root, COVERAGE)
    if not os.path.exists(p):
        return None
    t = json.load(open(p)).get("partial_through")
    if not t:
        return None
    y, m = (int(x) for x in t.split("-"))
    return y, m


def gaps(nodata, root):
    """NODATA plus the unpublished months of the partial year, sorted."""
    g = set(nodata)
    cov = coverage(root)
    if cov and cov[1] < 12:
        g |= {(cov[0], m) for m in range(cov[1] + 1, 13)}
    return sorted(g)


def through(root):
    """'YYYY-MM' when the record ends part-way through a year, else None."""
    cov = coverage(root)
    return f"{cov[0]}-{cov[1]:02d}" if cov and cov[1] < 12 else None


def last_year(root, y1):
    """The final year on the axis: the partial year counts even if a rare hazard
    has no report in it yet."""
    cov = coverage(root)
    return max(y1, cov[0]) if cov else y1


def selected(hazards):
    """Hazards to build this run. BUILD_ONLY=hail,wind limits a run to those, so a
    slow machine (or a time-limited shell) can rebuild one hazard at a time; the
    index files are merged, so the others are kept."""
    only = os.environ.get("BUILD_ONLY")
    if not only:
        return list(hazards)
    want = [h.strip() for h in only.split(",") if h.strip()]
    return [h for h in hazards if h in want]
