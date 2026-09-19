from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path
from typing import Any

SECTIONS = {
    "new_project_discovery": "New Projects / Early Signals",
    "utility_service": "Power & Regulatory",
    "interconnection": "Power & Regulatory",
    "transmission_substation": "Power & Regulatory",
    "generation_storage": "Power & Regulatory",
    "puc_proceeding": "Power & Regulatory",
    "zoning": "Planning / Permitting / Incentives",
    "permit": "Planning / Permitting / Incentives",
    "environmental_permit": "Planning / Permitting / Incentives",
    "incentive": "Planning / Permitting / Incentives",
    "water_sewer": "Planning / Permitting / Incentives",
    "construction_start": "Construction / Energization / Delays",
    "topping_out": "Construction / Energization / Delays",
    "equipment_delivery": "Construction / Energization / Delays",
    "energization": "Construction / Energization / Delays",
    "delay": "Construction / Energization / Delays",
    "cancellation": "Construction / Energization / Delays",
}


def _section(event: dict[str, Any]) -> str:
    return SECTIONS.get(str(event.get("event_type")), "Watchlist Changes")


def select_digest_events(events: list[dict[str, Any]], minimum_materiality: int = 45) -> list[dict[str, Any]]:
    candidates = [event for event in events if int(event.get("materiality", 0)) >= minimum_materiality and int(event.get("novelty", 0)) >= 35]
    return sorted(candidates, key=lambda event: (int(event.get("materiality", 0)), str(event.get("occurred_at", ""))), reverse=True)


def render_digest(events: list[dict[str, Any]], digest_type: str, as_of: str) -> tuple[str, str, str]:
    selected = select_digest_events(events)
    label = "Morning Brief" if digest_type.lower().startswith("morning") else "Evening Brief"
    date_label = datetime.fromisoformat(as_of).strftime("%B %d, %Y")
    subject = f"{label} — Data Center Development Intelligence — {date_label}"
    grouped: dict[str, list[dict[str, Any]]] = {}
    for event in selected:
        grouped.setdefault(_section(event), []).append(event)

    text_lines = [subject, "", "TOP DEVELOPMENTS"]
    html_parts = [f"<h1>{html.escape(subject)}</h1>", "<h2>Top Developments</h2>"]
    if not selected:
        no_change = (
            "No new developments met the publication threshold during this reporting window. "
            "The tracked-project watchlist remains unchanged."
        )
        text_lines.extend(["", no_change])
        html_parts.append(f"<p>{html.escape(no_change)}</p>")
    for event in selected[:3]:
        text_lines.extend([f"• {event['headline']} [{event['materiality']}/100]", f"  {event['what_new']}", f"  Why it matters: {event['why_matters']}", f"  Evidence: {event['source_url']}", ""])
        html_parts.append(_event_html(event))
    for section in ("New Projects / Early Signals", "Power & Regulatory", "Planning / Permitting / Incentives", "Construction / Energization / Delays", "Watchlist Changes"):
        section_events = grouped.get(section, [])
        if not section_events:
            continue
        text_lines.extend([section.upper(), ""])
        html_parts.append(f"<h2>{html.escape(section)}</h2>")
        for event in section_events:
            text_lines.extend([f"• {event['headline']}", f"  New: {event['what_new']}", f"  Implication: {event['implication']}", f"  Confidence: {event['confidence']}/100", f"  {event['source_url']}", ""])
            html_parts.append(_event_html(event))
    text_lines.extend(["Method note: scores are transparent prioritization aids, not facts. Source links are the audit record."])
    html_parts.append("<p><small>Scores are transparent prioritization aids, not facts. Source links are the audit record.</small></p>")
    return subject, "\n".join(text_lines), "\n".join(html_parts)


def _event_html(event: dict[str, Any]) -> str:
    return (
        "<article style='border:1px solid #dce2e8;border-radius:12px;padding:16px;margin:12px 0'>"
        f"<h3>{html.escape(event['headline'])}</h3>"
        f"<p><strong>What changed:</strong> {html.escape(event['what_new'])}</p>"
        f"<p><strong>Why it matters:</strong> {html.escape(event['why_matters'])}</p>"
        f"<p><strong>Implication:</strong> {html.escape(event['implication'])}</p>"
        f"<p>Materiality {event['materiality']} · Novelty {event['novelty']} · Confidence {event['confidence']}</p>"
        f"<p><a href='{html.escape(event['source_url'], quote=True)}'>Underlying evidence — {html.escape(event['source_name'])}</a></p>"
        "</article>"
    )


def write_digest(events: list[dict[str, Any]], digest_type: str, as_of: str, output_dir: str | Path = "data/digests") -> tuple[Path, Path]:
    subject, text_body, html_body = render_digest(events, digest_type, as_of)
    date_part = as_of[:10]
    stem = f"{date_part}-{digest_type.lower().replace(' ', '-')}"
    folder = Path(output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    text_path, html_path = folder / f"{stem}.txt", folder / f"{stem}.html"
    text_path.write_text(f"Subject: {subject}\n\n{text_body}", encoding="utf-8")
    html_path.write_text(f"<!doctype html><html><body>{html_body}</body></html>", encoding="utf-8")
    return text_path, html_path
