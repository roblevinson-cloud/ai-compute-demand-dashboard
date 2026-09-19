from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .brief_archive import load_brief_archive
from .legacy_import import load_legacy_portfolio
from .resolution import compare_project
from .source_registry import load_source_registry, source_summary


def _event(
    event_id: str,
    project_id: str,
    project_name: str,
    occurred_at: str,
    event_type: str,
    headline: str,
    what_new: str,
    why_matters: str,
    implication: str,
    source_name: str,
    source_type: str,
    source_url: str,
    materiality: int,
    novelty: int,
    confidence: int,
    evidence: str,
    numbers: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    return {
        "id": event_id,
        "project_id": project_id,
        "project_name": project_name,
        "occurred_at": occurred_at,
        "event_type": event_type,
        "headline": headline,
        "what_new": what_new,
        "why_matters": why_matters,
        "implication": implication,
        "source_name": source_name,
        "source_type": source_type,
        "source_url": source_url,
        "materiality": materiality,
        "novelty": novelty,
        "confidence": confidence,
        "evidence": evidence,
        "numbers": numbers or [],
    }


def build_demo_data(
    source_path: str = "config/sources.yml",
    brief_archive_path: str | Path | None = "data/briefs.json",
) -> dict[str, Any]:
    sources = load_source_registry(source_path)
    jupiter = {
        "id": "project-jupiter",
        "slug": "project-jupiter-santa-teresa",
        "name": "Project Jupiter",
        "status": "construction / air permit stayed",
        "status_tone": "risk",
        "state": "NM",
        "county": "Doña Ana",
        "city": "Santa Teresa",
        "address": "Santa Teresa Industrial Park (parcel/address not verified)",
        "location_precision": "county / industrial park",
        "developer": ["STACK Infrastructure", "BorderPlex Digital Assets"],
        "tenant": ["OpenAI"],
        "operator": ["Oracle"],
        "utility": ["On-site YGI microgrid; El Paso Electric territory monitored"],
        "parcel": [],
        "alias": ["YGI Microgrid", "Stargate New Mexico", "BorderPlex Digital Infrastructure Campus"],
        "aliases": [
            {"name": "YGI Microgrid", "type": "power facility", "confidence": 98},
            {"name": "Stargate New Mexico", "type": "program / campus reference", "confidence": 94},
            {"name": "BorderPlex Digital Infrastructure Campus", "type": "precursor / development name", "confidence": 82},
        ],
        "mw": 2450,
        "it_mw": None,
        "acreage": 1400,
        "capex_usd_b": 165,
        "buildings": 4,
        "materiality": 98,
        "confidence": 94,
        "first_seen": "2025-02-25",
        "last_update": "2026-09-17T14:00:00-06:00",
        "summary": "Four-building AI campus in Doña Ana County linked to Oracle/OpenAI Stargate, with an adjacent 2.45 GW fuel-cell microgrid proposal and an unusually large IRB authorization.",
        "risk": "Air-permit and litigation path is active; generation MW is not the same as verified IT load.",
        "metrics": [
            {"label": "Generation proposal", "value": "2.45 GW", "boundary": "On-site Bloom fuel-cell nameplate; not verified IT load", "source_url": "https://www.oracle.com/news/announcement/oracle-borderplex-and-bloom-energy-to-power-project-jupiter-with-fuel-cell-technology-2026-04-27/"},
            {"label": "IRB authorization", "value": "Up to $165B", "boundary": "Bond ceiling / tax mechanism; not confirmed spend", "source_url": "https://www.nmborderplex.com/project-jupiter-approved-a-transformative-leap-for-the-new-mexico-borderplex/"},
            {"label": "Campus plan", "value": "4 buildings", "boundary": "Development plan", "source_url": "https://www.nmborderplex.com/project-jupiter-approved-a-transformative-leap-for-the-new-mexico-borderplex/"},
            {"label": "Long-term jobs", "value": "~750", "boundary": "Projection, not current employment", "source_url": "https://www.nmborderplex.com/project-jupiter-approved-a-transformative-leap-for-the-new-mexico-borderplex/"},
            {"label": "Air permit", "value": "NSR 10883", "boundary": "YGI Microgrid", "source_url": "https://www.env.nm.gov/public-notices/"},
            {"label": "NMED docket", "value": "AQB 26-57(P)", "boundary": "Permit proceeding", "source_url": "https://www.env.nm.gov/opf/docketed-matters/"},
        ],
        "relationships": [
            {"company": "STACK Infrastructure", "role": "developer", "confidence": 92},
            {"company": "BorderPlex Digital Assets", "role": "developer", "confidence": 98},
            {"company": "Oracle", "role": "operator / infrastructure partner", "confidence": 95},
            {"company": "OpenAI", "role": "tenant / customer", "confidence": 93},
            {"company": "Bloom Energy", "role": "power technology supplier", "confidence": 98},
            {"company": "Yucca Growth Infrastructure", "role": "microgrid applicant", "confidence": 100},
        ],
    }
    google = {
        "id": "google-lea-county",
        "slug": "google-lea-county-candidate",
        "name": "Google Lea County candidate",
        "status": "early signal / site evaluation",
        "status_tone": "signal",
        "state": "NM",
        "county": "Lea",
        "city": None,
        "address": "Undisclosed",
        "location_precision": "county",
        "developer": ["Google"],
        "tenant": ["Google"],
        "operator": ["Google"],
        "utility": ["Not disclosed"],
        "parcel": [],
        "alias": [],
        "aliases": [],
        "mw": None,
        "it_mw": None,
        "acreage": None,
        "capex_usd_b": None,
        "buildings": None,
        "materiality": 64,
        "confidence": 87,
        "first_seen": "2026-09-14",
        "last_update": "2026-09-15T13:00:00-06:00",
        "summary": "Google says it is exploring a data-center project in Lea County. Site, utility, power, acreage, schedule, and incentive structure remain undisclosed.",
        "risk": "Pre-development signal only; no parcel, MW, utility, or formal application is yet linked.",
        "metrics": [
            {"label": "Location", "value": "Lea County, NM", "boundary": "County only", "source_url": "https://blog.google/innovation-and-ai/infrastructure-and-cloud/global-network/lea-county-new-mexico/"},
            {"label": "Project stage", "value": "Exploring", "boundary": "Company language; no construction commitment", "source_url": "https://blog.google/innovation-and-ai/infrastructure-and-cloud/global-network/lea-county-new-mexico/"},
            {"label": "County framework", "value": "26-FEB-057R", "boundary": "General data-center requirements; project link unconfirmed", "source_url": "https://www.leacounty.gov/1378/2026-Lea-County-Resolutions"},
        ],
        "relationships": [{"company": "Google", "role": "prospective developer / operator", "confidence": 96}],
    }
    projects = [jupiter, google]
    portfolio_projects, portfolio_events, _portfolio_as_of = load_legacy_portfolio()
    existing_slugs = {project["slug"] for project in projects} | {"project-jupiter"}
    imported_projects = [project for project in portfolio_projects if project["slug"] not in existing_slugs]
    imported_project_ids = {project["id"] for project in imported_projects}
    projects.extend(imported_projects)

    events = [
        _event(
            "evt-jupiter-permit-stay", "project-jupiter", jupiter["name"], "2026-09-17T17:00:00-06:00",
            "delay", "NMED marks the Project Jupiter microgrid air-permit process stayed",
            "NMED's public-facing notice says the YGI Microgrid permit comment process is stayed by the New Mexico Supreme Court pending further notice.",
            "A court stay is a direct critical-path risk for the 2.45 GW generation facility, even though Oracle says campus and microgrid construction scopes are separate.",
            "Move the air-permit milestone to stayed, preserve the campus/microgrid boundary, and monitor the Supreme Court register plus NMED docket AQB 26-57(P).",
            "New Mexico Environment Department", "primary_regulatory", "https://www.env.nm.gov/",
            99, 99, 99, "UPDATED: Stayed By New Mexico Supreme Court — Further notice will be provided when available.",
            [{"label": "Permit", "value": "10883"}, {"label": "Docket", "value": "AQB 26-57(P)"}],
        ),
        _event(
            "evt-google-lea", "google-lea-county", google["name"], "2026-09-14T14:00:00-06:00",
            "new_project_discovery", "Google discloses an unnamed Lea County data-center exploration",
            "Google publicly identified Lea County but supplied no site, MW, utility, acreage, or timetable.",
            "The company-level signal starts a county-wide discovery sweep before a planning or utility filing surfaces.",
            "Treat as a separate early-stage candidate; monitor Lea County agendas, IRB/LEDA actions, NMED permits, utility filings, land records, and local reporting.",
            "Google", "company", "https://blog.google/innovation-and-ai/infrastructure-and-cloud/global-network/lea-county-new-mexico/",
            64, 96, 91, "Google is exploring a new data center project in Lea County, New Mexico.",
            [{"label": "Named geography", "value": "Lea County, NM"}],
        ),
        _event(
            "evt-jupiter-permit-statement", "project-jupiter", jupiter["name"], "2026-09-14T11:00:00-06:00",
            "environmental_permit", "Oracle separates campus construction from the adjacent microgrid permit",
            "Oracle stated that the data-center campus and proposed microgrid are separate facilities on adjacent sites and under separate operators.",
            "This narrows the legal and permitting boundary: an air-permit event for YGI is related to Jupiter but is not automatically a permit for the campus itself.",
            "Keep the campus and generation asset linked but model them as distinct facilities and permit scopes.",
            "Oracle", "company", "https://www.oracle.com/news/announcement/project-jupiter-statement-on-construction-permitting-2026-09-14/",
            88, 87, 92, "The Project Jupiter data center campus and the proposed microgrid are separate facilities on separate but adjacent sites.",
        ),
        _event(
            "evt-jupiter-hearing", "project-jupiter", jupiter["name"], "2026-09-14T09:00:00-06:00",
            "puc_proceeding", "NMED posts an amended hearing notice in YGI Microgrid docket",
            "NMED added an amended Sept. 14 hearing notice to the public record for permit 10883 / docket AQB 26-57(P).",
            "Hearing-calendar changes can move the critical path for a 2.45 GW on-site generation plan.",
            "Flag the permit schedule as unstable and compare each new notice with the prior hearing order.",
            "New Mexico Environment Department", "primary_regulatory", "https://www.env.nm.gov/public-notices/",
            94, 93, 97, "Amended Notice of Hearing-9.14.2026; permit application 10883.",
            [{"label": "Permit", "value": "10883"}, {"label": "Docket", "value": "AQB 26-57(P)"}],
        ),
        _event(
            "evt-jupiter-admin-record", "project-jupiter", jupiter["name"], "2026-08-25T12:00:00-06:00",
            "environmental_permit", "NMED publishes the draft administrative record index",
            "The agency posted an index and two document batches covering 180 items for the YGI permit record.",
            "The document set creates a primary-source corpus for emissions, modeling, public comments, and procedural changes.",
            "Ingest and diff the record at document level; prioritize revised modeling and hearing exhibits.",
            "New Mexico Environment Department", "primary_regulatory", "https://www.env.nm.gov/public-notices/",
            86, 90, 98, "Draft Administrative Record, Documents 1-47 and 48-180.",
            [{"label": "Administrative-record items", "value": "180"}],
        ),
        _event(
            "evt-jupiter-power-revision", "project-jupiter", jupiter["name"], "2026-04-27T09:00:00-06:00",
            "generation_storage", "Project Jupiter switches its disclosed power design to Bloom fuel cells",
            "Oracle and BorderPlex said the campus would use up to 2.45 GW of Bloom fuel cells, replacing earlier turbine and diesel plans.",
            "A full power-architecture change affects air permitting, emissions, water, equipment procurement, and schedule risk.",
            "Track fuel-cell delivery milestones and treat 2.45 GW as generation nameplate—not IT load.",
            "Oracle", "company", "https://www.oracle.com/news/announcement/oracle-borderplex-and-bloom-energy-to-power-project-jupiter-with-fuel-cell-technology-2026-04-27/",
            98, 98, 95, "Up to 2.45 GW of Bloom Energy fuel-cell capacity.",
            [{"label": "Generation nameplate", "value": "2.45 GW"}],
        ),
        _event(
            "evt-jupiter-stargate", "project-jupiter", jupiter["name"], "2025-09-23T08:00:00-06:00",
            "tenant_customer_identification", "OpenAI names Doña Ana County as a Stargate location",
            "OpenAI identified a Doña Ana County, New Mexico site in its Oracle-led Stargate expansion announcement.",
            "This strongly links the previously local development record to a named AI customer and national infrastructure program.",
            "Raise entity-match confidence while retaining source-specific capacity boundaries.",
            "OpenAI", "company", "https://openai.com/index/five-new-stargate-sites/",
            96, 95, 94, "The announcement names a site in Doña Ana County, New Mexico.",
        ),
        _event(
            "evt-jupiter-irb", "project-jupiter", jupiter["name"], "2025-09-19T17:00:00-06:00",
            "incentive", "Doña Ana County approves up to $165B of Project Jupiter IRBs",
            "County commissioners approved an IRB authorization covering buildings, equipment, site infrastructure, and a microgrid.",
            "The ceiling is exceptionally large and signals local authorization, but it must not be represented as committed capex or issued debt.",
            "Move the project from proposal toward authorized development; continue tracking bond series and performance obligations.",
            "New Mexico Border Industrial Association", "primary_government", "https://www.nmborderplex.com/project-jupiter-approved-a-transformative-leap-for-the-new-mexico-borderplex/",
            97, 98, 90, "Approved up to $165 billion in Industrial Revenue Bonds.",
            [{"label": "IRB ceiling", "value": "$165B"}, {"label": "Planned buildings", "value": "4"}],
        ),
        _event(
            "evt-borderplex-mou", "project-jupiter", jupiter["name"], "2025-02-25T10:00:00-07:00",
            "new_project_discovery", "New Mexico announces the BorderPlex digital-infrastructure campus",
            "The governor announced a $5B Santa Teresa campus and state MOU with BorderPlex Digital Assets.",
            "This was the precursor signal linking geography, developer, power/cooling partner, jobs, and investment before Project Jupiter's later identity became public.",
            "Create the project record and search county incentives, utility infrastructure, land, permits, and company relationships.",
            "Office of the Governor of New Mexico", "primary_government", "https://www.governor.state.nm.us/2025/02/25/governor-announces-partnership-with-borderplex-digital-digital-infrastructure-campus-represents-5-billion-investment-in-santa-teresa-expected-to-create-1000-jobs/",
            84, 100, 94, "Digital infrastructure campus represents $5 billion investment in Santa Teresa.",
            [{"label": "Announced investment", "value": "$5B"}, {"label": "Expected jobs", "value": "1,000"}],
        ),
    ]
    events.extend(event for event in portfolio_events if event["project_id"] in imported_project_ids)

    ygi_signal = {
        "county": "Doña Ana", "state": "NM", "developer": ["Yucca Growth Infrastructure", "BorderPlex Digital Assets"],
        "tenant": ["OpenAI"], "mw": 2450, "alias": ["YGI Microgrid"],
    }
    google_signal = {"county": "Lea", "state": "NM", "developer": ["Google"], "tenant": ["Google"]}
    jupiter_matchable = {
        "id": jupiter["id"], "county": jupiter["county"], "state": jupiter["state"], "developer": jupiter["developer"] + ["Yucca Growth Infrastructure"],
        "tenant": jupiter["tenant"], "mw": jupiter["mw"], "alias": [item["name"] for item in jupiter["aliases"]],
    }
    ygi_match = compare_project(ygi_signal, jupiter_matchable).to_dict()
    google_match = compare_project(google_signal, jupiter_matchable).to_dict()
    review_queue = [
        {
            "id": "match-ygi-jupiter", "signal": "YGI Microgrid / permit 10883", "candidate": "Project Jupiter",
            "status": "pending human confirmation", "created_at": "2026-04-27", **ygi_match,
            "next_action": "Confirm facility-level relationship: link as adjacent power facility, not as the same physical asset.",
        },
        {
            "id": "match-google-jupiter", "signal": "Google unnamed Lea County project", "candidate": "Project Jupiter",
            "status": "triaged — keep separate", "created_at": "2026-09-14", **google_match,
            "next_action": "Open a separate project record and run a Lea County discovery sweep; revisit only if parcel/company evidence converges.",
        },
    ]

    now = datetime.now(UTC).isoformat()
    health = []
    for index, source in enumerate(sources):
        health.append({
            "key": source["key"], "name": source["name"], "source_type": source["source_type"],
            "jurisdiction": source["jurisdiction"], "status": "healthy" if index % 7 else "changed",
            "last_checked": f"2026-09-18T14:{(index * 3) % 60:02d}:00Z",
            "last_new_document": "2026-09-18T13:42:00Z" if index in {0, 1, 6, 14} else "2026-09-17T18:10:00Z",
            "interval_minutes": source["interval_minutes"], "priority": source["priority"], "url": source["url"],
            "tags": source.get("tags", []),
        })

    briefs = [
        {
            "id": "brief-evening-2026-09-17", "digest_type": "evening", "type": "Evening Brief", "date": "2026-09-17",
            "subject": "Evening Data Center Intelligence — Court stay raises Jupiter critical-path risk",
            "summary": "NMED now marks the YGI Microgrid air-permit process stayed by the New Mexico Supreme Court. Google's unnamed Lea County disclosure remains a separate early-stage discovery signal.",
            "event_ids": ["evt-jupiter-permit-stay", "evt-google-lea", "evt-jupiter-permit-statement"],
        },
        {
            "id": "brief-morning-2026-09-18", "digest_type": "morning", "type": "Morning Brief", "date": "2026-09-18",
            "subject": "Morning Data Center Intelligence — Jupiter air-permit process stayed",
            "summary": "The leading overnight development is NMED's notice that the YGI Microgrid permit process is stayed, combined with Oracle's clarification that the campus and adjacent microgrid are separate facilities.",
            "event_ids": ["evt-jupiter-permit-stay", "evt-jupiter-permit-statement", "evt-jupiter-hearing"],
        },
    ]
    archived_briefs = load_brief_archive(brief_archive_path) if brief_archive_path is not None else []
    if archived_briefs:
        briefs = archived_briefs
    else:
        briefs.sort(key=lambda item: (item["date"], item["digest_type"]), reverse=True)

    return {
        "meta": {
            "title": "GridSignal",
            "subtitle": "U.S. data center development intelligence",
            "generated_at": now,
            "as_of": "2026-09-18T10:30:00-04:00",
            "mode": "U.S. portfolio — evidence-linked project intelligence",
            "disclaimer": "The national portfolio is imported from the linked project monitor and merged with the newer New Mexico records. Capacity, capital, and schedule boundaries are preserved; verify live status at each source.",
        },
        "kpis": {
            "tracked_projects": len(projects), "priority_events": sum(event["materiality"] >= 85 for event in events),
            "new_signals": sum(event["event_type"] == "new_project_discovery" for event in events),
            "review_items": len(review_queue), "healthy_sources": sum(item["status"] == "healthy" for item in health),
            "source_count": len(health),
        },
        "projects": projects,
        "events": events,
        "review_queue": review_queue,
        "source_health": health,
        "source_registry_summary": source_summary(sources),
        "briefs": briefs,
        "event_taxonomy": [
            "new_project_discovery", "land_acquisition_site_control", "zoning", "permit", "utility_service",
            "interconnection", "transmission_substation", "generation_storage", "puc_proceeding", "incentive",
            "water_sewer", "environmental_permit", "financing", "tenant_customer_identification", "contractor",
            "construction_start", "topping_out", "equipment_delivery", "energization", "expansion", "schedule_change",
            "cost_change", "opposition_litigation", "regulatory_decision", "delay", "cancellation", "commencement_of_operations",
        ],
    }
