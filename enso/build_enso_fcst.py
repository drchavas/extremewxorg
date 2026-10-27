#!/usr/bin/env python3
"""Fetch NOAA CPC's official RONI outlook and write data/roni_fcst.json for ensofcst.html.

    python3 build_enso_fcst.py data            # run monthly, after CPC's update (2nd Thursday)

Source: https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/roni/outlook/
(the "Official NOAA Relative Oceanic Nino Index (RONI) Outlook"): for 9 upcoming,
overlapping 3-month seasons, the 5/15/25/50/75/85/95th percentiles of the forecast RONI.
CPC publishes it only as an HTML table, so this parses that table and checks it hard
(9 consecutive seasons, increasing percentiles, plausible values); if anything looks off
it stops without touching the existing file, so a changed page layout can't publish junk.

The first season's center month is the issue month (October 2026 issue: SON 2026 first,
centered on October); each later season moves one month on.
"""
import datetime as dt, html, json, os, re, sys, urllib.request

URL = 'https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/roni/outlook/'
LET = 'JFMAMJJASOND'
CODES = [LET[i] + LET[(i + 1) % 12] + LET[(i + 2) % 12] for i in range(12)]   # JFM .. DJF; index = first month - 1
PCTS = [5, 15, 25, 50, 75, 85, 95]
MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September',
          'October', 'November', 'December']


def fail(msg):
    sys.exit('build_enso_fcst: ' + msg + ' -- roni_fcst.json left unchanged')


def main(outdir):
    req = urllib.request.Request(URL, headers={'User-Agent': 'extremewx.org data build'})
    raw = urllib.request.urlopen(req, timeout=60).read().decode('utf-8', 'replace')
    s = re.sub(r'<!--.*?-->', ' ', raw, flags=re.S)                 # old issue dates sit in comments
    s = re.sub(r'<(script|style)\b.*?</\1>', ' ', s, flags=re.S | re.I)
    m = re.search(r'Issued\s+(' + '|'.join(MONTHS) + r')\s+(\d{4})', s)
    if not m:
        fail('no "Issued <Month> <Year>" on the page')
    iy, im = int(m.group(2)), MONTHS.index(m.group(1)) + 1
    rows = []
    for tr in re.findall(r'<tr\b.*?</tr>', s, flags=re.S | re.I):
        cells = [html.unescape(re.sub(r'<[^>]+>', ' ', c)).strip()
                 for c in re.findall(r'<t[dh]\b.*?</t[dh]>', tr, flags=re.S | re.I)]
        cells = [re.sub(r'\s+', ' ', c) for c in cells if c.strip()]
        if not cells or cells[0].split()[0] not in CODES:     # row header: "SON" + a "Sep Oct Nov" tooltip
            continue
        cells[0] = cells[0].split()[0]
        nums = []
        for c in cells[1:]:
            c = c.replace('−', '-')
            if re.fullmatch(r'-?\d+(\.\d+)?', c):
                nums.append(float(c))
        if len(nums) != 7:
            fail(f'season {cells[0]}: expected 7 percentiles, got {nums}')
        rows.append((cells[0], nums))
    if len(rows) != 9:
        fail(f'expected 9 seasons, found {len(rows)}')
    first = CODES.index(rows[0][0])                # first month of the first season, 0-based
    if (first + 1) % 12 != im - 1:
        fail(f'first season {rows[0][0]} is not centered on the issue month {MONTHS[im-1]}')
    seasons = []
    for k, (code, q) in enumerate(rows):
        if code != CODES[(first + k) % 12]:
            fail(f'season {k} is {code}, expected {CODES[(first + k) % 12]}')
        if any(b < a for a, b in zip(q, q[1:])) or not all(-4 < v < 5 for v in q):
            fail(f'season {code}: percentiles not increasing or implausible: {q}')
        cm = im + k                                 # center month, counted from the issue month
        cy, cmo = iy + (cm - 1) // 12, (cm - 1) % 12 + 1
        seasons.append({'code': code, 'center': f'{cy:04d}-{cmo:02d}',
                        'q': {str(p): v for p, v in zip(PCTS, q)}})
    out = {'source': URL, 'issued': f'{iy:04d}-{im:02d}',
           'fetched': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'seasons': seasons}
    path = os.path.join(outdir, 'roni_fcst.json')
    with open(path, 'w') as f:
        json.dump(out, f, indent=1)
    dj = next((x for x in seasons if x['code'] == 'DJF'), None)
    print(f'{path}: issued {MONTHS[im-1]} {iy}, {seasons[0]["code"]} {seasons[0]["center"]} .. '
          f'{seasons[-1]["code"]} {seasons[-1]["center"]}' +
          (f'; DJF centered {dj["center"]} median {dj["q"]["50"]:+.2f}' if dj else '; no DJF in range'))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'data')
