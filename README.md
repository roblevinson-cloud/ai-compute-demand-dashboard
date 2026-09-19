# GridSignal — Data Center Development Intelligence

GridSignal is a runnable MVP for discovering U.S. data-center projects before they become national business-news stories. It monitors primary and local sources, preserves the original evidence, converts documents into a fixed event schema, and maintains one auditable record per project.

The included dashboard combines the repository's **24-project national data-center portfolio** with a discovery investigation for **Google's unnamed Lea County announcement**. Project Jupiter is de-duplicated against the newer evidence-backed New Mexico record, producing **25 unique tracked projects**. The evidence supports keeping Google's Lea County signal separate from Project Jupiter: they are in different counties, have different named parties, and share no known parcel, utility, site-control, or project alias.

## What is implemented

- PostgreSQL schema for projects, aliases, companies and relationships, sources, raw documents, extracted events, project events, fact claims, entity-match candidates, alerts, digests, checkpoints, collection runs, and errors.
- Hourly-capable source registry prioritizing PUC/PRC, environmental, county, utility, economic-development, company, local-media, and industry sources.
- Conditional web/RSS collectors with immutable, SHA-256-addressed raw snapshots.
- Versioned structured extraction with an inexpensive deterministic fallback and a clean seam for stronger model adapters.
- Conservative entity resolution with explicit feature weights, contradiction penalties, and a human review queue.
- Transparent 0–100 materiality, novelty, and confidence scores with stored factor breakdowns.
- Immediate-alert queue for events crossing materiality, novelty, and confidence thresholds.
- Morning (6:30 a.m. Eastern) and evening (6:00 p.m. Eastern) digest windows, stored in PostgreSQL and emitted as text and email-ready HTML.
- Responsive dashboard with project search/filtering, evidence-backed project pages, an event feed, entity review queue, source health, and report archive.
- Tests for extraction, scoring, resolution, source configuration, demo integrity, and digest output.

## Quick start: review the New Mexico pilot

The committed dashboard is already built in `docs/`. `build-demo` imports the three portfolio datasets under `docs/data-centers/data/`, preserves their capacity and financing boundaries, and merges them with the newer New Mexico records. To rebuild and serve it:

```powershell
.\.venv\Scripts\python.exe -m dc_intel.cli build-demo
.\.venv\Scripts\python.exe -m http.server 8080 --directory docs
```

Open `http://localhost:8080`.

The pilot is intentionally explicit about fact boundaries:

- Project Jupiter's **2.45 GW** is the proposed Bloom fuel-cell generation nameplate, not verified IT MW or utility load.
- The **$165 billion** figure is an IRB authorization ceiling, not confirmed project spend.
- Google's Lea County record remains an early signal because no parcel, MW, utility, acreage, or formal application is linked yet.

## Run the PostgreSQL-backed worker

Copy `.env.example` to `.env`, change the database password, then run:

```powershell
docker compose up --build
```

This starts PostgreSQL with a persistent volume, a one-time schema initializer, the collection/processing worker, and the dashboard on `http://localhost:8080`.

Without Docker:

```powershell
pip install -e ".[dev]"
$env:DATABASE_URL = "postgresql://dcintel:dcintel@localhost:5432/dcintel"
dc-intel init-db
dc-intel sync-sources
dc-intel run-once
dc-intel worker --poll-seconds 60
```

## Commands

| Command | Purpose |
|---|---|
| `dc-intel build-demo` | Build the evidence-backed New Mexico dashboard |
| `dc-intel build-live` | Build the same dashboard from PostgreSQL records |
| `dc-intel source-summary` | Validate and summarize the source registry |
| `dc-intel init-db` | Apply the PostgreSQL schema idempotently |
| `dc-intel sync-sources` | Upsert `config/sources.yml` into PostgreSQL |
| `dc-intel seed-demo-db` | Upsert the evidence-backed pilot into PostgreSQL |
| `dc-intel collect` | Poll only sources that are due |
| `dc-intel process` | Extract and resolve unprocessed documents |
| `dc-intel run-once` | Sync, collect, and process a complete cycle |
| `dc-intel worker` | Continuously run collection, processing, alerts, and scheduled digests |
| `dc-intel digest --type morning` | Generate a standalone email-ready pilot brief |

