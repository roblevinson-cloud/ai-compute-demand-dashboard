from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .collectors import collect_source, html_to_text
from .db import connect
from .extraction import content_fingerprint, deterministic_extract
from .resolution import rank_candidates
from .scoring import score_confidence, score_materiality, score_novelty
from .source_registry import load_source_registry

LOG = logging.getLogger(__name__)


def _source_row_to_config(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "key": row["source_key"], "name": row["name"], "source_type": row["source_type"],
        "jurisdiction": row.get("jurisdiction"), "url": row["base_url"],
        "method": row["collection_method"], "interval_minutes": row["schedule_minutes"],
        "priority": row["priority"], "enabled": row["enabled"], "parser_config": row.get("parser_config") or {},
    }


def collect_due(connection: Any, raw_root: str | Path = "data/raw", limit: int = 100) -> dict[str, int]:
    rows = list(connection.execute("""
        SELECT * FROM sources
        WHERE enabled AND (
            last_attempt_at IS NULL OR
            last_attempt_at <= now() - make_interval(mins => schedule_minutes)
        ) ORDER BY priority DESC, last_attempt_at NULLS FIRST LIMIT %s
    """, (limit,)).fetchall())
    stats = {"sources_attempted": 0, "documents_new": 0, "errors": 0}
    for row in rows:
        source = _source_row_to_config(row)
        stats["sources_attempted"] += 1
        run = connection.execute(
            "INSERT INTO collection_runs (source_id) VALUES (%s) RETURNING id, started_at", (row["id"],)
        ).fetchone()
        connection.execute("UPDATE sources SET last_attempt_at = now() WHERE id = %s", (row["id"],))
        connection.commit()
        checkpoint = connection.execute("SELECT * FROM source_checkpoints WHERE source_id = %s", (row["id"],)).fetchone()
        try:
            documents, next_checkpoint = collect_source(source, raw_root, dict(checkpoint) if checkpoint else None)
            inserted = 0
            for document in documents:
                result = connection.execute("""
                    INSERT INTO raw_documents (
                        source_id, collection_run_id, canonical_url, title, published_at, retrieved_at,
                        content_type, content_hash, storage_uri, byte_size, http_headers, metadata
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb)
                    ON CONFLICT (source_id, canonical_url, content_hash) DO NOTHING RETURNING id
                """, (
                    row["id"], run["id"], document.canonical_url, document.title, document.published_at,
                    document.retrieved_at, document.content_type, document.content_hash, document.storage_uri,
                    document.byte_size, json.dumps(document.metadata.get("http_headers", {})), json.dumps(document.metadata),
                )).fetchone()
                inserted += int(result is not None)
            connection.execute("""
                INSERT INTO source_checkpoints (source_id, etag, last_modified, content_hash, cursor, checked_at)
                VALUES (%s,%s,%s,%s,%s,now()) ON CONFLICT (source_id) DO UPDATE SET
                    etag=EXCLUDED.etag, last_modified=EXCLUDED.last_modified,
                    content_hash=EXCLUDED.content_hash, cursor=EXCLUDED.cursor, checked_at=now()
            """, (row["id"], next_checkpoint.get("etag"), next_checkpoint.get("last_modified"), next_checkpoint.get("content_hash"), next_checkpoint.get("cursor")))
            connection.execute("UPDATE collection_runs SET finished_at=now(), status='ok', documents_found=%s, documents_new=%s, duration_ms=(EXTRACT(EPOCH FROM (now() - started_at))*1000)::int WHERE id=%s", (len(documents), inserted, run["id"]))
            connection.execute("UPDATE sources SET last_success_at=now(), consecutive_failures=0 WHERE id=%s", (row["id"],))
            connection.commit()
            stats["documents_new"] += inserted
        except Exception as exc:  # noqa: BLE001 - one broken source must not stop the collection cycle
            connection.execute("UPDATE collection_runs SET finished_at=now(), status='error', detail=%s::jsonb WHERE id=%s", (json.dumps({"error": str(exc)}), run["id"]))
            connection.execute("INSERT INTO collection_errors (collection_run_id, source_id, error_class, message) VALUES (%s,%s,%s,%s)", (run["id"], row["id"], type(exc).__name__, str(exc)[:4000]))
            connection.execute("UPDATE sources SET consecutive_failures=consecutive_failures+1 WHERE id=%s", (row["id"],))
            connection.commit()
            stats["errors"] += 1
            LOG.warning("Collection failed for %s: %s", source["key"], exc)
    return stats


