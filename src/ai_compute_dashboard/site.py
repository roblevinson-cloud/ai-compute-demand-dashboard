from __future__ import annotations

import html
import json
import shutil
from pathlib import Path
from typing import Any


def build_site(data: dict[str, Any], output: str | Path = "docs/index.html") -> None:
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, separators=(",", ":"), default=str).replace("</", "<\\/")
    title = html.escape(data["meta"]["title"])
    subtitle = html.escape(data["meta"]["subtitle"])
    page = (
        TEMPLATE.replace("__TITLE__", title)
        .replace("__SUBTITLE__", subtitle)
        .replace("__DATA__", payload)
    )
    destination.write_text(page, encoding="utf-8")

    data_path = destination.parent / "data" / "dashboard.json"
    data_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    source_assets = Path(__file__).with_name("static")
    destination_assets = destination.parent / "assets"
    destination_assets.mkdir(parents=True, exist_ok=True)
    for asset in ("dashboard.css", "dashboard.js"):
        shutil.copyfile(source_assets / asset, destination_assets / asset)


TEMPLATE = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <meta name="description" content="AI compute demand, capacity, market tightness, and interactive infrastructure economics." />
  <meta property="og:title" content="AI Compute Demand & Infrastructure Economics" />
  <meta property="og:description" content="An audit-friendly dashboard for AI workload, capacity, and project-level infrastructure returns." />
  <meta property="og:image" content="https://roblevinson-cloud.github.io/ai-compute-demand-dashboard/og.png" />
  <meta name="twitter:card" content="summary_large_image" />
  <title>__TITLE__</title>
  <script src="assets/plotly.min.js"></script>
  <link rel="stylesheet" href="assets/dashboard.css" />
