from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


def build_site(data: dict[str, Any], output: str | Path = "docs/index.html") -> None:
    p = Path(output); p.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, separators=(",", ":"), default=str).replace("</", "<\\/")
    title = html.escape(data["meta"]["title"])
    subtitle = html.escape(data["meta"]["subtitle"])
    page = TEMPLATE.replace("__TITLE__", title).replace("__SUBTITLE__", subtitle).replace("__DATA__", payload)
    p.write_text(page, encoding="utf-8")
    data_path = p.parent / "data" / "dashboard.json"
    data_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


TEMPLATE = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>__TITLE__</title>
  <script src="assets/plotly.min.js"></script>
  <style>
    :root{--bg:#07111f;--panel:#0e1b2d;--panel2:#12243a;--text:#ecf3fb;--muted:#9eb0c5;--line:#263b54;--cyan:#51d6e8;--violet:#9c8cff;--green:#66d9a5;--amber:#ffca6a;--red:#ff7d8a}
    *{box-sizing:border-box} body{margin:0;background:radial-gradient(circle at 15% 0%,#102944 0,#07111f 42%);color:var(--text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif}
    .wrap{max-width:1500px;margin:auto;padding:30px 24px 70px}.top{display:flex;justify-content:space-between;gap:20px;align-items:flex-start;margin-bottom:24px}
    h1{font-size:clamp(28px,4vw,48px);letter-spacing:-.04em;margin:0 0 8px}.subtitle{color:var(--muted);font-size:16px;max-width:900px}.meta{text-align:right;color:var(--muted);font-size:12px;line-height:1.6}
    .badge{display:inline-flex;align-items:center;gap:7px;padding:6px 10px;border:1px solid var(--line);border-radius:999px;background:#0b1727}.dot{width:8px;height:8px;border-radius:50%;background:var(--green)}
    .demo{background:#3b2610;color:#ffe3ad;border:1px solid #77501f;padding:10px 14px;border-radius:10px;margin:0 0 18px;display:none}
    .kpis{display:grid;grid-template-columns:repeat(5,minmax(160px,1fr));gap:14px;margin:18px 0}.card{background:linear-gradient(145deg,var(--panel2),var(--panel));border:1px solid var(--line);border-radius:16px;padding:17px;box-shadow:0 12px 35px #0003}
    .label{text-transform:uppercase;letter-spacing:.09em;color:var(--muted);font-size:11px}.value{font-size:30px;font-weight:720;margin-top:7px;letter-spacing:-.03em}.delta{font-size:12px;margin-top:5px;color:var(--muted)}
    .grid{display:grid;grid-template-columns:2fr 1fr;gap:14px}.span2{grid-column:span 2}.chart{height:390px}.chart.tall{height:470px}.section-title{font-size:16px;margin:0 0 4px}.section-note{font-size:12px;color:var(--muted);margin-bottom:8px}
    table{border-collapse:collapse;width:100%;font-size:12px}th,td{text-align:left;border-bottom:1px solid var(--line);padding:9px 7px}th{color:var(--muted);font-weight:600}.status{padding:3px 7px;border-radius:999px;background:#173226;color:#9cf1c7}.status.stale{background:#392b16;color:#ffd389}.status.demo{background:#372c60;color:#cfc5ff}.status.error{background:#481f2a;color:#ffb1bc}
    .method{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:14px}.method p{font-size:13px;color:var(--muted);line-height:1.55}.method b{color:var(--text)}
    footer{color:var(--muted);font-size:11px;line-height:1.6;margin-top:30px;border-top:1px solid var(--line);padding-top:16px}
    @media(max-width:1000px){.kpis{grid-template-columns:repeat(2,1fr)}.grid{grid-template-columns:1fr}.span2{grid-column:auto}.method{grid-template-columns:1fr 1fr}.top{display:block}.meta{text-align:left;margin-top:12px}}
    @media(max-width:600px){.kpis,.method{grid-template-columns:1fr}.wrap{padding:20px 12px}.chart{height:330px}}
  </style>
</head>
<body>
<div class="wrap">
  <div class="top"><div><h1>__TITLE__</h1><div class="subtitle">__SUBTITLE__</div></div><div class="meta"><span class="badge"><span class="dot"></span><span id="freshness">Built</span></span><br><span id="generated"></span></div></div>
  <div class="demo" id="demoBanner"><b>Demonstration mode.</b> The bundled series is synthetic and exists only to preview the interface. Live collectors never fabricate missing observations.</div>
  <div class="kpis">
    <div class="card"><div class="label">Workload index</div><div class="value" id="kWork">—</div><div class="delta" id="dWork">Observed token workload</div></div>
    <div class="card"><div class="label">Physical compute index</div><div class="value" id="kCompute">—</div><div class="delta" id="dCompute">Estimated H100-equivalent use</div></div>
    <div class="card"><div class="label">Tightness index</div><div class="value" id="kTight">—</div><div class="delta">Price + latency − availability</div></div>
    <div class="card"><div class="label">Capacity index</div><div class="value" id="kCapacity">—</div><div class="delta">Operational H100-equivalents</div></div>
    <div class="card"><div class="label">Efficiency index</div><div class="value" id="kEfficiency">—</div><div class="delta">Tokens per estimated H100-hour</div></div>
  </div>
  <div class="grid">
    <div class="card span2"><h2 class="section-title">Workload versus physical compute</h2><div class="section-note">Indices are normalized to 100 over the opening base period. Compute uses configurable model weights.</div><div id="mainChart" class="chart tall"></div></div>
    <div class="card"><h2 class="section-title">Observed token throughput</h2><div class="section-note">OpenRouter traffic only unless a separately labeled global anchor is supplied.</div><div id="tokensChart" class="chart"></div></div>
    <div class="card"><h2 class="section-title">Latest model mix</h2><div class="section-note">Top model shares on the most recent observed day.</div><div id="mixChart" class="chart"></div></div>
    <div class="card"><h2 class="section-title">GPU rental market</h2><div class="section-note">Median $/GPU-hour and observable units available.</div><div id="gpuChart" class="chart"></div></div>
    <div class="card"><h2 class="section-title">Capacity and data-center power</h2><div class="section-note">Epoch AI aggregates when recognized in the current source schema.</div><div id="capacityChart" class="chart"></div></div>
    <div class="card"><h2 class="section-title">API efficiency and congestion</h2><div class="section-note">Independent model speed, latency and output-price indices.</div><div id="apiChart" class="chart"></div></div>
    <div class="card"><h2 class="section-title">Frontier training compute</h2><div class="section-note">Identified training runs are event data, shown on a logarithmic scale.</div><div id="trainingChart" class="chart"></div></div>
    <div class="card span2"><h2 class="section-title">Grid-load physical cross-check</h2><div class="section-note">Regional load and weather-model residuals. Residuals are not a pure AI measure.</div><div id="gridChart" class="chart"></div></div>
    <div class="card span2"><h2 class="section-title">Source health and audit trail</h2><div class="section-note">A source can fail without preventing the remaining dashboard from updating.</div><div style="overflow:auto"><table><thead><tr><th>Source</th><th>Status</th><th>Latest observation</th><th>Last collection</th><th>Rows</th></tr></thead><tbody id="sourceTable"></tbody></table></div></div>
  </div>
  <div class="method">
    <div class="card"><b>Workload</b><p>Raw routed tokens plus optional disclosed global anchors. Native tokenizer differences remain visible rather than being hidden.</p></div>
    <div class="card"><b>Physical compute</b><p>Input and output token estimates multiplied by auditable H100-second weights. Low-confidence model classifications are flagged.</p></div>
    <div class="card"><b>Tightness</b><p>Rental price and API latency rise with tightness; available GPU supply reduces it. Components remain separately chartable.</p></div>
    <div class="card"><b>Capacity</b><p>Operational H100-equivalent systems and AI data-center MW. Training compute is stored separately because it is lumpy.</p></div>
  </div>
  <footer>Sources supported by this build: OpenRouter, Artificial Analysis, Vast.ai, U.S. EIA, Open-Meteo, Epoch AI and MLCommons/MLPerf. Data use remains subject to each source’s terms. “H100-equivalent hours” is an estimate, not a metered fleet total.</footer>
</div>
<script>
const D=__DATA__;
const s=D.series||[], dates=s.map(x=>x.date); const val=(k)=>s.map(x=>x[k]);
const fmt=(x,d=0)=>x==null?'—':Number(x).toLocaleString(undefined,{maximumFractionDigits:d});
const pct=(x)=>x==null?'—':`${x>=0?'+':''}${fmt(x,1)}% / 28d`;
document.getElementById('generated').textContent=`Generated ${D.meta.generated_at_utc}`;
document.getElementById('freshness').textContent=D.meta.demo_mode?'Demo snapshot':'Latest build';
if(D.meta.demo_mode)document.getElementById('demoBanner').style.display='block';
[['kWork','workload_index'],['kCompute','physical_compute_index'],['kTight','tightness_index'],['kCapacity','capacity_index'],['kEfficiency','efficiency_index']].forEach(([id,k])=>document.getElementById(id).textContent=fmt(D.kpis[k],1));
document.getElementById('dWork').textContent=pct(D.kpis.token_growth_28d);
document.getElementById('dCompute').textContent=pct(D.kpis.compute_growth_28d);
const layout=(extra={})=>Object.assign({margin:{l:55,r:25,t:18,b:45},paper_bgcolor:'transparent',plot_bgcolor:'transparent',font:{color:'#b8c6d8',size:11},xaxis:{gridcolor:'#21344a'},yaxis:{gridcolor:'#21344a'},legend:{orientation:'h',y:1.12},hovermode:'x unified'},extra);
const config={displaylogo:false,responsive:true};
Plotly.newPlot('mainChart',[
{x:dates,y:val('workload_index'),name:'Fixed-weight workload',mode:'lines',line:{width:3}},
{x:dates,y:val('physical_compute_index'),name:'Physical compute estimate',mode:'lines',line:{width:3}},
{x:dates,y:val('capacity_index'),name:'Capacity',mode:'lines',line:{width:2,dash:'dot'}},
{x:dates,y:val('tightness_index'),name:'Tightness',mode:'lines',line:{width:2,dash:'dash'}}],layout({yaxis:{title:'Index (base = 100)',gridcolor:'#21344a'}}),config);
const tokenTraces=[{x:dates,y:val('tokens'),name:'OpenRouter observed',mode:'lines',fill:'tozeroy',line:{width:2}}];
const anchors=D.global_token_anchors||[]; if(anchors.length){tokenTraces.push({x:anchors.map(x=>x.date),y:anchors.map(x=>x.high_tokens),name:'Global high',mode:'lines',line:{width:0},hoverinfo:'skip'});tokenTraces.push({x:anchors.map(x=>x.date),y:anchors.map(x=>x.low_tokens),name:'Global range',mode:'lines',fill:'tonexty',line:{width:0}});tokenTraces.push({x:anchors.map(x=>x.date),y:anchors.map(x=>x.central_tokens),name:'Global central',mode:'lines',line:{width:3,dash:'dash'}})}
Plotly.newPlot('tokensChart',tokenTraces,layout({yaxis:{title:'Tokens/day',type:'log',gridcolor:'#21344a'}}),config);
const mix=D.model_mix||[]; Plotly.newPlot('mixChart',[{labels:mix.map(x=>x.model),values:mix.map(x=>x.tokens),type:'pie',hole:.55,textinfo:'percent',hovertemplate:'%{label}<br>%{value:.3s} tokens<extra></extra>'}],layout({showlegend:true,legend:{font:{size:9},orientation:'v',x:1,y:1},margin:{l:10,r:10,t:10,b:10}}),config);
Plotly.newPlot('gpuChart',[{x:dates,y:val('gpu_price'),name:'Median price',mode:'lines',yaxis:'y'},{x:dates,y:val('gpu_units'),name:'Available units',mode:'lines',yaxis:'y2'}],layout({yaxis:{title:'$/GPU-hour',gridcolor:'#21344a'},yaxis2:{title:'GPU units',overlaying:'y',side:'right',showgrid:false}}),config);
Plotly.newPlot('capacityChart',[{x:dates,y:val('capacity_h100_eq'),name:'H100 equivalents',mode:'lines',yaxis:'y'},{x:dates,y:val('datacenter_power_mw'),name:'AI DC power MW',mode:'lines',yaxis:'y2'}],layout({yaxis:{title:'H100-equivalents',gridcolor:'#21344a'},yaxis2:{title:'MW',overlaying:'y',side:'right',showgrid:false}}),config);
Plotly.newPlot('apiChart',[{x:dates,y:val('api_speed_index'),name:'Output speed',mode:'lines'},{x:dates,y:val('api_latency_index'),name:'TTFT / latency',mode:'lines'},{x:dates,y:val('api_price_index'),name:'Output price',mode:'lines',line:{dash:'dot'}}],layout({yaxis:{title:'Index (base = 100)',gridcolor:'#21344a'}}),config);
const trn=D.training_events||[]; Plotly.newPlot('trainingChart',[{x:trn.map(x=>x.date),y:trn.map(x=>x.flop),text:trn.map(x=>x.model),name:'Training runs',mode:'markers',marker:{size:9},hovertemplate:'%{text}<br>%{x}<br>%{y:.2e} FLOP<extra></extra>'}],layout({showlegend:false,yaxis:{title:'Training FLOP',type:'log',gridcolor:'#21344a'}}),config);
const gr=D.grid_residuals||[]; const regions=[...new Set(gr.map(x=>x.region))]; const traces=[]; regions.forEach(r=>{const a=gr.filter(x=>x.region===r);traces.push({x:a.map(x=>x.date),y:a.map(x=>x.grid_load_mw),name:`${r} load`,mode:'lines'});traces.push({x:a.map(x=>x.date),y:a.map(x=>x.grid_residual_mw),name:`${r} residual`,mode:'lines',line:{dash:'dot'}})}); Plotly.newPlot('gridChart',traces,layout({yaxis:{title:'MW',gridcolor:'#21344a'}}),config);
const tb=document.getElementById('sourceTable'); (D.source_health||[]).sort((a,b)=>a.source.localeCompare(b.source)).forEach(x=>{const tr=document.createElement('tr');tr.innerHTML=`<td>${x.source}</td><td><span class="status ${x.status}">${x.status}</span></td><td>${x.latest_observation||'—'}</td><td>${x.last_collection||'—'}</td><td>${fmt(x.rows)}</td>`;tb.appendChild(tr)});
</script>
</body></html>'''
