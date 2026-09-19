from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any


def build_site(data: dict[str, Any], output: str | Path = "docs/index.html") -> Path:
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, separators=(",", ":"), default=str).replace("</", "<\\/")
    destination.write_text(TEMPLATE.replace("__DATA__", payload), encoding="utf-8")
    data_path = destination.parent / "data" / "intelligence.json"
    data_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    asset_source = Path(__file__).with_name("static")
    asset_destination = destination.parent / "assets"
    asset_destination.mkdir(parents=True, exist_ok=True)
    for name in ("intel.css", "intel.js"):
        shutil.copyfile(asset_source / name, asset_destination / name)
    return destination


TEMPLATE = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="description" content="Project-centric U.S. data center development intelligence monitor.">
  <title>GridSignal — Data Center Development Intelligence</title>
  <link rel="stylesheet" href="assets/intel.css">
</head>
<body>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand"><span class="brand-mark" aria-hidden="true">G</span><div><strong>GridSignal</strong><span>Development intelligence</span></div></div>
      <nav class="nav" aria-label="Main navigation">
        <button class="nav-item active" data-view="overview"><span>⌂</span>Overview</button>
        <button class="nav-item" data-view="projects"><span>▦</span>Projects</button>
        <button class="nav-item" data-view="events"><span>≡</span>Event feed</button>
        <button class="nav-item" data-view="review"><span>◇</span>Review queue <b id="reviewBadge">0</b></button>
        <button class="nav-item" data-view="sources"><span>◉</span>Source health</button>
        <button class="nav-item" data-view="briefs"><span>▤</span>Brief archive</button>
      </nav>
      <div class="sidebar-footer">
        <span class="live-dot"></span><div><strong>U.S. project portfolio</strong><small>Evidence-linked snapshot</small></div>
      </div>
    </aside>

    <div class="main-shell">
      <header class="topbar">
        <div class="mobile-brand">GridSignal</div>
        <label class="global-search"><span>⌕</span><input id="globalSearch" type="search" placeholder="Search projects, companies, counties, dockets…" aria-label="Search intelligence"></label>
        <div class="top-actions"><span class="asof" id="asOf"></span><button class="icon-button" id="methodButton" title="Methodology">?</button><button class="avatar" title="Analyst workspace">RL</button></div>
      </header>

      <main>
        <section class="view active" id="view-overview">
          <div class="page-head"><div><span class="eyebrow">COMMAND CENTER</span><h1>Development pulse</h1><p id="modeLabel"></p></div><div class="page-actions"><button class="secondary" data-view-jump="review">Review matches</button><button class="primary" data-view-jump="briefs">Open latest brief</button></div></div>
          <div class="demo-note" id="demoNote"></div>
          <div class="kpi-grid" id="kpiGrid"></div>
          <div class="overview-grid">
            <section class="panel span-2"><div class="panel-head"><div><span class="section-label">RANKED INTELLIGENCE</span><h2>Top developments</h2></div><button class="text-button" data-view-jump="events">View all events →</button></div><div id="topEvents" class="event-list"></div></section>
            <aside class="panel watch-panel"><div class="panel-head"><div><span class="section-label">WATCHLIST</span><h2>Project exposure</h2></div></div><div id="watchlist" class="watchlist"></div></aside>
            <section class="panel span-2"><div class="panel-head"><div><span class="section-label">EARLY WARNING</span><h2>Discovery & identity signals</h2></div><span class="count-chip" id="signalCount"></span></div><div id="discoverySignals"></div></section>
            <aside class="panel"><div class="panel-head"><div><span class="section-label">COLLECTION</span><h2>Source network</h2></div><button class="text-button" data-view-jump="sources">Inspect →</button></div><div id="sourcePulse"></div></aside>
          </div>
        </section>

        <section class="view" id="view-projects">
          <div class="page-head"><div><span class="eyebrow">PROJECT REGISTRY</span><h1>Tracked developments</h1><p>One record per known or suspected project, with fact-level provenance.</p></div></div>
          <div class="filter-bar">
            <label>Company<select id="filterCompany"><option value="">All companies</option></select></label>
            <label>State<select id="filterState"><option value="">All states</option></select></label>
            <label>County<select id="filterCounty"><option value="">All counties</option></select></label>
            <label>Status<select id="filterStatus"><option value="">All statuses</option></select></label>
            <label>Min MW<input id="filterMw" type="number" min="0" placeholder="Any"></label>
            <label>Min materiality<input id="filterMateriality" type="number" min="0" max="100" placeholder="Any"></label>
          </div>
          <div class="table-panel"><table class="data-table"><thead><tr><th>Project</th><th>Location</th><th>Companies</th><th>Status</th><th>Power</th><th>Materiality</th><th>Updated</th></tr></thead><tbody id="projectTable"></tbody></table></div>
          <div id="projectDetail" class="project-detail" hidden></div>
        </section>

        <section class="view" id="view-events">
          <div class="page-head"><div><span class="eyebrow">CHANGE LOG</span><h1>Event feed</h1><p>Ranked by materiality, novelty, and confidence—not article volume.</p></div></div>
          <div class="filter-bar compact"><label>Event type<select id="filterEventType"><option value="">All event types</option></select></label><label>Minimum materiality<input id="filterEventScore" type="number" min="0" max="100" value="0"></label><label>From date<input id="filterEventDate" type="date"></label></div>
          <div id="eventFeed" class="event-feed"></div>
        </section>

        <section class="view" id="view-review">
          <div class="page-head"><div><span class="eyebrow">HUMAN-IN-THE-LOOP</span><h1>Entity review queue</h1><p>Candidate relationships remain explicit until the evidence supports a decision.</p></div></div>
          <div class="guardrail"><strong>No silent merges.</strong><span>Every candidate keeps its feature score, supporting evidence, conflicts, and recommended next action.</span></div>
          <div id="reviewQueue" class="review-grid"></div>
        </section>

        <section class="view" id="view-sources">
          <div class="page-head"><div><span class="eyebrow">OPERATIONS</span><h1>Source health</h1><p>Primary and local sources lead discovery; national media remains a secondary layer.</p></div></div>
          <div id="sourceStats" class="source-stats"></div>
          <div class="table-panel"><table class="data-table"><thead><tr><th>Source</th><th>Type</th><th>Jurisdiction</th><th>Status</th><th>Cadence</th><th>Last checked</th><th>Priority</th></tr></thead><tbody id="sourceTable"></tbody></table></div>
        </section>

        <section class="view" id="view-briefs">
          <div class="page-head"><div><span class="eyebrow">DELIVERABLES</span><h1>Intelligence briefs</h1><p>Automatically generated at 6:30 a.m. and 6:00 p.m. Eastern, ready to paste into an email.</p></div><div class="page-actions"><button class="secondary" id="copyBriefText">Copy plain text</button><button class="primary" id="copyBriefRich">Copy formatted email</button></div></div>
          <div class="brief-layout"><div id="briefList" class="brief-list"></div><article id="briefPreview" class="brief-preview"></article></div>
        </section>

        <section class="view" id="view-methodology">
          <div class="page-head"><div><span class="eyebrow">AUDIT LAYER</span><h1>How the monitor thinks</h1><p>Fixed schemas and transparent scores make every result reviewable.</p></div></div>
          <div class="method-grid">
            <article class="panel"><span class="method-number">01</span><h2>Collect & preserve</h2><p>Poll APIs, RSS, web pages, and document indexes. Store the exact original bytes, URL, headers, retrieval time, and SHA-256 hash.</p></article>
            <article class="panel"><span class="method-number">02</span><h2>Extract fixed JSON</h2><p>Map every document into one versioned schema covering event type, companies, location, project hints, facts, dockets, permits, and evidence spans.</p></article>
            <article class="panel"><span class="method-number">03</span><h2>Resolve conservatively</h2><p>Compare location, parcel, companies, utility, MW, acreage, aliases, and timing. Contradictions lower the score; candidates remain reviewable.</p></article>
            <article class="panel"><span class="method-number">04</span><h2>Score the change</h2><p>Materiality weights scale, stage, regulation, parties, and schedule risk. Novelty penalizes repetition. Confidence separates source, extraction, match, and corroboration.</p></article>
          </div>
          <div class="panel taxonomy-panel"><div class="panel-head"><div><span class="section-label">CONTROLLED VOCABULARY</span><h2>Event taxonomy</h2></div></div><div id="taxonomy" class="taxonomy"></div></div>
        </section>
      </main>
    </div>
  </div>
  <div class="toast" id="toast" role="status"></div>
  <script>window.INTEL_DATA=__DATA__;</script>
  <script src="assets/intel.js"></script>
</body>
</html>'''