</head>
<body>
  <div class="shell">
    <header class="topbar">
      <div>
        <div class="eyebrow">AI infrastructure intelligence</div>
        <h1>__TITLE__</h1>
        <p class="subtitle">__SUBTITLE__</p>
      </div>
      <div class="build-meta">
        <span class="freshness-badge"><span class="freshness-dot"></span><span id="freshness">Built</span></span>
        <span id="generated"></span>
      </div>
    </header>

    <nav class="module-nav" aria-label="Dashboard modules">
      <button class="module-tab active" data-view="demand" type="button">Demand signals</button>
      <button class="module-tab" data-view="economics" type="button">Infrastructure economics</button>
      <button class="module-tab" data-view="methodology" type="button">Methodology</button>
    </nav>

    <main>
      <section class="view active" id="view-demand" aria-labelledby="demand-heading">
        <div class="demo-banner" id="demoBanner"><strong>Demonstration mode.</strong> The bundled demand series is synthetic and exists only to preview the interface. Live collectors never fabricate missing observations.</div>
        <div class="section-intro">
          <div><div class="section-kicker">Market monitor</div><h2 id="demand-heading">Demand, supply, and bottleneck signals</h2></div>
          <p>Indices translate heterogeneous workload and infrastructure data into comparable directional signals.</p>
        </div>
        <div class="kpi-grid demand-kpis">
          <article class="panel metric-card"><div class="metric-head"><span>Workload index</span><span class="type-badge calculated">Calculated</span></div><div class="metric-value" id="kWork">—</div><div class="metric-foot" id="dWork">Observed token workload</div></article>
          <article class="panel metric-card"><div class="metric-head"><span>Physical compute index</span><span class="type-badge estimated">Estimated</span></div><div class="metric-value" id="kCompute">—</div><div class="metric-foot" id="dCompute">H100-equivalent use</div></article>
          <article class="panel metric-card"><div class="metric-head"><span>Tightness index</span><span class="type-badge calculated">Calculated</span></div><div class="metric-value" id="kTight">—</div><div class="metric-foot">Price + latency − availability</div></article>
          <article class="panel metric-card"><div class="metric-head"><span>Capacity index</span><span class="type-badge calculated">Calculated</span></div><div class="metric-value" id="kCapacity">—</div><div class="metric-foot">Operational H100-equivalents</div></article>
          <article class="panel metric-card"><div class="metric-head"><span>Efficiency index</span><span class="type-badge calculated">Calculated</span></div><div class="metric-value" id="kEfficiency">—</div><div class="metric-foot">Tokens per estimated H100-hour</div></article>
        </div>

        <div class="chart-grid">
          <article class="panel span-2"><div class="panel-heading"><div><h3>Workload versus physical compute</h3><p>Calculated indices normalized to 100 over the opening base period.</p></div></div><div id="mainChart" class="chart chart-tall"></div></article>
          <article class="panel"><div class="panel-heading"><div><h3>Observed token throughput</h3><p>Reported OpenRouter traffic; modeled global anchors remain separate.</p></div></div><div id="tokensChart" class="chart"></div></article>
          <article class="panel"><div class="panel-heading"><div><h3>Latest model mix</h3><p>Calculated share of reported tokens on the latest observed day.</p></div></div><div id="mixChart" class="chart"></div></article>
          <article class="panel"><div class="panel-heading"><div><h3>GPU rental market</h3><p>Reported median price and observable available units.</p></div></div><div id="gpuChart" class="chart"></div></article>
          <article class="panel"><div class="panel-heading"><div><h3>Capacity and data-center power</h3><p>Reported aggregated capacity recognized from Epoch AI.</p></div></div><div id="capacityChart" class="chart"></div></article>
          <article class="panel"><div class="panel-heading"><div><h3>API efficiency and congestion</h3><p>Calculated indices from reported speed, latency, and price.</p></div></div><div id="apiChart" class="chart"></div></article>
          <article class="panel"><div class="panel-heading"><div><h3>Frontier training compute</h3><p>Reported or estimated event data on a logarithmic scale.</p></div></div><div id="trainingChart" class="chart"></div></article>
          <article class="panel span-2"><div class="panel-heading"><div><h3>Grid-load physical cross-check</h3><p>Reported load and calculated weather-model residuals; residuals are not a pure AI measure.</p></div></div><div id="gridChart" class="chart"></div></article>
          <article class="panel span-2"><div class="panel-heading"><div><h3>Source health and audit trail</h3><p>One failed source does not prevent the remaining dashboard from updating.</p></div></div><div class="table-wrap"><table><thead><tr><th>Source</th><th>Status</th><th>Latest observation</th><th>Last collection</th><th>Rows</th></tr></thead><tbody id="sourceTable"></tbody></table></div></article>
        </div>
      </section>

      <section class="view" id="view-economics" aria-labelledby="economics-heading">
        <div class="economics-hero">
          <div>
            <div class="section-kicker">Scenario laboratory</div>
            <h2 id="economics-heading">AI Infrastructure Economics</h2>
            <p>Project-level returns for hyperscaler and AI-cloud capacity. Edit any assumption; every output recalculates locally and immediately.</p>
          </div>
          <div class="economics-controls">
            <label class="select-label" for="companySelect">Focus company</label>
            <select id="companySelect" aria-label="Focus company"></select>
            <div class="scenario-control" role="group" aria-label="Scenario">
              <button type="button" data-scenario="bear">Bear</button>
              <button type="button" data-scenario="base" class="active">Base</button>
              <button type="button" data-scenario="bull">Bull</button>
            </div>
          </div>
        </div>

        <div class="classification-legend" aria-label="Metric classification legend">
          <span>Classification</span>
          <span class="type-badge reported">Reported</span>
          <span class="type-badge calculated">Calculated</span>
          <span class="type-badge estimated">Estimated</span>
          <span class="type-badge user-supplied">User-supplied</span>
        </div>

        <div class="kpi-grid economics-kpis" id="economicsKpis"></div>
        <div class="model-warning" id="modelWarning" role="status"></div>

        <div class="economics-layout">
          <div class="economics-main">
            <article class="panel"><div class="panel-heading split"><div><h3>Return profile by company</h3><p>Calculated project returns under the selected scenario.</p></div><span class="type-badge calculated">Calculated</span></div><div id="returnChart" class="chart chart-tall"></div></article>
            <div class="chart-grid compact">
              <article class="panel"><div class="panel-heading split"><div><h3>Utilization and payback</h3><p>Bubble size represents modeled project capital.</p></div><span class="type-badge calculated">Calculated</span></div><div id="utilizationChart" class="chart"></div></article>
              <article class="panel"><div class="panel-heading split"><div><h3 id="cashFlowTitle">Project cash-flow path</h3><p>Annual and cumulative unlevered cash flow.</p></div><span class="type-badge calculated">Calculated</span></div><div id="cashFlowChart" class="chart"></div></article>
            </div>
            <article class="panel"><div class="panel-heading"><div><h3>Latest reported company context</h3><p>Quarterly filing and earnings-call fields are context only; they are not silently treated as project economics.</p></div></div><div class="table-wrap"><table><thead><tr><th>Metric</th><th>Value</th><th>Type</th><th>Period</th><th>Source</th></tr></thead><tbody id="reportedContext"></tbody></table></div></article>
          </div>

          <aside class="panel assumption-panel">
            <div class="assumption-sticky">
              <div class="panel-heading"><div><h3>Editable assumptions</h3><p id="assumptionSubtitle">Base scenario</p></div></div>
              <div class="assumption-actions"><button type="button" class="secondary-button" id="resetAssumptions">Reset scenario</button><button type="button" class="secondary-button" id="exportAssumptions">Export JSON</button></div>
            </div>
            <div id="assumptionInputs"></div>
          </aside>
        </div>
      </section>

      <section class="view" id="view-methodology" aria-labelledby="methodology-heading">
        <div class="section-intro methodology-intro">
          <div><div class="section-kicker">Audit layer</div><h2 id="methodology-heading">Transparent methodology</h2></div>
          <p>Reported facts remain separate from modeled allocations and calculated outputs. Nothing in this module is company guidance.</p>
        </div>
        <div class="methodology-grid" id="metricMethodology"></div>
        <article class="panel update-architecture">
          <div class="panel-heading"><div><h3>Quarterly update architecture</h3><p>The static GitHub Pages build is refreshed from versioned observations.</p></div></div>
          <div class="pipeline-flow">
            <div><span>01</span><strong>Company filings</strong><p>SEC Company Facts supplies standardized reported revenue, capex, depreciation, operating income, and cash flow.</p></div>
            <div><span>02</span><strong>Earnings-call feed</strong><p>An optional normalized feed captures sourced capacity, active-power, AI-revenue, and utilization disclosures.</p></div>
            <div><span>03</span><strong>Typed observations</strong><p>Each record keeps period, source URL, quality, provenance, and estimate status in the existing long-form schema.</p></div>
            <div><span>04</span><strong>Scenario model</strong><p>Bear, base, and bull assumptions combine with reported facts; the site rebuilds and deploys through the existing workflow.</p></div>
          </div>
        </article>
        <div class="methodology-grid classification-cards">
          <article class="panel"><span class="type-badge reported">Reported</span><h3>Primary-source fact</h3><p>Directly disclosed in an SEC filing, earnings release, or sourced call transcript.</p></article>
          <article class="panel"><span class="type-badge calculated">Calculated</span><h3>Formula output</h3><p>Deterministically produced from visible inputs using the documented equations.</p></article>
          <article class="panel"><span class="type-badge estimated">Estimated</span><h3>Model assumption</h3><p>Analyst assumption, allocation, or fallback that is not directly disclosed by the company.</p></article>
          <article class="panel"><span class="type-badge user-supplied">User-supplied</span><h3>Local override</h3><p>An assumption changed in this browser; reset restores the versioned scenario value.</p></article>
        </div>
        <article class="panel limitations"><h3>Important limitations</h3><p>Hyperscalers rarely disclose AI-only revenue, capex allocation, accelerator counts, utilization, or project economics. The model therefore converts company-wide capital-spend facts into a hypothetical AI project using explicit allocation and unit-economics assumptions. Internal-use capacity at Meta and Alphabet is represented by an estimated economic value per GPU-hour, not an external rental price. Financing structure, working capital, land timing, prepayments, tax credits, and company-level overhead are excluded.</p></article>
      </section>
    </main>

    <footer>Sources supported by this build include SEC EDGAR Company Facts, company investor-relations materials, OpenRouter, Artificial Analysis, Vast.ai, U.S. EIA, Open-Meteo, Epoch AI, and MLCommons/MLPerf. Data use remains subject to each source’s terms. “H100-equivalent hours” and all infrastructure economics are estimates or calculations unless explicitly labeled reported.</footer>
  </div>

  <script>window.DASHBOARD_DATA=__DATA__;</script>
  <script src="assets/dashboard.js"></script>
</body>
</html>'''
