#!/usr/bin/env node
/* Build the data for the location page (enso/ensolocal.html):  node enso/src/build_local.js
   Run it whenever the ENSO data change (and it is cheap to run monthly with build_enso_fcst.py).

   It loads the SAME page script (enso.js, as the forecast page: REG and FCST on, the default
   settings) in a sandbox, so every number is computed by the code that draws the maps. For each
   field and calendar month it stores, per box, the regression on the Dec-Feb RONI that the
   forecast page maps:  mean (the climatology), bp, bn, mp, mn (map at RONI v = mapAt(fit, v))
   and pp, pn (the slope p-values; the page fades a cell when the side shown has p >= 0.05).
   Boxes the maps leave blank are left out. The location page then evaluates the fit at CPC's
   forecast, read live from data/roni_fcst.json, so a new outlook needs no rebuild.

   Output: enso/local/meta.json (fields, grids, per-month color domains) and
           enso/local/t/<lat10>_<lon10>.json, one file per 10° tile with data. */
const fs=require('fs'), path=require('path'), vm=require('vm');
const SRC=__dirname, ROOT=path.resolve(SRC,'..','..'), OUT=path.join(SRC,'..','local');

const el=new Proxy(function(){},{get:(t,k)=>k==='style'||k==='dataset'||k==='classList'?new Proxy({},{get:()=>()=>{}}):
  (k==='querySelectorAll'?()=>[]:(k==='appendChild'||k==='setAttribute'||k==='addEventListener'||k==='getContext')?()=>{}:''),set:()=>true});
const ctx={console,Math,JSON,Date,Promise,Set,Map,Proxy,Float32Array,Float64Array,Int32Array,Int16Array,Uint8Array,Uint8ClampedArray,
  Blob,Response,DecompressionStream,TextDecoder,URLSearchParams,setTimeout,clearTimeout,
  fetch:async url=>{ const p=path.join(ROOT,url.split('?')[0]);
    if(!fs.existsSync(p)) return new Response('',{status:404});
    return new Response(fs.readFileSync(p)); }};
ctx.window=ctx; ctx.window.addEventListener=()=>{}; ctx.window.innerWidth=1440;
ctx.document={getElementById:()=>el,querySelector:()=>el,querySelectorAll:()=>[],createElement:()=>el,
  documentElement:el,body:el,addEventListener:()=>{}};
ctx.location={hash:'',pathname:'/',hostname:'local'}; ctx.history={replaceState:()=>{}}; ctx.navigator={};
vm.createContext(ctx);

let js=fs.readFileSync(path.join(SRC,'enso.js'),'utf8')
  .replace('const REG=/*__REG__*/false;','const REG=true;').replace('const FCST=/*__FCST__*/false;','const FCST=true;');
if(!/\ninit\(\);\s*$/.test(js)) throw new Error('enso.js no longer ends with init(); update build_local.js');
js=js.replace(/\ninit\(\);\s*$/,'\n');
js+=`
;(async()=>{
  RONI=await (await fetch(ENSO_BASE+'data/roni.json')).json();
  RFC=await (await fetch(ENSO_BASE+'data/roni_fcst.json')).json();
  Object.assign(S,{dt:'on',sm:'on',base:'all',str:0.5,per:'all',pc:'pct',av:'mon',un:'C',mode:'diff'});
  /* the strength the color scales are set at: CPC's Dec-Feb median of the coming winter */
  const dj=RFC.seasons.find(q=>q.code==='DJF'); const vRef=dj?dj.q['50']:1.5;
  const ROWS=[['t2m',0],['pr',0],['sf',0],['tcd',0],['tornado',0],['hail',0],['wind',0]];
  const meta={built:new Date().toISOString().slice(0,16)+'Z',vRef,issued:RFC.issued,fields:[]}, tiles={};
  const q=v=>v==null||!isFinite(v)?null:+(+v).toPrecision(3);
  for(const [k,thr] of ROWS){
    S.f=k; S.thr=thr; S.ro=vRef; DS=await loadDS();
    const f=F(), g=DS.grid, months=[];
    for(let mi=0;mi<12;mi++){
      const X0=await DS.XK(mi), X=smoothOn()?smoothX(DS,X0):X0, win=windowYears(), n=win.length, NC=DS.NC;
      const xs=new Float64Array(n), ys=new Float64Array(n), rx=new Float64Array(n), det=S.dt==='on', cnt=isCount();
      const fits=new Array(NC).fill(null), clim=new Float32Array(NC).fill(NaN);
      for(let c=0;c<NC;c++){ let kk=0, any=false;
        for(const w of win){ const v=X[w.y*NC+c]; if(!isFinite(v)) continue; xs[kk]=w.Y; ys[kk]=v; rx[kk]=w.x; kk++; if(v!==0) any=true; }
        if(kk<3||(cnt&&!any)) continue;
        const st=regStats(xs.subarray(0,kk),ys.subarray(0,kk),rx.subarray(0,kk),det); if(!st||!isFinite(st.bp)) continue;
        fits[c]=st; clim[c]=st.mean; }
      /* the maps' blanking: snowfall below 0.01 mm/day; count boxes below 2% of the field's
         98th-percentile climatology (and no test below 5%) */
      let climRef=0;
      if(cnt){ const cv=[]; for(const v of clim) if(v>0) cv.push(v); cv.sort((a,b)=>a-b); climRef=quantile(cv,0.98); }
      const disp=[];
      for(let c=0;c<NC;c++){ const st=fits[c]; if(!st) continue;
        if(isSnow()&&!(st.mean>=0.01-1e-6)){ fits[c]=null; continue; }
        if(cnt&&!(st.mean>=0.02*climRef)){ fits[c]=null; continue; }
        st.noTest=cnt&&st.mean<0.05*climRef;
        const d=mapAt(st,vRef), den=pctDenom(st.mean,climRef);
        if(isFinite(den)) disp.push(Math.abs(100*d/den)); }
      /* the map's color domain for this month (ERA5: fixed per field; counts: 95th percentile) */
      let dom;
      if(f.src==='era5'){ S.pc=isTemp()?'abs':'pct'; dom=domains([]).diff; S.pc='pct'; }
      else { disp.sort((a,b)=>a-b); const hd=Math.min(niceUp(quantile(disp.filter(x=>x>0),0.95)),200); dom={lo:-hd,hi:hd,st:CMAP.div}; }
      /* mp, mn (mean of max(x,0), min(x,0) over the years) are the same for every box with the
         full record: store them once */
      const cnt2=new Map(); for(const st of fits) if(st){ const k2=st.mp+'|'+st.mn; cnt2.set(k2,(cnt2.get(k2)||0)+1); }
      const [mp0,mn0]=[...cnt2.entries()].sort((a,b)=>b[1]-a[1])[0][0].split('|').map(Number);
      months.push({mp:mp0,mn:mn0,climRef:q(climRef),lo:dom.lo,hi:dom.hi,cmap:Object.keys(CMAP).find(n=>CMAP[n]===dom.st),
                   nyears:n,y0:win[0].Y,y1:win[n-1].Y});
      for(let c=0;c<NC;c++){ const st=fits[c]; if(!st) continue;
        const la=DS.lat[c], lo=((DS.lon[c]%360)+360)%360, key=Math.floor(la/10)*10+'_'+Math.floor(lo/10)*10;
        const T=(tiles[key]=tiles[key]||{}), F2=(T[k]=T[k]||{}), id=DS.cells[c];
        const rec=[q(st.mean),q(st.bp),q(st.bn),st.noTest?null:q(st.pp),st.noTest?null:q(st.pn)];
        if(Math.abs(st.mp-mp0)>1e-9||Math.abs(st.mn-mn0)>1e-9) rec.push(st.mp,st.mn);   // a box missing years
        (F2[id]=F2[id]||new Array(12).fill(null))[mi]=rec; }
    }
    meta.fields.push({k,thr,label:menuItem()[2],src:f.src,grid:{lat0:g.lat0,lon0:g.lon0,g:g.g,nlat:g.nlat,nlon:g.nlon,global:g.global},
      ey0:DS.ey0,ey1:DS.ey1,months});
    console.log(k,'done', months.map(m=>m.lo+'/'+m.hi).join(' '));
  }
  __OUT(meta,tiles);
})().catch(e=>{ console.error(e); process.exitCode=1; });
`;
ctx.process=process;
/* tiles that touch land: any coastline vertex in the tile (grown by one tile edge of 2°),
   or the tile centre inside a land polygon */
