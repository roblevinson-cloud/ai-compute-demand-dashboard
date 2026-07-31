from datetime import datetime, timedelta, timezone

import pandas as pd

from ai_compute_dashboard.metrics import build_dashboard_data
from ai_compute_dashboard.pipeline import (
    _merge_collector_status,
    _prepare_render_observations,
)


def _row(
    source: str,
    metric: str,
    dimension: str,
    value: float,
    *,
    quality: str = "observed",
    collected_at: str = "2026-07-24T20:00:00Z",
) -> dict:
    return {
        "observed_at_utc": "2026-07-24",
        "source": source,
        "metric": metric,
        "dimension": dimension,
        "value": value,
        "unit": "test-unit",
        "quality": quality,
        "is_estimate": quality == "synthetic_demo",
        "collected_at_utc": collected_at,
        "provenance": "synthetic demo" if quality == "synthetic_demo" else "test",
        "metadata_json": "{}",
    }


def _config(manual_path: str) -> dict:
    return {
        "dashboard": {
            "title": "Test dashboard",
            "subtitle": "Test data",
            "base_period_days": 28,
            "stale_after_hours": 36,
            "assumed_output_token_share": 0.25,
            "minimum_days_for_grid_model": 60,
        },
        "manual": {"global_token_estimates": manual_path},
    }


def test_demo_compute_is_not_combined_with_token_derived_estimate(tmp_path):
    observations = pd.DataFrame([
        _row("demo", "tokens_total", "frontier-general", 1_000_000),
        _row("demo", "h100_equivalent_hours", "all", 123.0),
    ])

    render, demo_mode = _prepare_render_observations(observations)
    data = build_dashboard_data(
        render,
        _config(str(tmp_path / "missing.csv")),
        "config/model_weights.csv",
    )

    assert demo_mode is True
    assert len(render) == len(observations)
    assert data["series"][0]["h100_hours"] == 123.0
    assert {item["status"] for item in data["source_health"]} == {"demo"}


def test_training_event_is_not_displayed_twice_when_mirrored(tmp_path):
    event = _row("demo", "training_compute", "frontier-run-1", 1.8e25)
    mirrored = {**event, "source": "epoch"}

    data = build_dashboard_data(
        pd.DataFrame([event, mirrored]),
        _config(str(tmp_path / "missing.csv")),
        "config/model_weights.csv",
    )

    assert data["training_events"] == [
        {
            "date": "2026-07-24",
            "model": "frontier-run-1",
            "flop": 1.8e25,
            "source": "epoch",
        }
    ]


def test_source_health_distinguishes_demo_live_and_stale(tmp_path):
    now = datetime.now(timezone.utc)
    live_at = now.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    stale_at = (now - timedelta(hours=72)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    observations = pd.DataFrame([
        _row("openrouter", "tokens_total", "demo-model", 1.0, quality="synthetic_demo", collected_at=live_at),
        _row("live-source", "unused", "all", 1.0, collected_at=live_at),
        _row("stale-source", "unused", "all", 1.0, collected_at=stale_at),
    ])

    data = build_dashboard_data(
        observations,
        _config(str(tmp_path / "missing.csv")),
        "config/model_weights.csv",
    )
    statuses = {item["source"]: item["status"] for item in data["source_health"]}

    assert statuses == {
        "live-source": "live",
        "openrouter": "demo",
        "stale-source": "stale",
    }


def test_failed_collection_is_labeled_failed():
    data = {
        "source_health": [
            {"source": "openrouter", "status": "stale", "rows": 10}
        ]
    }
    statuses = [{
        "collector": "openrouter_rankings",
        "status": "error",
        "rows": 0,
        "at": "2026-07-31T19:22:51Z",
        "detail": "API key is not configured",
    }]

    _merge_collector_status(data, statuses)

    assert data["source_health"] == [{
        "source": "openrouter",
        "status": "failed",
        "rows": 10,
        "last_collection": "2026-07-31T19:22:51Z",
        "detail": "API key is not configured",
    }]
