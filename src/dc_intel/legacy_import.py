from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .scoring import score_materiality


DATA_FILES = ("projects.json", "credit_projects.json", "hy_projects.json")
UNKNOWN_PARTIES = {"", "n/d", "none", "unknown", "undisclosed"}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _parties(value: Any) -> list[str]:
    text = _text(value)
    if not text or text.casefold() in UNKNOWN_PARTIES or text.casefold().startswith("undisclosed"):
        return []
    values = [re.sub(r"\s+at issuance;.*$", "", item.strip(), flags=re.IGNORECASE) for item in re.split(r"\s+(?:\+|/)\s+", text) if item.strip()]
    return list(dict.fromkeys(values))


def _location(value: Any) -> tuple[str | None, str, str | None, str]:
    text = _text(value)
    states = list(dict.fromkeys(re.findall(r"\b[A-Z]{2}\b", text)))
    if len(states) > 1:
        return None, "Multi-state portfolio", " + ".join(states), "multi-site portfolio"

    state = states[0] if states else None
    county_match = re.search(r"(?:^|[,/])\s*([^,/]+?)\s+(County|Parish)\b", text, re.IGNORECASE)
    county = county_match.group(1).strip() if county_match else None
    first = text.split(",", 1)[0].strip() if text else ""
    city = None if county and first.casefold().endswith((" county", " parish")) else first or None
    if not county:
        county = first or "Location not normalized"
    return city, county, state, "county / city from portfolio disclosure"


def _valid_url(value: Any) -> str:
    url = _text(value)
    return url if url.startswith("https://") else "https://roblevinson-cloud.github.io/ai-compute-demand-dashboard/data-centers/"


def _source(project: dict[str, Any]) -> tuple[str, str, str, str]:
    evidence = project.get("evidence") or []
    sources = project.get("sources") or []
    if evidence:
        item = evidence[0]
        source_type = "company" if any(word in _text(item.get("source")).casefold() for word in ("sec", "company", "digital", "oracle", "meta", "hut", "cipher", "terawulf", "galaxy")) else "national_media"
        return (
            _text(item.get("source")) or "Portfolio source",
            source_type,
            _valid_url(item.get("url")),
            _text(item.get("headline")) or _text(project.get("summary")),
        )
    if sources:
        item = sources[0]
        return (
            _text(item.get("name")) or "Portfolio source",
            "company" if "company" in _text(item.get("type")).casefold() else "national_media",
            _valid_url(item.get("url")),
            _text(project.get("summary")),
        )
    return (
        "Data center project portfolio",
        "other",
        "https://roblevinson-cloud.github.io/ai-compute-demand-dashboard/data-centers/",
        _text(project.get("summary")),
    )


def _evidence_dates(project: dict[str, Any], fallback: str) -> tuple[str, str]:
    dates = [
        _text(item.get("date"))
        for item in (project.get("evidence") or [])
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", _text(item.get("date")))
    ]
    return (min(dates), max(dates)) if dates else (fallback, fallback)


def _event_type(status: str) -> str:
    lowered = status.casefold()
    if "partially operational" in lowered:
        return "expansion"
    if "operational" in lowered:
        return "commencement_of_operations"
    if "construction" in lowered:
        return "construction_start"
    return "new_project_discovery"


def _stage_weight(status: str) -> int:
    lowered = status.casefold()
    if "operational" in lowered:
        return 12
    if "under construction" in lowered:
        return 10
    if "early construction" in lowered or "permitting" in lowered:
        return 7
    return 4


def _metric(label: str, value: Any, boundary: str, source_url: str) -> dict[str, Any]:
    return {"label": label, "value": value, "boundary": boundary, "source_url": source_url}


