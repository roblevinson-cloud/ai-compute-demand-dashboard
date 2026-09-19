from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .demo import build_demo_data
from .digest import render_digest


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:70]


def _hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def _relationship_type(value: str) -> str:
    lowered = value.lower()
    if "tenant" in lowered or "customer" in lowered:
        return "tenant"
    if "operator" in lowered:
        return "operator"
    if "developer" in lowered or "applicant" in lowered:
        return "developer"
    if "utility" in lowered:
        return "utility"
    return "contractor"


def seed_demo_database(connection: Any) -> dict[str, int]:
    data = build_demo_data()
    counts = {"projects": 0, "events": 0, "candidates": 0, "digests": 0}
    project_ids: dict[str, Any] = {}
    for project in data["projects"]:
        row = connection.execute("""
            INSERT INTO projects (
                canonical_name, slug, status, location_precision, address, city, county, state,
                acreage, building_count, utility_load_mw, it_load_mw, generation_capacity_mw,
                capex_usd, status_detail, first_seen_at, last_updated_at, metadata
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
            ON CONFLICT (slug) DO UPDATE SET
                canonical_name=EXCLUDED.canonical_name, status=EXCLUDED.status,
                last_updated_at=EXCLUDED.last_updated_at, status_detail=EXCLUDED.status_detail,
                metadata=EXCLUDED.metadata
            RETURNING id
        """, (
            project["name"], project["slug"], project["status"], project["location_precision"],
            project["address"], project["city"], project["county"], project["state"], project["acreage"],
            project["buildings"], None, project["it_mw"], project["mw"],
            project["capex_usd_b"] * 1e9 if project["capex_usd_b"] else None,
            project["summary"], project["first_seen"], project["last_update"], json.dumps({"pilot": True, "risk": project["risk"]}),
        )).fetchone()
        project_ids[project["id"]] = row["id"]
        for alias in project["aliases"]:
            connection.execute("""
                INSERT INTO project_aliases (project_id, alias, alias_type, confidence)
                VALUES (%s,%s,%s,%s) ON CONFLICT (project_id, alias) DO UPDATE SET
                    alias_type=EXCLUDED.alias_type, confidence=EXCLUDED.confidence
            """, (row["id"], alias["name"], alias["type"], alias["confidence"]))
        for relationship in project["relationships"]:
            company = connection.execute("""
                INSERT INTO companies (canonical_name) VALUES (%s)
                ON CONFLICT (canonical_name) DO UPDATE SET updated_at=now() RETURNING id
            """, (relationship["company"],)).fetchone()
            connection.execute("""
                INSERT INTO project_companies (project_id, company_id, relationship_type, confidence)
                VALUES (%s,%s,%s,%s) ON CONFLICT (project_id, company_id, relationship_type) DO UPDATE SET
                    confidence=EXCLUDED.confidence
            """, (row["id"], company["id"], _relationship_type(relationship["role"]), relationship["confidence"]))
        counts["projects"] += 1

    event_ids: dict[str, Any] = {}
    extracted_ids: dict[str, Any] = {}
    raw_by_project: dict[str, Any] = {}
    raw_folder = Path("data/raw/demo")
    raw_folder.mkdir(parents=True, exist_ok=True)
    for event in data["events"]:
        source_key = f"pilot-{_key(event['source_name'])}"
        source = connection.execute("""
            INSERT INTO sources (source_key, name, source_type, jurisdiction, base_url, collection_method, schedule_minutes, priority)
            VALUES (%s,%s,%s,'New Mexico',%s,'page',60,90)
            ON CONFLICT (source_key) DO UPDATE SET base_url=EXCLUDED.base_url RETURNING id
        """, (source_key, event["source_name"], event["source_type"], event["source_url"])).fetchone()
        digest = _hash(event)
        path = raw_folder / f"{digest}.json"
        if not path.exists():
            path.write_text(json.dumps(event, indent=2), encoding="utf-8")
        raw = connection.execute("""
            INSERT INTO raw_documents (
                source_id, canonical_url, title, published_at, content_type, content_hash,
                storage_uri, byte_size, metadata
            ) VALUES (%s,%s,%s,%s,'application/json',%s,%s,%s,%s::jsonb)
            ON CONFLICT (source_id, canonical_url, content_hash) DO UPDATE SET title=EXCLUDED.title
            RETURNING id
        """, (source["id"], event["source_url"], event["headline"], event["occurred_at"], digest, path.as_posix(), path.stat().st_size, json.dumps({"pilot": True}))).fetchone()
        raw_by_project.setdefault(event["project_id"], raw["id"])
        extraction_payload = {
            "schema_version": "1.0", "headline": event["headline"], "summary": event["what_new"],
            "event_type": event["event_type"], "why_it_matters": event["why_matters"],
            "implication": event["implication"], "evidence": event["evidence"], "numbers": event["numbers"],
        }
        extraction_hash = _hash(extraction_payload)
        extracted = connection.execute("""
            INSERT INTO extracted_events (
                raw_document_id, schema_version, event_type, headline, summary, occurred_at,
                extraction_model, extraction_confidence, extraction_json, extraction_hash
            ) VALUES (%s,'1.0',%s,%s,%s,%s,'curated-pilot',%s,%s::jsonb,%s)
            ON CONFLICT (raw_document_id, extraction_hash) DO UPDATE SET headline=EXCLUDED.headline
            RETURNING id
        """, (raw["id"], event["event_type"], event["headline"], event["what_new"], event["occurred_at"], event["confidence"], json.dumps(extraction_payload), extraction_hash)).fetchone()
        extracted_ids[event["id"]] = extracted["id"]
        project_event = connection.execute("""
            INSERT INTO project_events (
                project_id, extracted_event_id, event_type, occurred_at,
                materiality_score, novelty_score, confidence_score, score_breakdown, analyst_status
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,'pilot-reviewed')
            ON CONFLICT (project_id, extracted_event_id) DO UPDATE SET
                materiality_score=EXCLUDED.materiality_score, novelty_score=EXCLUDED.novelty_score,
                confidence_score=EXCLUDED.confidence_score
            RETURNING id
        """, (project_ids[event["project_id"]], extracted["id"], event["event_type"], event["occurred_at"],
              event["materiality"], event["novelty"], event["confidence"], json.dumps({
                  "materiality": {"value": event["materiality"], "explanation": event["why_matters"]},
                  "novelty": {"value": event["novelty"]}, "confidence": {"value": event["confidence"]},
              }))).fetchone()
        event_ids[event["id"]] = project_event["id"]
        counts["events"] += 1

    for project in data["projects"]:
        raw_id = raw_by_project.get(project["id"])
        if not raw_id:
            continue
        for metric in project["metrics"]:
            exists = connection.execute("SELECT 1 FROM fact_claims WHERE project_id=%s AND field_name=%s AND evidence_quote=%s", (project_ids[project["id"]], _key(metric["label"]).replace("-", "_"), metric["boundary"])).fetchone()
            if not exists:
                connection.execute("""
                    INSERT INTO fact_claims (project_id, raw_document_id, field_name, value_json, confidence, evidence_quote)
                    VALUES (%s,%s,%s,%s::jsonb,%s,%s)
                """, (project_ids[project["id"]], raw_id, _key(metric["label"]).replace("-", "_"), json.dumps(metric["value"]), project["confidence"], metric["boundary"]))

    for candidate in data["review_queue"]:
        signal_event = "evt-google-lea" if "google" in candidate["id"] else "evt-jupiter-power-revision"
        extracted_id = extracted_ids[signal_event]
        candidate_project = project_ids.get(candidate["candidate_project_id"])
        exists = connection.execute("SELECT 1 FROM entity_match_candidates WHERE extracted_event_id=%s AND candidate_project_id=%s", (extracted_id, candidate_project)).fetchone()
        if not exists:
            connection.execute("""
                INSERT INTO entity_match_candidates (
                    extracted_event_id, candidate_project_id, score, recommendation,
                    supporting_evidence, conflicting_evidence, feature_scores, review_status, resolution_note
                ) VALUES (%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s)
            """, (extracted_id, candidate_project, candidate["score"], candidate["recommendation"],
                  json.dumps(candidate["supporting"]), json.dumps(candidate["conflicts"]), json.dumps(candidate["feature_scores"]),
                  "pending" if "pending" in candidate["status"] else "triaged", candidate["next_action"]))
            counts["candidates"] += 1

    for brief in data["briefs"]:
        events = [event for event in data["events"] if event["id"] in brief["event_ids"]]
        subject, body_text, body_html = render_digest(events, brief["type"], brief["date"] + "T12:00:00-04:00")
        ids = [event_ids[event_id] for event_id in brief["event_ids"] if event_id in event_ids]
        connection.execute("""
            INSERT INTO digests (digest_type, window_start, window_end, subject, body_text, body_html, event_ids)
            VALUES (%s,%s::date,%s::date + interval '23 hours 59 minutes',%s,%s,%s,%s::uuid[])
            ON CONFLICT (digest_type, window_start, window_end) DO NOTHING
        """, (brief["type"].split()[0].lower(), brief["date"], brief["date"], subject, body_text, body_html, ids))
        counts["digests"] += 1
    connection.commit()
    return counts
