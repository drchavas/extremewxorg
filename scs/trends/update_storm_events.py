#!/usr/bin/env python3
"""
update_storm_events.py
----------------------
Bring the Baseball Cards source CSVs up to date with NOAA, so the build_*.py
scripts can extend the site past its last year. Run it, then rebuild (see README).

    python3 update_storm_events.py "/path/to/Baseball Cards"            # do it
    python3 update_storm_events.py "/path/to/Baseball Cards" --dry-run  # report only
    python3 update_storm_events.py "/path/to/Baseball Cards" --full     # refetch every year

Exit status: 0 = something changed, 3 = already current, other = error.

Storm Events (hail, tornado, thunderstorm wind)
    NCEI publishes one "details" file per year and re-issues it whenever a year is
    revised; the creation date is in the name (..._d2025_c20260819.csv.gz). This
    script remembers which file it used for each year in storm_events_coverage.json
    and refreshes a year when NCEI's file changes. By default only the three most
    recent years are watched (that is where revisions happen; --full refreshes all).

    The newest year is usually incomplete. Complete years go into
    <hazard>_events_complete_years.csv as before; the incomplete year goes into
    <hazard>_events_partial_year.csv, and its last published month is recorded as
    "partial_through". The builders mask the unpublished months (storm_coverage.py),
    so the pages show the months that exist without counting the rest as zero.
    A year counts as complete once it contains December.

ISD station files (freezing rain, peak wind)
    NOAA froze ISD on 24 Aug 2025 and moved the CSVs to the NODD bucket below.
    With --isd DIR the script fills in any station-year missing from DIR for the
    stations already there (a one-time catch-up, since the product no longer grows).
"""
import argparse
import csv
import datetime as dt
import gzip
import io
import json
import os
import re
import sys
import tempfile
import urllib.request

LISTING = "https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/"
ISD_URL = "https://noaa-global-hourly-pds.s3.amazonaws.com/{year}/{sid}.csv"
ISD_LAST_YEAR = 2025          # ISD frozen 2025-08-24
COVERAGE = "storm_events_coverage.json"
RECENT = 3

HAZARDS = {   # folder/file stem -> the EVENT_TYPE values it holds
    "Hail Days Baseball Card/hail_events":         {"Hail"},
    "Tornado Days Baseball Card/tornado_events":   {"Tornado"},
    "Tstm Winds Baseball Card/wind_events":        {"Thunderstorm Wind"},
}
NAME = re.compile(r"StormEvents_details-ftp_v1\.0_d(\d{4})_c(\d{8})\.csv\.gz")
csv.field_size_limit(1 << 30)


