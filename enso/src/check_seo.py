#!/usr/bin/env python3
"""Check that the FAQPage structured data in the template says exactly what the visible
"Quick answers" box says (search engines require it), and that every paper DOI in the
"Foundations" box is also listed as a Dataset citation.   python3 enso/src/check_seo.py"""
import os, re, json, html
T = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ensogrid.tmpl.html')).read()
ld = json.loads(re.search(r'<script type="application/ld\+json">\n(.*?)\n</script>', T, re.S).group(1).replace('<\\/', '</'))
g = {x['@type']: x for x in ld['@graph']}
box = T[T.index('id="faqBox"'):T.index('</details>', T.index('id="faqBox"'))]
vis = [(html.unescape(q), html.unescape(a)) for q, a in re.findall(r'<h3>(.*?)</h3>\s*<p>(.*?)</p>', box, re.S)]
faq = [(q['name'], q['acceptedAnswer']['text']) for q in g['FAQPage']['mainEntity']]
ok = vis == faq
print('Quick answers vs FAQPage:', 'match' if ok else 'MISMATCH', f'({len(vis)} visible, {len(faq)} structured)')
pap = T[T.index('id="papersBox"'):T.index('</details>', T.index('id="papersBox"'))]
dois = ['https://doi.org/' + __import__('urllib.parse').parse.unquote(d) for d in re.findall(r'href="https://doi.org/([^"]+)"', pap)]
cit = g['Dataset'].get('citation', [])
miss = [d for d in dois if d not in cit]; extra = [c for c in cit if c not in dois]
print(f'Foundations papers: {len(dois)}; Dataset citations: {len(cit)}; missing {len(miss)}; extra {len(extra)}')
for d in miss + extra: print('  ', d)
raise SystemExit(0 if ok and not miss and not extra else 1)
