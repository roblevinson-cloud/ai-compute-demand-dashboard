const BUILD='20260904d';
const root=document.getElementById('researchRoot');
fetch(`../data/research_reports.json?v=${BUILD}`,{cache:'no-store'}).then(r=>r.json()).then(data=>{
  document.getElementById('asof').textContent='As of · '+data.as_of;
  const rows=[...(data.reports||[])].sort((a,b)=>String(b.sort_key).localeCompare(String(a.sort_key)));
  const orgs=[...new Set(rows.map(r=>r.organization))];
  const ib=rows.filter(r=>/Investment bank/i.test(r.type)).length;
  root.innerHTML=`<div class="grid kpis section"><div class="card pad"><div class="label">TRACKED REPORTS</div><div class="big">${rows.length}</div><div class="sub">Dated, source-linked industry research</div></div><div class="card pad"><div class="label">PUBLISHERS</div><div class="big">${orgs.length}</div><div class="sub">Banks, brokers, consultants and industry specialists</div></div><div class="card pad"><div class="label">BANK RESEARCH</div><div class="big">${ib}</div><div class="sub">Investment-bank / capital-markets pieces</div></div><div class="card pad"><div class="label">LATEST</div><div class="big" style="font-size:18px">${rows[0]?.organization||'n/d'}</div><div class="sub">${rows[0]?.date||''} · ${rows[0]?.title||''}</div></div></div><div class="card section">${rows.map(r=>`<a class="researchrow" href="${r.url}" target="_blank" rel="noopener"><div class="researchdate">${r.date}</div><div class="researchorg">${r.organization}</div><div class="researchtype">${r.type}</div><div><div class="researchtitle">${r.title}</div><div class="researchwhy">${r.why_it_matters}</div></div><div class="researchlink">Open report ↗</div></a>`).join('')}</div>`;
}).catch(err=>{console.error(err);root.innerHTML='<div class="card pad">Research library unavailable.</div>'});
