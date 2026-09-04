const BUILD='20260904c';
const fmt=(n,d=0)=>Number(n).toLocaleString(undefined,{maximumFractionDigits:d});
const el=(id)=>document.getElementById(id);
const num=(v)=>typeof v==='number'&&Number.isFinite(v);
const text=(v,f='n/d')=>(v===null||v===undefined||v==='')?f:v;
const mw=(v)=>num(v)?fmt(v,1)+' MW':'n/d';
const projectHref=(p)=>`./project/?slug=${encodeURIComponent(p.slug)}&v=${BUILD}`;
let projects=[];
Promise.all([
  fetch(`./data/projects.json?v=${BUILD}`,{cache:'no-store'}).then(r=>r.json()),
  fetch(`./data/credit_projects.json?v=${BUILD}`,{cache:'no-store'}).then(r=>r.json()),
  fetch(`./data/hy_projects.json?v=${BUILD}`,{cache:'no-store'}).then(r=>r.json())
]).then(([base,credit,hy])=>{
  const overrides=credit.overrides||{};
  const mergedBase=base.projects.map(p=>({...p,...(overrides[p.slug]||{})}));
  projects=[...mergedBase,...(credit.projects||[]),...(hy.projects||[])];
  el('asof').textContent='As of · '+(credit.as_of||hy.as_of||base.as_of);
  renderKPIs();renderBars();renderTable(projects);
});
fetch(`./data/news.json?v=${BUILD}`,{cache:'no-store'}).then(r=>r.json()).then(data=>{el('newsFeed').innerHTML=data.items.map(n=>`<a class="news" href="${n.url}" target="_blank" rel="noopener"><div><div class="ndate">${n.date}</div><div class="nsource">${n.source}</div></div><div class="nhead">${n.headline}</div><div class="ntag">${n.tag}</div></a>`).join('')});
function renderKPIs(){
  const total=projects.reduce((a,p)=>a+(num(p.critical_it_mw)?p.critical_it_mw:0),0);
  const debt=projects.reduce((a,p)=>a+(num(p.debt_amount_b)?p.debt_amount_b:0),0);
  const watch=projects.filter(p=>num(p.risk_score)&&p.risk_score>=50).length;
  const ig=projects.filter(p=>String(p.credit_bucket||'').startsWith('IG')).length;
  const hy=projects.filter(p=>String(p.credit_bucket||'').startsWith('HY')).length;
  const loan=projects.filter(p=>String(p.credit_bucket||'').includes('bank loan')).length;
  el('kpis').innerHTML=[['TRACKED PROJECTS',projects.length,`${ig} IG / IG-linked · ${hy} HY`],['CRITICAL IT',(total/1000).toFixed(2)+' GW','Known / disclosed capacity basis'],['PROJECT DEBT','$'+debt.toFixed(1)+'B',`${loan} bank-loan programs · bonds + project loans`],['WATCHLIST',watch+' projects','Power · permits · construction · credit']].map(x=>`<div class="card pad"><div class="label">${x[0]}</div><div class="big">${x[1]}</div><div class="sub">${x[2]}</div></div>`).join('');
}
function barRows(list,valKey,max,labelFn,live=false){if(!list.length||!max)return '<div class="pad sub">No comparable data.</div>';return list.map(p=>{const v=p[valKey];const liveV=num(p.live_mw)?p.live_mw:0;return `<a class="barrow barlink" href="${projectHref(p)}" aria-label="Open ${p.name} project page"><div class="barname">${p.name}</div><div class="bartrack"><div class="barfill" style="width:${v/max*100}%"></div>${live?`<div class="barlive" style="width:${liveV/max*100}%"></div>`:''}</div><div class="barval">${labelFn(p)}</div></a>`}).join('')}
function renderBars(){const byMW=projects.filter(p=>num(p.critical_it_mw)&&p.critical_it_mw>0).sort((a,b)=>b.critical_it_mw-a.critical_it_mw).slice(0,12);const byDebt=projects.filter(p=>num(p.debt_amount_b)&&p.debt_amount_b>0).sort((a,b)=>b.debt_amount_b-a.debt_amount_b).slice(0,12);const byCap=projects.filter(p=>num(p.capex_per_mw)&&p.capex_per_mw>0).sort((a,b)=>b.capex_per_mw-a.capex_per_mw).slice(0,12);el('capacityChart').innerHTML=barRows(byMW,'critical_it_mw',Math.max(...byMW.map(p=>p.critical_it_mw)),p=>mw(p.critical_it_mw),true)+`<div class="legend"><span><i class="dot cyan"></i>Tracked / contracted</span><span><i class="dot green"></i>Live</span><span>Click any project to open its deal page</span></div>`;el('debtChart').innerHTML=barRows(byDebt,'debt_amount_b',Math.max(...byDebt.map(p=>p.debt_amount_b)),p=>'$'+p.debt_amount_b.toFixed(p.debt_amount_b<1?2:1)+'B')+`<div class="legend">Known project debt; bank programs and bonds shown on the same scale. Click through for capital structure.</div>`;el('capexChart').innerHTML=barRows(byCap,'capex_per_mw',Math.max(...byCap.map(p=>p.capex_per_mw)),p=>text(p.capex_per_mw_display),false)+`<div class="legend">Disclosure bases vary; click a project for the precise $/MW definition and source notes.</div>`}
function riskPill(p){let c=p.risk_color==='green'?'green':(num(p.risk_score)&&p.risk_score>=75?'red':'amber');return `<span class="pill ${c}">${text(p.risk_label)}</span><div class="sub">${text(p.delay_view)}</div>`}
function creditCell(p){return `<div>${text(p.credit_bucket)}</div><div class="sub">${text(p.rating_display)} · ${text(p.financing_type)}</div>`}
function debtCell(p){return `<div>${text(p.debt_amount_display)}</div><div class="sub">${text(p.coupon_display)} · ${text(p.maturity)}</div>`}
function renderTable(rows){const tb=document.querySelector('#projectTable tbody');tb.innerHTML=rows.map(p=>`<tr data-slug="${p.slug}"><td><a class="projectlink" href="${projectHref(p)}"><div class="projname">${p.name}</div><div class="sub">${text(p.campus)} · ${text(p.location)}</div></a></td><td><div>${text(p.developer)}</div><div class="sub">${text(p.landlord)}</div></td><td><div>${text(p.tenant)}</div><div class="sub">${text(p.tenant_detail)}</div></td><td class="nowrap"><div>${mw(p.critical_it_mw)}</div><div class="sub">${num(p.live_mw)?fmt(p.live_mw,1)+' MW live':'n/d live'}</div></td><td><div>${text(p.capex_per_mw_display)}</div><div class="sub">${text(p.capex_total_display)}</div></td><td>${creditCell(p)}</td><td>${debtCell(p)}</td><td><div>${text(p.power_provider)}</div><div class="sub">${text(p.power_source)}</div></td><td>${text(p.delivery)}</td><td>${riskPill(p)}</td></tr>`).join('');tb.querySelectorAll('tr').forEach(tr=>tr.onclick=(e)=>{if(e.target.closest('a'))return;location.href=`./project/?slug=${encodeURIComponent(tr.dataset.slug)}&v=${BUILD}`})}
let asc=true,sortKey='name';document.querySelectorAll('#projectTable th').forEach(th=>th.onclick=()=>{const k=th.dataset.key;asc=k===sortKey?!asc:true;sortKey=k;const rows=[...projects].sort((a,b)=>{let x=a[k]??'',y=b[k]??'';if(typeof x==='number'&&typeof y==='number')return asc?x-y:y-x;return asc?String(x).localeCompare(String(y)):String(y).localeCompare(String(x))});renderTable(rows)});