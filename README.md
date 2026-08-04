# AI Compute Demand Dashboard

A deployable, audit-friendly dashboard for measuring AI workload, physical compute consumption, capacity, and market tightness.

The repository is designed to run on **GitHub Actions every six hours**, append observations to Git-tracked history, rebuild a static interactive dashboard, and publish it with **GitHub Pages**. It degrades gracefully: a failed or missing source is shown as stale/missing instead of silently replaced.

## What the dashboard measures

| Pillar | Headline measure | Primary inputs |
|---|---|---|
| Workload | Observed tokens and a fixed-weight workload index | OpenRouter rankings; optional manual/global anchors |
| Physical consumption | Estimated H100-equivalent hours and power proxy | Model token mix × configurable compute weights; grid load |
| Tightness | GPU rental price, availability, rented share, API latency | Vast.ai and Artificial Analysis |
| Capacity | Operational H100-equivalent capacity and AI data-center MW | Epoch AI data-center and cluster datasets |
| Efficiency | Tokens per estimated H100-hour, model speed and price | Artificial Analysis, OpenRouter catalog, MLPerf calibration files |

## AI Infrastructure Economics

The **Infrastructure economics** module is part of the same generated GitHub Pages site. It compares Microsoft, Amazon, Alphabet, Meta, Oracle, and CoreWeave under editable bear/base/bull cases and calculates:

- project IRR;
- data-center ROIC;
- implied GPU utilization;
- fractional payback period;
- depreciation-adjusted return; and
- marginal operating margin.

Each visible input and output carries one of four labels:

| Label | Meaning |
|---|---|
| Reported | Direct company disclosure collected from a filing, earnings release, or sourced call transcript |
| Calculated | Deterministic output of a documented formula |
| Estimated | Versioned model assumption or fallback not directly disclosed by the company |
| User-supplied | A local browser override; reset restores the versioned scenario value |

Scenario defaults and input ranges live in `config/infrastructure_economics.yml`. Browser edits are saved only on the device and can be exported as JSON; they never overwrite repository data.

### Economics formulas

```text
AI project capex = reported/fallback capital-spend basis × AI allocation share
GPU-equivalents  = project capex × accelerated-compute share ÷ all-in GPU cost
GPU utilization = annual project revenue ÷ (GPU-equivalents × 8,760 × value/GPU-hour)

Marginal operating margin =
  (revenue − non-power opex − electricity − straight-line depreciation) ÷ revenue

Data-center ROIC = year-one NOPAT ÷ AI project capex
Depreciation-adjusted return = (year-one NOPAT + depreciation) ÷ AI project capex
Project IRR = discount rate that sets the modeled project cash-flow NPV to zero
Payback = first fractional year in which cumulative unlevered cash flow is positive
```

The model excludes financing structure, working capital, land timing, prepayments, tax credits, and company-level overhead. Internal-use capacity is assigned an estimated economic value per GPU-hour and is not treated as reported cloud pricing.

**Important:** raw tokens are not comparable across all providers or models. The dashboard therefore keeps raw observed tokens separate from compute-weighted estimates and marks model-weight assumptions explicitly.

## Repository layout

```text
.github/workflows/update-dashboard.yml  scheduled collection + Pages deployment
config/dashboard.yml                    sources, zones, thresholds, assumptions
config/infrastructure_economics.yml     bear/base/bull economics model inputs
config/model_weights.csv                editable compute-per-token assumptions
data/observations.csv                   append-only normalized observations
 data/manual/                            disclosed/global anchors and call overlays
 data/raw/                               downloaded source snapshots (gitignored by default)
docs/index.html                         static interactive dashboard
src/ai_compute_dashboard/               collectors, storage, metrics, site builder
tests/                                  calculation tests
```

## Fast start

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\\Scripts\\activate
pip install -e .
npm install
cp .env.example .env
python -m ai_compute_dashboard.pipeline demo
python -m ai_compute_dashboard.pipeline build
python -m http.server 8000 --directory docs
```

Open `http://localhost:8000`.

The repository ships with **clearly labeled synthetic demo data** so the interface can be reviewed before credentials are added. Running `collect` never fabricates missing live data.

## Live setup on GitHub

1. Create an empty GitHub repository.
2. Copy this repository into it and push to `main`.
3. In **Settings → Secrets and variables → Actions**, add whichever keys you have:

| Secret | Purpose | Required? |
|---|---|---|
| `OPENROUTER_API_KEY` | Daily top-50 model token totals | Strongly recommended |
| `EIA_API_KEY` | Hourly grid load by balancing authority | Strongly recommended |
| `ARTIFICIAL_ANALYSIS_API_KEY` | Model speed, latency, quality and price | Recommended; free key works |
| `VAST_API_KEY` | Current rental offers | Recommended |
| `VAST_HOST_API_KEY` | Vast supply/demand market metrics and history | Optional; host keys only |
| `SEC_USER_AGENT` | Descriptive SEC API user agent, including a contact address | Recommended for quarterly economics updates |
| `ECONOMICS_DISCLOSURES_URL` | Optional normalized CSV/JSON feed of sourced earnings-call disclosures | Optional |

4. Under **Settings → Pages**, select **GitHub Actions** as the source.
5. Run **Actions → Update AI compute dashboard → Run workflow** once.

The workflow:

- runs at minute 17 every six hours;
- calls every configured collector independently;
- appends and de-duplicates observations;
- rebuilds `docs/index.html` and `docs/data/dashboard.json`;
- commits data changes back to `main`;
- deploys `docs/` to GitHub Pages.

