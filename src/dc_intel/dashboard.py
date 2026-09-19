from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .models import EVENT_TYPES


def _iso(value: Any) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else (str(value) if value else None)


def _json(value: Any, fallback: Any) -> Any:
    return value if isinstance(value, (dict, list)) else fallback


def _by_role(relationships: list[dict[str, Any]], roles: set[str]) -> list[str]:
    return [item["company"] for item in relationships if item["role"] in roles]


def build_live_dashboard_data(connection: Any) -> dict[str, Any]:
    project_rows = list(connection.execute("SELECT * FROM projects ORDER BY last_updated_at DESC").fetchall())
    event_rows = list(connection.execute("""
        SELECT pe.*, ee.headline, ee.summary, ee.extraction_json,
               p.canonical_name project_name, s.name source_name, s.source_type,
               rd.canonical_url source_url
        FROM project_events pe
        JOIN extracted_events ee ON ee.id=pe.extracted_event_id
        JOIN projects p ON p.id=pe.project_id
        JOIN raw_documents rd ON rd.id=ee.raw_document_id
        JOIN sources s ON s.id=rd.source_id
        ORDER BY COALESCE(pe.occurred_at, pe.created_at) DESC
        LIMIT 1000
    """).fetchall())
    alias_rows = list(connection.execute("SELECT * FROM project_aliases ORDER BY confidence DESC").fetchall())
    relationship_rows = list(connection.execute("""
        SELECT pc.*, c.canonical_name company_name
        FROM project_companies pc JOIN companies c ON c.id=pc.company_id
        ORDER BY pc.confidence DESC
    """).fetchall())
    fact_rows = list(connection.execute("""
        SELECT cpf.*, rd.canonical_url source_url
        FROM current_project_facts cpf JOIN raw_documents rd ON rd.id=cpf.raw_document_id
        ORDER BY cpf.field_name
    """).fetchall())

    aliases_by_project: dict[str, list[dict[str, Any]]] = {}
    for row in alias_rows:
        aliases_by_project.setdefault(str(row["project_id"]), []).append({
            "name": row["alias"], "type": row["alias_type"], "confidence": row["confidence"],
        })
    relationships_by_project: dict[str, list[dict[str, Any]]] = {}
    for row in relationship_rows:
        relationships_by_project.setdefault(str(row["project_id"]), []).append({
            "company": row["company_name"], "role": row["relationship_type"], "confidence": row["confidence"],
        })
    facts_by_project: dict[str, list[dict[str, Any]]] = {}
    for row in fact_rows:
        facts_by_project.setdefault(str(row["project_id"]), []).append({
            "label": str(row["field_name"]).replace("_", " ").title(),
            "value": row["value_json"], "boundary": row.get("evidence_quote") or "See source evidence",
            "source_url": row["source_url"],
        })

    events = []
    event_scores: dict[str, int] = {}
    for row in event_rows:
        project_id = str(row["project_id"])
        breakdown = _json(row.get("score_breakdown"), {})
        extraction = _json(row.get("extraction_json"), {})
        materiality_detail = _json(breakdown.get("materiality"), {})
        event = {
            "id": str(row["id"]), "project_id": project_id, "project_name": row["project_name"],
            "occurred_at": _iso(row.get("occurred_at") or row.get("created_at")),
            "event_type": row["event_type"], "headline": row["headline"],
            "what_new": row["summary"],
            "why_matters": materiality_detail.get("explanation") or "This record changes a tracked project fact or milestone.",
            "implication": extraction.get("implication") or "Review affected facts, milestones, and follow-on sources.",
            "source_name": row["source_name"], "source_type": row["source_type"], "source_url": row["source_url"],
            "materiality": row["materiality_score"], "novelty": row["novelty_score"], "confidence": row["confidence_score"],
            "evidence": extraction.get("summary") or row["summary"], "numbers": [],
        }
        events.append(event)
        event_scores[project_id] = max(event_scores.get(project_id, 0), int(row["materiality_score"]))

    projects = []
    for row in project_rows:
        project_id = str(row["id"])
        relationships = relationships_by_project.get(project_id, [])
        projects.append({
            "id": project_id, "slug": row["slug"], "name": row["canonical_name"], "status": row["status"],
            "status_tone": "risk" if row["status"] in {"delayed", "cancelled", "stayed"} else "signal",
            "state": row.get("state"), "county": row.get("county"), "city": row.get("city"),
            "address": row.get("address") or "Undisclosed", "location_precision": row.get("location_precision"),
            "developer": _by_role(relationships, {"developer", "owner"}), "tenant": _by_role(relationships, {"tenant", "customer"}),
            "operator": _by_role(relationships, {"operator"}), "utility": _by_role(relationships, {"utility"}) or ["Not verified"],
            "parcel": row.get("parcel_ids") or [], "alias": [item["name"] for item in aliases_by_project.get(project_id, [])],
            "aliases": aliases_by_project.get(project_id, []), "mw": row.get("generation_capacity_mw") or row.get("utility_load_mw"),
            "it_mw": row.get("it_load_mw"), "acreage": row.get("acreage"),
            "capex_usd_b": float(row["capex_usd"]) / 1e9 if row.get("capex_usd") else None,
            "buildings": row.get("building_count"), "materiality": event_scores.get(project_id, 0), "confidence": 0,
            "first_seen": _iso(row.get("first_seen_at")), "last_update": _iso(row.get("last_updated_at")),
            "summary": row.get("status_detail") or "Live project record assembled from sourced events and claims.",
            "risk": "Review unresolved entity candidates and source-level fact boundaries.",
            "metrics": facts_by_project.get(project_id, []), "relationships": relationships,
        })

    candidate_rows = list(connection.execute("""
        SELECT emc.*, ee.headline signal, p.canonical_name candidate
        FROM entity_match_candidates emc
        JOIN extracted_events ee ON ee.id=emc.extracted_event_id
        LEFT JOIN projects p ON p.id=emc.candidate_project_id
        WHERE emc.review_status='pending' ORDER BY emc.score DESC
    """).fetchall())
    review_queue = [{
        "id": str(row["id"]), "signal": row["signal"], "candidate": row.get("candidate") or "New project record",
        "status": row["review_status"], "created_at": _iso(row["created_at"]), "score": row["score"],
        "recommendation": row["recommendation"], "supporting": _json(row.get("supporting_evidence"), []),
        "conflicts": _json(row.get("conflicting_evidence"), []), "feature_scores": _json(row.get("feature_scores"), {}),
        "next_action": row.get("resolution_note") or "Review the source evidence and accept, reject, split, or create a project.",
    } for row in candidate_rows]

    source_rows = list(connection.execute("SELECT * FROM sources ORDER BY priority DESC, name").fetchall())
    source_health = []
    for row in source_rows:
        failures = int(row.get("consecutive_failures") or 0)
        source_health.append({
            "key": row["source_key"], "name": row["name"], "source_type": row["source_type"],
            "jurisdiction": row.get("jurisdiction"), "status": "failed" if failures >= 3 else ("degraded" if failures else "healthy"),
            "last_checked": _iso(row.get("last_attempt_at")), "last_new_document": _iso(row.get("last_success_at")),
            "interval_minutes": row["schedule_minutes"], "priority": row["priority"], "url": row["base_url"], "tags": [],
        })
    by_type: dict[str, int] = {}
    for source in source_health:
        by_type[source["source_type"]] = by_type.get(source["source_type"], 0) + 1

    digest_rows = list(connection.execute("SELECT * FROM digests ORDER BY generated_at DESC LIMIT 30").fetchall())
    briefs = [{
        "id": str(row["id"]), "type": str(row["digest_type"]).title() + " Brief",
        "date": _iso(row["window_end"])[:10], "subject": row["subject"],
        "summary": str(row["body_text"]).split("\n")[2] if len(str(row["body_text"]).split("\n")) > 2 else row["subject"],
        "event_ids": [str(value) for value in (row.get("event_ids") or [])],
    } for row in digest_rows]
    healthy = sum(source["status"] == "healthy" for source in source_health)
    return {
        "meta": {
            "title": "GridSignal", "subtitle": "U.S. data center development intelligence",
            "generated_at": datetime.now(UTC).isoformat(), "as_of": datetime.now(UTC).isoformat(),
            "mode": "Live PostgreSQL monitor", "disclaimer": "Live records remain source-bounded; open the linked evidence before relying on a claim.",
        },
        "kpis": {
            "tracked_projects": len(projects), "priority_events": sum(event["materiality"] >= 85 for event in events),
            "new_signals": sum(event["event_type"] == "new_project_discovery" for event in events),
            "review_items": len(review_queue), "healthy_sources": healthy, "source_count": len(source_health),
        },
        "projects": projects, "events": events, "review_queue": review_queue,
        "source_health": source_health,
        "source_registry_summary": {"total": len(source_health), "enabled": sum(bool(row["enabled"]) for row in source_rows), "by_type": by_type, "by_jurisdiction": {}},
        "briefs": briefs, "event_taxonomy": list(EVENT_TYPES),
    }
