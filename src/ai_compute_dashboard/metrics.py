from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

import numpy as np
import pandas as pd


def _daily(df: pd.DataFrame, metric: str, source: str | None = None, agg: str = "sum") -> pd.Series:
    x = df[df["metric"].eq(metric)].copy()
    if source:
        x = x[x["source"].eq(source)]
    if x.empty:
        return pd.Series(dtype=float)
    x["date"] = pd.to_datetime(x["observed_at_utc"], utc=True, errors="coerce").dt.date.astype(str)
    if agg == "mean":
        return x.groupby("date")["value"].mean()
    if agg == "median":
        return x.groupby("date")["value"].median()
    return x.groupby("date")["value"].sum()


def _base_index(series: pd.Series, days: int = 28) -> pd.Series:
    s = series.dropna().sort_index()
    if s.empty:
        return s
    base = float(s.iloc[:min(days, len(s))].mean())
    return s / base * 100 if base else s * np.nan


def _pct_change(series: pd.Series, periods: int) -> pd.Series:
    return series.pct_change(periods=periods) * 100


def _weights(path: str | Path) -> pd.DataFrame:
    return pd.read_csv(path)


def derive_compute_observations(df: pd.DataFrame, weights_path: str | Path, output_share: float) -> pd.DataFrame:
    tok = df[(df["source"] == "openrouter") & (df["metric"] == "tokens_total")].copy()
    if tok.empty:
        return pd.DataFrame(columns=df.columns)
    w = _weights(weights_path)
    def match(model: str) -> pd.Series:
        for _, row in w.iterrows():
            if re.search(str(row["pattern"]), model):
                return row
        return w.iloc[-1]
    rows = []
    for _, row in tok.iterrows():
        wt = match(str(row["dimension"]))
        total = float(row["value"])
        inp, out = total * (1-output_share), total * output_share
        seconds = inp/1e6*float(wt["input_h100_seconds_per_million_tokens"]) + out/1e6*float(wt["output_h100_seconds_per_million_tokens"])
        seconds *= float(wt.get("reasoning_multiplier", 1.0))
        rows.append({
            "observed_at_utc": row["observed_at_utc"], "source": "derived",
            "metric": "h100_equivalent_hours", "dimension": row["dimension"],
            "value": seconds/3600, "unit": "H100-hour", "quality": "estimated",
            "is_estimate": True, "collected_at_utc": row["collected_at_utc"],
            "provenance": "OpenRouter tokens × config/model_weights.csv",
            "metadata_json": json.dumps({"weight_category": wt["category"], "confidence": wt["confidence"]}),
        })
    return pd.DataFrame(rows)


def _grid_residual(df: pd.DataFrame, minimum_days: int) -> pd.DataFrame:
    load = df[(df.metric == "grid_load") & (df.source == "eia")].copy()
    temp = df[(df.metric == "temperature") & (df.source == "open_meteo")].copy()
    if load.empty or temp.empty:
        return pd.DataFrame(columns=["date", "region", "grid_load_mw", "grid_residual_mw"])
    for x in (load, temp):
        x["ts"] = pd.to_datetime(x.observed_at_utc, utc=True, errors="coerce")
        x["date"] = x.ts.dt.floor("D")
    ld = load.groupby(["dimension", "date"]).value.mean().rename("load").reset_index()
    tp = temp.groupby(["dimension", "date"]).value.mean().rename("temp_c").reset_index()
    merged = ld.merge(tp, on=["dimension", "date"], how="inner")
    results = []
    for region, g in merged.groupby("dimension"):
        g = g.sort_values("date").copy()
        temp_f = g.temp_c * 9/5 + 32
        g["cdd"] = np.maximum(temp_f - 65, 0)
        g["hdd"] = np.maximum(65 - temp_f, 0)
        g["trend"] = np.arange(len(g))
        if len(g) >= minimum_days:
            dow = pd.get_dummies(g.date.dt.dayofweek, prefix="dow", drop_first=True, dtype=float)
            X = pd.concat([pd.Series(1.0, index=g.index, name="const"), g[["cdd", "hdd", "trend"]], dow.set_index(g.index)], axis=1)
            beta, *_ = np.linalg.lstsq(X.values, g.load.values, rcond=None)
            g["residual"] = g.load - X.values @ beta
        else:
            g["residual"] = np.nan
        for _, r in g.iterrows():
            results.append({"date": r.date.strftime("%Y-%m-%d"), "region": region, "grid_load_mw": r.load, "grid_residual_mw": r.residual})
    return pd.DataFrame(results)