## Pipeline

```text
Source registry
   ↓ conditional GET / RSS / document index
Immutable raw document + content hash
   ↓ fixed extraction schema
Extracted event + evidence spans
   ↓ project candidate scoring
Linked project event OR explicit review candidate
   ↓ fact comparison and score breakdowns
Current project facts + timeline + alert/digest eligibility
```

Documents are the evidence layer; events are the change layer; projects are the analytical unit. A repeated article may be stored for audit while receiving a low novelty score and no prominent placement.

## PostgreSQL model

The schema is in [`src/dc_intel/schema.sql`](src/dc_intel/schema.sql). Important separations include:

- `raw_documents` stores immutable source snapshots and retrieval metadata.
- `extracted_events` stores the versioned model/deterministic output.
- `project_events` stores the project link, novelty decision, and three score breakdowns.
- `fact_claims` stores every claim with document-level provenance and an evidence excerpt; superseded values remain queryable.
- `entity_match_candidates` stores both supporting and conflicting evidence. Even high-scoring candidates remain auditable.
- `alerts` and `digests` are delivery artifacts, separate from the underlying event record.

## Extraction contract

Every incoming document maps to schema version `1.0` with event type, project name and aliases, company/role mentions, normalized location, typed fact candidates with evidence, docket and permit identifiers, discovery triggers, confidence, and warnings.

The deterministic extractor is intentionally conservative. It is suitable for routine triage and makes uncertainty visible. Production adapters should send difficult documents—scanned PDFs, ambiguous aliases, complex multi-project packets, or conflicting facts—to a stronger model while returning exactly the same schema.

## Entity resolution rules

The resolver compares parcel/address, county/state, developer, tenant, utility, MW, acreage, and aliases. Different counties and conflicting named tenants are hard conflicts. Results are:

- `candidate_auto_link`: score at least 88 and no hard conflict;
- `human_review`: score 45–87;
- `likely_new_project`: score below 45.

“Auto-link” is a recommendation, not permission to erase the candidate trail. Facility boundaries matter: the demo links the YGI Microgrid to Project Jupiter while preserving it as an adjacent power facility with a separate permit scope.

## Scoring

- **Materiality** is additive across event significance, MW, capital scale, project stage, regulatory effect, named major parties, and schedule/cancellation risk.
- **Novelty** rewards new or changed facts and first primary records, then subtracts content-duplication penalties.
- **Confidence** separately weights source reliability, extraction certainty, entity-match certainty, and corroboration.

Primary regulatory and government sources have higher default reliability weights than company announcements or media. Score components are stored as JSON on each project event and displayed independently.

## Operations and expansion

- [Architecture](documentation/architecture.md)
- [Operations and source onboarding](documentation/operations.md)
- [U.S. coverage roadmap](documentation/roadmap.md)

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The test build does not need live network access or a PostgreSQL server. CI additionally initializes the schema against PostgreSQL 16.

## Known MVP boundaries

- Generic page/RSS collection is implemented; JS-only portals, CAPTCHAs, and authenticated docket systems need source-specific adapters.
- PDF bytes are preserved, but production should attach `pdftotext` plus OCR for image-only packets before extraction.
- The committed pilot dashboard is a curated, evidence-linked demonstration. `build-live` exports current PostgreSQL records into the same UI; a public deployment should add authentication or publish only a deliberately filtered static export.
- Email content is generated and stored, but an SMTP/transactional-email transport is deliberately left as a deployment adapter so credentials and recipients are never embedded in the repository.
