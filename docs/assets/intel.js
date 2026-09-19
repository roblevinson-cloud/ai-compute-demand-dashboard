const D = window.INTEL_DATA;
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const esc = (value) => String(value ?? "").replace(/[&<>'"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c]));
const fmtDate = (value, long = false) => {
  if (!value) return "—";
  const date = new Date(/^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value}T12:00:00` : value);
  return new Intl.DateTimeFormat("en-US", long ? {month:"short",day:"numeric",year:"numeric",hour:"numeric",minute:"2-digit"} : {month:"short",day:"numeric",year:"numeric"}).format(date);
};
const label = (value) => String(value || "").replaceAll("_", " ").replace(/\b\w/g, c => c.toUpperCase());
const scoreTone = (value) => value >= 85 ? "#0b8f83" : value >= 65 ? "#b7791f" : "#617080";

let state = {view: "overview", projectFilters: {}, eventFilters: {}, selectedBrief: D.briefs[0]?.id};

function showView(name) {
  state.view = name;
  $$(".view").forEach(el => el.classList.toggle("active", el.id === `view-${name}`));
  $$(".nav-item").forEach(el => el.classList.toggle("active", el.dataset.view === name));
  if (name !== "projects") history.replaceState(null, "", `#${name}`);
  window.scrollTo({top: 0, behavior: "instant"});
}

function setupNavigation() {
  $$('[data-view]').forEach(button => button.addEventListener("click", () => showView(button.dataset.view)));
  $$('[data-view-jump]').forEach(button => button.addEventListener("click", () => showView(button.dataset.viewJump)));
  $("#methodButton").addEventListener("click", () => showView("methodology"));
  const hash = location.hash.slice(1);
  if (hash.startsWith("project/")) {
    showView("projects");
    openProject(hash.split("/")[1]);
  } else if (["overview","projects","events","review","sources","briefs","methodology"].includes(hash)) showView(hash);
}

function renderKpis() {
  const items = [
    ["Tracked projects", D.kpis.tracked_projects, "Known + suspected"],
    ["Priority events", D.kpis.priority_events, "Materiality ≥ 85"],
    ["New signals", D.kpis.new_signals, "Needs source sweep"],
    ["Entity reviews", D.kpis.review_items, "No silent merges"],
    ["Healthy sources", D.kpis.healthy_sources, `of ${D.kpis.source_count} monitored`],
    ["Collection cadence", "1h", "Priority sources"],
  ];
  $("#kpiGrid").innerHTML = items.map(item => `<article class="kpi"><span class="kpi-label">${esc(item[0])}</span><strong>${esc(item[1])}</strong><small>${esc(item[2])}</small></article>`).join("");
}

function eventRow(event) {
  return `<article class="event-row">
    <div class="score-dial" style="border-top-color:${scoreTone(event.materiality)}">${event.materiality}</div>
    <div class="event-copy"><h3>${esc(event.headline)}</h3><p>${esc(event.what_new)}</p><div class="event-meta"><span class="tag">${esc(label(event.event_type))}</span><span class="tag">N ${event.novelty}</span><span class="tag">C ${event.confidence}</span><a class="source-tag" href="${esc(event.source_url)}" target="_blank" rel="noreferrer">${esc(event.source_name)} ↗</a></div></div>
    <time class="event-date">${fmtDate(event.occurred_at)}</time>
  </article>`;
}

function renderOverview() {
  const top = [...D.events].sort((a,b) => b.materiality-a.materiality || b.novelty-a.novelty).slice(0,4);
  $("#topEvents").innerHTML = top.map(eventRow).join("");
  const watchlist = [...D.projects].sort((a,b) => b.materiality-a.materiality).slice(0,6);
  $("#watchlist").innerHTML = watchlist.map(project => `<article class="watch-item" data-project="${esc(project.id)}"><div class="watch-top"><strong>${esc(project.name)}</strong><span class="status-pill ${esc(project.status_tone)}">${esc(project.status)}</span></div><p>${esc(project.county)}, ${esc(project.state)} · ${project.it_mw ? `${project.it_mw.toLocaleString()} MW critical IT` : project.mw ? `${project.mw.toLocaleString()} MW utility / generation` : "Scale undisclosed"}</p><div class="mini-meter"><i style="width:${project.materiality}%"></i></div></article>`).join("");
  $$(".watch-item").forEach(item => item.addEventListener("click", () => openProject(item.dataset.project)));
  const signal = D.events.find(event => event.id === "evt-google-lea") || D.events.find(event => event.event_type === "new_project_discovery");
  const match = D.review_queue.find(item => item.id === "match-google-jupiter") || D.review_queue[0];
  $("#discoverySignals").innerHTML = signal ? `<article class="discovery-card"><div><h3>${esc(signal.headline)}</h3><p>${esc(signal.why_matters)}</p><div class="event-meta"><span class="tag">${esc(label(signal.source_type))}</span><span class="tag">Discovery sweep</span></div></div>${match ? `<div class="compare"><strong>${match.score}%</strong><small>to ${esc(match.candidate)}<br>${esc(label(match.recommendation))}</small></div>` : ""}</article>` : '<div class="empty">No active discovery signals.</div>';
  $("#signalCount").textContent = `${D.kpis.new_signals} active signal${D.kpis.new_signals === 1 ? "" : "s"}`;
  const types = D.source_registry_summary.by_type;
  $("#sourcePulse").innerHTML = `<div class="source-donut"><div><span><strong>${D.kpis.healthy_sources}</strong><small>healthy</small></span></div></div><div class="pulse-legend"><div><span>Primary / regulatory</span><b>${(types.primary_regulatory||0)+(types.primary_government||0)+(types.utility||0)}</b></div><div><span>Company sources</span><b>${types.company||0}</b></div><div><span>Local / trade</span><b>${(types.local_media||0)+(types.trade_media||0)}</b></div></div>`;
}

function fillSelect(selector, values) {
  const select = $(selector);
  values.filter(Boolean).sort().forEach(value => select.insertAdjacentHTML("beforeend", `<option value="${esc(value)}">${esc(value)}</option>`));
}

function setupProjectFilters() {
  fillSelect("#filterCompany", [...new Set(D.projects.flatMap(project => [...project.developer, ...project.tenant, ...project.operator]))]);
  fillSelect("#filterState", [...new Set(D.projects.map(project => project.state))]);
  fillSelect("#filterCounty", [...new Set(D.projects.map(project => project.county))]);
  fillSelect("#filterStatus", [...new Set(D.projects.map(project => project.status))]);
  ["#filterCompany","#filterState","#filterCounty","#filterStatus","#filterMw","#filterMateriality"].forEach(selector => $(selector).addEventListener("input", renderProjectTable));
}

function filteredProjects() {
  const company = $("#filterCompany").value;
  const status = $("#filterStatus").value;
  const stateValue = $("#filterState").value;
  const county = $("#filterCounty").value;
  const mw = Number($("#filterMw").value || 0);
  const materiality = Number($("#filterMateriality").value || 0);
  const query = $("#globalSearch").value.trim().toLowerCase();
  return D.projects.filter(project => {
    const companies = [...project.developer, ...project.tenant, ...project.operator];
    const projectMw = Math.max(project.it_mw || 0, project.mw || 0);
    const haystack = JSON.stringify(project).toLowerCase();
    return (!company || companies.includes(company)) && (!status || project.status === status) && (!stateValue || project.state === stateValue) && (!county || project.county === county) && (!mw || projectMw >= mw) && project.materiality >= materiality && (!query || haystack.includes(query));
  });
}

function powerCell(project) {
  if (project.it_mw) return `${project.it_mw.toLocaleString()} MW<br><small>critical IT${project.mw ? ` · ${project.mw.toLocaleString()} MW utility / facility` : ""}</small>`;
  if (project.mw) return `${project.mw.toLocaleString()} MW<br><small>utility / generation boundary</small>`;
  return `Undisclosed<br><small>—</small>`;
}

function renderProjectTable() {
  const rows = filteredProjects().sort((a,b) => b.materiality-a.materiality || a.name.localeCompare(b.name));
  $("#projectTable").innerHTML = rows.length ? rows.map(project => `<tr data-project="${esc(project.id)}"><td><span class="project-name">${esc(project.name)}<small>${esc(project.aliases.map(item => item.name).join(" · ") || "No known aliases")}</small></span></td><td>${esc(project.county)}, ${esc(project.state || "—")}<br><small>${esc(project.location_precision)}</small></td><td>${esc(project.developer.join(", ") || "Not disclosed")}<br><small>${esc(project.tenant.join(", ") || "Tenant not disclosed")}</small></td><td><span class="status-pill ${esc(project.status_tone)}">${esc(project.status)}</span></td><td>${powerCell(project)}</td><td><span class="score-number">${project.materiality}</span></td><td>${fmtDate(project.last_update)}</td></tr>`).join("") : `<tr><td colspan="7" class="empty">No projects match these filters.</td></tr>`;
  $$("#projectTable tr[data-project]").forEach(row => row.addEventListener("click", () => openProject(row.dataset.project)));
}

function openProject(id) {
  const project = D.projects.find(item => item.id === id);
  if (!project) return;
  showView("projects");
  history.replaceState(null, "", `#project/${project.id}`);
  const events = D.events.filter(event => event.project_id === project.id).sort((a,b) => b.occurred_at.localeCompare(a.occurred_at));
  const detail = $("#projectDetail");
  detail.hidden = false;
  detail.innerHTML = `<article class="detail-shell"><div class="detail-hero"><div><span class="eyebrow">${esc(project.county)}, ${esc(project.state)} · ${esc(project.status)}</span><h2>${esc(project.name)}</h2><p>${esc(project.summary)}</p></div><div class="detail-score"><strong>${project.materiality}</strong><span>Materiality</span></div></div><div class="detail-body"><div>
    <section class="detail-section"><h3>Current facts · source bounded</h3><div class="fact-grid">${project.metrics.map(metric => `<article class="fact-card"><span>${esc(metric.label)}</span><strong>${esc(metric.value)}</strong><small>${esc(metric.boundary)}</small><a class="source-tag" href="${esc(metric.source_url)}" target="_blank" rel="noreferrer">Evidence ↗</a></article>`).join("")}</div></section>
    <section class="detail-section" style="margin-top:20px"><h3>Companies & roles</h3><div class="table-panel"><table class="data-table"><thead><tr><th>Company</th><th>Relationship</th><th>Confidence</th></tr></thead><tbody>${project.relationships.map(item => `<tr><td>${esc(item.company)}</td><td>${esc(item.role)}</td><td>${item.confidence}/100</td></tr>`).join("")}</tbody></table></div></section>
  </div><aside>
    <section class="detail-section"><h3>Development timeline</h3><div class="timeline">${events.map(event => `<article class="timeline-item"><time>${fmtDate(event.occurred_at)}</time><h4>${esc(event.headline)}</h4><a href="${esc(event.source_url)}" target="_blank" rel="noreferrer">${esc(event.source_name)} ↗</a></article>`).join("") || '<p class="empty">No events yet.</p>'}</div></section>
    <section class="detail-section" style="margin-top:12px"><h3>Aliases & boundaries</h3>${project.aliases.map(item => `<div class="fact-card"><strong>${esc(item.name)}</strong><small>${esc(item.type)} · confidence ${item.confidence}/100</small></div>`).join("") || '<p class="empty">No confirmed aliases.</p>'}<div class="next-action"><strong>Risk note:</strong> ${esc(project.risk)}</div></section>
  </aside></div></article>`;
  detail.scrollIntoView({behavior:"smooth", block:"start"});
}

function setupEventFilters() {
  fillSelect("#filterEventType", [...new Set(D.events.map(event => event.event_type))]);
  ["#filterEventType", "#filterEventScore", "#filterEventDate"].forEach(selector => $(selector).addEventListener("input", renderEventFeed));
}

function renderEventFeed() {
  const type = $("#filterEventType").value;
  const score = Number($("#filterEventScore").value || 0);
  const from = $("#filterEventDate").value;
  const query = $("#globalSearch").value.trim().toLowerCase();
  const events = D.events.filter(event => (!type || event.event_type === type) && event.materiality >= score && (!from || event.occurred_at.slice(0,10) >= from) && (!query || JSON.stringify(event).toLowerCase().includes(query)));
  $("#eventFeed").innerHTML = events.length ? events.map(event => `<article class="feed-card"><div class="score-stack"><div><span>M</span><strong>${event.materiality}</strong></div><div><span>N</span><strong>${event.novelty}</strong></div><div><span>C</span><strong>${event.confidence}</strong></div></div><div class="feed-main"><span class="section-label">${esc(event.project_name)} · ${fmtDate(event.occurred_at)}</span><h2>${esc(event.headline)}</h2><p>${esc(label(event.event_type))}</p><div class="feed-facts"><div><strong>WHAT CHANGED</strong> ${esc(event.what_new)}</div><div><strong>WHY IT MATTERS</strong> ${esc(event.why_matters)}</div><div><strong>IMPLICATION</strong> ${esc(event.implication)}</div></div></div><aside class="evidence-box"><span>Evidence excerpt</span><blockquote>“${esc(event.evidence)}”</blockquote><a href="${esc(event.source_url)}" target="_blank" rel="noreferrer">Open ${esc(event.source_name)} ↗</a></aside></article>`).join("") : '<div class="panel empty">No events match these filters.</div>';
}

function renderReviewQueue() {
  $("#reviewBadge").textContent = D.review_queue.length;
  $("#reviewQueue").innerHTML = D.review_queue.map(item => `<article class="review-card"><header class="review-head"><div><h2>${esc(item.signal)} → ${esc(item.candidate)}</h2><p>${esc(item.status)} · ${fmtDate(item.created_at)}</p></div><div class="match-score"><strong>${item.score}%</strong><small>${esc(label(item.recommendation))}</small></div></header><div class="review-body"><div class="evidence-columns"><div><h3>Supporting evidence</h3>${item.supporting.length ? `<ul>${item.supporting.map(value => `<li>${esc(value)}</li>`).join("")}</ul>` : '<p class="empty">No affirmative match features.</p>'}</div><div><h3>Conflicts</h3>${item.conflicts.length ? `<ul class="conflicts">${item.conflicts.map(value => `<li>${esc(value)}</li>`).join("")}</ul>` : '<p class="empty">No hard conflicts detected.</p>'}</div></div><div class="next-action"><strong>Recommended next action:</strong> ${esc(item.next_action)}</div></div></article>`).join("");
}

function renderSources() {
  const total = D.source_health.length;
  const changed = D.source_health.filter(item => item.status === "changed").length;
  const primary = D.source_health.filter(item => ["primary_regulatory","primary_government","utility"].includes(item.source_type)).length;
  const hourly = D.source_health.filter(item => item.interval_minutes <= 60).length;
  $("#sourceStats").innerHTML = [[total,"Registered sources"],[primary,"Primary / utility"],[hourly,"Hourly priority"],[changed,"Changed this cycle"]].map(item => `<article class="source-stat"><strong>${item[0]}</strong><span>${item[1]}</span></article>`).join("");
  $("#sourceTable").innerHTML = D.source_health.map(source => `<tr><td><a class="project-name" href="${esc(source.url)}" target="_blank" rel="noreferrer">${esc(source.name)} ↗</a><br><small>${esc(source.tags.slice(0,3).join(" · "))}</small></td><td>${esc(label(source.source_type))}</td><td>${esc(source.jurisdiction)}</td><td><span class="health ${esc(source.status)}">${esc(label(source.status))}</span></td><td>${source.interval_minutes} min</td><td>${fmtDate(source.last_checked, true)}</td><td>${source.priority}</td></tr>`).join("");
}

function renderBriefs() {
  $("#briefList").innerHTML = D.briefs.map(brief => `<button class="brief-item ${brief.id === state.selectedBrief ? "active" : ""}" data-brief="${esc(brief.id)}"><span>${esc(brief.type)}</span><strong>${esc(brief.subject)}</strong><small>${fmtDate(brief.date)}</small></button>`).join("");
  $$(".brief-item").forEach(button => button.addEventListener("click", () => {state.selectedBrief = button.dataset.brief; renderBriefs();}));
  const brief = D.briefs.find(item => item.id === state.selectedBrief) || D.briefs[0];
  if (!brief) return;
  const events = brief.event_ids.map(id => D.events.find(event => event.id === id)).filter(Boolean);
  $("#briefPreview").innerHTML = `<span class="brief-kicker">${esc(brief.type)} · ${fmtDate(brief.date)}</span><h2>${esc(brief.subject)}</h2><p class="dek">${esc(brief.summary)}</p><span class="section-label">TOP DEVELOPMENTS</span>${events.map(event => `<section class="brief-event"><h3>${esc(event.headline)}</h3><p><strong>What changed:</strong> ${esc(event.what_new)}</p><p><strong>Why it matters:</strong> ${esc(event.why_matters)}</p><p><strong>Implication:</strong> ${esc(event.implication)}</p><div class="event-meta"><span class="tag">M ${event.materiality}</span><span class="tag">N ${event.novelty}</span><span class="tag">C ${event.confidence}</span><a class="source-tag" href="${esc(event.source_url)}" target="_blank" rel="noreferrer">Underlying evidence ↗</a></div></section>`).join("")}`;
}

function briefText() {
  const brief = D.briefs.find(item => item.id === state.selectedBrief) || D.briefs[0];
  const events = brief.event_ids.map(id => D.events.find(event => event.id === id)).filter(Boolean);
  return [`Subject: ${brief.subject}`, "", brief.summary, "", "TOP DEVELOPMENTS", ...events.flatMap(event => ["", event.headline, `What changed: ${event.what_new}`, `Why it matters: ${event.why_matters}`, `Implication: ${event.implication}`, `Scores: materiality ${event.materiality}, novelty ${event.novelty}, confidence ${event.confidence}`, `Evidence: ${event.source_url}`])].join("\n");
}

function setupGlobalSearch() {
  $("#globalSearch").addEventListener("input", () => {
    renderProjectTable();
    renderEventFeed();
    const query = $("#globalSearch").value.trim();
    if (query && !["projects","events"].includes(state.view)) showView("projects");
  });
}

function toast(message) {
  const node = $("#toast"); node.textContent = message; node.classList.add("show");
  setTimeout(() => node.classList.remove("show"), 1800);
}

function init() {
  $("#asOf").textContent = `As of ${fmtDate(D.meta.as_of, true)}`;
  $("#modeLabel").textContent = D.meta.mode;
  $("#demoNote").innerHTML = `<strong>Portfolio data:</strong> ${esc(D.meta.disclaimer)}`;
  renderKpis(); renderOverview(); setupProjectFilters(); renderProjectTable(); setupEventFilters(); renderEventFeed(); renderReviewQueue(); renderSources(); renderBriefs();
  $("#taxonomy").innerHTML = D.event_taxonomy.map(item => `<span>${esc(label(item))}</span>`).join("");
  setupNavigation(); setupGlobalSearch();
  $("#copyBrief").addEventListener("click", async () => { await navigator.clipboard.writeText(briefText()); toast("Email-ready brief copied"); });
}

init();