def build_dashboard_data(df: pd.DataFrame, config: dict[str, Any], weights_path: str | Path) -> dict[str, Any]:
    dashboard_cfg = config["dashboard"]
    derived = derive_compute_observations(df, weights_path, float(dashboard_cfg["assumed_output_token_share"]))
    full = pd.concat([df, derived], ignore_index=True)

    tokens = _daily(full, "tokens_total", "openrouter")
    compute = _daily(full, "h100_equivalent_hours", "derived")
    gpu_price = _daily(full, "gpu_price_median", None, "median")
    gpu_units = _daily(full, "gpu_units_available", None, "sum")
    latency = _daily(full, "ttft", "artificial_analysis", "median")
    capacity = _daily(full, "operational_h100_equivalents", "epoch", "sum")
    dc_power = _daily(full, "operational_ai_datacenter_power", "epoch", "sum")
    grid = _daily(full, "grid_load", "eia", "mean")
    output_speed = _daily(full, "output_speed", "artificial_analysis", "median")
    api_price = _daily(full, "output_price", "artificial_analysis", "median")

    dates = sorted(set().union(*[set(s.index) for s in [tokens, compute, gpu_price, gpu_units, latency, capacity, dc_power, grid, output_speed, api_price] if not s.empty]))
    frame = pd.DataFrame(index=dates)
    frame.index.name = "date"
    for name, s in {
        "tokens": tokens, "h100_hours": compute, "gpu_price": gpu_price,
        "gpu_units": gpu_units, "latency": latency, "capacity_h100_eq": capacity,
        "datacenter_power_mw": dc_power, "grid_load_mw": grid,
        "output_speed": output_speed, "api_output_price": api_price,
    }.items():
        frame[name] = s
    frame = frame.sort_index().ffill(limit=14)
    base_days = int(dashboard_cfg.get("base_period_days", 28))
    frame["workload_index"] = _base_index(frame.tokens, base_days)
    frame["physical_compute_index"] = _base_index(frame.h100_hours, base_days)
    frame["capacity_index"] = _base_index(frame.capacity_h100_eq, base_days)
    frame["efficiency_index"] = _base_index(frame.tokens / frame.h100_hours.replace(0, np.nan), base_days)
    frame["api_speed_index"] = _base_index(frame.output_speed, base_days)
    frame["api_latency_index"] = _base_index(frame.latency, base_days)
    frame["api_price_index"] = _base_index(frame.api_output_price, base_days)

    # Tightness: price and latency up; available units down. Normalize each to base-period ratios.
    price_i = _base_index(frame.gpu_price, base_days)
    latency_i = _base_index(frame.latency, base_days)
    availability_i = 10000 / _base_index(frame.gpu_units, base_days).replace(0, np.nan)
    tight_parts = pd.concat([price_i.rename("price"), latency_i.rename("latency"), availability_i.rename("availability")], axis=1)
    frame["tightness_index"] = tight_parts.mean(axis=1, skipna=True)
    frame["token_growth_28d"] = _pct_change(frame.tokens, 28)
    frame["compute_growth_28d"] = _pct_change(frame.h100_hours, 28)
    frame["token_growth_yoy"] = _pct_change(frame.tokens, 365)
    frame["compute_growth_yoy"] = _pct_change(frame.h100_hours, 365)

    grid_resid = _grid_residual(full, int(dashboard_cfg.get("minimum_days_for_grid_model", 60)))

    # Model mix, latest day.
    model_mix = []
    latest_token_date = None
    tok_rows = full[(full.source == "openrouter") & (full.metric == "tokens_total")].copy()
    if not tok_rows.empty:
        tok_rows["date"] = pd.to_datetime(tok_rows.observed_at_utc, utc=True).dt.date.astype(str)
        latest_token_date = tok_rows.date.max()
        m = tok_rows[tok_rows.date == latest_token_date].sort_values("value", ascending=False)
        total = m.value.sum()
        model_mix = [{"model": r.dimension, "tokens": r.value, "share": r.value/total if total else None} for _, r in m.head(12).iterrows()]

    training_rows = full[full.metric.eq("training_compute")].copy()
    training_events = []
    if not training_rows.empty:
        training_rows["date"] = pd.to_datetime(training_rows.observed_at_utc, utc=True, errors="coerce").dt.date.astype(str)
        training_events = [{"date": r.date, "model": r.dimension, "flop": float(r.value), "source": r.source} for _, r in training_rows.sort_values("date").iterrows()]

    # Manual global anchors.
    anchors = []
    manual = Path(config.get("manual", {}).get("global_token_estimates", ""))
    if manual.exists() and manual.stat().st_size:
        try:
            a = pd.read_csv(manual).replace({np.nan: None})
            anchors = a.to_dict("records")
        except Exception:
            pass

    # Source health based on latest collection and latest observation.
    health = []
    now = pd.Timestamp.now(tz="UTC")
    for source, g in full.groupby("source"):
        obs = pd.to_datetime(g.observed_at_utc, utc=True, errors="coerce").max()
        collected = pd.to_datetime(g.collected_at_utc, utc=True, errors="coerce").max()
        age = (now - collected).total_seconds()/3600 if pd.notna(collected) else None
        status = "live" if age is not None and age <= float(dashboard_cfg.get("stale_after_hours", 36)) else "stale"
        if source == "demo": status = "demo"
        health.append({"source": source, "latest_observation": None if pd.isna(obs) else obs.isoformat(), "last_collection": None if pd.isna(collected) else collected.isoformat(), "age_hours": age, "status": status, "rows": len(g)})

    latest = frame.dropna(how="all").tail(1)
    kpis = {}
    if not latest.empty:
        row = latest.iloc[0]
        for col in ["workload_index", "physical_compute_index", "tightness_index", "capacity_index", "efficiency_index", "tokens", "h100_hours", "token_growth_28d", "compute_growth_28d"]:
            value = row.get(col)
            kpis[col] = None if pd.isna(value) else float(value)

    frame_out = frame.reset_index().replace({np.nan: None}).to_dict("records")
    return {
        "meta": {
            "title": dashboard_cfg["title"], "subtitle": dashboard_cfg["subtitle"],
            "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "demo_mode": bool((df.source == "demo").any()),
            "methodology_version": "0.1.0",
            "latest_openrouter_date": latest_token_date,
        },
        "kpis": kpis, "series": frame_out, "model_mix": model_mix,
        "grid_residuals": grid_resid.replace({np.nan: None}).to_dict("records"),
        "training_events": training_events,
        "global_token_anchors": anchors, "source_health": health,
    }
