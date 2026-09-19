from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class EventType(StrEnum):
    NEW_PROJECT = "new_project_discovery"
    LAND = "land_acquisition_site_control"
    ZONING = "zoning"
    PERMIT = "permit"
    UTILITY_SERVICE = "utility_service"
    INTERCONNECTION = "interconnection"
    TRANSMISSION = "transmission_substation"
    GENERATION = "generation_storage"
    PUC = "puc_proceeding"
    INCENTIVE = "incentive"
    WATER = "water_sewer"
    ENVIRONMENTAL = "environmental_permit"
    FINANCING = "financing"
    TENANT = "tenant_customer_identification"
    CONTRACTOR = "contractor"
    CONSTRUCTION_START = "construction_start"
    TOPPING_OUT = "topping_out"
    EQUIPMENT = "equipment_delivery"
    ENERGIZATION = "energization"
    EXPANSION = "expansion"
    SCHEDULE = "schedule_change"
    COST = "cost_change"
    OPPOSITION = "opposition_litigation"
    REGULATORY_DECISION = "regulatory_decision"
    DELAY = "delay"
    CANCELLATION = "cancellation"
    OPERATIONS = "commencement_of_operations"


EVENT_TYPES = tuple(item.value for item in EventType)


@dataclass(slots=True)
class EvidenceSpan:
    quote: str
    page: int | None = None
    start_char: int | None = None
    end_char: int | None = None


@dataclass(slots=True)
class FactCandidate:
    field: str
    value: Any
    unit: str | None = None
    as_of: str | None = None
    confidence: int = 50
    evidence: list[EvidenceSpan] = field(default_factory=list)


@dataclass(slots=True)
class ExtractionResult:
    schema_version: str
    document_id: str
    headline: str
    published_at: str | None
    event_type: str
    summary: str
    project_name: str | None = None
    aliases: list[str] = field(default_factory=list)
    companies: list[dict[str, str]] = field(default_factory=list)
    location: dict[str, Any] = field(default_factory=dict)
    facts: list[FactCandidate] = field(default_factory=list)
    docket_numbers: list[str] = field(default_factory=list)
    permit_numbers: list[str] = field(default_factory=list)
    discovery_triggers: list[str] = field(default_factory=list)
    extraction_confidence: int = 50
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Score:
    value: int
    factors: dict[str, float]
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class MatchCandidate:
    candidate_project_id: str
    score: int
    recommendation: str
    supporting: list[str]
    conflicts: list[str]
    feature_scores: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