function landTiles(){
  const t=JSON.parse(fs.readFileSync(path.join(ROOT,'enso','geo','countries-110m.json'),'utf8'));
  const [sx,sy]=t.transform.scale, [tx,ty]=t.transform.translate;
  const arcs=t.arcs.map(a=>{ let x=0,y=0; return a.map(([dx,dy])=>{ x+=dx; y+=dy; return [x*sx+tx,y*sy+ty]; }); });
  const ring=ids=>{ const out=[]; for(const i of ids){ const a=i<0?arcs[~i].slice().reverse():arcs[i]; out.push(...(out.length?a.slice(1):a)); } return out; };
  const polys=[]; for(const g of t.objects.land.geometries){
    const P=g.type==='Polygon'?[g.arcs]:g.type==='MultiPolygon'?g.arcs:[]; for(const p of P) polys.push(p.map(ring)); }
  const keep=new Set(), key=(la,lo)=>Math.floor(la/10)*10+'_'+Math.floor((((lo%360)+360)%360)/10)*10;
  for(const p of polys) for(const r of p) for(const [lo,la] of r)
    for(const dla of [-2,0,2]) for(const dlo of [-2,0,2]) if(Math.abs(la+dla)<90) keep.add(key(la+dla,lo+dlo));
  const inside=(x,y,r)=>{ let c=false; for(let i=0,j=r.length-1;i<r.length;j=i++){ const [xi,yi]=r[i],[xj,yj]=r[j];
    if((yi>y)!==(yj>y)&&x<(xj-xi)*(y-yi)/(yj-yi)+xi) c=!c; } return c; };
  for(let la=-90;la<90;la+=10) for(let lo=0;lo<360;lo+=10){ const cx=lo+5>180?lo+5-360:lo+5, cy=la+5;
    if(polys.some(p=>inside(cx,cy,p[0])&&!p.slice(1).some(h=>inside(cx,cy,h)))) keep.add(la+'_'+lo); }
  return keep;
}
ctx.__OUT=(meta,tiles)=>{
  const land=landTiles(); for(const k of Object.keys(tiles)) if(!land.has(k)) delete tiles[k];
  meta.tiles=Object.keys(tiles).sort();
  fs.mkdirSync(path.join(OUT,'t'),{recursive:true});
  fs.writeFileSync(path.join(OUT,'meta.json'),JSON.stringify(meta));
  let n=0, bytes=0;
  for(const [k,v] of Object.entries(tiles)){ const s=JSON.stringify(v); fs.writeFileSync(path.join(OUT,'t',k+'.json'),s); n++; bytes+=s.length; }
  console.log('wrote',n,'tiles,',(bytes/1e6).toFixed(1),'MB, meta',path.join(OUT,'meta.json'));
};
vm.runInContext(js,ctx,{filename:'enso.js'});
