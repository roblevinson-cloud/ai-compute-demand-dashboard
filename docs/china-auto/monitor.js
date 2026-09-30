'use strict';
const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num=n=>n==null?'—':Number(n).toLocaleString('en-US',{maximumFractionDigits:0});
const pct=n=>n==null?'—':(n>=0?'+':'')+(100*n).toFixed(1)+'%';
const short=(n,m)=>n==null?'—':(m!=='units'?'$':'')+(Math.abs(n)>=1e9?(n/1e9).toFixed(2)+'bn':Math.abs(n)>=1e6?(n/1e6).toFixed(2)+'m':Math.abs(n)>=1e3?(n/1e3).toFixed(1)+'k':num(n));
const dateLabel=p=>new Date(p+'-01T00:00:00Z').toLocaleDateString('en-US',{month:'short',year:'numeric',timeZone:'UTC'});
const shift=(p,n)=>{let [y,m]=p.split('-').map(Number),v=y*12+m-1+n;return Math.floor(v/12)+'-'+String(v%12+1).padStart(2,'0')};
const colors={comtrade_china:'#176b8b',gacc_portal:'#27917c',comtrade_mirror:'#bb7430',cpca:'#8757a5'};
let D,byCountry,index;
function source(r,m){return r?.[m==='units'?'units_source':'value_source']}
function sourceText(s){return D.sources[s]?.label||'Not reported'}
function sourceLink(s,url){return s?`<a href="${esc(url||D.sources[s].url)}" target="_blank" rel="noopener">${esc(sourceText(s))}</a>`:'—'}
function isBreak(a,b,m){return !!(a&&b&&(source(a,m)!==source(b,m)||(m!=='units'&&a.value_basis!==b.value_basis)))}
function growth(a,b,m){return a?.[m]!=null&&b?.[m]>0?a[m]/b[m]-1:null}
function drawChart(rows,m){
 const W=Math.max(420,$('chart').clientWidth||1200),H=window.innerWidth<760?280:340,L=75,R=22,T=28,B=48,iw=W-L-R,ih=H-T-B,vals=rows.filter(r=>r[m]!=null),max=Math.max(1,...vals.map(r=>r[m]))*1.12;
 const x=i=>L+(rows.length===1?iw/2:i*iw/(rows.length-1)),y=v=>T+ih-v/max*ih;
 let svg=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc($('chartTitle').textContent)}"><title>${esc($('chartTitle').textContent)}</title>`;
 for(let i=0;i<5;i++){let v=max*i/4;svg+=`<line x1="${L}" x2="${W-R}" y1="${y(v)}" y2="${y(v)}" stroke="#e1eaf0"/><text x="${L-10}" y="${y(v)+4}" text-anchor="end" font-size="12" fill="#607887">${short(v,m)}</text>`}
 const tickStep=Math.max(1,Math.ceil(rows.length/(W<700?4:9)));rows.forEach((r,i)=>{if(i%tickStep===0||i===rows.length-1)svg+=`<text x="${x(i)}" y="${H-16}" text-anchor="middle" font-size="12" fill="#607887">${r.period}</text>`});
 rows.forEach((r,i)=>{
  if(r[m]==null)return;
  const s=source(r,m),c=colors[s]||'#537785',p=rows[i-1];
  if(p?.[m]!=null)svg+=`<line x1="${x(i-1)}" y1="${y(p[m])}" x2="${x(i)}" y2="${y(r[m])}" stroke="${c}" stroke-width="2.6" ${isBreak(r,p,m)?'stroke-dasharray="5 5"':''}/>`;
  if(p?.[m]!=null&&isBreak(r,p,m))svg+=`<line x1="${x(i)}" x2="${x(i)}" y1="${T}" y2="${T+ih}" stroke="#acb8c2" stroke-dasharray="3 5"/>`;
  svg+=`<circle cx="${x(i)}" cy="${y(r[m])}" r="4" fill="${c}" tabindex="0"><title>${r.period}: ${m!=='units'?'$':''}${num(r[m])}\n${esc(sourceText(s))}${r.qty_estimated?' · estimated quantity':''}${r.units_note?' · '+esc(r.units_note):''}</title></circle>`;
 });
 if(!vals.length)svg+=`<text x="${W/2}" y="${H/2}" text-anchor="middle" fill="#607887">No reported observations for this selection</text>`;
 svg+='</svg>';$('chart').innerHTML=svg;
 $('legend').innerHTML=[...new Set(vals.map(r=>source(r,m)))].map(s=>`<span><i class="dot" style="background:${colors[s]}"></i>${esc(sourceText(s))}</span>`).join('');
}
function selection(){const country=$('country').value;return (byCountry.get(country)||[]).filter(r=>r.period>=$('start').value&&r.period<=$('end').value)}
function render(){
 if($('start').value>$('end').value){$('scopeNote').textContent='Choose a start month on or before the end month.';return}
 const rows=selection(),m=$('metric').value,iso=$('country').value,vals=rows.filter(r=>r[m]!=null),last=vals.at(-1),name=iso==='WLD'?'World total':D.countries.find(c=>c.iso3===iso).country;
 $('chartTitle').textContent=`${name} · ${m==='units'?'export units':m==='value_usd'?'trade value (USD)':'customs value per unit'} · monthly`;
 $('latest').textContent=short(last?.[m],m);$('latestPeriod').textContent=last?dateLabel(last.period)+(last.period!==$('end').value?' · latest available; later months missing':''):'No observations';
 for(const [k,n] of [['mom',-1],['yoy',-12]]){
  let prior=last?index.get(iso+'|'+shift(last.period,n)):null,g=growth(last,prior,m),br=isBreak(last,prior,m)&&g!=null;
  $(k).textContent=pct(g)+(br?' †':'');$(k+'Note').textContent=g==null?'Comparison month unavailable':br?'Source/basis changed · not like-for-like':(m==='units'&&(last?.units_status==='reported_subtotal_lower_bound'||prior?.units_status==='reported_subtotal_lower_bound'))?'Includes a flagged quantity subtotal':'Calculated from stored monthly observations';
 }
 $('count').textContent=vals.length+' / '+rows.length;$('countNote').textContent='Months with selected metric · blanks stay blank';
 $('scopeNote').textContent=iso==='WLD'?(m==='units'?'One joined series: China-reported HS 8703 units through '+D.meta.china_reported_latest+'; CPCA passenger-vehicle exports including CKD kits thereafter. The January 2025 break changes both source and product scope. Do not interpret that step as organic growth. September 2020 is a reported-unit subtotal: reported quantities cover 99.9958% of export value; see the monthly table.':m==='value_usd'?'One joined FOB value series: China customs via UN Comtrade, extended by GACC via China Data Portal. All available months are shown; the source transition is marked.':'Value per unit is shown only when value and units share the same customs scope. It is intentionally blank when national industry units are paired with HS 8703 values.'):'One country series: China-reported exports first, then destination-reported imports where available. Arrival timing, CIF/FOB valuation and estimated quantities can change at the join. No report means missing, not zero. '+(last&&last.period!==$('end').value?'This country has not reported through your selected end month.':'');
 drawChart(rows,m);
 $('monthly').innerHTML=rows.slice().reverse().map(r=>`<tr><td>${r.period}</td><td>${num(r.units)}${r.qty_estimated?' <span class="tag">est.</span>':''}</td><td>${r.value_usd==null?'—':'$'+num(r.value_usd)}</td><td>${r.unit_value_usd==null?'—':'$'+num(r.unit_value_usd)}</td><td class="source">${sourceLink(r.units_source,r.units_source_url)}</td><td class="source">${sourceLink(r.value_source,r.value_source_url)}${r.value_basis?' · '+esc(r.value_basis):''}</td><td class="${r.status==='not_reported'?'missing':''}">${r.status==='not_reported'?'Not reported':r.units_status==='reported_subtotal_lower_bound'?'Subtotal · '+(100*r.quantity_value_coverage).toFixed(4)+'% value coverage':r.units_source==='cpca'?'Industry units / customs value':r.qty_estimated?'Estimated quantity':'Reported'}</td></tr>`).join('');
 renderRanking();
}
function renderRanking(){
 const p=$('rankMonth').value,m=$('metric').value,sort=$('rankSort').value,strict=$('comparable').checked;
 let rank=D.countries.map(c=>{const r=index.get(c.iso3+'|'+p),prev=index.get(c.iso3+'|'+shift(p,-12));let g=growth(r,prev,m),br=g!=null&&isBreak(r,prev,m);return{...c,r,prev,g,br,delta:g!=null?r[m]-prev[m]:null,last:(byCountry.get(c.iso3)||[]).filter(x=>x.period<=p&&x[m]!=null).at(-1)}});
 const available=rank.filter(x=>x.r?.[m]!=null).length,comparable=rank.filter(x=>x.g!=null&&!x.br).length;
 const score=x=>sort==='level'?x.r?.[m]:strict&&x.br?null:sort==='change'?x.delta:x.g;
 rank.sort((a,b)=>(score(b)??-Infinity)-(score(a)??-Infinity)||a.country.localeCompare(b.country));
 $('rankNote').textContent=`${dateLabel(p)}: ${available} of ${rank.length} destinations have ${m==='units'?'units':m==='value_usd'?'value':'value per unit'}; ${comparable} have a same-source year-earlier comparison. Rankings use only the selected month. A country's latest observation is shown separately and never substituted. `+(m==='units'?'Unit gains are export/import gains, not incumbent market-share losses.':'Value is FOB where available; otherwise import value, usually CIF.');
 $('ranking').innerHTML=rank.map(x=>{const suppress=strict&&x.br;return `<tr><td><a href="#chart" data-country="${esc(x.iso3)}">${esc(x.country)}</a></td><td>${x.r?.[m]==null?'—':(m!=='units'?'$':'')+num(x.r[m])}</td><td>${suppress?'Source break †':x.delta==null?'—':(x.delta>=0?'+':'')+num(x.delta)+(x.br?' †':'')}</td><td>${suppress?'—':pct(x.g)+(x.br?' †':'')}</td><td class="source">${esc(sourceText(source(x.r,m)))}${m!=='units'&&x.r?.value_basis?' · '+esc(x.r.value_basis):''}${x.r?.qty_estimated?' · estimated units':''}</td><td>${x.last?x.last.period+' · '+short(x.last[m],m):'Not reported'}</td></tr>`}).join('');
 document.querySelectorAll('[data-country]').forEach(a=>a.addEventListener('click',()=>{$('country').value=a.dataset.country;render()}));
}
function downloadRows(rows,name){
 const fields=[...new Set(rows.flatMap(r=>Object.keys(r)))];const q=v=>v==null?'':'"'+String(v).replace(/"/g,'""')+'"';
 const csv='\ufeff'+fields.map(q).join(',')+'\r\n'+rows.map(r=>fields.map(k=>q(r[k])).join(',')).join('\r\n');
 const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'})),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
fetch('data/series.json',{cache:'no-cache'}).then(r=>{if(!r.ok)throw new Error('Data request failed: '+r.status);return r.json()}).then(d=>{
 if(d.record_columns)d.records=d.records.map(values=>Object.fromEntries(d.record_columns.map((key,i)=>[key,values[i]])));
 D=d;byCountry=new Map([['WLD',D.world]]);for(const r of D.records){if(!byCountry.has(r.iso3))byCountry.set(r.iso3,[]);byCountry.get(r.iso3).push(r)}index=new Map([...D.world,...D.records].map(r=>[r.iso3+'|'+r.period,r]));
 $('country').insertAdjacentHTML('beforeend',D.countries.map(c=>`<option value="${esc(c.iso3)}">${esc(c.country)}</option>`).join(''));
 for(const id of ['start','end','rankMonth'])$(id).max=D.meta.latest_period;
 $('end').value=D.meta.latest_period;
 const broad=D.coverage.filter(c=>{const prev=D.coverage.find(x=>x.period===shift(c.period,-12));return c.china_destinations>0||(c.mirror_destinations>=30&&prev&&c.mirror_destinations/(prev.mirror_destinations||prev.china_destinations)>=.75)}).at(-1);
 // Prefer the latest month with broad coverage within the mirror period.
 const mirrorBroad=D.coverage.filter(c=>c.mirror_destinations>=70).at(-1);
 $('rankMonth').value=mirrorBroad?.period||broad?.period||D.meta.latest_period;
 $('coverageTitle').textContent=`${dateLabel(D.meta.start_period)} – ${dateLabel(D.meta.latest_period)} · ${D.meta.months} monthly observations`;
 $('coverageDetail').textContent=`Global value: ${D.meta.value_months}/${D.meta.months} months. Global units: ${D.meta.unit_months}/${D.meta.months} months. ${D.meta.unit_subtotal_months.length} historical unit subtotal flagged. Country coverage varies; every row has a source.`;
 $('coverageTable').innerHTML=D.coverage.slice().reverse().map(r=>`<tr><td>${r.period}</td><td>${r.china_destinations}</td><td>${r.mirror_destinations}</td><td>${r.unit_destinations}</td><td>${short(r.world_value_usd,'value_usd')}</td></tr>`).join('');
 $('updated').textContent='Built '+D.meta.built_at_utc.slice(0,10)+' · source snapshots '+D.meta.history_updated_at.slice(0,10)+' / '+D.meta.current_updated_at.slice(0,10);
 for(const id of ['country','metric','start','end'])$(id).addEventListener('change',render);
 for(const id of ['rankMonth','rankSort','comparable'])$(id).addEventListener('change',renderRanking);
 $('reset').addEventListener('click',()=>{$('start').value=D.meta.start_period;$('end').value=D.meta.latest_period;render()});
 $('downloadSelection').addEventListener('click',()=>downloadRows(selection(),`china-auto-${$('country').value}-${$('start').value}-${$('end').value}.csv`));
 window.addEventListener('resize',()=>drawChart(selection(),$('metric').value));
 $('loading').hidden=true;$('app').hidden=false;render();
}).catch(e=>{$('loading').textContent='Unable to load the monitor: '+e.message+'. The CSV files remain available in the data directory.';console.error(e)});
