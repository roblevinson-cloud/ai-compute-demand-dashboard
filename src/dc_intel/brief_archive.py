from __future__ import annotations

import html
import json
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .digest import render_digest, select_digest_events

EASTERN = ZoneInfo("America/New_York")
BRIEF_SCHEDULES = (("morning", time(6, 30)), ("evening", time(18, 0)))


def parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed


def digest_window(now: datetime, digest_type: str) -> tuple[datetime, datetime]:
    now_eastern = now.astimezone(EASTERN)
    if digest_type == "morning":
        start = datetime.combine(now_eastern.date() - timedelta(days=1), time(18, 0), EASTERN)
        end = datetime.combine(now_eastern.date(), time(6, 30), EASTERN)
    elif digest_type == "evening":
        start = datetime.combine(now_eastern.date(), time(0, 0), EASTERN)
        end = datetime.combine(now_eastern.date(), time(18, 0), EASTERN)
    else:
        raise ValueError(f"Unsupported digest type: {digest_type}")
    return start.astimezone(UTC), end.astimezone(UTC)


def due_digest_types(now: datetime) -> list[str]:
    now_eastern = now.astimezone(EASTERN)
    return [digest_type for digest_type, scheduled_time in BRIEF_SCHEDULES if now_eastern.time() >= scheduled_time]


def events_in_window(
    events: list[dict[str, Any]], window_start: datetime, window_end: datetime
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for event in events:
        occurred_at = event.get("occurred_at")
        if not occurred_at:
            continue
        occurred = parse_datetime(str(occurred_at)).astimezone(UTC)
        if window_start <= occurred < window_end:
            matches.append(event)
    return matches


def _summary(events: list[dict[str, Any]]) -> str:
    if not events:
        return (
            "No new developments met the publication threshold during this reporting window. "
            "The tracked-project watchlist remains unchanged."
        )
    first = events[0]
    if len(events) == 1:
        return f"One development met the publication threshold: {first['headline']}."
    return f"{len(events)} developments met the publication threshold, led by: {first['headline']}."


def build_archive_brief(events: list[dict[str, Any]], digest_type: str, now: datetime) -> dict[str, Any]:
    now_eastern = now.astimezone(EASTERN)
    window_start, window_end = digest_window(now, digest_type)
    window_events = events_in_window(events, window_start, window_end)
    selected = select_digest_events(window_events)
    subject, body_text, body_html = render_digest(
        window_events,
        digest_type,
        window_end.astimezone(EASTERN).isoformat(),
    )
    email_body = body_text.removeprefix(subject).lstrip()
    date_value = now_eastern.date().isoformat()
    stem = f"{date_value}-{digest_type}"
    return {
        "id": f"brief-{digest_type}-{date_value}",
        "digest_type": digest_type,
        "type": "Morning Brief" if digest_type == "morning" else "Evening Brief",
        "date": date_value,
        "subject": subject,
        "summary": _summary(selected),
        "event_ids": [str(event["id"]) for event in selected],
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "generated_at": now.astimezone(UTC).replace(microsecond=0).isoformat(),
        "body_text": f"Subject: {subject}\n\n{email_body}",
        "body_html": body_html,
        "text_url": f"briefs/{stem}.txt",
        "html_url": f"briefs/{stem}.html",
    }


def load_brief_archive(path: str | Path = "data/briefs.json") -> list[dict[str, Any]]:
    archive_path = Path(path)
    if not archive_path.exists():
        return []
    payload = json.loads(archive_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise TypeError(f"Brief archive must contain a JSON list: {archive_path}")
    return sorted(payload, key=lambda item: (str(item.get("date", "")), str(item.get("digest_type", ""))), reverse=True)


def save_brief_archive(briefs: list[dict[str, Any]], path: str | Path = "data/briefs.json") -> Path:
    archive_path = Path(path)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(
        briefs,
        key=lambda item: (str(item.get("date", "")), str(item.get("digest_type", ""))),
        reverse=True,
    )
    archive_path.write_text(json.dumps(ordered, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return archive_path


def write_brief_files(brief: dict[str, Any], output_dir: str | Path = "docs/briefs") -> tuple[Path, Path]:
    folder = Path(output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    stem = f"{brief['date']}-{brief['digest_type']}"
    text_path = folder / f"{stem}.txt"
    html_path = folder / f"{stem}.html"
    text_path.write_text(str(brief["body_text"]), encoding="utf-8")
    html_path.write_text(
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        f"<title>{html.escape(str(brief['subject']))}</title></head><body>{brief['body_html']}</body></html>",
        encoding="utf-8",
    )
    return text_path, html_path
