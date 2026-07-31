from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


def load_config(path: str | None = None) -> dict[str, Any]:
    p = Path(path or os.getenv("DASHBOARD_CONFIG", "config/dashboard.yml"))
    with p.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def env(name: str) -> str | None:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else None
