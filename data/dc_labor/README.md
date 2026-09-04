# Data Center Electrician Labor Monitor

This folder is the persistent historical store for the Data Center Labor Monitor.

## Sources

Primary source: `https://where2bro.com/hot-spots/` (IBEW traveler / job-call market data).

The scheduled GitHub Action fetches the source every six hours. A raw HTML snapshot is retained only when the page content hash changes.

## Files

- `raw/*_where2bro_hot_spots.html` — immutable source snapshots when content changes.
- `calls.csv` — normalized data-center-related job calls, one row per parsed call.
- `latest.json` — current market-level dashboard payload.
- `last_hash.txt` — content fingerprint used to prevent duplicate raw snapshots.

## Normalized call schema

`observed_at, source_date, local, market, city_label, project, openings, weekly_hours, base_hourly, incentive_hourly, per_diem_daily, ot_multiplier, confidence, stress_score, source_url, source_text`

## Stress score

0–100 composite of:

1. Explicit open positions (log-scaled, max 40 points)
2. Weekly schedule above 40 hours (max 20)
3. Explicit hourly incentive / over-scale pay (max 20)
4. Overtime multiplier (5 points for 1.5x; 10 for 2.0x)
5. Daily per diem / daily incentive (max 10)

The score measures difficulty attracting electrical labor, not project completion or delay directly.

## Deceleration rule

A market is flagged when explicitly identifiable data-center openings fall at least 50% versus its prior observation, provided the prior observation had at least five openings. This is an investigative signal, not proof of a delay: calls can disappear because positions were filled, a phase completed, contractors rotated, or reporting changed.

## Project Jupiter geography

Project Jupiter / Santa Teresa is tracked through **IBEW Local 583 El Paso**, because Local 583 dispatches Santa Teresa, New Mexico work. Albuquerque / Rio Rancho (Local 611) is maintained as a separate labor market and is not used as the primary Project Jupiter proxy.

`Project Miner / Santa Teresa` is stored as its own project alias rather than automatically merging it into `Project Jupiter`; the alias can be upgraded when stronger primary-source confirmation is available.
