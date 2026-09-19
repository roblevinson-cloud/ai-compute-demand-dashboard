from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

BACKFILL_START = date(2025, 12, 19)
BACKFILL_END = date(2026, 9, 19)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def _project(raw: dict[str, Any]) -> dict[str, Any]:
    project_id = str(raw["id"])
    name = str(raw["name"])
    status = str(raw.get("status") or "research signal / source review")
    confidence = int(raw.get("confidence") or 92)
    source_url = str(raw.get("source_url") or "https://roblevinson-cloud.github.io/ai-compute-demand-dashboard/")
    developers = list(raw.get("developer") or [])
    tenants = list(raw.get("tenant") or [])
    operators = list(raw.get("operator") or [])
    utilities = list(raw.get("utility") or ["Not disclosed"])
    metrics = list(raw.get("metrics") or [])
    for label, value, boundary in (
        ("Utility / facility power", raw.get("mw"), "Research disclosure; not verified IT load"),
        ("Critical IT capacity", raw.get("it_mw"), "Research disclosure"),
        ("Site acreage", raw.get("acreage"), "Research disclosure"),
        ("Capital program", raw.get("capex_usd_b"), "Research disclosure; announced amount"),
    ):
        if value is None:
            continue
        suffix = " MW" if "power" in label.casefold() or "capacity" in label.casefold() else ""
        if label == "Site acreage":
            suffix = " acres"
        if label == "Capital program":
            suffix = "B"
            value = f"${value}"
        metrics.append({"label": label, "value": f"{value}{suffix}", "boundary": boundary, "source_url": source_url})
    relationships = list(raw.get("relationships") or [])
    for companies, role in (
        (developers, "developer"),
        (tenants, "tenant / customer"),
        (operators, "operator"),
        (utilities, "utility / power provider"),
    ):
        relationships.extend(
            {"company": company, "role": role, "confidence": confidence}
            for company in companies
            if company != "Not disclosed"
        )
    return {
        "id": project_id,
        "slug": str(raw.get("slug") or _slug(name)),
        "name": name,
        "status": status,
        "status_tone": str(raw.get("status_tone") or ("risk" if any(word in status.casefold() for word in ("delay", "withdraw", "denied", "risk")) else "signal")),
        "state": raw.get("state"),
        "county": raw.get("county") or "Location not fully normalized",
        "city": raw.get("city"),
        "address": raw.get("address") or "Undisclosed",
        "location_precision": raw.get("location_precision") or "city / county from source",
        "developer": developers,
        "tenant": tenants,
        "operator": operators,
        "utility": utilities,
        "parcel": list(raw.get("parcel") or []),
        "alias": list(raw.get("alias") or []),
        "aliases": list(raw.get("aliases") or []),
        "mw": raw.get("mw"),
        "it_mw": raw.get("it_mw"),
        "acreage": raw.get("acreage"),
        "capex_usd_b": raw.get("capex_usd_b"),
        "buildings": raw.get("buildings"),
        "materiality": int(raw.get("materiality") or 80),
        "confidence": confidence,
        "first_seen": raw.get("first_seen") or "2026-01-01",
        "last_update": raw.get("last_update") or "2026-09-19",
        "summary": raw.get("summary") or f"{name} was added during GridSignal's nine-month historical source review.",
        "risk": raw.get("risk") or "Stage, load, schedule, and counterparties require continued source verification.",
        "metrics": metrics,
        "relationships": relationships,
    }


def _event(raw: dict[str, Any], project_names: dict[str, str]) -> dict[str, Any]:
    project_id = str(raw["project_id"])
    occurred_at = str(raw["occurred_at"])
    parsed = date.fromisoformat(occurred_at[:10])
    if not BACKFILL_START <= parsed <= BACKFILL_END:
        raise ValueError(f"Research event outside the nine-month backfill window: {raw.get('id')}")
    scores = raw.get("scores") or {}
    important_numbers = raw.get("important_numbers") or {}
    numbers = list(raw.get("numbers") or [])
    numbers.extend({"label": str(label).replace("_", " ").title(), "value": str(value)} for label, value in important_numbers.items())
    headline = str(raw["headline"])
    evidence = str(raw.get("evidence") or headline)
    return {
        "id": str(raw["id"]),
        "project_id": project_id,
        "project_name": str(raw.get("project_name") or project_names.get(project_id) or project_id),
        "occurred_at": occurred_at,
        "event_type": str(raw.get("event_type") or "new_project_discovery"),
        "headline": headline,
        "what_new": str(raw.get("what_new") or evidence),
        "why_matters": str(raw.get("why_matters") or "The source adds a dated, project-specific development milestone to the national timeline."),
        "implication": str(raw.get("implication") or "Update the project record and monitor the next disclosed permit, power, construction, or operating milestone."),
        "source_name": str(raw["source_name"]),
        "source_type": str(raw.get("source_type") or "research_source"),
        "source_url": str(raw["source_url"]),
        "materiality": int(raw.get("materiality") or scores.get("materiality") or 80),
        "novelty": int(raw.get("novelty") or scores.get("novelty") or 90),
        "confidence": int(raw.get("confidence") or scores.get("confidence") or 92),
        "evidence": evidence,
        "numbers": numbers,
    }


def load_research_backfill(
    path: str | Path = "data/research_backfill.json",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source = Path(path)
    if not source.exists():
        return [], []
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"Research backfill must contain a JSON object: {source}")
    projects = payload.get("projects") or []
    events = payload.get("events") or []
    if not isinstance(projects, list) or not isinstance(events, list):
        raise TypeError(f"Research backfill projects and events must be JSON lists: {source}")

    project_ids = {str(project["id"]) for project in projects}
    if len(project_ids) != len(projects):
        raise ValueError("Research backfill contains duplicate project ids")
    event_ids = {str(event["id"]) for event in events}
    if len(event_ids) != len(events):
        raise ValueError("Research backfill contains duplicate event ids")
    project_names = {str(project["id"]): str(project["name"]) for project in projects}
    normalized_projects = [_project(project) for project in projects]
    normalized_events = [_event(event, project_names) for event in events]
    for event in normalized_events:
        if not str(event.get("source_url", "")).startswith("https://"):
            raise ValueError(f"Research event requires a direct HTTPS source URL: {event.get('id')}")
        if not event.get("occurred_at") or not event.get("project_id"):
            raise ValueError(f"Research event requires occurred_at and project_id: {event.get('id')}")
    return normalized_projects, normalized_events
