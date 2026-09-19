from __future__ import annotations

import hashlib
import re
from typing import Any

from .models import EVENT_TYPES, EvidenceSpan, ExtractionResult, FactCandidate

EVENT_PATTERNS = {
    "cancellation": (r"\bcancell?ed\b", r"\babandon(?:ed)?\b", r"\bwithdrawn\b"),
    "delay": (r"\bdelay(?:ed)?\b", r"\bpostpone(?:d)?\b", r"\bstay(?:ed)?\b"),
    "commencement_of_operations": (r"\boperational\b", r"\bcommenced operations\b"),
    "energization": (r"\benergiz(?:e|ed|ation)\b", r"\bpowered on\b"),
    "construction_start": (r"\bbroke ground\b", r"\bconstruction (?:has )?(?:begun|started|underway)\b"),
    "transmission_substation": (r"\bsubstation\b", r"\btransmission line\b"),
    "interconnection": (r"\binterconnection\b",),
    "utility_service": (r"\butility service\b", r"\blarge[- ]load\b", r"\btariff\b"),
    "puc_proceeding": (r"\bpublic regulation commission\b", r"\bpublic utility commission\b", r"\bdocket\b"),
    "environmental_permit": (r"\bair quality permit\b", r"\benvironmental permit\b"),
    "water_sewer": (r"\bwater\b", r"\bwastewater\b", r"\bsewer\b"),
    "incentive": (r"\bindustrial revenue bond", r"\btax abatement\b", r"\bLEDA\b"),
    "zoning": (r"\brezon(?:e|ing)\b", r"\bzoning\b", r"\bconditional use\b"),
    "permit": (r"\bbuilding permit\b", r"\bpermit application\b"),
    "generation_storage": (r"\bmicrogrid\b", r"\bfuel cell\b", r"\bbattery storage\b", r"\bgeneration\b"),
    "new_project_discovery": (r"\bexplor(?:e|ing) a (?:new )?data center\b", r"\bnew data center project\b"),
}


def _first_number(pattern: str, text: str) -> tuple[float, str] | None:
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None
    value = float(match.group(1).replace(",", ""))
    return value, match.group(0)


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]


def deterministic_extract(
    *, document_id: str, title: str, text: str, published_at: str | None = None
) -> ExtractionResult:
    """Low-cost fallback extractor using the same schema as the LLM adapter.

    It intentionally leaves uncertain entity fields empty instead of inventing them.
    """
    combined = f"{title}\n{text}"
    event_type = "new_project_discovery"
    for candidate, patterns in EVENT_PATTERNS.items():
        if any(re.search(pattern, combined, re.IGNORECASE) for pattern in patterns):
            event_type = candidate
            break

    facts: list[FactCandidate] = []
    fact_patterns = [
        ("utility_load_mw", r"([\d,.]+)\s*(?:MW|megawatts?)\b", "MW", 76),
        ("generation_capacity_mw", r"([\d,.]+)\s*(?:GW|gigawatts?)\b", "GW", 72),
        ("capex_usd_b", r"\$\s*([\d,.]+)\s*billion\b", "USD billion", 80),
        ("acreage", r"([\d,.]+)\s*acres?\b", "acres", 78),
        ("square_feet", r"([\d,.]+)\s*(?:square feet|sq\.?\s*ft\.?)\b", "square feet", 76),
    ]
    for field, pattern, unit, confidence in fact_patterns:
        parsed = _first_number(pattern, combined)
        if not parsed:
            continue
        value, quote = parsed
        if unit == "GW":
            value *= 1000
            unit = "MW"
        facts.append(FactCandidate(field, value, unit, published_at, confidence, [EvidenceSpan(quote)]))

    docket_numbers = sorted(set(re.findall(r"\b(?:AQB\s*)?\d{2}-\d{2,5}(?:\([A-Z]\))?(?:-[A-Z]{2})?\b", combined)))
    permit_numbers = sorted(set(re.findall(r"\b(?:permit(?: application)?(?: no\.?| #)?\s*)(\d{4,6}[A-Z0-9-]*)", combined, re.IGNORECASE)))
    location: dict[str, Any] = {}
    nm_counties = ["Doña Ana", "Dona Ana", "Lea", "Valencia", "Bernalillo", "Sandoval", "Luna", "Otero"]
    for county in nm_counties:
        if re.search(rf"\b{re.escape(county)} County\b", combined, re.IGNORECASE):
            location = {"county": "Doña Ana" if county == "Dona Ana" else county, "state": "NM"}
            break

    project_match = re.search(r"\b(Project\s+[A-Z][A-Za-z0-9-]+)\b", combined)
    project_name = project_match.group(1) if project_match else None
    summary = next((sentence for sentence in _sentences(text) if len(sentence) >= 40), title)
    triggers = []
    if event_type == "new_project_discovery" or ("data center" in combined.lower() and not project_name):
        triggers.append("unnamed_or_new_project_signal")
    confidence = 68 if facts or location else 48
    result = ExtractionResult(
        schema_version="1.0",
        document_id=document_id,
        headline=title.strip(),
        published_at=published_at,
        event_type=event_type if event_type in EVENT_TYPES else "new_project_discovery",
        summary=summary[:800],
        project_name=project_name,
        location=location,
        facts=facts,
        docket_numbers=docket_numbers,
        permit_numbers=permit_numbers,
        discovery_triggers=triggers,
        extraction_confidence=confidence,
        warnings=["Deterministic fallback extraction; route ambiguous records to a stronger model."],
    )
    validate_extraction(result.to_dict())
    return result


def validate_extraction(payload: dict[str, Any]) -> None:
    required = {"schema_version", "document_id", "headline", "event_type", "summary", "facts"}
    missing = sorted(required - payload.keys())
    if missing:
        raise ValueError(f"Extraction is missing required fields: {', '.join(missing)}")
    if payload["event_type"] not in EVENT_TYPES:
        raise ValueError(f"Unknown event type: {payload['event_type']}")
    confidence = int(payload.get("extraction_confidence", 0))
    if not 0 <= confidence <= 100:
        raise ValueError("extraction_confidence must be between 0 and 100")


def content_fingerprint(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
