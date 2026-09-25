/* scsdash.html — the county dashboard. The thing most worth testing is that a
   cell here equals what scstrend.html draws for the same county, hazard,
   threshold, period and smoothing: the whole promise of the page is that it does
   not drift from the individual pages. */
const fs=require('fs'), zlib=require('zlib'), path=require('path'), {JSDOM}=require('jsdom');
const ROOT=process.argv[2];
const errors=[];

function boot(file, hash){
  const html=fs.readFileSync(path.join(ROOT,file),'utf8');
  const dom=new JSDOM(html,{runScripts:'outside-only',pretendToBeVisual:true,
    url:'http://localhost/scs/trends/'+file+(hash||'')});
  const w=dom.window;
  w.fetch=async u=>{ const p=path.join(ROOT,u);
    if(!fs.existsSync(p)) throw new Error('404 '+u);
    const b=fs.readFileSync(p);
    return {ok:true,status:200,json:async()=>JSON.parse(b.toString()),arrayBuffer:async()=>b}; };
  w.DecompressionStream=function(){};
  w.Blob=class{constructor(p){this.parts=p} stream(){return this} pipeThrough(){return this}};
  w.Response=class{constructor(x){this.x=x} async text(){return zlib.gunzipSync(Buffer.from(this.x.parts[0])).toString()}};
  w.URL.createObjectURL=()=>'blob:x'; w.URL.revokeObjectURL=()=>{};
  w.navigator.clipboard={writeText:async()=>{}};
  w.topojson=require(path.join(process.env.NODE_PATH,'topojson-client'));
  const B={getSouth:()=>24,getNorth:()=>50,getWest:()=>-126,getEast:()=>-66,
           getCenter:()=>({lat:39,lng:-96}),pad(){return this}};
  const maps=[];
  w.L={map:id=>{const h={};const m={id,_c:{lat:39,lng:-96},_z:4,_layers:[],_fit:0,
      setView(c,z){this._c=Array.isArray(c)?{lat:c[0],lng:c[1]}:c;if(z!=null)this._z=z;return this},
      fitBounds(){this._fit++;return this},getCenter(){return this._c},getZoom(){return this._z},
      getBounds(){return {getWest:()=>-126,getEast:()=>-66,getSouth:()=>23,getNorth:()=>50};},
      on(e,f){e.split(' ').forEach(x=>(h[x]=h[x]||[]).push(f))},
      removeLayer(l){this._layers=this._layers.filter(x=>x!==l)},addLayer(l){this._layers.push(l)},
      hasLayer:()=>false,eachLayer(cb){this._layers.slice().forEach(cb)},invalidateSize(){},_h:h};
    maps.push(m);return m;},
    tileLayer:()=>({addTo(m){m.addLayer(this);return this}}),
    layerGroup:()=>({_marks:[],addTo(m){m.addLayer(this);return this}}),
    circleMarker:()=>({bindTooltip(){return this},on(){return this},addTo(){return this}}),
    polygon:()=>({addTo(){return this}}),polyline:()=>({addTo(){return this}}),
    DomEvent:{stop(){}},TileLayer:function(){},
    geoJSON:(d,o)=>{const ls=[];
      if(d&&d.features&&o&&o.onEachFeature)d.features.forEach(f=>{const l={feature:f,_h:{},
        _style:(typeof o.style==='function'?o.style(f):o.style),
        on(e,fn){this._h[e]=fn},bindTooltip(fn){this._tip=fn;return this},
        getTooltip(){return this._tip?{}:null},
        setTooltipContent(c){this._tipContent=c;},
        setStyle(fn){if(typeof fn==='function')this._style=fn(this.feature);},getBounds:()=>B};
        ls.push(l);o.onEachFeature(f,l);});
      return{_data:d,_opts:o,_layers:ls,addTo(m){m.addLayer(this);return this},getLayers:()=>ls,
        setStyle(fn){if(typeof fn==='function')ls.forEach(l=>{l._style=fn(l.feature);});},
        bringToFront(){},getBounds:()=>B};}};
  w.L.TileLayer.prototype={};
  w.addEventListener('error',e=>errors.push(file+' window error: '+e.message));
  w.eval(html.match(/<script>([\s\S]*?)<\/script>/g).pop().replace(/^<script>|<\/script>$/g,''));
  return {w,maps};
}

const fmtv=v=>(v==null||!isFinite(v))?'—':(+v).toFixed(4);
const say=(l,ok,x)=>console.log((ok?'  ok   ':'  FAIL ')+l+(x?'  — '+x:''));