def _transform(project: dict[str, Any], as_of: str) -> tuple[dict[str, Any], dict[str, Any]]:
    slug = _text(project.get("slug"))
    project_id = f"portfolio-{slug}"
    name = _text(project.get("name")) or _text(project.get("campus")) or slug
    status = _text(project.get("status")) or "Status not disclosed"
    city, county, state, precision = _location(project.get("location"))
    source_name, source_type, source_url, evidence_quote = _source(project)
    first_seen, last_update = _evidence_dates(project, as_of)
    critical_it_mw = project.get("critical_it_mw")
    utility_mw = project.get("utility_mw")
    capex_b = project.get("capex_total_b")
    risk_score = int(project.get("risk_score") or 0)
    materiality = score_materiality({
        "event_type": _event_type(status),
        "mw": critical_it_mw or utility_mw,
        "capex_usd_b": capex_b,
        "stage_weight": _stage_weight(status),
        "major_party": bool(_parties(project.get("tenant"))),
        "risk_weight": 5 if risk_score >= 60 else (2 if risk_score >= 45 else 0),
    }).value
    evidence_count = len(project.get("evidence") or [])
    confidence = min(94, 74 + evidence_count * 4)

    developer = _parties(project.get("developer"))
    tenant = _parties(project.get("tenant"))
    landlord = _parties(project.get("landlord"))
    guarantor = _parties(project.get("guarantor"))
    power_provider = _parties(project.get("power_provider"))
    relationships: list[dict[str, Any]] = []
    for companies, role, role_confidence in (
        (developer, "developer", 88),
        (tenant, "tenant / customer", 88),
        (landlord, "landlord / project owner", 84),
        (guarantor, "guarantor / credit support", 80),
        (power_provider, "utility / power provider", 78),
    ):
        for company in companies:
            relationships.append({"company": company, "role": role, "confidence": role_confidence})

    metrics: list[dict[str, Any]] = []
    if critical_it_mw is not None:
        metrics.append(_metric("Critical IT capacity", f"{critical_it_mw:g} MW", "Reported portfolio capacity boundary", source_url))
    if utility_mw is not None:
        metrics.append(_metric("Utility / facility power", f"{utility_mw:g} MW", _text(project.get("power_source")) or "Utility or facility power boundary", source_url))
    if _text(project.get("capex_total_display")):
        metrics.append(_metric("Capital program", project["capex_total_display"], _text(project.get("capex_note")) or "Portfolio disclosure; review source scope", source_url))
    if _text(project.get("debt_amount_display")):
        metrics.append(_metric("Project debt", project["debt_amount_display"], _text(project.get("financing")) or "Project-level financing", source_url))
    if _text(project.get("delivery")):
        metrics.append(_metric("Delivery", project["delivery"], f"Next milestone: {_text(project.get('next_milestone')) or 'not disclosed'}", source_url))
    if not metrics:
        metrics.append(_metric("Portfolio status", status, "Imported from the linked project portfolio", source_url))

    campus = _text(project.get("campus"))
    aliases = [] if not campus or campus.casefold() == name.casefold() else [{"name": campus, "type": "campus / financing name", "confidence": 88}]
    summary = _text(project.get("summary")) or f"{campus or name} is tracked in {_text(project.get('location'))} as {status.lower()}."
    risk = _text(project.get("delay_view")) or _text(project.get("risk_label")) or "Review delivery, power, construction, and tenant-credit milestones."
    numbers = []
    if critical_it_mw is not None:
        numbers.append({"label": "Critical IT", "value": f"{critical_it_mw:g} MW"})
    if utility_mw is not None:
        numbers.append({"label": "Utility / facility power", "value": f"{utility_mw:g} MW"})
    if _text(project.get("capex_total_display")):
        numbers.append({"label": "Capital program", "value": project["capex_total_display"]})

    transformed = {
        "id": project_id,
        "slug": slug,
        "name": name,
        "status": status,
        "status_tone": "risk" if risk_score >= 50 else "signal",
        "state": state,
        "county": county,
        "city": city,
        "address": _text(project.get("location")) or "Undisclosed",
        "location_precision": precision,
        "developer": developer,
        "tenant": tenant,
        "operator": [],
        "utility": power_provider or ["Not disclosed"],
        "parcel": [],
        "alias": [item["name"] for item in aliases],
        "aliases": aliases,
        "mw": utility_mw,
        "it_mw": critical_it_mw,
        "acreage": project.get("acreage"),
        "capex_usd_b": capex_b,
        "buildings": project.get("building_count"),
        "materiality": materiality,
        "confidence": confidence,
        "first_seen": first_seen,
        "last_update": last_update,
        "summary": summary,
        "risk": risk,
        "metrics": metrics,
        "relationships": relationships,
    }
    event = {
        "id": f"evt-portfolio-{slug}",
        "project_id": project_id,
        "project_name": name,
        "occurred_at": last_update,
        "event_type": _event_type(status),
        "headline": f"{name} added from the national project portfolio",
        "what_new": f"GridSignal imported {campus or name} in {_text(project.get('location'))} with a current status of {status}.",
        "why_matters": summary,
        "implication": f"Monitor {_text(project.get('next_milestone')) or 'the next disclosed milestone'} and verify changes against the linked evidence.",
        "source_name": source_name,
        "source_type": source_type,
        "source_url": source_url,
        "materiality": materiality,
        "novelty": 72,
        "confidence": confidence,
        "evidence": evidence_quote or summary,
        "numbers": numbers,
    }
    return transformed, event


def load_legacy_portfolio(data_dir: str | Path | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    folder = Path(data_dir) if data_dir else Path(__file__).resolve().parents[2] / "docs" / "data-centers" / "data"
    payloads: dict[str, dict[str, Any]] = {}
    for filename in DATA_FILES:
        path = folder / filename
        if not path.exists():
            continue
        payloads[filename] = json.loads(path.read_text(encoding="utf-8"))
    if not payloads:
        return [], [], "2026-09-18"

    base = payloads.get("projects.json", {})
    credit = payloads.get("credit_projects.json", {})
    high_yield = payloads.get("hy_projects.json", {})
    overrides = credit.get("overrides") or {}
    merged_base = [{**project, **overrides.get(project.get("slug"), {})} for project in base.get("projects", [])]
    raw_projects = [*merged_base, *credit.get("projects", []), *high_yield.get("projects", [])]
    as_of = _text(credit.get("as_of") or high_yield.get("as_of") or base.get("as_of")) or "2026-09-18"

    projects: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    seen: set[str] = set()
    for project in raw_projects:
        slug = _text(project.get("slug"))
        if not slug or slug in seen:
            continue
        seen.add(slug)
        transformed, event = _transform(project, as_of)
        projects.append(transformed)
        events.append(event)
    return projects, events, as_of