def _document_text(document: dict[str, Any]) -> str:
    path = Path(document["storage_uri"])
    if not path.exists():
        return ""
    content = path.read_bytes()
    content_type = str(document.get("content_type") or "")
    if "html" in content_type or path.suffix.lower() in {".html", ".htm"}:
        return html_to_text(content)
    if "pdf" in content_type or path.suffix.lower() == ".pdf":
        return ""  # A production deployment should attach pdftotext/OCR here.
    return content.decode("utf-8", errors="replace")


def _fact_map(extraction: Any) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for fact in extraction.facts:
        values[fact.field] = fact.value
    return values


def _project_candidates(connection: Any) -> list[dict[str, Any]]:
    rows = connection.execute("""
        SELECT p.id, p.canonical_name, p.county, p.state, p.parcel_ids parcel,
               p.utility_load_mw mw, p.acreage,
               COALESCE(array_agg(DISTINCT pa.alias) FILTER (WHERE pa.alias IS NOT NULL), '{}') alias,
               COALESCE(array_agg(DISTINCT c.canonical_name) FILTER (WHERE pc.relationship_type IN ('developer','owner')), '{}') developer,
               COALESCE(array_agg(DISTINCT c.canonical_name) FILTER (WHERE pc.relationship_type IN ('tenant','customer')), '{}') tenant,
               COALESCE(array_agg(DISTINCT c.canonical_name) FILTER (WHERE pc.relationship_type = 'utility'), '{}') utility
        FROM projects p
        LEFT JOIN project_aliases pa ON pa.project_id=p.id
        LEFT JOIN project_companies pc ON pc.project_id=p.id
        LEFT JOIN companies c ON c.id=pc.company_id
        GROUP BY p.id
    """).fetchall()
    return [dict(row) for row in rows]