For the economics module, the same run also queries the SEC Company Facts API for recognized quarterly and annual facts. A normalized earnings-call feed can supply company-specific `company_ai_infrastructure_revenue`, `company_gpu_utilization`, and `company_active_power_mw` observations without changing the calculation code.

Scheduled GitHub Actions are not guaranteed to start at the exact minute under heavy platform load, so the dashboard displays source age and last-success time.

## Local collection

```bash
# Collect all sources that have credentials/configuration
python -m ai_compute_dashboard.pipeline collect

# Recompute indices and rebuild the site
python -m ai_compute_dashboard.pipeline build

# Both steps
python -m ai_compute_dashboard.pipeline run
```

Useful environment variables:

```bash
BACKFILL_DAYS=30
DASHBOARD_CONFIG=config/dashboard.yml
OBSERVATIONS_PATH=data/observations.csv
```

For an initial grid-history backfill, temporarily use `BACKFILL_DAYS=365`. Later scheduled runs can use 14–30 days because storage is de-duplicated.

## Data model

Every observation uses the same long-form schema:

```text
observed_at_utc, source, metric, dimension, value, unit,
quality, is_estimate, collected_at_utc, provenance, metadata_json
```

Examples:

```text
2026-07-24,openrouter,tokens_total,openai/gpt-x,1.25e11,tokens,observed,false,...
2026-07-24,vast,gpu_price,H100_SXM,2.15,USD/GPU-hour,observed,false,...
2026-07-24,derived,h100_equivalent_hours,openrouter_observed,88000,H100-hour,estimated,true,...
2026-06-30,sec_companyfacts,company_capex,MSFT,3.1e10,USD,reported,false,...
```

## Compute-weighted token methodology

For each model/day:

```text
input_tokens  = total_tokens × (1 - assumed_output_share)
output_tokens = total_tokens × assumed_output_share

H100 seconds =
  input_tokens / 1,000,000 × input_h100_seconds_per_million
+ output_tokens / 1,000,000 × output_h100_seconds_per_million
```

The weight table is pattern-based and intentionally editable. Unknown models receive the default weight. Reasoning-model patterns can receive a multiplier. The site shows the share of tokens assigned low-confidence/default weights.

Two index concepts are kept separate:

- **Fixed-weight workload index:** holds model compute weights fixed, measuring workload quantity/mix.
- **Physical consumption estimate:** can use updated efficiency calibrations, approximating actual accelerator hours.

The starter repository uses one weight table for both, but the schema supports dated calibration tables later.

## Weather-adjusted grid residual

When enough matching temperature and load history exists, the pipeline fits a rolling daily model for each configured balancing authority:

```text
load = intercept + CDD65 + HDD65 + weekday effects + time trend
```

The residual is a physical-load cross-check, not a pure AI measurement. Data centers, manufacturing and other structural load can all affect it. Until at least 60 daily observations exist, the dashboard displays raw load growth rather than a residual.

## Adding global token anchors

No public source is a complete global token meter. Add disclosed or independently modeled anchors to:

`data/manual/global_token_estimates.csv`

with columns:

```text
date,low_tokens,central_tokens,high_tokens,source,notes
```

The dashboard will display these separately from OpenRouter-observed traffic. Do not scale OpenRouter to the world without an explicit, versioned scaling assumption.

## Source behavior

- **OpenRouter:** official SDK; top 50 public models plus `other`; requires a key.
- **OpenRouter model catalog:** public pricing/context metadata; no key.
- **Artificial Analysis:** free V2 language-model endpoint; requires a free key and attribution.
- **Vast.ai:** offer search requires a client key. Full supply/demand metrics require a host key.
- **EIA:** hourly RTO/BA load endpoint; requires a free EIA key.
- **Open-Meteo:** recent temperature history for weather normalization; no key.
- **Epoch AI:** public CSV downloads; schema is detected defensively and raw snapshots are retained locally.
- **MLPerf:** official summary results JSON is downloaded as a calibration reference; no key.
- **SEC Company Facts:** no API key; standardized revenue, capex, depreciation, operating income, and operating cash flow for the six modeled companies. Set a descriptive `SEC_USER_AGENT`.
- **Company disclosures:** optional normalized CSV/JSON overlay for earnings-call and investor-relations disclosures. Every row must include its classification and source URL; `data/manual/company_disclosures.csv` is the version-controlled fallback.

## Quarterly economics update contract

The optional disclosure feed uses these columns:

```text
observed_at_utc,ticker,metric,value,unit,classification,
source_url,source_label,notes
```

Supported economics disclosures include `company_ai_infrastructure_revenue`, `company_gpu_utilization`, and `company_active_power_mw`. Additive fields remain visible as reported context. AI-infrastructure revenue can replace the base-case revenue assumption when directly reported; bear and bull cases remain estimated scenario transformations. Raw snapshots are retained under `data/raw/`, normalized records append to `data/observations.csv`, and the generated economics payload is published in `docs/data/dashboard.json`.

## Production hardening

For a serious investment/research deployment, the next upgrades should be:

1. Move immutable raw snapshots to S3/R2 and keep Git only for processed daily data.
2. Add a hosted Postgres/Timescale database if hourly history becomes large.
3. Create dated model-weight calibration tables from MLPerf and independent serving tests.
4. Add first-party disclosures and revenue/user anchors to the manual-ingestion process.
5. Add alert thresholds for acceleration, source breaks and model-mix shifts.
6. Add regional power-price and interconnection-queue datasets.

## Licensing and attribution

Code is MIT licensed. Data retains each source's original terms. The dashboard footer includes required source attribution. Review source terms before commercial redistribution.
