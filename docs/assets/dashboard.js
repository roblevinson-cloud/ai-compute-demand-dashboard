(() => {
  "use strict";

  const D = window.DASHBOARD_DATA || {};
  const E = D.infrastructure_economics || { companies: [], assumptions: [], metrics: [] };
  const plotConfig = { displaylogo: false, responsive: true, scrollZoom: false };
  const plotColors = ["#55d8e5", "#67a9ff", "#a88bff", "#ffbd66", "#67d49b", "#ff7c82"];
  const byId = (id) => document.getElementById(id);
  const finite = (value, fallback = 0) => Number.isFinite(Number(value)) ? Number(value) : fallback;
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[character]);
  const fmt = (value, digits = 0) => value == null || !Number.isFinite(Number(value)) ? "—" : Number(value).toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: digits });
  const fmtPct = (value, digits = 1) => value == null || !Number.isFinite(Number(value)) ? "—" : `${fmt(value, digits)}%`;
  const fmtMoneyB = (value, digits = 1) => value == null || !Number.isFinite(Number(value)) ? "—" : `$${fmt(value, digits)}B`;
  const badge = (classification) => `<span class="type-badge ${escapeHtml(classification)}">${escapeHtml(classification)}</span>`;

  function baseLayout(extra = {}) {
    return Object.assign({
      margin: { l: 55, r: 25, t: 30, b: 45 },
      paper_bgcolor: "transparent",
      plot_bgcolor: "transparent",
      font: { color: "#9fb0bd", size: 10 },
      colorway: plotColors,
      xaxis: { gridcolor: "#203545", zerolinecolor: "#31495b" },
      yaxis: { gridcolor: "#203545", zerolinecolor: "#31495b" },
      legend: { orientation: "h", y: 1.14 },
      hovermode: "x unified",
      hoverlabel: { bgcolor: "#10202f", bordercolor: "#35536a", font: { color: "#edf4f8" } },
    }, extra);
  }

  function initializeHeader() {
    byId("generated").textContent = D.meta?.generated_at_utc ? `Generated ${D.meta.generated_at_utc}` : "";
    byId("freshness").textContent = D.meta?.demo_mode ? "Demo snapshot" : "Latest build";
    if (D.meta?.demo_mode) byId("demoBanner").style.display = "block";
  }

  function renderDemand() {
    const series = D.series || [];
    const dates = series.map((row) => row.date);
    const values = (key) => series.map((row) => row[key]);
    const kpis = D.kpis || {};
    const pct28 = (value) => value == null ? "—" : `${value >= 0 ? "+" : ""}${fmt(value, 1)}% / 28d`;
    [["kWork", "workload_index"], ["kCompute", "physical_compute_index"], ["kTight", "tightness_index"], ["kCapacity", "capacity_index"], ["kEfficiency", "efficiency_index"]]
      .forEach(([id, key]) => { byId(id).textContent = fmt(kpis[key], 1); });
    byId("dWork").textContent = pct28(kpis.token_growth_28d);
    byId("dCompute").textContent = pct28(kpis.compute_growth_28d);

    Plotly.newPlot("mainChart", [
      { x: dates, y: values("workload_index"), name: "Fixed-weight workload", mode: "lines", line: { width: 3 } },
      { x: dates, y: values("physical_compute_index"), name: "Physical compute estimate", mode: "lines", line: { width: 3 } },
      { x: dates, y: values("capacity_index"), name: "Capacity", mode: "lines", line: { width: 2, dash: "dot" } },
      { x: dates, y: values("tightness_index"), name: "Tightness", mode: "lines", line: { width: 2, dash: "dash" } },
    ], baseLayout({ yaxis: { title: "Index (base = 100)", gridcolor: "#203545" } }), plotConfig);

    const tokenTraces = [{ x: dates, y: values("tokens"), name: "OpenRouter reported", mode: "lines", fill: "tozeroy", line: { width: 2 } }];
    const anchors = D.global_token_anchors || [];
    if (anchors.length) {
      tokenTraces.push({ x: anchors.map((row) => row.date), y: anchors.map((row) => row.high_tokens), name: "Global high", mode: "lines", line: { width: 0 }, hoverinfo: "skip" });
      tokenTraces.push({ x: anchors.map((row) => row.date), y: anchors.map((row) => row.low_tokens), name: "Estimated global range", mode: "lines", fill: "tonexty", line: { width: 0 } });
      tokenTraces.push({ x: anchors.map((row) => row.date), y: anchors.map((row) => row.central_tokens), name: "Estimated global central", mode: "lines", line: { width: 3, dash: "dash" } });
    }
    Plotly.newPlot("tokensChart", tokenTraces, baseLayout({ yaxis: { title: "Tokens/day", type: "log", gridcolor: "#203545" } }), plotConfig);

    const mix = D.model_mix || [];
    Plotly.newPlot("mixChart", [{ labels: mix.map((row) => row.model), values: mix.map((row) => row.tokens), type: "pie", hole: .58, textinfo: "percent", hovertemplate: "%{label}<br>%{value:.3s} tokens<extra></extra>" }], baseLayout({ showlegend: true, legend: { font: { size: 9 }, orientation: "v", x: 1, y: 1 }, margin: { l: 8, r: 8, t: 10, b: 10 } }), plotConfig);
    Plotly.newPlot("gpuChart", [{ x: dates, y: values("gpu_price"), name: "Median price", mode: "lines", yaxis: "y" }, { x: dates, y: values("gpu_units"), name: "Available units", mode: "lines", yaxis: "y2" }], baseLayout({ yaxis: { title: "$/GPU-hour", gridcolor: "#203545" }, yaxis2: { title: "GPU units", overlaying: "y", side: "right", showgrid: false } }), plotConfig);
    Plotly.newPlot("capacityChart", [{ x: dates, y: values("capacity_h100_eq"), name: "H100 equivalents", mode: "lines", yaxis: "y" }, { x: dates, y: values("datacenter_power_mw"), name: "AI DC power MW", mode: "lines", yaxis: "y2" }], baseLayout({ yaxis: { title: "H100-equivalents", gridcolor: "#203545" }, yaxis2: { title: "MW", overlaying: "y", side: "right", showgrid: false } }), plotConfig);
    Plotly.newPlot("apiChart", [{ x: dates, y: values("api_speed_index"), name: "Output speed", mode: "lines" }, { x: dates, y: values("api_latency_index"), name: "TTFT / latency", mode: "lines" }, { x: dates, y: values("api_price_index"), name: "Output price", mode: "lines", line: { dash: "dot" } }], baseLayout({ yaxis: { title: "Index (base = 100)", gridcolor: "#203545" } }), plotConfig);
    const training = D.training_events || [];
    Plotly.newPlot("trainingChart", [{ x: training.map((row) => row.date), y: training.map((row) => row.flop), text: training.map((row) => row.model), name: "Training runs", mode: "markers", marker: { size: 8 }, hovertemplate: "%{text}<br>%{x}<br>%{y:.2e} FLOP<extra></extra>" }], baseLayout({ showlegend: false, yaxis: { title: "Training FLOP", type: "log", gridcolor: "#203545" } }), plotConfig);
    const residuals = D.grid_residuals || [];
    const gridTraces = [];
    [...new Set(residuals.map((row) => row.region))].forEach((region) => {
      const rows = residuals.filter((row) => row.region === region);
      gridTraces.push({ x: rows.map((row) => row.date), y: rows.map((row) => row.grid_load_mw), name: `${region} load`, mode: "lines" });
      gridTraces.push({ x: rows.map((row) => row.date), y: rows.map((row) => row.grid_residual_mw), name: `${region} residual`, mode: "lines", line: { dash: "dot" } });
    });
    Plotly.newPlot("gridChart", gridTraces, baseLayout({ yaxis: { title: "MW", gridcolor: "#203545" } }), plotConfig);

    const table = byId("sourceTable");
    table.innerHTML = "";
    (D.source_health || []).sort((a, b) => a.source.localeCompare(b.source)).forEach((row) => {
      table.insertAdjacentHTML("beforeend", `<tr><td>${escapeHtml(row.source)}</td><td><span class="status ${escapeHtml(row.status)}">${escapeHtml(row.status)}</span></td><td>${escapeHtml(row.latest_observation || "—")}</td><td>${escapeHtml(row.last_collection || "—")}</td><td>${fmt(row.rows)}</td></tr>`);
    });
  }

  let scenario = "base";
  let selectedTicker = E.companies?.[0]?.ticker || "MSFT";
  let overrides = {};
  try { overrides = JSON.parse(localStorage.getItem("infrastructureEconomicsOverrides") || "{}"); } catch (_) { overrides = {}; }

  function overrideKey(ticker, scenarioName, key) { return `${ticker}:${scenarioName}:${key}`; }
  function company(ticker = selectedTicker) { return E.companies.find((item) => item.ticker === ticker); }

  function resolvedProfile(ticker, scenarioName) {
    const source = company(ticker)?.scenarios?.[scenarioName]?.inputs || {};
    const inputs = {};
    Object.entries(source).forEach(([key, item]) => {
      const stored = overrides[overrideKey(ticker, scenarioName, key)];
      inputs[key] = { ...item };
      if (stored != null && Number.isFinite(Number(stored))) {
        inputs[key].value = Number(stored);
        inputs[key].classification = "user-supplied";
        inputs[key].source = "Browser override";
        inputs[key].source_url = "";
        inputs[key].note = "Locally edited; reset restores the versioned scenario value.";
      }
    });
    return inputs;
  }

  function valuesOnly(profile) {
    return Object.fromEntries(Object.entries(profile).map(([key, item]) => [key, finite(item.value)]));
  }

  function irr(cashFlows) {
    if (!cashFlows.length || cashFlows[0] >= 0 || !cashFlows.slice(1).some((value) => value > 0)) return null;
    const npv = (rate) => cashFlows.reduce((sum, value, year) => sum + value / ((1 + rate) ** year), 0);
    let low = -.9999;
    let high = 10;
    let lowValue = npv(low);
    if (lowValue * npv(high) > 0) return null;
    for (let index = 0; index < 180; index += 1) {
      const middle = (low + high) / 2;
      const value = npv(middle);
      if (Math.abs(value) < 1e-10) return middle;
      if (lowValue * value <= 0) high = middle;
      else { low = middle; lowValue = value; }
    }
    return (low + high) / 2;
  }

  function calculateEconomics(input) {
    const totalCapex = Math.max(finite(input.total_capex_basis_usd_b), 0);
    const projectCapex = totalCapex * finite(input.ai_capex_share_pct) / 100;
    const hardwareCapex = projectCapex * finite(input.gpu_hardware_share_pct) / 100;
    const gpuEquivalents = hardwareCapex * 1e9 / Math.max(finite(input.all_in_gpu_cost_usd), 1);
    const maximumRevenue = gpuEquivalents * 8760 * Math.max(finite(input.blended_revenue_per_gpu_hour_usd), 0) / 1e9;
    const firstYearRevenue = Math.max(finite(input.annual_project_revenue_usd_b), 0);
    const utilization = maximumRevenue ? firstYearRevenue / maximumRevenue : null;
    const physicalUtilization = Math.min(Math.max(utilization || 0, 0), 1);
    const pue = Math.max(finite(input.pue, 1), 1);
    const energyPrice = Math.max(finite(input.energy_cost_per_kwh_usd), 0);
    const powerKw = Math.max(finite(input.gpu_power_kw), 0);
    const firstYearEnergy = gpuEquivalents * powerKw * pue * 8760 * physicalUtilization * energyPrice / 1e9;
    const nonPowerOpex = firstYearRevenue * finite(input.non_power_opex_pct_revenue) / 100;
    const depreciationYears = Math.max(Math.round(finite(input.depreciation_years, 5)), 1);
    const annualDepreciation = projectCapex / depreciationYears;
    const yearOneEbit = firstYearRevenue - nonPowerOpex - firstYearEnergy - annualDepreciation;
    const taxRate = finite(input.tax_rate_pct) / 100;
    const yearOneNopat = yearOneEbit * (1 - taxRate);
    const maintenanceRate = finite(input.maintenance_capex_pct_revenue) / 100;
    const life = Math.max(Math.round(finite(input.project_life_years, 8)), 1);
    const growth = finite(input.revenue_growth_pct) / 100;
    const cashFlows = [-projectCapex];
    const rows = [{ year: 0, revenue_usd_b: 0, energy_cost_usd_b: 0, depreciation_usd_b: 0, free_cash_flow_usd_b: -projectCapex, cumulative_cash_flow_usd_b: -projectCapex }];
    let cumulative = -projectCapex;
    let previousCumulative = cumulative;
    let payback = null;
    for (let year = 1; year <= life; year += 1) {
      const revenue = firstYearRevenue * ((1 + growth) ** (year - 1));
      const yearUtilization = maximumRevenue ? revenue / maximumRevenue : 0;
      const energy = gpuEquivalents * powerKw * pue * 8760 * Math.min(Math.max(yearUtilization, 0), 1) * energyPrice / 1e9;
      const cashOpex = revenue * finite(input.non_power_opex_pct_revenue) / 100 + energy;
      const depreciation = year <= depreciationYears ? annualDepreciation : 0;
      const ebit = revenue - cashOpex - depreciation;
      const cashTax = Math.max(ebit, 0) * taxRate;
      const maintenance = revenue * maintenanceRate;
      let freeCashFlow = revenue - cashOpex - cashTax - maintenance;
      if (year === life) freeCashFlow += projectCapex * finite(input.residual_value_pct) / 100;
      cashFlows.push(freeCashFlow);
      cumulative += freeCashFlow;
      if (payback == null && cumulative >= 0 && freeCashFlow > 0) payback = year - 1 + (-previousCumulative / freeCashFlow);
      rows.push({ year, revenue_usd_b: revenue, energy_cost_usd_b: energy, depreciation_usd_b: depreciation, free_cash_flow_usd_b: freeCashFlow, cumulative_cash_flow_usd_b: cumulative });
      previousCumulative = cumulative;
    }
    const projectIrr = irr(cashFlows);
    const discountRate = finite(input.discount_rate_pct) / 100;
    const projectNpv = cashFlows.reduce((sum, value, year) => sum + value / ((1 + discountRate) ** year), 0);
    const ratio = (numerator, denominator) => denominator ? numerator / denominator * 100 : null;
    return {
      project_capex_usd_b: projectCapex,
      gpu_equivalents: gpuEquivalents,
      maximum_revenue_usd_b: maximumRevenue,
      annual_energy_cost_usd_b: firstYearEnergy,
      project_irr_pct: projectIrr == null ? null : projectIrr * 100,
      data_center_roic_pct: ratio(yearOneNopat, projectCapex),
      gpu_utilization_pct: utilization == null ? null : utilization * 100,
      payback_years: payback,
      depreciation_adjusted_return_pct: ratio(yearOneNopat + annualDepreciation, projectCapex),
      marginal_operating_margin_pct: ratio(yearOneEbit, firstYearRevenue),
      project_npv_usd_b: projectNpv,
      cash_flows: rows,
    };
  }

  function companyResult(ticker, scenarioName = scenario) {
    return calculateEconomics(valuesOnly(resolvedProfile(ticker, scenarioName)));
  }

  const metricFormatters = {
    project_irr_pct: (value) => fmtPct(value),
    data_center_roic_pct: (value) => fmtPct(value),
    gpu_utilization_pct: (value) => fmtPct(value),
    payback_years: (value) => value == null ? "> project life" : `${fmt(value, 1)} yrs`,
    depreciation_adjusted_return_pct: (value) => fmtPct(value),
    marginal_operating_margin_pct: (value) => fmtPct(value),
  };

  function renderEconomicsKpis() {
    const current = company();
    const result = companyResult(selectedTicker);
    byId("economicsKpis").innerHTML = (E.metrics || []).map((metric) => `<article class="panel metric-card"><div class="metric-head"><span>${escapeHtml(metric.label)}</span>${badge(metric.classification)}</div><div class="metric-value">${metricFormatters[metric.key]?.(result[metric.key]) ?? fmt(result[metric.key], 1)}</div><div class="metric-foot">${escapeHtml(current.name)} · ${escapeHtml(scenario)} scenario</div></article>`).join("");
    const warnings = [];
    if (result.gpu_utilization_pct > 100) warnings.push("Modeled utilization exceeds 100%; increase capacity or value per GPU-hour, or reduce project revenue.");
    if (result.project_irr_pct == null) warnings.push("No conventional positive IRR exists within the modeled project life.");
    const warning = byId("modelWarning");
    warning.textContent = warnings.join(" ");
    warning.style.display = warnings.length ? "block" : "none";
  }

  function renderEconomicsCharts() {
    const companies = E.companies || [];
    const names = companies.map((item) => item.name);
    const results = companies.map((item) => companyResult(item.ticker));
    const colors = companies.map((item) => item.color);
    Plotly.react("returnChart", [
      { x: names, y: results.map((row) => row.project_irr_pct), name: "Project IRR", type: "bar" },
      { x: names, y: results.map((row) => row.data_center_roic_pct), name: "Data-center ROIC", type: "bar" },
      { x: names, y: results.map((row) => row.depreciation_adjusted_return_pct), name: "Dep.-adjusted return", type: "bar" },
      { x: names, y: results.map((row) => row.marginal_operating_margin_pct), name: "Marginal op. margin", type: "bar" },
    ], baseLayout({ barmode: "group", yaxis: { title: "Percent", ticksuffix: "%", gridcolor: "#203545" }, hovermode: "closest" }), plotConfig);

    Plotly.react("utilizationChart", [{
      x: results.map((row) => row.gpu_utilization_pct),
      y: results.map((row) => row.payback_years),
      text: names,
      customdata: results.map((row) => [row.project_irr_pct, row.project_capex_usd_b]),
      mode: "markers+text",
      textposition: "top center",
      marker: { color: colors, size: results.map((row) => Math.max(13, Math.sqrt(Math.max(row.project_capex_usd_b, 0)) * 3.1)), line: { color: "#dbeaf0", width: 1 }, opacity: .86 },
      hovertemplate: "%{text}<br>Utilization %{x:.1f}%<br>Payback %{y:.1f} years<br>IRR %{customdata[0]:.1f}%<br>Project capex $%{customdata[1]:.1f}B<extra></extra>",
    }], baseLayout({ showlegend: false, hovermode: "closest", xaxis: { title: "Calculated GPU utilization", ticksuffix: "%", gridcolor: "#203545" }, yaxis: { title: "Payback years", gridcolor: "#203545" }, margin: { l: 55, r: 20, t: 28, b: 50 } }), plotConfig);

    const current = company();
    const rows = companyResult(selectedTicker).cash_flows;
    byId("cashFlowTitle").textContent = `${current.name} project cash-flow path`;
    Plotly.react("cashFlowChart", [
      { x: rows.map((row) => `Y${row.year}`), y: rows.map((row) => row.free_cash_flow_usd_b), name: "Annual FCF", type: "bar", marker: { color: rows.map((row) => row.free_cash_flow_usd_b < 0 ? "#ff7c82" : current.color) } },
      { x: rows.map((row) => `Y${row.year}`), y: rows.map((row) => row.cumulative_cash_flow_usd_b), name: "Cumulative", mode: "lines+markers", yaxis: "y2", line: { color: "#edf4f8", width: 2 } },
    ], baseLayout({ hovermode: "x unified", yaxis: { title: "Annual FCF ($B)", gridcolor: "#203545" }, yaxis2: { title: "Cumulative ($B)", overlaying: "y", side: "right", showgrid: false }, margin: { l: 55, r: 55, t: 28, b: 45 } }), plotConfig);
  }

  const assumptionGroups = [
    ["Capital & capacity", ["total_capex_basis_usd_b", "ai_capex_share_pct", "gpu_hardware_share_pct", "all_in_gpu_cost_usd", "gpu_power_kw", "pue"]],
    ["Revenue & operating cost", ["annual_project_revenue_usd_b", "blended_revenue_per_gpu_hour_usd", "non_power_opex_pct_revenue", "energy_cost_per_kwh_usd", "revenue_growth_pct", "maintenance_capex_pct_revenue"]],
    ["Returns & life cycle", ["depreciation_years", "tax_rate_pct", "discount_rate_pct", "project_life_years", "residual_value_pct"]],
  ];

  function setOverride(key, value, updateInputs = false) {
    const definition = E.assumptions.find((item) => item.key === key);
    const bounded = Math.min(Math.max(Number(value), Number(definition.min)), Number(definition.max));
    overrides[overrideKey(selectedTicker, scenario, key)] = bounded;
    try { localStorage.setItem("infrastructureEconomicsOverrides", JSON.stringify(overrides)); } catch (_) { /* device storage is optional */ }
    renderEconomicsKpis();
    renderEconomicsCharts();
    if (updateInputs) renderAssumptions();
  }

  function renderAssumptions() {
    const profile = resolvedProfile(selectedTicker, scenario);
    const definitions = Object.fromEntries(E.assumptions.map((item) => [item.key, item]));
    byId("assumptionSubtitle").textContent = `${company().name} · ${scenario} scenario`;
    byId("assumptionInputs").innerHTML = assumptionGroups.map(([groupName, keys]) => `<div class="assumption-group"><h4>${escapeHtml(groupName)}</h4>${keys.map((key) => {
      const definition = definitions[key];
      const item = profile[key];
      if (!definition || !item) return "";
      const source = item.source_url ? `<a class="source-link" href="${escapeHtml(item.source_url)}" target="_blank" rel="noopener">source ↗</a>` : `<span>${escapeHtml(definition.short_unit)}</span>`;
      return `<div class="assumption-row" data-assumption="${escapeHtml(key)}"><label for="range-${escapeHtml(key)}"><span>${escapeHtml(definition.label)}</span>${badge(item.classification)}</label><div class="input-wrap"><input id="range-${escapeHtml(key)}" type="range" min="${definition.min}" max="${definition.max}" step="${definition.step}" value="${item.value}" aria-label="${escapeHtml(definition.label)}"><input class="input-number" type="number" min="${definition.min}" max="${definition.max}" step="${definition.step}" value="${item.value}" aria-label="${escapeHtml(definition.label)} numeric value"></div><div class="assumption-help"><span title="${escapeHtml(definition.description)}">${escapeHtml(item.source)} · ${escapeHtml(item.period || E.meta?.as_of || "")}</span>${source}</div></div>`;
    }).join("")}</div>`).join("");

    byId("assumptionInputs").querySelectorAll(".assumption-row").forEach((row) => {
      const key = row.dataset.assumption;
      const range = row.querySelector('input[type="range"]');
      const number = row.querySelector('input[type="number"]');
      range.addEventListener("input", () => { number.value = range.value; setOverride(key, range.value, false); });
      number.addEventListener("input", () => { if (number.value !== "") { range.value = number.value; setOverride(key, number.value, false); } });
      range.addEventListener("change", () => renderAssumptions());
      number.addEventListener("change", () => renderAssumptions());
    });
  }

  function formatReportedValue(item) {
    if (item.unit === "USD") return `$${fmt(item.value / 1e9, 2)}B`;
    if (String(item.unit).includes("percent") || item.unit === "%") return fmtPct(item.value, 1);
    return `${fmt(item.value, 1)} ${escapeHtml(item.unit || "")}`;
  }

  function renderReportedContext() {
    const rows = company().reported_context || [];
    byId("reportedContext").innerHTML = rows.length ? rows.map((item) => `<tr><td>${escapeHtml(item.label)}</td><td>${formatReportedValue(item)}</td><td>${badge(item.classification)}</td><td>${escapeHtml(item.period || "—")}</td><td>${item.source_url ? `<a class="source-link" href="${escapeHtml(item.source_url)}" target="_blank" rel="noopener">${escapeHtml(item.source || "Primary source")} ↗</a>` : escapeHtml(item.source || "—")}</td></tr>`).join("") : `<tr><td class="empty-row" colspan="5">No recognized reported context is in this snapshot. Scenario fallbacks remain visibly labeled estimated.</td></tr>`;
  }

  function renderEconomics() {
    renderEconomicsKpis();
    renderEconomicsCharts();
    renderAssumptions();
    renderReportedContext();
  }

  function initializeEconomics() {
    const select = byId("companySelect");
    select.innerHTML = E.companies.map((item) => `<option value="${escapeHtml(item.ticker)}">${escapeHtml(item.name)} · ${escapeHtml(item.ticker)}</option>`).join("");
    select.value = selectedTicker;
    select.addEventListener("change", () => { selectedTicker = select.value; renderEconomics(); });
    document.querySelectorAll("[data-scenario]").forEach((button) => button.addEventListener("click", () => {
      scenario = button.dataset.scenario;
      document.querySelectorAll("[data-scenario]").forEach((item) => item.classList.toggle("active", item === button));
      renderEconomics();
    }));
    byId("resetAssumptions").addEventListener("click", () => {
      Object.keys(overrides).filter((key) => key.startsWith(`${selectedTicker}:${scenario}:`)).forEach((key) => delete overrides[key]);
      try { localStorage.setItem("infrastructureEconomicsOverrides", JSON.stringify(overrides)); } catch (_) { /* optional */ }
      renderEconomics();
    });
    byId("exportAssumptions").addEventListener("click", () => {
      const result = companyResult(selectedTicker);
      const calculatedMetrics = Object.fromEntries((E.metrics || []).map((metric) => [metric.key, { label: metric.label, value: result[metric.key], unit: metric.unit, classification: metric.classification }]));
      const exportData = { company: selectedTicker, scenario, exported_at: new Date().toISOString(), inputs: resolvedProfile(selectedTicker, scenario), calculated_metrics: calculatedMetrics };
      const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: "application/json" });
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = `${selectedTicker.toLowerCase()}-${scenario}-infrastructure-economics.json`;
      link.click();
      setTimeout(() => URL.revokeObjectURL(link.href), 1000);
    });
  }

  function renderMethodology() {
    byId("metricMethodology").innerHTML = (E.metrics || []).map((metric) => `<article class="panel"><div class="metric-head"><span>${escapeHtml(metric.label)}</span>${badge(metric.classification)}</div><h3>${escapeHtml(metric.label)}</h3><p>${escapeHtml(metric.formula)}</p></article>`).join("");
  }

  function setView(viewName, replaceHash = true) {
    document.querySelectorAll(".view").forEach((view) => view.classList.toggle("active", view.id === `view-${viewName}`));
    document.querySelectorAll(".module-tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.view === viewName));
    if (replaceHash) history.replaceState(null, "", viewName === "demand" ? location.pathname + location.search : `#${viewName}`);
    if (viewName === "economics") {
      renderEconomics();
      requestAnimationFrame(() => ["returnChart", "utilizationChart", "cashFlowChart"].forEach((id) => Plotly.Plots.resize(byId(id))));
    }
  }

  function initializeNavigation() {
    document.querySelectorAll(".module-tab").forEach((tab) => tab.addEventListener("click", () => setView(tab.dataset.view)));
    const initial = ["economics", "methodology"].includes(location.hash.slice(1)) ? location.hash.slice(1) : "demand";
    setView(initial, false);
  }

  initializeHeader();
  renderDemand();
  initializeEconomics();
  renderMethodology();
  initializeNavigation();
})();
