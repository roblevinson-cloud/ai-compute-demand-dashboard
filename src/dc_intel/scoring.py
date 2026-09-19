from __future__ import annotations

import math
from typing import Any

from .models import Score

EVENT_BASE = {
    "new_project_discovery": 18,
    "land_acquisition_site_control": 14,
    "zoning": 16,
    "permit": 17,
    "utility_service": 21,
    "interconnection": 22,
    "transmission_substation": 23,
    "generation_storage": 27,
    "puc_proceeding": 21,
    "incentive": 15,
    "water_sewer": 14,
    "environmental_permit": 18,
    "financing": 16,
    "tenant_customer_identification": 19,
    "contractor": 10,
    "construction_start": 20,
    "topping_out": 14,
    "equipment_delivery": 13,
    "energization": 24,
    "expansion": 19,
    "schedule_change": 20,
    "cost_change": 17,
    "opposition_litigation": 21,
    "regulatory_decision": 23,
    "delay": 23,
    "cancellation": 25,
    "commencement_of_operations": 24,
}


SOURCE_RELIABILITY = {
    "primary_regulatory": 45,
    "primary_government": 43,
    "company": 36,
    "utility": 40,
    "local_media": 32,
    "trade_media": 30,
    "national_media": 28,
    "property_record": 38,
    "other": 20,
}


def _clamp(value: float) -> int:
    return round(max(0, min(100, value)))


def score_materiality(event: dict[str, Any]) -> Score:
    """Transparent additive score; factor values sum to the reported score."""
    event_type = str(event.get("event_type") or "")
    mw = float(event.get("mw") or event.get("utility_load_mw") or 0)
    capex_b = float(event.get("capex_usd_b") or 0)
    factors = {
        "event_significance": float(EVENT_BASE.get(event_type, 10)),
        "scale_mw": min(24.0, 5.5 * math.log10(1 + max(mw, 0))),
        "capital_scale": min(14.0, 5.0 * math.log10(1 + max(capex_b, 0))),
        "stage_signal": float(max(0, min(12, event.get("stage_weight", 0)))),
        "regulatory_effect": float(max(0, min(10, event.get("regulatory_weight", 0)))),
        "named_major_party": 6.0 if event.get("major_party") else 0.0,
        "schedule_or_risk": float(max(0, min(9, event.get("risk_weight", 0)))),
    }
    value = _clamp(sum(factors.values()))
    strongest = sorted(factors, key=factors.get, reverse=True)[:3]
    return Score(value, factors, "Driven by " + ", ".join(name.replace("_", " ") for name in strongest) + ".")


def score_novelty(event: dict[str, Any]) -> Score:
    duplicate = float(event.get("duplicate_similarity") or 0)
    new_fact_count = int(event.get("new_fact_count") or 0)
    changed_fact_count = int(event.get("changed_fact_count") or 0)
    factors = {
        "new_facts": min(42.0, new_fact_count * 10.5),
        "changed_facts": min(28.0, changed_fact_count * 14.0),
        "first_primary_record": 20.0 if event.get("first_primary_record") else 0.0,
        "original_reporting": 10.0 if event.get("original_reporting") else 0.0,
        "duplication_penalty": -50.0 * max(0, min(1, duplicate)),
    }
    value = _clamp(sum(factors.values()))
    return Score(value, factors, "Measures changed facts and first-source value after duplicate-content penalties.")


def score_confidence(event: dict[str, Any]) -> Score:
    source_type = str(event.get("source_type") or "other")
    extraction = float(event.get("extraction_confidence") or 50)
    match = float(event.get("match_confidence") or 0)
    corroboration = min(10.0, float(event.get("corroborating_sources") or 0) * 3.5)
    factors = {
        "source_reliability": float(SOURCE_RELIABILITY.get(source_type, 20)),
        "extraction": 0.25 * max(0, min(100, extraction)),
        "entity_match": 0.20 * max(0, min(100, match)),
        "corroboration": corroboration,
    }
    value = _clamp(sum(factors.values()))
    return Score(value, factors, "Separates source reliability, extraction certainty, entity match, and corroboration.")
