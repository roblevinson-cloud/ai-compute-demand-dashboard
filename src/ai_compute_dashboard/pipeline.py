from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
import shutil
import sys

import pandas as pd

from .collectors import COLLECTORS
from .common import append_observations, read_observations, utc_now
from .config import load_config
from .demo import seed_demo
from .metrics import build_dashboard_data
from .site import build_site

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOG = logging.getLogger(__name__)

DEMO_SOURCE_BY_METRIC = {
    "tokens_total": "openrouter",
    "h100_equivalent_hours": "derived",
    "gpu_price_median": "vast",
    "gpu_units_available": "vast",
    "ttft": "artificial_analysis",
    "output_speed": "artificial_analysis",
    "operational_h100_equivalents": "epoch",
    "operational_ai_datacenter_power": "epoch",
    "grid_load": "eia",
    "temperature": "open_meteo",
    "training_compute": "epoch",
}

COLLECTOR_SOURCE = {
    "openrouter_rankings": "openrouter",
    "openrouter_models": "openrouter_catalog",
    "artificial_analysis": "artificial_analysis",
    "vast_offers": "vast",
    "vast_market_metrics": "vast_market",
    "eia_grid": "eia",
    "weather": "open_meteo",
    "epoch": "epoch",
    "mlperf": "mlperf",
    "sec_companyfacts": "sec_companyfacts",
    "company_disclosures": "company_disclosures",
}


def _prepare_render_observations(df: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
    """Exclude demo rows from live builds and remap demo-only rows without copying."""
    has_demo = bool(df.source.eq("demo").any())
    has_live = bool(df.source.ne("demo").any())
    if has_live:
        return df[df.source.ne("demo")].copy(), False

    render = df.copy()
    demo_rows = render.source.eq("demo")
    mapped_sources = render.loc[demo_rows, "metric"].map(DEMO_SOURCE_BY_METRIC)
    render.loc[demo_rows, "source"] = mapped_sources.fillna("demo")
    render.loc[demo_rows, "quality"] = "synthetic_demo"
    render.loc[demo_rows, "is_estimate"] = True
    return render, has_demo


def _merge_collector_status(data: dict, statuses: list[dict]) -> None:
    """Overlay latest collector failures onto observation-based source health."""
    health = data.setdefault("source_health", [])
    by_source = {item.get("source"): item for item in health}
    for item in statuses:
        if item.get("status") == "ok":
            continue
        collector = item.get("collector")
        source = COLLECTOR_SOURCE.get(collector, collector)
        current = by_source.get(source)
        if current is None:
            current = {
                "source": source,
                "latest_observation": None,
                "age_hours": None,
                "rows": 0,
            }
            health.append(current)
            by_source[source] = current
        current.update({
            "last_collection": item.get("at"),
            "status": "failed",
            "detail": item.get("detail"),
        })


def collect(config: dict, observations_path: str) -> int:
    raw_dir = Path("data/raw") / utc_now()[:10]
    raw_dir.mkdir(parents=True, exist_ok=True)
    all_obs = []
    statuses = []
    for name, collector in COLLECTORS.items():
        source_cfg = config.get("sources", {}).get(name, {})
        if not source_cfg.get("enabled", False):
            continue
        LOG.info("Collecting %s", name)
        try:
            obs = collector(source_cfg, raw_dir)
            all_obs.extend(obs)
            statuses.append({"collector": name, "status": "ok", "rows": len(obs), "at": utc_now()})
            LOG.info("%s: %d observations", name, len(obs))
        except Exception as exc:
            statuses.append({"collector": name, "status": "error", "rows": 0, "at": utc_now(), "detail": str(exc)})
            LOG.warning("%s failed: %s", name, exc)
    append_observations(observations_path, all_obs)
    Path("data/collector_status.json").write_text(json.dumps(statuses, indent=2), encoding="utf-8")
    return 0 if all_obs else 2


def build(config: dict, observations_path: str) -> None:
    df = read_observations(observations_path)
    if df.empty:
        raise RuntimeError("No observations exist. Run the demo or configure at least one collector.")
    render, demo_mode = _prepare_render_observations(df)
    data = build_dashboard_data(render, config, "config/model_weights.csv")
    data["meta"]["demo_mode"] = demo_mode
    # Surface collectors that failed before producing observations.
    status_path = Path("data/collector_status.json")
    if status_path.exists():
        try:
            statuses = json.loads(status_path.read_text(encoding="utf-8"))
            _merge_collector_status(data, statuses)
        except Exception as exc:
            LOG.warning("Could not merge collector status: %s", exc)
    build_site(data, "docs/index.html")
    LOG.info("Built docs/index.html with %d time-series rows", len(data["series"]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["collect", "build", "run", "demo", "clear-demo"])
    args = parser.parse_args(argv)
    config = load_config()
    observations_path = os.getenv("OBSERVATIONS_PATH", "data/observations.csv")
    if args.command == "demo":
        Path(observations_path).unlink(missing_ok=True)
        seed_demo(observations_path)
        build(config, observations_path)
        return 0
    if args.command == "clear-demo":
        df = read_observations(observations_path)
        df[df.source != "demo"].to_csv(observations_path, index=False)
        return 0
    rc = 0
    if args.command in ("collect", "run"):
        rc = collect(config, observations_path)
    if args.command in ("build", "run"):
        build(config, observations_path)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
