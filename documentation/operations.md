# Operations and source onboarding

## Source tiers

1. Primary regulatory: PUC/PSC/PRC dockets, environmental permits, tariff filings, interconnection and transmission records.
2. Primary government: planning packets, agendas, minutes, permits, incentive approvals, assessor/recorder records.
3. Utilities and companies: service announcements, substation projects, procurement, construction, and customer disclosures.
4. Local media: county newspapers, business publications, and television sites that surface local names and opposition.
5. Trade and national media: validation and context, not the primary discovery mechanism.

## Adding a source

Add an entry to `config/sources.yml` with a unique key, source type, jurisdiction, canonical URL, collection method, interval, priority, and watch terms. Run `dc-intel source-summary` and the tests. For a page that cannot be handled by the generic collector, add a narrowly scoped adapter and a fixture-based parser test.

Respect robots rules, terms of use, rate limits, and public-record access constraints. Prefer APIs and RSS. Poll document indexes instead of repeatedly downloading every PDF. Never bypass authentication, CAPTCHA, or access controls.

## Failure handling

Collection failures are isolated per source and written to `collection_errors`. Consecutive failures are visible in source health. A production alert should fire when:

- a priority-90+ source fails three consecutive times;
- a source that normally changes becomes stale;
- a parser suddenly produces zero documents after a page redesign;
- content type or response size changes materially;
- the raw snapshot succeeds but extraction repeatedly fails.

## Digest windows

- Morning: prior day 6:00 p.m. Eastern through 6:30 a.m. Eastern.
- Evening: midnight through 6:00 p.m. Eastern.

The digest selector requires materiality at least 45 and novelty at least 35. A source can appear in the audit trail without being repeated in the report.
