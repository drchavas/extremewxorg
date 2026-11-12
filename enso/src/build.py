#!/usr/bin/env python3
"""Build the three ENSO pages from this folder:  python3 enso/src/build.py  (from anywhere).

  ensogrid.tmpl.html  the page template. Blocks <!--X-->...<!--/X--> are kept only on the
                      pages whose letter is in X:  C = ensogrid.html (composites, public at
                      elninolanina.org), R = ensoreg.html (regression, hidden), F = ensofcst.html
                      (forecast, hidden). Unmarked text goes on all three.
  enso.js             the page script, inlined at /*__SCRIPT__*/ with REG / FCST set per page.

Each page ships as one file. The "Data last updated ..." stamp that update_stamps.py writes
into the built pages is carried over, so building never resets it.
    python3 enso/src/build.py --check    rebuild in memory and report any page that differs
"""
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.dirname(HERE)
PAGES = [('ensogrid', 'C', False, False), ('ensoreg', 'R', True, False), ('ensofcst', 'F', True, True)]
STAMP = re.compile(r'Data last updated [^<]*')

def build(letter, reg, fcst, old=None):
    h = open(os.path.join(HERE, 'ensogrid.tmpl.html')).read()
    js = open(os.path.join(HERE, 'enso.js')).read()
    s = re.sub(r'<!--([CRF]+)-->(.*?)<!--/\1-->(\n?)',
               lambda m: m.group(2) + m.group(3) if letter in m.group(1) else '', h, flags=re.S)
    assert not re.search(r'<!--/?[CRF]+-->', s), 'unbalanced block marker'
    js = js.replace('const REG=/*__REG__*/false;', 'const REG=%s;' % ('true' if reg else 'false'))
    js = js.replace('const FCST=/*__FCST__*/false;', 'const FCST=%s;' % ('true' if fcst else 'false'))
    assert js.count('const REG=') == 1 and js.count('const FCST=') == 1
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
