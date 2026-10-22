import pandas as pd, numpy as np, glob, os, sys, pyarrow.parquet as pq
st=pd.read_csv('stl.csv',dtype=str).set_index('GHCN_ID')
y=sys.argv[1]; rows=[]
for f in glob.glob(f'cache/{y}/*.parquet'):
    sid=os.path.basename(f)[:-8]
    d=pq.read_table(f,columns=['DATE','temperature']).to_pandas()
    d=d[d.temperature.notna()]
    if d.empty: continue
    lon=float(st.loc[sid,'LONGITUDE']); off=int(np.floor(lon/15+0.5))
    t=pd.to_datetime(d.DATE)+pd.Timedelta(hours=off)
    day=t.dt.date; h=t.dt.hour
    nd=day.nunique()
    on=day[(h>=1)&(h<=5)].nunique()
    hrs=t.dt.floor('h').nunique()
    rows.append((sid,st.loc[sid,'ICAO'],st.loc[sid,'STATE'],st.loc[sid,'NAME'],nd,round(on/nd,3),round(hrs/nd,1)))
o=pd.DataFrame(rows,columns=['id','icao','state','name','days','night','hpd'])
o.to_csv(f'overnight_{y}.csv',index=False); print(len(o))
print(o.night.describe()); print(np.histogram(o.night,bins=[0,.05,.2,.5,.8,.9,.95,1.01]))