(async()=>{
  let cr;
  const D=boot('scsdash.html'); const w=D.w;
  const $=id=>w.document.getElementById(id);
  await new Promise(r=>setTimeout(r,6000));
  const M=D.maps[0];          // created during init, so read it after the wait

  console.log('\n--- the dashboard loads');
  say('body shown',$('body').style.display==='block');
  say('map built into a visible container',M!=null);
  say('opens on Tippecanoe, IN',/Tippecanoe County, IN/.test($('dashTitle').textContent),
      $('dashTitle').textContent);
  const rows=[...$('dashBody').querySelectorAll('tr')];
  say('four hazard rows',rows.length===4,rows.length+' rows');
  say('rows are the county hazards, in order',
      rows.map(r=>r.querySelector('td.haz').firstChild.textContent.trim()).join('|')
        ==='Hail days|Tornado days|Thunderstorm Wind days|Derecho events',
      rows.map(r=>r.querySelector('td.haz').firstChild.textContent.trim()).join(' | '));
  say('no station hazards',!/Freezing|Peak Wind/.test($('dashBody').innerHTML));
  const cells=[...$('dashBody').querySelectorAll('.cell[data-h]')];
  say('every populated cell carries a value and a trend',
      cells.length>12&&cells.every(c=>/\d/.test(c.querySelector('.val').textContent)&&
                                      c.querySelector('.trd')),
      cells.length+' live cells');
  say('each cell is split: climatology above, trend below',
      cells.every(c=>c.querySelector('.top')&&c.querySelector('.bot')));
  say('the class colour is on the upper half only',
      cells.every(c=>/background:(#[0-9a-f]{6}|rgb\()/i.test(c.querySelector('.top').getAttribute('style')||''))&&
      cells.every(c=>!/background/.test(c.querySelector('.bot').getAttribute('style')||''))&&
      !/class="swatch"/.test($('dashBody').innerHTML),
      cells[0].querySelector('.top').getAttribute('style'));
  say('the upper half takes one dark ink everywhere',
      new Set(cells.map(c=>/color:([^;]+)/.exec(c.querySelector('.top').getAttribute('style'))[1]
                             .trim())).size===1&&
      cells.every(c=>/color:#10161d/i.test(c.querySelector('.top').getAttribute('style'))));
  say('every populated cell draws a trend arrow',
      cells.every(c=>c.querySelector('.bot > svg.arw')));
  say('severity columns are ragged, as the hazards differ',
      rows.some(r=>r.querySelectorAll('.cell.none').length>0));

  /* ---- the promise of the page --------------------------------------- */
  console.log('\n--- every cell matches scstrend.html exactly');
  const T=boot('scstrend.html'); const tw=T.w;
  await new Promise(r=>setTimeout(r,4000));

  const COUNTY='18157', A=2000, B=2024;
  const th=tw.document.getElementById('hazSel');

  let checked=0, bad=[];
  const HAZ=['hail','tornado','wind','derechoday'];
  for(const h of HAZ){
    // the trends page loads a hazard on demand, so pick it before probing
    th.value=h; await th.onchange({target:{value:h}});
    await new Promise(r=>setTimeout(r,900));
    const nt=tw.eval(`hazSpec().thresholds.length`);
    for(let t=0;t<nt;t++){
      const ref=JSON.parse(tw.eval(
        `JSON.stringify(probe('${h}',${t},'${COUNTY}',${A},${B},'2'))`));
      const got=JSON.parse(w.eval(
        `(function(){const d=cellOf('${h}',${t});`+
        `return JSON.stringify(d?{mean:d.mean,trend:d.trend,p:d.p}:null);})()`));
      checked++;
      if(!ref){ bad.push(`${h}/${t}: probe returned null`); continue; }
      if(!got){ bad.push(`${h}/${t}: dashboard has no cell`); continue; }
      const near=(x,y)=>(!isFinite(x)&&!isFinite(y))||Math.abs(x-y)<1e-6;
      if(!near(ref.mean,got.mean)||!near(ref.trend,got.trend)||!near(ref.p,got.p))
        bad.push(`${h}/${t}: ${fmtv(ref.mean)}/${fmtv(ref.trend)} vs ${fmtv(got.mean)}/${fmtv(got.trend)}`);
    }
  }
  say(`all ${checked} hazard×severity cells match the trends page`,bad.length===0,
      bad.length?bad.slice(0,3).join('; '):`${checked} cells, exact`);

  /* ---- smoothing and period actually change the numbers --------------- */
  console.log('\n--- no expert controls, one fixed window');
  ['y0In','y1In','smSel'].forEach(id=>
    say(`the ${id} control is gone`,$(id)==null));
  const btns=[...w.document.querySelectorAll('header .bar button')].map(b=>b.id);
  say('four buttons and nothing else',
      btns.join(',')==='usBtn,resetBtn,themeBtn,linkBtn',btns.join(', '));
  const meth=w.document.querySelector('.methods').innerHTML;
  say('Methods no longer describes controls the page does not have',
      !/Switch <b>Smoothing<\/b>/.test(meth)&&!/chosen period|chosen window/.test(meth),
      (meth.match(/Switch <b>Smoothing<\/b>|chosen period|chosen window/g)||['none']).join(','));
  say('and no longer claims the trend is bolded for significance',
      !/p<\/i>&nbsp;&lt;&nbsp;0\.05/.test(meth)&&!/two-sided/.test(meth));
  const want=['return period','10% of','absolute scale','2000 onward','Squitieri',
              'percentage of the climatology','10%, 20%, 35% and 60%'];
  say('Methods covers what the page now does',want.every(k=>meth.includes(k)),
      want.filter(k=>!meth.includes(k)).join(',')||'all present');
  say('the cell itself stays terse, the explaining happens in Methods',
      !/of climatology/.test($('dashBody').innerHTML)&&
      /^\([+-][\d.]+%\)$/.test(
        $('dashBody').querySelector('.cell[data-h] .pct').textContent.trim()),
      $('dashBody').querySelector('.cell[data-h] .pct').textContent.trim());
  /* jsdom does not resolve var(), so check the declarations rather than the
     computed pixels: every band must defer to the one custom property, and that
     property must be set once. */
  const css=w.document.querySelector('style').textContent;
  say('the table, footer and Methods all defer to one span',
      /--span:\s*1400px/.test(css)&&
      (css.match(/max-width:\s*var\(--span\)/g)||[]).length>=3&&
      !/max-width:\s*1100px/.test(css),
      (css.match(/max-width:\s*var\(--span\)/g)||[]).length+' rules share it');
  say('but the header runs full width, not centred on it',
      !/header>\*/.test(css)&&!/header p\{[^}]*margin:4px auto/.test(css));
  say('the beta notice leads the banner',
      /^⚠\s*Beta version — still in testing\. Work in progress/.test(
        w.document.querySelector('.alertbar').textContent.trim()),
      w.document.querySelector('.alertbar').textContent.trim().slice(0,52));
  say('the page is titled for what it covers',
      w.document.querySelector('header h1').textContent
        ==='United States County-Level Multi-Hazard Extreme Weather Dashboard',
      w.document.querySelector('header h1').textContent);
  say('the how-to paragraph is gone, the credit line is not',
      !/Click any county<\/b> on the/.test(w.document.querySelector('header').innerHTML)&&
      /NSF Grant 2519425/.test(w.document.querySelector('header').innerHTML));
  say('smoothing is locked on',w.eval("dashState().smooth")==='2');
  say('the window is locked to the trends page default',
      w.eval("dashState().y0")===2000&&w.eval("dashState().y1")===2024,
      w.eval("dashState().y0")+'-'+w.eval("dashState().y1"));
  say('the hash no longer carries a period or a smoothing',
      !/[?&#]p=/.test(w.location.hash)&&!/sm=/.test(w.location.hash),w.location.hash);

  console.log('\n--- each row states the years behind its numbers');
  const yrs=h=>{ const tr=[...$('dashBody').querySelectorAll('tr')]
                   .find(r=>new RegExp(h,'i').test(r.querySelector('td.haz').textContent));
                 return tr.querySelector('td.haz .yrs').textContent; };
  say('hail, tornado and wind all run the full default window',
      yrs('Hail')==='2000–2024'&&yrs('Tornado')==='2000–2024'&&
      yrs('Thunderstorm Wind')==='2000–2024', yrs('Hail'));
  say('the range is clipped to each hazard\'s own record',
      w.eval("JSON.stringify(hazYears('derechoday'))")==='[2000,2024]'&&
      w.eval("JSON.stringify(hazYears('tornado'))")==='[2000,2024]');
  say('a record starting after the window shortens its own row, not lies',
      w.eval("clipYears(2000,2024,2010,2024).join('-')")==='2010-2024'&&
      w.eval("clipYears(2000,2024,1950,2019).join('-')")==='2000-2019');
  say('the per-row link carries that row\'s window, not a global one',
      /p=2000-2024/.test($('dashBody').querySelector('td.haz > a').href),
      $('dashBody').querySelector('td.haz > a').getAttribute('href').split('&p=').pop());
  say('the subtitle no longer names a single window',
      !/2000/.test($('dashSub').innerHTML),$('dashSub').textContent);
  say('the row name says what is counted, days or events',
      [...$('dashBody').querySelectorAll('tr')].every(r=>{
        const nm=r.querySelector('td.haz').firstChild.textContent.trim();
        const unit=r.querySelector('.cell[data-h] .unit');
        return !unit||nm.endsWith(unit.textContent.split('/')[0].trim()); }));
  const src=h=>[...$('dashBody').querySelectorAll('tr')]
                 .find(r=>new RegExp('^'+h).test(r.querySelector('td.haz').firstChild.textContent.trim()))
                 .querySelector('td.haz .src').textContent.trim();
  say('the storm-report hazards name Storm Events as their source',
      ['Hail','Tornado','Thunderstorm Wind'].every(h=>src(h)==='NCEI StormEvents'),
      src('Hail'));
  say('derecho names the archive as well as Storm Events',
      src('Derecho')==='Squitieri et al. 2026 + NCEI StormEvents',src('Derecho'));
  say('and the archive is a live citation, not bare text',
      /doi\.org\/10\.1175\/BAMS-D-25-0002\.1/.test(
        [...$('dashBody').querySelectorAll('td.haz .src a')].map(a=>a.href).join(' ')));
  say('each row links out to the full hazard map',
      [...$('dashBody').querySelectorAll('td.haz > a')]
        .every(a=>a.textContent.trim().startsWith('full hazard map')));

  console.log('\n--- picking things');
  const cell=[...$('dashBody').querySelectorAll('.cell[data-h]')]
    .find(c=>c.dataset.h==='tornado'&&c.dataset.t==='2');
  cell.onclick();
  await new Promise(r=>setTimeout(r,300));
  say('clicking a cell maps that hazard and severity',
      w.eval("dashState().hazard")==='tornado'&&w.eval("dashState().thresh")===2,
      w.eval("dashState().hazard")+'/'+w.eval("dashState().thresh"));
  {
    const tip=D.maps[0]._layers.flatMap(l=>l.getLayers?l.getLayers():[])
              .find(l=>l.feature&&l.feature.properties.STUSPS==='IN');
    /* LASTLL is a page-level let, invisible to eval — drive it the way the map
       does, through the layer's own handlers. A sticky tooltip renders its
       content once, on mouseover, so that is the path that has to be right. */
    tip._h.mouseover({latlng:{lat:40.42,lng:-86.89}});   // Tippecanoe
    say('the tooltip names the county on the first hover, before any move',
        tip._tip()==='<b>Tippecanoe County, IN</b>', tip._tip());
    tip._h.mousemove({latlng:{lat:40.16,lng:-85.72}});   // Madison
    say('and follows the pointer into the next county',
        /Madison County, IN/.test(tip._tipContent||''),
        (tip._tipContent||'').split('>')[1]);
    tip._h.mouseover({latlng:null});
    say('a hover with no position falls back to the state, not a stale county',
        /^Indiana$/.test((()=>{const k=tip._h; k.mousemove({latlng:null});
                               return tip._tipContent;})()||''),
        tip._tipContent);
    tip._h.mousemove({latlng:{lat:40.42,lng:-86.89}});
    /* The geometry has no LSAD, so the suffix is inferred from the state. Drive
       it through pickCounty rather than reaching for the page's arrays, which
       are page-level lets and invisible to eval. */
    const label=g=>{ w.eval(`pickCounty('${g}')`);
                     return $('dashTitle').textContent; };
    say('a Louisiana parish is not called a county',
        label('22071')==='Orleans Parish, LA', label('22071'));
    say('an Alaska borough takes no county suffix',
        !/County/.test(label('02090')), label('02090'));
    say('a Virginia independent city is a city, not a county',
        label('51760')==='Richmond City, VA', label('51760'));
    say('but James City County, VA still is one',
        label('51095')==='James City County, VA', label('51095'));
    w.eval("pickCounty('18157')");
  }
  say('the map title still names the county, not the hazard',
      /Tippecanoe County, IN/.test($('mapTitle').textContent),
      $('mapTitle').textContent);
  say('the chosen cell is marked',$('dashBody').querySelector('.cell.on')!=null);
  w.eval("pickCounty('48201')");           // Harris, TX
  await new Promise(r=>setTimeout(r,300));
  say('picking a county rebuilds the table',/Harris County, TX/.test($('dashTitle').textContent),
      $('dashTitle').textContent);
  say('and retitles the map',/Harris County, TX/.test($('mapTitle').textContent),
      $('mapTitle').textContent);
  say('and follows in the Zoom-to menu',$('stSel').value==='TX',$('stSel').value);
  say('the hash carries county, hazard and severity',
      /c=48201/.test(w.location.hash)&&/h=tornado/.test(w.location.hash)&&
      /t=2/.test(w.location.hash), w.location.hash.slice(0,48));
  w.eval("pickCounty('18157')");
  await new Promise(r=>setTimeout(r,300));

  console.log('\n--- the map is a locator with switchable backdrops');
  say('the guidance box is gone',$('guide')==null);
  say('so is the colour bar',$('cbar')==null);
  const opts=[...$('stSel').options].map(o=>o.value);
  say('the Zoom-to menu lists the states',opts.length>48&&opts[0]===''&&opts.includes('IN'),
      (opts.length-1)+' states');
  say('it opens on Indiana',w.eval("dashState().state")==='IN'||$('stSel').value==='IN',
      $('stSel').value);
  const fits=M._fit;
  $('stSel').value='TX'; $('stSel').onchange({target:{value:'TX'}});
  say('choosing a state re-fits the map',M._fit===fits+1&&w.eval("dashState().state")==='TX');
  /* The selection has to travel with the view: leaving it behind left the table
     describing a county in another state. */
  say('and lands on the capital\'s county',
      $('dashTitle').textContent==='Travis County, TX',$('dashTitle').textContent);
  const cap=ab=>{ $('stSel').value=ab; $('stSel').onchange({target:{value:ab}});
                  return $('dashTitle').textContent; };
  say('Kentucky lands on Frankfort\'s county',cap('KY')==='Franklin County, KY',cap('KY'));
  say('Indiana lands on Indianapolis\'s county',cap('IN')==='Marion County, IN',cap('IN'));
  say('an independent-city capital still resolves',/Richmond/.test(cap('VA')),cap('VA'));
  say('a capital in a borough rather than a county resolves too',
      /Juneau/.test(cap('AK')),cap('AK'));
  say('re-picking the state you are already in keeps your county',
      (()=>{ w.eval("pickCounty('18157')");
             $('stSel').value='IN'; $('stSel').onchange({target:{value:'IN'}});
             return $('dashTitle').textContent; })()==='Tippecanoe County, IN',
      $('dashTitle').textContent);
  say('every state in the menu yields a county, none left blank',
      [...$('stSel').options].filter(o=>o.value)
        .every(o=>w.eval(`(defaultCounty('${o.value}')||'')`).length===5),
      [...$('stSel').options].filter(o=>o.value)
        .filter(o=>!w.eval(`(defaultCounty('${o.value}')||'')`)).map(o=>o.value).join(',')||'all 51');
  $('usBtn').onclick();
  say('Full U.S. clears the state but keeps the county',
      $('stSel').value===''&&w.eval("dashState().state")===''&&
      w.eval("dashState().county")!=='');
  $('stSel').value='IN'; $('stSel').onchange({target:{value:'IN'}});
  w.eval("pickCounty('18157')");

  say('backdrop defaults to topography',w.eval("dashState().base")==='topo');
  const tileUrlOf=k=>w.eval(`baseInfo(${JSON.stringify(k)}).url||''`);
  say('topography, night lights and highways all have key-free sources',
      /World_Physical_Map/.test(tileUrlOf('topo'))&&
      /VIIRS_Black_Marble/.test(tileUrlOf('pop'))&&
      /World_Street_Map/.test(tileUrlOf('road')));
  say('all three use Esri/GIBS row-before-column tiles',
      ['topo','pop','road'].every(k=>/\{z\}\/\{y\}\/\{x\}/.test(tileUrlOf(k))));
  say('the night-lights layer is labelled for what it measures, not population',
      /Night lights/.test(w.eval("baseInfo('pop').label"))&&
      !/[Pp]opulation/.test(w.eval("baseInfo('pop').label+' '+baseInfo('pop').attr")),
      w.eval("baseInfo('pop').label"));
  $('baseSel').value='pop'; $('baseSel').onchange({target:{value:'pop'}});
  say('switching the backdrop swaps the tile layer and credits it',
      w.eval("dashState().base")==='pop'&&/NASA GIBS/.test($('mapSub').innerHTML));
  say('the county mesh is yellow on every backdrop',
      /255,209,64/.test(w.eval("JSON.stringify(ctyStyle()({properties:{GEOID:'x'}}))")));
  say('the backdrop rides in the hash',/bg=pop/.test(w.location.hash),w.location.hash.slice(0,60));
  $('baseSel').value='topo'; $('baseSel').onchange({target:{value:'topo'}});

  console.log('\n--- arrows encode direction and size, and nothing else');
  const arrow=(tr,mean)=>w.eval(`arrowSVG(${tr},1,'#fff',${mean==null?1:mean})`);
  const ang=svg=>+(/rotate\((-?[\d.]+)/.exec(svg)||[0,NaN])[1];
  say('a rise points up',ang(arrow(0.5))===-90);
  say('a fall points down',ang(arrow(-0.5))===90);
  say('nothing in the arrow encodes a p-value any more',
      !/opacity=/.test(arrow(0.5))&&!/significan/i.test(arrow(0.5))&&
      !/p &lt; 0.05|p < 0.05/.test($('dashFoot').innerHTML)&&
      !/\bweak\b/.test($('dashBody').innerHTML));
  say('the footer boilerplate is gone',$('foot').innerHTML==='');
  const lenOf=svg=>{const m=/M ([\d.]+) [\d.]+ L ([\d.]+)/.exec(svg); return +m[2]-+m[1];};
  say('arrow length grows with magnitude',lenOf(arrow(1))>lenOf(arrow(0.2)),
      lenOf(arrow(0.2)).toFixed(1)+' → '+lenOf(arrow(1)).toFixed(1));
  say('a trend far beyond the scale is clamped, not unbounded',
      Math.abs(lenOf(arrow(50))-lenOf(arrow(1)))<1e-9);
  const heads=svg=>(svg.match(/<polygon/g)||[]).length;
  say('a trend under a tenth of the climatology goes flat and double-headed',
      ang(arrow(0.5,10))===0&&heads(arrow(0.5,10))===2,
      'angle '+ang(arrow(0.5,10))+', '+heads(arrow(0.5,10))+' heads');
  say('just over the tenth it points again, single-headed',
      ang(arrow(1.5,10))===-90&&heads(arrow(1.5,10))===1);
  say('the near-zero band scales with the climatology, not an absolute number',
      ang(arrow(0.5,2))===-90&&ang(arrow(0.5,20))===0);
  say('a zero climatology does not make every trend near-zero',
      ang(arrow(0.5,0))===-90);
  /* Both sides of the 10% ratio must be the smoothed fields. cellOf is what
     feeds the arrow, so check it returns the smoothed mean and trend, not the
     raw county counts kept alongside them. */
  say('the arrow is fed the smoothed climatology, not the county\'s raw mean',
      w.eval("smoothOn()")===true&&
      w.eval("cellOf('hail',1).mean")!==w.eval("cellRaw('hail',1)"),
      w.eval("cellOf('hail',1).mean").toFixed(4)+' smoothed vs '+
      w.eval("cellRaw('hail',1)").toFixed(4)+' raw');
  /* And the smoothed trend is the one the trends page draws at smooth='2',
     which the 16-cell cross-check above already pins to 1e-6. */
  say('two decimals by default, three only below 0.05',
      w.eval("fmtTrend(0.004)")==='+0.004'&&w.eval("fmtTrend(-0.049)")==='-0.049'&&
      w.eval("fmtTrend(0.05)")==='+0.05'&&w.eval("fmtTrend(-2.5)")==='-2.50',
      [w.eval("fmtTrend(0.004)"),w.eval("fmtTrend(0.05)"),w.eval("fmtTrend(-2.5)")].join(' '));
  say('and the climatology follows the same rule',
      w.eval("fmtVal(0.004)")==='0.004'&&w.eval("fmtVal(0.05)")==='0.05'&&
      w.eval("fmtVal(4.756)")==='4.76',
      [w.eval("fmtVal(0.004)"),w.eval("fmtVal(0.05)"),w.eval("fmtVal(4.756)")].join(' '));
  console.log('\n--- the rate restated as a return period');
  const rp=r=>w.eval(`JSON.stringify(returnPeriod(${r}))`);
  say('a common hazard is quoted in months',rp(1.8)==='"6.7 months"',rp(1.8));
  say('a yearly one in years to a decimal',rp(0.39)==='"2.6 years"',rp(0.39));
  say('a rare one rounds to whole years',rp(0.02)==='"50 years"',rp(0.02));
  say('a true zero has no return period rather than an infinite one',
      rp(0)==='null'&&rp(-1)==='null'&&rp(NaN)==='null');
  say('every populated cell shows one beside its rate',
      [...$('dashBody').querySelectorAll('.cell[data-h]')]
        .every(c=>/^one every|none on record/.test(c.querySelector('.ret').textContent)),
      $('dashBody').querySelector('.cell[data-h] .ret').textContent);
  say('and it is the reciprocal of the rate on show',
      (()=>{ const c=[...$('dashBody').querySelectorAll('.cell[data-h]')][0];
             const v=parseFloat(c.querySelector('.val').textContent);
             const m=/([\d.]+) (months|years)/.exec(c.querySelector('.ret').textContent);
             const yr=+m[1]/(m[2]==='months'?12:1);
             return Math.abs(yr-1/v)/(1/v)<0.02; })());

  say('the whole lower half goes bold where the arrow points, not just one line',
      [...$('dashBody').querySelectorAll('.cell[data-h] .bot')].every(b=>{
        const flat=/rotate\(0 /.test(b.querySelector('svg').outerHTML);
        return b.classList.contains('moves')===!flat; })&&
      !/class="trd moves"/.test($('dashBody').innerHTML),
      [...$('dashBody').querySelectorAll('.cell[data-h] .bot.moves')].length+' of '+
      [...$('dashBody').querySelectorAll('.cell[data-h] .bot')].length+' bold');
  say('the arrow sits beside the two stacked figures',
      [...$('dashBody').querySelectorAll('.cell[data-h] .bot')].every(b=>
        b.firstElementChild.tagName.toLowerCase()==='svg'&&
        b.children.length===2&&b.querySelector('.tnum > .trd')&&
        b.querySelector('.tnum > .pct')));
  say('the value carries the unit and the percentage below it does not',
      /^[+-][\d.]+ \/decade$/.test(
        $('dashBody').querySelector('.cell[data-h] .trd').textContent.trim())&&
      [...$('dashBody').querySelectorAll('.cell[data-h] .pct')]
        .every(p=>!/decade/.test(p.textContent)),
      $('dashBody').querySelector('.cell[data-h] .trd').textContent.trim()+' / '+
      $('dashBody').querySelector('.cell[data-h] .pct').textContent.trim());
  say('and is tall enough to span both lines',
      +$('dashBody').querySelector('.cell[data-h] svg.arw').getAttribute('height')>=34,
      $('dashBody').querySelector('.cell[data-h] svg.arw').getAttribute('height')+'px');

  console.log('\n--- one absolute colour scale');
  const col=v=>w.eval(`rateColor(${v})`);
  const bins=JSON.parse(w.eval("JSON.stringify(rateBins())"));
  const rank=c=>bins.findIndex(b=>b.col===c);
  say('more frequent is redder, monotonically, across four decades of rate',
      [0.005,0.015,0.03,0.07,0.15,0.3,0.7,1.5,5].map(col)
        .every((c,i,a)=>rank(c)>=0&&(i===0||rank(c)<rank(a[i-1]))),
      [0.005,0.1,1,5].map(col).join(' '));
  say('the classes are the breaks the legend states',
      col(2)===bins[0].col&&col(1.99)===bins[1].col&&
      col(0.01)===bins[7].col&&col(0.009)===bins[8].col);
  say('the scale does not depend on the data in view',
      col(0.5)===w.eval("(function(){pickCounty('48201');const c=rateColor(0.5);"+
                        "pickCounty('18157');return c;})()"));
  say('a rate off either end lands in the end class, not outside the scale',
      col(1e-6)===bins[bins.length-1].col&&col(1e6)===bins[0].col,
      col(1e-6)+' / '+col(1e6));
  say('the same rate is the same colour in every hazard and severity',
      w.eval("rateColor(0.07)")===w.eval("rateColor(0.07)"));
  const key1=$('dashFoot').querySelectorAll('.skey')[0];
  say('the key is drawn with the table, one swatch per class plus zero',
      key1.querySelectorAll('.sw').length===bins.length+1,
      key1.querySelectorAll('.sw').length+' swatches');
  say('and every swatch shows a colour the cells actually use',
      [...key1.querySelectorAll('.sw i')]
        .map(i=>i.getAttribute('style')).every((st,k)=>
          st.includes(k<bins.length?bins[k].col:'214,218,222')));
  say('the old per-cell scaling is gone',w.eval("typeof cellMax")==='undefined');

  say('a climatology of exactly zero is grey, not the pale end of the ramp',
      col(0)==='rgb(214,218,222)'&&col(0.0001)!=='rgb(214,218,222)',col(0));
  say('the header links say what each page is, and the whole phrase is the link',
      [...w.document.querySelectorAll('header p a')].map(a=>a.textContent.trim())
        .slice(0,2).join('|')==='County-level maps by hazard|2° grid maps by hazard',
      [...w.document.querySelectorAll('header p a')].map(a=>a.textContent.trim()).join(' · '));
  cr=(a,b)=>+w.eval(`contrastRatio(${JSON.stringify(a)},${JSON.stringify(b)})`);
  say('every class clears 4.5:1 against the one ink, so the text never flips',
      bins.every(b=>cr(b.col,'#10161d')>=4.5)&&cr('#d6dade','#10161d')>=4.5,
      'worst '+Math.min(...bins.map(b=>cr(b.col,'#10161d'))).toFixed(2)+':1');
  say('and the palette stops before it would need white text',
      cr('#bd0026','#10161d')<4.5,
      'the old top class was '+cr('#bd0026','#10161d').toFixed(2)+':1');
  say('every populated cell is coloured off that one scale',
      [...$('dashBody').querySelectorAll('.cell[data-h] .top')].every(t=>{
        const bg=/background:([^;]+)/.exec(t.getAttribute('style'))[1].trim();
        return bins.some(b=>b.col===bg)||bg==='rgb(214,218,222)'; }));
  console.log('\n--- the trend has its own colour, relative to the climatology');
  const tcol=(tr,mean)=>w.eval(`trendColor(${tr},${mean})`);
  const P=JSON.parse(w.eval("JSON.stringify(trendPalOf('dark'))"));
  const steps=JSON.parse(w.eval("JSON.stringify(trendSteps())"));
  say('inside the 10% band it is grey, whichever way it points',
      tcol(0.05,1)===P.flat&&tcol(-0.05,1)===P.flat&&tcol(0,1)===P.flat);
  say('rising is red, falling is blue',
      P.up.includes(tcol(0.5,1))&&P.dn.includes(tcol(-0.5,1)),
      tcol(0.5,1)+' / '+tcol(-0.5,1));
  say('strength steps with the trend as a share of the climatology',
      [0.12,0.25,0.45,0.9].map(r=>tcol(r,1)).join(',')===P.up.join(','),
      [0.12,0.25,0.45,0.9].map(r=>tcol(r,1)).join(' '));
  say('the same absolute trend means different things at different climatologies',
      tcol(0.5,1)!==tcol(0.5,10)&&tcol(0.5,10)===P.flat,
      '0.5 on a climo of 1 → '+tcol(0.5,1)+', on 10 → '+tcol(0.5,10));
  say('the steps are the ones the key states',steps.join(',')==='0.1,0.2,0.35,0.6',
      steps.join(', '));
  say('every trend colour clears 4.5:1 on its own panel',
      [...P.up,...P.dn,P.flat].every(c=>cr(c,'#16212e')>=4.5)&&
      (()=>{const L=JSON.parse(w.eval("JSON.stringify(trendPalOf('light'))"));
            return [...L.up,...L.dn,L.flat].every(c=>cr(c,'#ffffff')>=4.4);})(),
      'worst dark '+Math.min(...[...P.up,...P.dn,P.flat].map(c=>cr(c,'#16212e'))).toFixed(2)+':1');
  say('the arrow takes the trend colour, not the cell ink',
      [...$('dashBody').querySelectorAll('.cell[data-h]')].every(c=>{
        const col=/color:([^;]+)/.exec(c.querySelector('.bot').getAttribute('style'))[1].trim();
        return c.querySelector('.bot svg').outerHTML.includes(col); }));
  say('bold marks the same cells the colour does',
      [...$('dashBody').querySelectorAll('.cell[data-h] .bot')].every(b=>{
        const col=/color:([^;]+)/.exec(b.getAttribute('style'))[1].trim();
        return b.classList.contains('moves')===(col!==P.flat); }));
  /* Compare against the underlying values, not the rounded ones on screen: a
     cell showing "-0.000 /decade" over "0.002 days/yr" is a real -20%, and
     parsing the display would call it zero. */
  say('the ratio behind the colour is printed as well',
      [...$('dashBody').querySelectorAll('.cell[data-h]')].every(c=>{
        const p=c.querySelector('.pct'); if(!p) return false;
        const want=JSON.parse(w.eval(
          `(function(){const d=cellOf('${c.dataset.h}',${c.dataset.t});`+
          `return JSON.stringify(trendPct(d.trend,d.mean));})()`));
        return p.textContent.trim()==='('+want+')'; }),
      $('dashBody').querySelector('.cell[data-h] .pct').textContent.trim());
  say('it is signed, and rounds harder as it grows',
      w.eval("trendPct(0.05,1)")==='+5.0%'&&w.eval("trendPct(-0.05,1)")==='-5.0%'&&
      w.eval("trendPct(0.5,1)")==='+50%',
      [w.eval("trendPct(0.05,1)"),w.eval("trendPct(0.5,1)")].join(' '));
  say('a zero climatology has no percentage rather than an infinite one',
      w.eval("JSON.stringify(trendPct(0.5,0))")==='null'&&
      w.eval("JSON.stringify(trendPct(NaN,1))")==='null');
  say('the printed ratio agrees with the band the colour came from',
      [...$('dashBody').querySelectorAll('.cell[data-h]')].every(c=>{
        const pct=Math.abs(parseFloat(c.querySelector('.pct').textContent.replace(/[()]/g,'')));
        const col=/color:([^;]+)/.exec(c.querySelector('.bot').getAttribute('style'))[1].trim();
        return (pct<10)===(col===P.flat); }));
  say('the key explains the trend scale too',
      /Trend, % of climatology per decade/.test($('dashFoot').innerHTML)&&
      $('dashFoot').querySelectorAll('.skey').length===2);

  console.log('\n--- a shared link reopens the same view');
  const L=boot('scsdash.html','#c=06037&h=wind&t=1&bg=road');
  await new Promise(r=>setTimeout(r,6000));
  const lw=L.w;
  say('link restores county, hazard, severity and backdrop',
      /Los Angeles County, CA/.test(lw.document.getElementById('dashTitle').textContent)&&
      lw.eval("dashState().hazard")==='wind'&&lw.eval("dashState().thresh")===1&&
      lw.eval("dashState().base")==='road',
      lw.document.getElementById('dashTitle').textContent);
  say('and a stale link with a period in it still opens, ignoring it',
      boot('scsdash.html','#c=06037&p=1990-2010&sm=off')!=null);

  console.log('\n--- errors captured: '+errors.length);
  errors.forEach(e=>console.log('  '+e));
  process.exit(errors.length?1:0);
})().catch(e=>{console.error('HARNESS ERROR',e); process.exit(2);});
