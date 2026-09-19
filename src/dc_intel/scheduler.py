from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .digest import render_digest

EASTERN = ZoneInfo("America/New_York")


def _event_rows(connection: Any, window_start: datetime, window_end: datetime) -> list[dict[str, Any]]:
    rows = connection.execute("""
        SELECT pe.id, pe.event_type, pe.occurred_at, pe.materiality_score materiality,
               pe.novelty_score novelty, pe.confidence_score confidence, pe.score_breakdown,
               ee.headline, ee.summary, ee.extraction_json, p.canonical_name project_name,
               s.name source_name, s.source_type, rd.canonical_url source_url
        FROM project_events pe
        JOIN extracted_events ee ON ee.id=pe.extracted_event_id
        JOIN projects p ON p.id=pe.project_id
        JOIN raw_documents rd ON rd.id=ee.raw_document_id
        JOIN sources s ON s.id=rd.source_id
        WHERE COALESCE(pe.occurred_at, pe.created_at) >= %s
          AND COALESCE(pe.occurred_at, pe.created_at) < %s
        ORDER BY pe.materiality_score DESC, COALESCE(pe.occurred_at, pe.created_at) DESC
    """, (window_start, window_end)).fetchall()
    events = []
    for row in rows:
        item = dict(row)
        breakdown = item.get("score_breakdown") or {}
        materiality_reason = ((breakdown.get("materiality") or {}).get("explanation") if isinstance(breakdown, dict) else None)
        extraction = item.get("extraction_json") or {}
        events.append({
            **item,
            "id": str(item["id"]),
            "what_new": item["summary"],
            "why_matters": materiality_reason or "The event changed a tracked project fact or development-stage signal.",
            "implication": extraction.get("implication") or "Review the project timeline and any affected milestone or source watchlist.",
            "evidence": extraction.get("summary") or item["summary"],
        })
    return events


def _window(now_eastern: datetime, digest_type: str) -> tuple[datetime, datetime]:
    if digest_type == "morning":
        start = datetime.combine(now_eastern.date() - timedelta(days=1), time(18, 0), EASTERN)
        end = datetime.combine(now_eastern.date(), time(6, 30), EASTERN)
    else:
        start = datetime.combine(now_eastern.date(), time(0, 0), EASTERN)
        end = datetime.combine(now_eastern.date(), time(18, 0), EASTERN)
    return start.astimezone(UTC), end.astimezone(UTC)


def generate_scheduled_digest(connection: Any, digest_type: str, now: datetime | None = None) -> bool:
    now_eastern = (now or datetime.now(UTC)).astimezone(EASTERN)
    window_start, window_end = _window(now_eastern, digest_type)
    exists = connection.execute(
        "SELECT 1 FROM digests WHERE digest_type=%s AND window_start=%s AND window_end=%s",
        (digest_type, window_start, window_end),
    ).fetchone()
    if exists:
        return False
    events = _event_rows(connection, window_start, window_end)
    subject, body_text, body_html = render_digest(events, digest_type, window_end.isoformat())
    event_ids = [event["id"] for event in events]
    connection.execute("""
        INSERT INTO digests (digest_type, window_start, window_end, subject, body_text, body_html, event_ids)
        VALUES (%s,%s,%s,%s,%s,%s,%s::uuid[])
    """, (digest_type, window_start, window_end, subject, body_text, body_html, event_ids))
    connection.commit()
    folder = Path("data/digests")
    folder.mkdir(parents=True, exist_ok=True)
    stem = f"{now_eastern.date().isoformat()}-{digest_type}"
    (folder / f"{stem}.txt").write_text(f"Subject: {subject}\n\n{body_text}", encoding="utf-8")
    (folder / f"{stem}.html").write_text(f"<!doctype html><html><body>{body_html}</body></html>", encoding="utf-8")
    return True


def run_due_digests(connection: Any, now: datetime | None = None) -> list[str]:
    now_eastern = (now or datetime.now(UTC)).astimezone(EASTERN)
    generated: list[str] = []
    schedules = (("morning", time(6, 30)), ("evening", time(18, 0)))
    for digest_type, scheduled_time in schedules:
        if now_eastern.time() >= scheduled_time and generate_scheduled_digest(connection, digest_type, now_eastern):
            generated.append(digest_type)
    return generated