def process_pending(connection: Any, limit: int = 100) -> dict[str, int]:
    documents = list(connection.execute("""
        SELECT rd.*, s.source_type FROM raw_documents rd
        JOIN sources s ON s.id=rd.source_id
        LEFT JOIN extracted_events ee ON ee.raw_document_id=rd.id
        WHERE ee.id IS NULL ORDER BY rd.retrieved_at LIMIT %s
    """, (limit,)).fetchall())
    projects = _project_candidates(connection)
    stats = {"documents_processed": 0, "events_linked": 0, "review_candidates": 0, "alerts_queued": 0}
    for document_row in documents:
        document = dict(document_row)
        text = _document_text(document)
        extraction = deterministic_extract(
            document_id=str(document["id"]), title=document.get("title") or "Untitled document",
            text=text, published_at=str(document.get("published_at") or document.get("retrieved_at")),
        )
        payload = extraction.to_dict()
        extraction_hash = content_fingerprint(json.dumps(payload, sort_keys=True, default=str).encode())
        extracted = connection.execute("""
            INSERT INTO extracted_events (
                raw_document_id, schema_version, event_type, headline, summary, occurred_at,
                extraction_model, extraction_confidence, extraction_json, extraction_hash
            ) VALUES (%s,%s,%s,%s,%s,%s,'deterministic-v1',%s,%s::jsonb,%s)
            RETURNING id
        """, (document["id"], extraction.schema_version, extraction.event_type, extraction.headline, extraction.summary,
              extraction.published_at, extraction.extraction_confidence, json.dumps(payload), extraction_hash)).fetchone()
        signal = {
            "county": extraction.location.get("county"), "state": extraction.location.get("state"),
            "alias": extraction.aliases + ([extraction.project_name] if extraction.project_name else []),
            **_fact_map(extraction),
        }
        exact = None
        if extraction.project_name:
            normalized = extraction.project_name.casefold()
            exact = next((project for project in projects if project["canonical_name"].casefold() == normalized or normalized in {str(alias).casefold() for alias in project.get("alias", [])}), None)
        ranked = rank_candidates(signal, projects) if projects else []
        top = ranked[0] if ranked else None
        linked = exact or (next((project for project in projects if top and str(project["id"]) == top.candidate_project_id), None) if top and top.recommendation == "candidate_auto_link" else None)
        if linked:
            facts = _fact_map(extraction)
            score_input = {
                "event_type": extraction.event_type, "mw": facts.get("utility_load_mw") or facts.get("generation_capacity_mw"),
                "capex_usd_b": facts.get("capex_usd_b"), "stage_weight": 6, "regulatory_weight": 8 if "permit" in extraction.event_type or "puc" in extraction.event_type else 0,
                "risk_weight": 7 if extraction.event_type in {"delay","cancellation","opposition_litigation"} else 0,
                "major_party": bool(extraction.companies), "new_fact_count": len(extraction.facts), "changed_fact_count": 0,
                "first_primary_record": document["source_type"].startswith("primary"), "source_type": document["source_type"],
                "extraction_confidence": extraction.extraction_confidence, "match_confidence": 100 if exact else top.score,
                "corroborating_sources": 0,
            }
            materiality, novelty, confidence = score_materiality(score_input), score_novelty(score_input), score_confidence(score_input)
            event = connection.execute("""
                INSERT INTO project_events (project_id, extracted_event_id, event_type, occurred_at, materiality_score, novelty_score, confidence_score, score_breakdown)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb) RETURNING id
            """, (linked["id"], extracted["id"], extraction.event_type, extraction.published_at, materiality.value, novelty.value, confidence.value,
                  json.dumps({"materiality": materiality.to_dict(), "novelty": novelty.to_dict(), "confidence": confidence.to_dict()}))).fetchone()
            for fact in extraction.facts:
                evidence = fact.evidence[0] if fact.evidence else None
                numeric = fact.value if isinstance(fact.value, (int, float)) else None
                connection.execute("""
                    INSERT INTO fact_claims (project_id, project_event_id, raw_document_id, field_name, value_json, normalized_numeric, unit, valid_from, confidence, evidence_quote, evidence_page)
                    VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s)
                """, (linked["id"], event["id"], document["id"], fact.field, json.dumps(fact.value), numeric, fact.unit, fact.as_of, fact.confidence,
                      evidence.quote if evidence else None, evidence.page if evidence else None))
            if materiality.value >= 90 and novelty.value >= 70 and confidence.value >= 70:
                connection.execute("INSERT INTO alerts (project_event_id, severity, subject, body_html) VALUES (%s,'critical',%s,%s)", (event["id"], extraction.headline, f"<p>{extraction.summary}</p>"))
                stats["alerts_queued"] += 1
            stats["events_linked"] += 1
        else:
            candidate_id = top.candidate_project_id if top and top.candidate_project_id != "unknown" else None
            connection.execute("""
                INSERT INTO entity_match_candidates (
                    extracted_event_id, candidate_project_id, proposed_project_json, score, recommendation,
                    supporting_evidence, conflicting_evidence, feature_scores
                ) VALUES (%s,%s,%s::jsonb,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb)
            """, (extracted["id"], candidate_id, json.dumps({"project_name": extraction.project_name, "location": extraction.location, "facts": [asdict(fact) for fact in extraction.facts]}),
                  top.score if top else 0, top.recommendation if top else "likely_new_project",
                  json.dumps(top.supporting if top else []), json.dumps(top.conflicts if top else []), json.dumps(top.feature_scores if top else {})))
            stats["review_candidates"] += 1
        connection.commit()
        stats["documents_processed"] += 1
    return stats


def run_once(database_url: str | None = None, source_path: str = "config/sources.yml") -> dict[str, Any]:
    from .db import upsert_sources

    sources = load_source_registry(source_path)
    with connect(database_url) as connection:
        upsert_sources(connection, sources)
        collection = collect_due(connection)
        processing = process_pending(connection)
    return {"collection": collection, "processing": processing}


def run_worker(database_url: str | None = None, poll_seconds: int = 60) -> None:
    from .scheduler import run_due_digests

    LOG.info("Worker started; polling due sources every %s seconds", poll_seconds)
    while True:
        try:
            result = run_once(database_url)
            with connect(database_url) as connection:
                result["digests_generated"] = run_due_digests(connection)
                if os.getenv("BUILD_LIVE_DASHBOARD", "0").lower() in {"1", "true", "yes"}:
                    from .dashboard import build_live_dashboard_data
                    from .site import build_site

                    build_site(build_live_dashboard_data(connection), "docs/index.html")
                    result["dashboard_built"] = True
            LOG.info("Worker cycle: %s", result)
        except Exception:
            LOG.exception("Worker cycle failed")
        time.sleep(max(10, poll_seconds))
