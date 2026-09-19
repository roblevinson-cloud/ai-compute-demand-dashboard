# U.S. coverage roadmap

## Phase 1 — harden New Mexico

- Add source-specific parsers for NMPRC eDocket, Doña Ana and Lea County packet systems, county assessor/recorder feeds, NMCID permits, NMED document indexes, El Paso Electric, and PNM.
- Add PDF text extraction, OCR, table capture, and page-level evidence coordinates.
- Backfill Project Jupiter, Meta Los Lunas, Crusoe facilities, and other New Mexico signals.
- Add analyst actions for accept link, reject link, create project, split facility, and supersede fact.

## Phase 2 — high-activity power markets

- Virginia/PJM: SCC, Dominion, NOVEC, Loudoun/Prince William planning and building records.
- Texas/ERCOT: PUCT, ERCOT interconnection and large-load materials, county/city agendas, Oncor/AEP/TNMP.
- Georgia/Carolinas: PSCs, Georgia Power and Duke large-load tariffs, county planning and incentive records.
- Ohio/Indiana/Michigan/Wisconsin: commissions, utilities, local tax-abatement and zoning systems.
- Arizona/Nevada/Oregon: commissions, water permits, utilities, county planning, state incentive programs.

## Phase 3 — national discovery graph

- Add FERC, EIA generator and transmission datasets, EPA ECHO/EIS, Army Corps notices, state air/water systems, USASpending, SEC filings, property feeds, and contractor procurement signals.
- Maintain utility-territory, substation, transmission-line, developer, contractor, and parcel graphs.
- Learn source-specific lag patterns and detect unusual agenda language before “data center” is explicitly named.

## Phase 4 — production intelligence product

- Authenticated multi-user dashboard and review workflow.
- Object storage, full-text/OpenSearch index, geospatial PostGIS queries, and deployment observability.
- Analyst feedback loops for match and score calibration.
- Per-user watchlists and alert policies across email, Slack, and webhook transports.
- Coverage and recall audits using known-project backtests: measure how many days the platform leads trade and national reporting.
