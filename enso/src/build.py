#!/usr/bin/env python3
"""Build the three ENSO pages from this folder:  python3 enso/src/build.py  (from anywhere).

  ensogrid.tmpl.html  the page template. Blocks <!--X-->...<!--/X--> are kept only on the
                      pages whose letter is in X:  C = ensogrid.html (composites, public at
                      elninolanina.org), R = ensoreg.html (regression, hidden), F = ensofcst.html
                      (forecast, hidden), S = ensoscience.html (both science views behind two
                      tabs, 2026-11-13). Unmarked text goes on all four.
                      On S: a block marked S is kept as is; N drops it; any other C or R block in
                      the body is kept inside <v-c>/<v-r>, and the script removes the view not shown
                      (#view=reg picks the regression view at load); C/R/F blocks in the head and
                      F-only blocks are dropped.
  enso.js             the page script, inlined at /*__SCRIPT__*/ with REG / FCST set per page.

Each page ships as one file. The "Data last updated ..." stamp that update_stamps.py writes
into the built pages is carried over, so building never resets it.
    python3 enso/src/build.py --check    rebuild in memory and report any page that differs
"""
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.dirname(HERE)
PAGES = [('ensogrid', 'C', False, False), ('ensoreg', 'R', True, False), ('ensofcst', 'F', True, True),
         ('ensoscience', 'S', None, False)]
STAMP = re.compile(r'Data last updated [^<]*')

def build(letter, reg, fcst, old=None):
    h = open(os.path.join(HERE, 'ensogrid.tmpl.html')).read()
    js = open(os.path.join(HERE, 'enso.js')).read()
    head_end = h.index('</head>')
    def keep(m):
        L, body, nl = m.group(1), m.group(2), m.group(3)
        if letter != 'S': return body + nl if letter in L else ''
        if 'N' in L: return ''
        if 'S' in L: return body + nl
        if m.start() < head_end or not ('C' in L or 'R' in L): return ''
        if 'C' in L and 'R' in L: return body + nl
        tag = 'v-c' if 'C' in L else 'v-r'
        return '<%s>%s</%s>%s' % (tag, body, tag, nl)
    s = re.sub(r'<!--([CRFSN]+)-->(.*?)<!--/\1-->(\n?)', keep, h, flags=re.S)
    assert not re.search(r'<!--/?[CRFSN]+-->', s), 'unbalanced block marker'
    if letter == 'S':        # the science page picks its view at load
        js = js.replace('const REG=/*__REG__*/false;',
                        'const SCI_PAGE=true; const REG=/(^|[#&])view=reg(&|$)/.test(location.hash);')
    js = js.replace('const REG=/*__REG__*/false;', 'const REG=%s;' % ('true' if reg else 'false'))
    js = js.replace('const FCST=/*__FCST__*/false;', 'const FCST=%s;' % ('true' if fcst else 'false'))
    assert js.count('const REG=') == 1 and js.count('const FCST=') == 1 and '__REG__' not in js
    s = s.replace('/*__SCRIPT__*/', js)
    if old:                                   # keep the live data stamp
        m = STAMP.search(old)
        if m: s = STAMP.sub(lambda _: m.group(0), s)
    return s

if __name__ == '__main__':
    check = '--check' in sys.argv; bad = 0
    for name, letter, reg, fcst in PAGES:
        p = os.path.join(OUT, name + '.html')
        old = open(p).read() if os.path.exists(p) else None
        new = build(letter, reg, fcst, old)
        if check:
            same = new == old; bad += not same
            print(f'{name}.html: {"identical" if same else "DIFFERS"}')
        elif new != old:
            open(p, 'w').write(new); print('wrote', p)
        else:
            print(f'{name}.html unchanged')
    sys.exit(1 if bad else 0)