def get(url, timeout=120):
    req = urllib.request.Request(url, headers={"User-Agent": "extremewx.org updater"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def listing():
    """year -> newest details file name on the server."""
    html = get(LISTING).decode("utf-8", "replace")
    best = {}
    for m in NAME.finditer(html):
        y, c = int(m.group(1)), m.group(2)
        if y not in best or c > NAME.match(best[y]).group(2):
            best[y] = m.group(0)
    if not best:
        raise SystemExit("!! no StormEvents_details files found at " + LISTING)
    return best


def load_cov(root):
    p = os.path.join(root, COVERAGE)
    return json.load(open(p)) if os.path.exists(p) else {"files": {}}


def read_details(blob):
    """All rows of one yearly details file, as dicts of strings."""
    with gzip.open(io.BytesIO(blob), "rt", encoding="utf-8", errors="replace", newline="") as fh:
        return list(csv.DictReader(fh))


def rewrite(path, header, drop_years, new_rows):
    """Stream `path`, dropping rows whose YEAR is in drop_years, append new_rows,
    and replace the file atomically. Untouched rows keep their exact values."""
    tmp = path + ".tmp"
    yi = header.index("YEAR")
    kept = 0
    with open(tmp, "w", newline="", encoding="utf-8") as out:
        w = csv.writer(out)
        w.writerow(header)
        if os.path.exists(path):
            with open(path, newline="", encoding="utf-8", errors="replace") as fh:
                r = csv.reader(fh)
                next(r, None)
                for row in r:
                    if row and row[yi] not in drop_years:
                        w.writerow(row); kept += 1
        for d in new_rows:
            w.writerow([d.get(c, "") for c in header])
    os.replace(tmp, path)
    return kept


def header_of(path):
    with open(path, newline="", encoding="utf-8", errors="replace") as fh:
        return next(csv.reader(fh))


def storm_events(root, dry, full):
    cov = load_cov(root)
    have = {int(k): v for k, v in cov.get("files", {}).items()}
    server = listing()
    newest = max(server)
    watch = set(server) if full else {y for y in server if y > newest - RECENT}
    todo = sorted(y for y in watch if have.get(y) != server[y])
    print(f"NCEI newest year {newest}; watching {min(watch)}-{max(watch)}")
    for y in sorted(watch):
        print(f"  {y}: server {server[y]}  local {have.get(y, '-')}"
              f"{'  <- update' if y in todo else ''}")
    if not todo:
        return False
    if dry:
        return True

    rows = {}                     # year -> rows of that year (all event types)
    last_month = {}
    for y in todo:
        print(f"  downloading {server[y]} ...", flush=True)
        rows[y] = read_details(get(LISTING + server[y], timeout=600))
        ym = [int(r["BEGIN_YEARMONTH"]) for r in rows[y] if r.get("BEGIN_YEARMONTH", "").isdigit()]
        last_month[y] = max(ym) % 100 if ym else 0
        print(f"    {len(rows[y]):,} rows, through month {last_month[y]}")

    # The newest year is partial until it reaches December.
    if newest in last_month:
        partial = newest if last_month[newest] < 12 else None
    else:                                       # not refetched: keep what we knew
        partial = newest if (cov.get("partial_through") or "").startswith(str(newest)) else None
    complete_new = [y for y in todo if y != partial]
    every_year = {str(y) for y in range(1900, 2200)}

    for stem, types in HAZARDS.items():
        cpath = os.path.join(root, stem + "_complete_years.csv")
        ppath = os.path.join(root, stem + "_partial_year.csv")
        header = header_of(cpath)
        if complete_new:
            new_c = [r for y in complete_new for r in rows[y] if r.get("EVENT_TYPE") in types]
            # drop refreshed years, and the partial year should it ever have leaked in
            drop = {str(y) for y in complete_new} | ({str(partial)} if partial else set())
            kept = rewrite(cpath, header, drop, new_c)
            print(f"  {os.path.basename(cpath)}: kept {kept:,}, added {len(new_c):,}")
        if partial in rows:
            new_p = [r for r in rows[partial] if r.get("EVENT_TYPE") in types]
            rewrite(ppath, header, every_year, new_p)      # the file holds only this year
            print(f"  {os.path.basename(ppath)}: {len(new_p):,} rows ({partial} so far)")
        elif partial is None and os.path.exists(ppath):
            rewrite(ppath, header, every_year, [])         # its year is complete now
            print(f"  {os.path.basename(ppath)}: emptied (year now complete)")

    files = {str(k): v for k, v in have.items()}
    files.update({str(y): server[y] for y in todo})
    cov.update({
        "files": files,
        "complete_through": (partial - 1) if partial else newest,
        "partial_through": f"{partial}-{last_month[partial]:02d}" if partial in last_month
                           else (cov.get("partial_through") if partial else None),
        "updated": dt.datetime.now().isoformat(timespec="seconds"),
        "source": LISTING,
    })
    json.dump(cov, open(os.path.join(root, COVERAGE), "w"), indent=1)
    print(f"  wrote {COVERAGE}: complete through {cov['complete_through']}, "
          f"partial {cov['partial_through']}")
    return True


def isd(isd_dir, dry):
    have = {}
    for f in os.listdir(isd_dir):
        m = re.fullmatch(r"(\d{11})_(\d{4})\.csv", f)
        if m:
            have.setdefault(m.group(1), set()).add(int(m.group(2)))
    changed = False
    for sid, years in sorted(have.items()):
        for y in range(max(years) + 1, ISD_LAST_YEAR + 1):
            out = os.path.join(isd_dir, f"{sid}_{y}.csv")
            print(f"  ISD {sid} {y}{' (dry run)' if dry else ''}")
            if dry:
                changed = True; continue
            try:
                blob = get(ISD_URL.format(year=y, sid=sid), timeout=300)
            except Exception as e:
                print(f"    !! {e}"); continue
            with open(out + ".tmp", "wb") as fh:   # atomic: never leave a half file
                fh.write(blob)
            os.replace(out + ".tmp", out)
            changed = True
    return changed


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", help='the "Baseball Cards" folder')
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--full", action="store_true", help="refresh every year, not just the recent ones")
    ap.add_argument("--isd", metavar="DIR", help="also catch up the ISD station-year CSVs in DIR")
    a = ap.parse_args()
    changed = storm_events(a.root, a.dry_run, a.full)
    if a.isd:
        changed = isd(a.isd, a.dry_run) or changed
    print("changes found" if changed else "already current")
    sys.exit(0 if changed else 3)


if __name__ == "__main__":
    main()
