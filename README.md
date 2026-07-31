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

**Important:** raw tokens are not comparable across all providers or models. The dashboard therefore keeps raw observed tokens separate from compute-weighted estimates and marks model-weight assumptions explicitly.

## Repository layout

```text
.github/workflows/update-dashboard.yml  scheduled collection + Pages deployment
config/dashboard.yml                    sources, zones, thresholds, assumptions
config/model_weights.csv                editable compute-per-token assumptions
data/observations.csv                   append-only normalized observations
 data/manual/                            disclosed/global anchors you add manually
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

4. Under **Settings → Pages**, select **GitHub Actions** as the source.
5. Run **Actions → Update AI compute dashboard → Run workflow** once.

The workflow:

- runs at minute 17 every six hours;
- calls every configured collector independently;
- appends and de-duplicates observations;
- rebuilds `docs/index.html` and `docs/data/dashboard.json`;
- commits data changes back to `main`;
- deploys `docs/` to GitHub Pages.

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
