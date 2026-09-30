# China Auto Export Monitor — methodology

Rebuilt 30 September 2026. The monitor displays one calendar-month series from January 2020 through the latest available month. Downloads retain the source of each observation. A displayed span does not imply every destination reports every month.

## Sources and joins

| Measure | Earlier history | Extension | Important difference |
|---|---|---|---|
| World USD value | China-reported HS 8703 world totals via UN Comtrade, 2020–2024 | GACC HS 8703 through China Data Portal, 2025 onward | Both are export/FOB value; dissemination and revisions can differ |
| World units | China-reported HS 8703 world quantities via UN Comtrade, 2020–2024 | CPCA passenger-vehicle exports from CADA monthly releases, 2025 onward | Industry passenger-vehicle counts include complete vehicles and CKD kits. HS 8703 also includes specialty vehicles, including golf cars. The join changes scope, not just publisher |
| Destination units and value | China-reported HS 8703 exports where present | Destination-reported HS 8703 imports from China where present | Import arrival timing and shipment timing differ; imports are usually CIF rather than FOB |

Primary source links: [UN Comtrade](https://comtradeplus.un.org/TradeFlow), [GACC via China Data Portal](https://chinadata.live/china-trade/hs/8703/), [CADA / CPCA releases](https://www.cada.cn/Trends/list_91_1.html). `industry_units.json` and the world CSV contain the exact release URL for each new monthly volume observation. August 2025 uses CADA's association account on NPOall. These are original monthly releases, rounded to the source's precision; subsequent industry revisions can make the published YoY percentage differ from a ratio of the stored observations. No values are inferred from YoY rates or interpolated.

## Rules

- China-reported country data takes priority. Where absent, use the destination's report for that exact country and calendar month. There is no rebasing, scaling, seasonal adjustment, interpolation or annual-to-month allocation.
- Missing observations remain blank. A missing customs row is not assumed to be a zero shipment.
- The world row uses published world totals, never the sum of whatever importing countries happen to have reported. One historical exception is explicitly flagged as a lower bound: September 2020 has no world quantity in UN Comtrade. Destinations with reported quantities cover 99.9958% of world value. Their 178,729.013 reported units are shown as a subtotal; the remaining $39,450 consists of $39,217 of unallocated destination value and $233 reported for Luxembourg without quantity. This is not an estimated exact global total. No USD/unit is calculated for that month.
- National units and national value have independently documented sources. No world USD/unit is calculated when industry units and customs value have different populations.
- A destination's reported FOB import value is selected when available; otherwise the primary import value (usually CIF) is used. `value_basis` records that choice. A historical bug displayed the primary import value even when labelling the observation FOB; the unified panel corrects it.
- The source-overlap download preserves paired 2024 China and destination reports. It is a diagnostic of timing/coverage/basis differences, not an adjustment factor applied to the series.
- World totals can exceed the sum of named destinations because some trade has unspecified or residual destinations. The historical unallocated value is retained in the coverage CSV.
- `qty_estimated` flags quantity estimates made by UN Comtrade. They can be fractional. Display rounding does not alter the raw downloadable quantities.
- Growth is calculated from exact prior calendar-month / prior-year-month observations. Missing comparators produce blanks. Comparisons across source or valuation-basis changes carry a flag (`*_source_break`) and a dagger in the UI. They are not like-for-like estimates.
- Destination ranking uses only the chosen month. A stale latest observation is shown separately, never inserted into a current-month ranking. Same-source comparisons are the default. Destination counts are displayed; do not treat a partial list as a complete global distribution.
- The starting ranking month is the latest mirror month with at least 70 reporting destinations; users can select a newer partial month. This is a display heuristic, not a statistical completeness threshold.
- Exports are origin-based and include foreign brands produced in China. They are not Chinese-brand retail registrations, and imports can include inventory accumulation and re-exports through hubs.

## Coverage at rebuild

Global value: 80/80 months. Joined units: 79 reported totals plus one clearly flagged historical subtotal, January 2020–August 2026. Full China-reported destination history: 60 months through December 2024. Newer mirror reporting is incomplete and uneven; Russia and UAE do not have recent mirror observations in the saved dataset. Do not infer their volumes from the available-country sample. The public GACC destination preview supplies five latest-month value observations, not a complete destination panel, and is retained separately in the raw source data.

## Files

- `data/world_monthly.csv`: 80 monthly national observations, with separate unit/value source labels and URLs.
- `data/destination_monthly.csv`: complete country × month grid, including blank observations and provenance.
- `data/source_overlap.csv`: overlapping China and mirror observations for source-break diligence.
- `data/coverage.csv`: reporting counts and historical world-to-destination reconciliation.
- `data/exports.json`, `data/current.json`, `data/industry_units.json`: underlying saved source layers.
- `data/series.json`: unified dashboard panel built deterministically from those inputs.

## Refresh and verification

The existing daily GitHub workflow refreshes sources, builds the unified panel, runs regression checks, and commits updated snapshots. Successful completion triggers Pages deployment, including when the update was committed by GitHub Actions. Failed/empty source calls preserve existing observations; errors remain in metadata. History refresh checks for missing older months as well as revisiting recent releases. Static exports and tables work without a chart CDN or external runtime.
