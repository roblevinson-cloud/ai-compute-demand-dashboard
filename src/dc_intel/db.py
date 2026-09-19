from __future__ import annotations

import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from importlib.resources import files
from typing import Any


def database_url() -> str:
    value = os.getenv("DATABASE_URL")
    if not value:
        raise RuntimeError("DATABASE_URL is required for database commands")
    return value


def _psycopg():
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:  # pragma: no cover - exercised in minimal installs
        raise RuntimeError("Install the project dependencies to use PostgreSQL: pip install -e .") from exc
    return psycopg, dict_row


@contextmanager
def connect(url: str | None = None) -> Iterator[Any]:
    psycopg, dict_row = _psycopg()
    with psycopg.connect(url or database_url(), row_factory=dict_row) as connection:
        yield connection


def init_database(url: str | None = None) -> None:
    schema = files("dc_intel").joinpath("schema.sql").read_text(encoding="utf-8")
    with connect(url) as connection:
        connection.execute(schema)
        connection.commit()


def upsert_sources(connection: Any, sources: list[dict[str, Any]]) -> int:
    sql = """
        INSERT INTO sources (
            source_key, name, source_type, jurisdiction, base_url,
            collection_method, schedule_minutes, priority, enabled, parser_config
        ) VALUES (
            %(key)s, %(name)s, %(source_type)s, %(jurisdiction)s, %(url)s,
            %(method)s, %(interval_minutes)s, %(priority)s, %(enabled)s, %(parser_config)s::jsonb
        )
        ON CONFLICT (source_key) DO UPDATE SET
            name = EXCLUDED.name,
            source_type = EXCLUDED.source_type,
            jurisdiction = EXCLUDED.jurisdiction,
            base_url = EXCLUDED.base_url,
            collection_method = EXCLUDED.collection_method,
            schedule_minutes = EXCLUDED.schedule_minutes,
            priority = EXCLUDED.priority,
            enabled = EXCLUDED.enabled,
            parser_config = EXCLUDED.parser_config,
            updated_at = now()
    """
    for source in sources:
        payload = {**source, "parser_config": json.dumps(source.get("parser_config") or {})}
        connection.execute(sql, payload)
    connection.commit()
    return len(sources)


def fetch_dashboard_rows(connection: Any) -> dict[str, list[dict[str, Any]]]:
    queries = {
        "projects": """
            SELECT p.*, COALESCE(array_agg(DISTINCT pa.alias) FILTER (WHERE pa.alias IS NOT NULL), '{}') aliases
            FROM projects p LEFT JOIN project_aliases pa ON pa.project_id = p.id
            GROUP BY p.id ORDER BY p.last_updated_at DESC
        """,
        "events": """
            SELECT pe.*, ee.headline, ee.summary, p.canonical_name project_name, p.slug project_slug,
                   rd.canonical_url source_url, s.name source_name, s.source_type
            FROM project_events pe
            JOIN extracted_events ee ON ee.id = pe.extracted_event_id
            JOIN projects p ON p.id = pe.project_id
            JOIN raw_documents rd ON rd.id = ee.raw_document_id
            JOIN sources s ON s.id = rd.source_id
            ORDER BY COALESCE(pe.occurred_at, pe.created_at) DESC
            LIMIT 500
        """,
        "review_queue": """
            SELECT emc.*, ee.headline, p.canonical_name candidate_project_name
            FROM entity_match_candidates emc
            JOIN extracted_events ee ON ee.id = emc.extracted_event_id
            LEFT JOIN projects p ON p.id = emc.candidate_project_id
            WHERE emc.review_status = 'pending' ORDER BY emc.score DESC
        """,
        "sources": "SELECT * FROM sources ORDER BY priority DESC, name",
        "digests": "SELECT * FROM digests ORDER BY generated_at DESC LIMIT 30",
    }
    return {name: list(connection.execute(query).fetchall()) for name, query in queries.items()}
