from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REQUIRED_SOURCE_FIELDS = {
    "key", "name", "source_type", "jurisdiction", "url", "method",
    "interval_minutes", "priority", "enabled",
}


def load_source_registry(path: str | Path = "config/sources.yml") -> list[dict[str, Any]]:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    sources = payload.get("sources") or []
    seen: set[str] = set()
    for index, source in enumerate(sources):
        missing = REQUIRED_SOURCE_FIELDS - source.keys()
        if missing:
            raise ValueError(f"Source #{index + 1} is missing: {', '.join(sorted(missing))}")
        if source["key"] in seen:
            raise ValueError(f"Duplicate source key: {source['key']}")
        seen.add(source["key"])
        if int(source["interval_minutes"]) < 5:
            raise ValueError(f"Source {source['key']} interval must be at least 5 minutes")
        source.setdefault("parser_config", {})
        source.setdefault("tags", [])
    return sources


def source_summary(sources: list[dict[str, Any]]) -> dict[str, Any]:
    by_type: dict[str, int] = {}
    by_jurisdiction: dict[str, int] = {}
    for source in sources:
        by_type[source["source_type"]] = by_type.get(source["source_type"], 0) + 1
        jurisdiction = source.get("jurisdiction") or "National"
        by_jurisdiction[jurisdiction] = by_jurisdiction.get(jurisdiction, 0) + 1
    return {
        "total": len(sources),
        "enabled": sum(bool(source.get("enabled")) for source in sources),
        "by_type": by_type,
        "by_jurisdiction": by_jurisdiction,
    }
