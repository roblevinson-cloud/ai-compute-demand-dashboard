from __future__ import annotations

import re
from typing import Any

from .models import MatchCandidate


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _values(record: dict[str, Any], key: str) -> set[str]:
    value = record.get(key)
    if isinstance(value, list):
        return {_norm(item) for item in value if _norm(item)}
    return {_norm(value)} if _norm(value) else set()


def _overlap(left: set[str], right: set[str]) -> bool:
    return bool(left and right and left.intersection(right))


def _numeric_similarity(a: Any, b: Any) -> float:
    try:
        x, y = float(a), float(b)
    except (TypeError, ValueError):
        return 0.0
    if x <= 0 or y <= 0:
        return 0.0
    return max(0.0, 1 - abs(x - y) / max(x, y))


def compare_project(signal: dict[str, Any], project: dict[str, Any]) -> MatchCandidate:
    """Return evidence, never a silent merge decision.

    Even an auto-link recommendation is persisted as a candidate for audit. Hard
    geography or named-tenant conflicts prevent automatic linking.
    """
    score = 0.0
    supporting: list[str] = []
    conflicts: list[str] = []
    features: dict[str, float] = {}

    weights = {
        "parcel": 30, "county": 18, "state": 5, "developer": 18,
        "tenant": 13, "utility": 8, "mw": 7, "acreage": 3, "alias": 27,
    }

    for key in ("parcel", "county", "state", "developer", "tenant", "utility", "alias"):
        matched = _overlap(_values(signal, key), _values(project, key))
        features[key] = float(weights[key] if matched else 0)
        if matched:
            score += weights[key]
            supporting.append(f"{key.replace('_', ' ').title()} matches")

    for key in ("mw", "acreage"):
        similarity = _numeric_similarity(signal.get(key), project.get(key))
        contribution = weights[key] * similarity
        features[key] = round(contribution, 2)
        if contribution >= weights[key] * 0.65:
            supporting.append(f"{key.upper()} is similar")
        score += contribution

    signal_county, project_county = _values(signal, "county"), _values(project, "county")
    hard_conflict = False
    if signal_county and project_county and not _overlap(signal_county, project_county):
        score -= 32
        hard_conflict = True
        conflicts.append("Different counties")
    signal_tenant, project_tenant = _values(signal, "tenant"), _values(project, "tenant")
    if signal_tenant and project_tenant and not _overlap(signal_tenant, project_tenant):
        score -= 18
        hard_conflict = True
        conflicts.append("Different named tenant/customer")
    signal_developer, project_developer = _values(signal, "developer"), _values(project, "developer")
    if signal_developer and project_developer and not _overlap(signal_developer, project_developer):
        score -= 8
        conflicts.append("Different named developer")

    final_score = round(max(0, min(100, score)))
    if final_score >= 88 and not hard_conflict:
        recommendation = "candidate_auto_link"
    elif final_score >= 45:
        recommendation = "human_review"
    else:
        recommendation = "likely_new_project"
    return MatchCandidate(
        candidate_project_id=str(project.get("id") or project.get("project_id") or "unknown"),
        score=final_score,
        recommendation=recommendation,
        supporting=supporting,
        conflicts=conflicts,
        feature_scores=features,
    )


def rank_candidates(signal: dict[str, Any], projects: list[dict[str, Any]]) -> list[MatchCandidate]:
    candidates = [compare_project(signal, project) for project in projects]
    return sorted(candidates, key=lambda item: item.score, reverse=True)
