from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

OBS_COLUMNS = [
    "observed_at_utc", "source", "metric", "dimension", "value", "unit",
    "quality", "is_estimate", "collected_at_utc", "provenance", "metadata_json",
]


@dataclass(frozen=True)
class Observation:
    observed_at_utc: str
    source: str
    metric: str
    dimension: str
    value: float
    unit: str
    quality: str = "observed"
    is_estimate: bool = False
    collected_at_utc: str = ""
    provenance: str = ""
    metadata_json: str = "{}"

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        if not row["collected_at_utc"]:
            row["collected_at_utc"] = utc_now()
        return row


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def json_text(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def ensure_parent(path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def read_observations(path: str | Path) -> pd.DataFrame:
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return pd.DataFrame(columns=OBS_COLUMNS)
    df = pd.read_csv(p)
    for col in OBS_COLUMNS:
        if col not in df.columns:
            df[col] = None
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["is_estimate"] = df["is_estimate"].astype(str).str.lower().isin(["true", "1", "yes"])
    return df[OBS_COLUMNS]


def append_observations(path: str | Path, observations: Iterable[Observation]) -> pd.DataFrame:
    p = ensure_parent(path)
    old = read_observations(p)
    rows = [o.to_dict() for o in observations]
    if not rows:
        return old
    new = pd.DataFrame(rows, columns=OBS_COLUMNS)
    combined = pd.concat([old, new], ignore_index=True)
    combined["value"] = pd.to_numeric(combined["value"], errors="coerce")
    combined = combined.dropna(subset=["observed_at_utc", "source", "metric", "value"])
    key = ["observed_at_utc", "source", "metric", "dimension"]
    combined = combined.sort_values(["collected_at_utc"]).drop_duplicates(key, keep="last")
    combined = combined.sort_values(["observed_at_utc", "source", "metric", "dimension"])
    combined.to_csv(p, index=False)
    return combined
