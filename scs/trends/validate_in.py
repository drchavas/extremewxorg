import json,gzip,math,collections
old=json.load(gzip.open('fzra_isd_indiana.json.gz')); new=json.load(gzip.open('out/fzra.json.gz'))
def series(d):
    y0=d['meta']['year0']; out=collections.defaultdict(lambda:collections.defaultdict(lambda:[0,0,0]))
    for n,(si,yi,mi) in enumerate(zip(d['si'],d['yi'],d['mi'])):
        for k in range(3): out[si][y0+yi][k]+=d['v'][k][n]
    return out
so,sn=series(old),series(new)
tot=diff=0
for i,s in enumerate(old['stations']):
    j=min(range(len(new['stations'])),key=lambda j:math.hypot(new['stations'][j]['lat']-s['lat'],new['stations'][j]['lon']-s['lon']))
    t=new['stations'][j]
    vo=set(old['validYears'][str(i)]); vn=set(new['validYears'].get(str(j),[]))
    both=sorted(vo&vn); bad=[(y,so[i][y],sn[j][y]) for y in both if so[i][y]!=sn[j][y]]
    tot+=len(both); diff+=len(bad)
    print(f"{s['name'][:28]:28s} -> {t['name'][:26]:26s} dp {s['dp']}->{t['dp']}  seasons old {len(vo)} new {len(vn)} common {len(both)} differ {len(bad)} {bad[:3]}  only-new {sorted(vn-vo)}")
print('station-seasons compared',tot,'differ',diff)
