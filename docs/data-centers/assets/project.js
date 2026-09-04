const root=document.getElementById('projectRoot'),slug=document.body.dataset.projectSlug||new URLSearchParams(location.search).get('slug');
const dataBase=location.pathname.includes('/data-centers/projects/')?'../../data':'../data';
const text=(v,f='n/d')=>(v===null||v===undefined||v==='')?f:v;
const num=(v)=>typeof v==='number'&&Number.isFinite(v);
const mw=(v)=>num(v)?Number(v).toLocaleString(undefined,{maximumFractionDigits:1})+' MW':'n/d';
const pill=(p)=>`<span class="pill ${p.risk_color==='green'?'green':(p.risk_score>=75?'red':'amber')}">${text(p.risk_label)}</span>`;
Promise.all([
 fetch(`${dataBase}/projects.json`).then(r=>r.json()),
 fetch(`${dataBase}/credit_projects.json`).then(r=>r.json()),
 fetch(`${dataBase}/hy_projects.json`).then(r=>r.json())
]).then(([base,credit,hy])=>{
 const overrides=credit.overrides||{};
 const all=[...base.projects.map(p=>({...p,...(overrides[p.slug]||{})})),...(credit.projects||[]),...(hy.projects||[])];
 document.getElementById('asof').textContent='As of · '+(credit.as_of||hy.as_of||base.as_of);
 const p=all.find(x=>x.slug===slug);
 if(!p){root.innerHTML='<h1>Project not found</h1><p class="lede">Return to the project monitor and select a tracked deal.</p>';return}
 document.title=p.name+' — DC Intelligence';render(p);
}).catch(err=>{console.error(err);root.innerHTML='<h1>Project data unavailable</h1><p class="lede">Return to the project monitor and try again.</p>'});
function facts(rows){return rows.filter(x=>x[1]!==null&&x[1]!==undefined&&x[1]!=='').map(x=>`<div class="fact"><strong>${x[0]}</strong><span>${x[1]}</span></div>`).join('')}
function render(p){
 const milestones=p.milestones||[], evidence=p.evidence||[], sources=p.sources||[], watch=p.watch||[];
 root.innerHTML=`<div class="eyebrow">PROJECT INTELLIGENCE</div>
 <section class="card hero section"><div class="heroMain"><div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap"><h1>${p.name}</h1>${pill(p)}</div><div class="heroMeta">${text(p.campus)} · ${text(p.location)}</div><div class="thesis">${text(p.summary)}</div><div class="section"><div class="label">CURRENT DELAY / CREDIT VIEW</div><div class="big" style="font-size:18px">${text(p.delay_view)}</div></div></div>
 <div class="heroMetrics">${[
   ['CRITICAL IT',mw(p.critical_it_mw),num(p.live_mw)?mw(p.live_mw)+' live':'0 MW live'],
   ['PROJECT DEBT',text(p.debt_amount_display,text(p.capex_total_display)),text(p.coupon_display)+' · '+text(p.maturity)],
   ['TENANT',text(p.tenant),text(p.lease_term)],
   ['NEXT TEST',text(p.next_milestone_date),text(p.next_milestone)]
 ].map(x=>`<div class="metric"><div class="label">${x[0]}</div><div class="big">${x[1]}</div><div class="sub">${x[2]}</div></div>`).join('')}</div></section>
 <section class="section"><div class="eyebrow">SCHEDULE</div><h1>Critical path</h1><div class="card"><div class="timeline">${milestones.map(m=>`<div class="mile ${text(m.state,'watch')}"><div class="mdate">${text(m.date)}</div><div class="mlabel">${text(m.label)}</div><div class="mnote">${text(m.note)}</div></div>`).join('')}</div></div></section>
 <section class="grid two section">
  <div class="card"><div class="cardhead"><strong>Deal & build economics</strong><span>Comparable operating fields</span></div>${facts([
   ['Developer / landlord',text(p.developer)+' · '+text(p.landlord)],['Tenant / support',text(p.tenant)+' · '+text(p.tenant_detail)],['Contracted revenue',text(p.contracted_revenue_display)],['Critical / utility capacity',mw(p.critical_it_mw)+' / '+mw(p.utility_mw)],['Capital intensity',text(p.capex_per_mw_display)+' — '+text(p.capex_note)],['Delivery',text(p.delivery)]
  ])}</div>
  <div class="card"><div class="cardhead"><strong>Capital markets</strong><span>${text(p.credit_bucket)}</span></div>${facts([
   ['Instrument',text(p.financing_type,text(p.financing))],['Debt amount',text(p.debt_amount_display)],['Coupon / spread',text(p.coupon_display)],['Maturity',text(p.maturity)],['Rating',text(p.rating_display)],['Issue price',text(p.issue_price_display)],['Security',text(p.security_display)],['Structure note',text(p.capital_markets_note,text(p.financing))]
  ])}</div>
 </section>
 <section class="grid two section">
  <div class="card"><div class="cardhead"><strong>Power stack</strong><span>${text(p.grid)}</span></div>${facts([['Provider',text(p.power_provider)],['Source / infrastructure',text(p.power_source)],['Utility MW',mw(p.utility_mw)],['Cooling',text(p.cooling)]])}</div>
  <div class="card"><div class="cardhead"><strong>What we are watching</strong><span>Forward indicators</span></div><div class="pad"><ul class="watchlist">${watch.map(w=>`<li>${w}</li>`).join('')}</ul></div></div>
 </section>
 <section class="section"><div class="eyebrow">FORENSICS</div><h1>Evidence ledger</h1><p class="lede">Primary filings and dated observations are preserved as separate evidence. Positive evidence can offset a rumor; adverse evidence does not automatically equal a confirmed delay.</p><div class="card section">${evidence.map(e=>`<a class="ev" ${e.url?`href="${e.url}" target="_blank" rel="noopener"`:''}><div class="evdate">${text(e.date)}</div><div class="evsrc">${text(e.source)}<div class="sub">${text(e.weight)}</div></div><div class="evheadline">${text(e.headline)}</div><div class="evsignal">${text(e.signal)}</div></a>`).join('')}</div></section>
 <section class="section"><div class="eyebrow">SOURCE STACK</div><h1>Primary links</h1><div class="card section">${sources.map(s=>`<a class="source" href="${s.url}" target="_blank" rel="noopener"><strong>${text(s.name)}</strong><span>${text(s.type)} ↗</span></a>`).join('')}</div></section>`;
}