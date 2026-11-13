#!/usr/bin/env python3
"""
Rewrite the "Data last updated …" stamp on every page from the data it actually loads.

    python3 update_stamps.py            # from the repo root (deploy_extremewxorg.sh runs it)
    python3 update_stamps.py --check    # print what would change, touch nothing

The stamps used to be typed by hand and went stale within a day (the landing page said
2026-10-08 while the derecho, TC and ENSO data were newer). Now each page's stamp is the
latest change to any of its data files: the file's last git commit time if it is
unchanged since that commit, or its modification time if it has uncommitted changes
(i.e. it is about to be deployed). The landing page takes the latest over the whole site.

A stamp is any element with class "dataupd" whose text starts "Data last updated".
A stamp that also carries data-for="<page>" (the per-card stamps on the landing page)
takes that page's stamp instead of its own page's.
"""
import os, re, subprocess, sys, datetime as dt

ROOT = os.path.dirname(os.path.abspath(__file__))
PAGES = {
    'index.html': ['scs/trends/data', 'tc/trends/data', 'enso/data', 'climate/data'],
    'enso/ensogrid.html': ['enso/data', 'scs/trends/data/grid_hail.json.gz', 'scs/trends/data/grid_tornado.json.gz',
                           'scs/trends/data/grid_wind.json.gz', 'scs/trends/data/grid_derechoday.json.gz'],
    'enso/ensoreg.html': ['enso/data', 'scs/trends/data/grid_hail.json.gz', 'scs/trends/data/grid_tornado.json.gz',
                          'scs/trends/data/grid_wind.json.gz', 'scs/trends/data/grid_derechoday.json.gz'],
    'enso/ensofcst.html': ['enso/data', 'scs/trends/data/grid_hail.json.gz', 'scs/trends/data/grid_tornado.json.gz',
                           'scs/trends/data/grid_wind.json.gz', 'scs/trends/data/grid_derechoday.json.gz'],
    'enso/ensoscience.html': ['enso/data', 'scs/trends/data/grid_hail.json.gz', 'scs/trends/data/grid_tornado.json.gz',
                              'scs/trends/data/grid_wind.json.gz', 'scs/trends/data/grid_derechoday.json.gz'],
    'climate/earthvis.html': ['climate/data', 'enso/data/tc_month.json.gz', 'scs/trends/data/grid_hail.json.gz',
                              'scs/trends/data/grid_tornado.json.gz', 'scs/trends/data/grid_wind.json.gz',
                              'scs/trends/data/grid_derechoday.json.gz'],
    'tc/trends/tctrend.html': ['tc/trends/data'],
    'scs/trends/scsdash.html': ['scs/trends/data'],
    'scs/trends/scsevents.html': ['scs/trends/data'],
    'scs/trends/scstrend.html': ['scs/trends/data'],
    'scs/trends/scstrend_grid.html': ['scs/trends/data'],
}
# class first, then (optionally) data-for, inside the same tag
STAMP = re.compile(r'(class="[^"]*\bdataupd\b[^"]*"(?![^>]*\bdata-for=)[^>]*>)Data last updated [^<]*(<)')
FOR = re.compile(r'(class="[^"]*\bdataupd\b[^"]*"[^>]*\bdata-for="([^"]+)"[^>]*>)Data last updated [^<]*(<)')


def git(*a):
    return subprocess.run(['git', '-C', ROOT, *a], capture_output=True, text=True).stdout


def files(paths):
    for p in paths:
        full = os.path.join(ROOT, p)
        if os.path.isdir(full):
            for dp, _, fs in os.walk(full):
                for f in fs:
                    if not f.startswith('.'):
                        yield os.path.relpath(os.path.join(dp, f), ROOT)
        elif os.path.exists(full):
            yield p


def changed(path, dirty):
    if path in dirty or path not in TRACKED:
        return dt.datetime.fromtimestamp(os.path.getmtime(os.path.join(ROOT, path)), dt.timezone.utc)
    t = git('log', '-1', '--format=%cI', '--', path).strip()
    return dt.datetime.fromisoformat(t).astimezone(dt.timezone.utc) if t else None


TRACKED = set(git('ls-files').split('\n'))
DIRTY = {l[3:].strip() for l in git('status', '--porcelain').split('\n') if l.strip()}
check = '--check' in sys.argv
STAMPS = {}
for page, paths in PAGES.items():
    times = [t for t in (changed(f, DIRTY) for f in files(paths)) if t]
    if times:
        STAMPS[page] = max(times).strftime('%Y-%m-%d %H:%M UTC')
for page, stamp in STAMPS.items():
    fn = os.path.join(ROOT, page)
    s = open(fn, encoding='utf-8').read()
    new, n = STAMP.subn(lambda m: f'{m.group(1)}Data last updated {stamp}{m.group(2)}', s)

    def per_card(m):
        st = STAMPS.get(m.group(2))
        if st is None:
            print(f'  ! {page}: data-for="{m.group(2)}" is not a page in PAGES')
            return m.group(0)
        return f'{m.group(1)}Data last updated {st}{m.group(3)}'
    new, k = FOR.subn(per_card, new)
    if n + k == 0:
        print(f'  ! {page}: no "Data last updated" stamp found')
    elif new != s:
        print(f'  {page}: {stamp}' + (f' (+{k} per-card)' if k else ''))
        if not check:
            open(fn, 'w', encoding='utf-8').write(new)
