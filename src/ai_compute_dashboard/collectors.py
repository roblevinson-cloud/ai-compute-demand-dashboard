from __future__ import annotations

import io
import json
import math
import os
import re
import subprocess
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests

from .common import Observation, json_text, utc_now
from .config import env

TIMEOUT = 45


def _date(value: Any) -> str:
    return pd.to_datetime(value, utc=True, errors="coerce").strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_float(value: Any) -> float | None:
    try:
        x = float(value)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _find_rows(payload: Any) -> list[dict[str, Any]]:
    """Find the most plausible list-of-dicts in an SDK/API response."""
    candidates: list[list[dict[str, Any]]] = []
    def walk(x: Any) -> None:
        if isinstance(x, list) and x and all(isinstance(i, dict) for i in x):
            candidates.append(x)
        if isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(payload)
    if not candidates:
        return []
    return max(candidates, key=len)


def collect_openrouter_rankings(cfg: dict[str, Any], raw_dir: Path) -> list[Observation]:
    key = env("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not configured")
    script = cfg["node_script"]
    proc = subprocess.run(
        ["node", script], check=False, capture_output=True, text=True,
        env={**os.environ, "OPENROUTER_API_KEY": key}, timeout=TIMEOUT,
    )
    if proc.returncode:
        detail = (proc.stderr or proc.stdout or f"exit code {proc.returncode}").strip()
        detail = detail.replace(key, "[REDACTED]")[-2000:]
        raise RuntimeError(f"OpenRouter rankings script failed: {detail}")
    payload = json.loads(proc.stdout)
    (raw_dir / "openrouter_rankings.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    rows = _find_rows(payload)
    out: list[Observation] = []
    for row in rows:
        date = row.get("date") or row.get("day") or row.get("period")
        model = row.get("model_permaslug") or row.get("modelPermaslug") or row.get("model") or row.get("slug")
        tokens = row.get("tokens") or row.get("total_tokens") or row.get("totalTokens") or row.get("token_count")
        if tokens is None:
            p = _safe_float(row.get("prompt_tokens") or row.get("promptTokens")) or 0
            c = _safe_float(row.get("completion_tokens") or row.get("completionTokens")) or 0
            tokens = p + c
        value = _safe_float(tokens)
        if date and model and value is not None:
            out.append(Observation(
                observed_at_utc=str(date)[:10], source="openrouter", metric="tokens_total",
                dimension=str(model), value=value, unit="tokens", provenance="openrouter.ai/rankings",
                metadata_json=json_text({"raw": row}),
            ))
    if not out:
        raise RuntimeError("OpenRouter response parsed but no ranking rows were recognized")
    return out


def collect_openrouter_models(cfg: dict[str, Any], raw_dir: Path) -> list[Observation]:
    r = requests.get(cfg["url"], timeout=TIMEOUT)
    r.raise_for_status()
    payload = r.json()
    (raw_dir / "openrouter_models.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    rows = payload.get("data", payload if isinstance(payload, list) else [])
    now = utc_now()[:10]
    out: list[Observation] = []
    for row in rows:
        model = row.get("id") or row.get("name")
        pricing = row.get("pricing") or {}
        prompt = _safe_float(pricing.get("prompt"))
        completion = _safe_float(pricing.get("completion"))
        if model and prompt is not None:
            out.append(Observation(now, "openrouter_catalog", "input_price", str(model), prompt * 1_000_000, "USD/1M tokens", provenance=cfg["url"]))
        if model and completion is not None:
            out.append(Observation(now, "openrouter_catalog", "output_price", str(model), completion * 1_000_000, "USD/1M tokens", provenance=cfg["url"]))
    return out


def collect_artificial_analysis(cfg: dict[str, Any], raw_dir: Path) -> list[Observation]:
    key = env("ARTIFICIAL_ANALYSIS_API_KEY")
    if not key:
        raise RuntimeError("ARTIFICIAL_ANALYSIS_API_KEY is not configured")
    page = 1
    all_rows: list[dict[str, Any]] = []
    while True:
        r = requests.get(cfg["url"], headers={"x-api-key": key}, params={"page": page}, timeout=TIMEOUT)
        r.raise_for_status()
        payload = r.json()
        all_rows.extend(payload.get("data", []))
        pagination = payload.get("pagination") or {}
        if not pagination.get("has_more") or page >= 10:
            break
        page += 1
    (raw_dir / "artificial_analysis_models.json").write_text(json.dumps(all_rows, indent=2), encoding="utf-8")
    now = utc_now()[:10]
    out: list[Observation] = []
    for row in all_rows:
        model = row.get("slug") or row.get("name")
        if not model:
            continue
        perf = row.get("performance") or {}
        pricing = row.get("pricing") or {}
        evals = row.get("evaluations") or {}
        fields = [
            ("output_speed", perf.get("median_output_tokens_per_second") or row.get("median_output_tokens_per_second"), "tokens/second"),
            ("ttft", perf.get("median_time_to_first_token_seconds") or row.get("median_time_to_first_token_seconds"), "seconds"),
            ("input_price", pricing.get("price_1m_input_tokens"), "USD/1M tokens"),
            ("output_price", pricing.get("price_1m_output_tokens"), "USD/1M tokens"),
            ("intelligence_index", evals.get("artificial_analysis_intelligence_index"), "index"),
        ]
        for metric, value, unit in fields:
            value = _safe_float(value)
            if value is not None:
                out.append(Observation(now, "artificial_analysis", metric, str(model), value, unit, provenance="artificialanalysis.ai"))
    return out


def collect_vast_offers(cfg: dict[str, Any], raw_dir: Path) -> list[Observation]:
    key = env("VAST_API_KEY")
    if not key:
        raise RuntimeError("VAST_API_KEY is not configured")
    payload = {
        "limit": int(cfg.get("limit", 500)), "type": "ondemand",
        "verified": {"eq": True}, "rentable": {"eq": True}, "rented": {"eq": False},
        "gpu_name": {"in": cfg.get("gpu_names", [])},
    }
    r = requests.post(cfg["url"], json=payload, headers={"Authorization": f"Bearer {key}"}, timeout=TIMEOUT)
    r.raise_for_status()
    body = r.json()
    (raw_dir / "vast_offers.json").write_text(json.dumps(body, indent=2), encoding="utf-8")
    rows = _find_rows(body)
    now = utc_now()
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        name = row.get("gpu_name") or row.get("gpuName")
        if name:
            grouped.setdefault(str(name), []).append(row)
    out: list[Observation] = []
    for name, offers in grouped.items():
        prices, units = [], 0.0
        for row in offers:
            ngpu = _safe_float(row.get("num_gpus") or row.get("numGpus")) or 1.0
            total = _safe_float(row.get("dph_total") or row.get("totalHour") or row.get("discountedTotalPerHour"))
            if total is not None:
                prices.append(total / max(ngpu, 1.0))
            units += ngpu
        if prices:
            out.append(Observation(now, "vast", "gpu_price_median", name, float(np.median(prices)), "USD/GPU-hour", provenance="vast.ai offer search"))
            out.append(Observation(now, "vast", "gpu_price_p10", name, float(np.percentile(prices, 10)), "USD/GPU-hour", provenance="vast.ai offer search"))
        out.append(Observation(now, "vast", "gpu_offers_available", name, float(len(offers)), "offers", provenance="vast.ai offer search"))
        out.append(Observation(now, "vast", "gpu_units_available", name, units, "GPUs", provenance="vast.ai offer search"))
    return out


def collect_vast_market_metrics(cfg: dict[str, Any], raw_dir: Path) -> list[Observation]:
    key = env("VAST_HOST_API_KEY")
    if not key:
        raise RuntimeError("VAST_HOST_API_KEY is not configured (host keys only)")
    r = requests.get(cfg["current_url"], headers={"Authorization": f"Bearer {key}"}, timeout=TIMEOUT)
    r.raise_for_status()
    body = r.json()
    (raw_dir / "vast_market_current.json").write_text(json.dumps(body, indent=2), encoding="utf-8")
    rows = _find_rows(body)
    now = utc_now()
    out: list[Observation] = []
    aliases = {
        "available": ("gpu_supply_available", "GPUs"),
        "rented": ("gpu_demand_rented", "GPUs"),
        "median_price": ("gpu_price_median", "USD/GPU-hour"),
        "price_median": ("gpu_price_median", "USD/GPU-hour"),
    }
    for row in rows:
        name = row.get("gpu_name") or row.get("name") or row.get("gpu")
        if not name:
            continue
        for raw, (metric, unit) in aliases.items():
            value = _safe_float(row.get(raw))
            if value is not None:
                out.append(Observation(now, "vast_market", metric, str(name), value, unit, provenance="vast.ai market metrics"))
    return out


def collect_eia_grid(cfg: dict[str, Any], raw_dir: Path) -> list[Observation]:
    key = env("EIA_API_KEY")
    if not key:
        raise RuntimeError("EIA_API_KEY is not configured")
    days = int(os.getenv("BACKFILL_DAYS", "30"))
    start = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H")
    params: list[tuple[str, Any]] = [
        ("api_key", key), ("frequency", "hourly"), ("data[0]", "value"),
        ("facets[type][]", "D"), ("start", start),
        ("sort[0][column]", "period"), ("sort[0][direction]", "asc"),
        ("offset", 0), ("length", 5000),
    ]
    for respondent in cfg.get("respondents", []):
        params.append(("facets[respondent][]", respondent))
    rows: list[dict[str, Any]] = []
    snapshots: list[dict[str, Any]] = []
    offset = 0
    while True:
        paged = [(k, v) for k, v in params if k != "offset"] + [("offset", offset)]
        r = requests.get(cfg["url"], params=paged, timeout=TIMEOUT)
        r.raise_for_status()
        body = r.json(); snapshots.append(body)
        response = body.get("response") or {}
        batch = response.get("data") or []
        rows.extend(batch)
        total = int(response.get("total") or len(rows))
        offset += len(batch)
        if not batch or offset >= total:
            break
    (raw_dir / "eia_grid.json").write_text(json.dumps(snapshots, indent=2), encoding="utf-8")
    out: list[Observation] = []
    for row in rows:
        period = row.get("period")
        respondent = row.get("respondent") or row.get("respondent-name")
        value = _safe_float(row.get("value"))
        if period and respondent and value is not None:
            out.append(Observation(_date(period), "eia", "grid_load", str(respondent), value, "MW", provenance="EIA electricity/rto/region-data"))
    return out


def collect_weather(cfg: dict[str, Any], raw_dir: Path) -> list[Observation]:
    days = min(int(os.getenv("BACKFILL_DAYS", "30")), 92)
    out: list[Observation] = []
    snapshots: dict[str, Any] = {}
    for region, geo in cfg.get("regions", {}).items():
        params = {
            "latitude": geo["latitude"], "longitude": geo["longitude"],
            "hourly": "temperature_2m", "past_days": days, "forecast_days": 1,
            "timezone": "UTC",
        }
        r = requests.get(cfg["url"], params=params, timeout=TIMEOUT)
        r.raise_for_status()
        body = r.json(); snapshots[region] = body
        hourly = body.get("hourly") or {}
        for ts, temp in zip(hourly.get("time", []), hourly.get("temperature_2m", [])):
            value = _safe_float(temp)
            if value is not None:
                out.append(Observation(_date(ts), "open_meteo", "temperature", region, value, "C", provenance="open-meteo.com"))
    (raw_dir / "weather.json").write_text(json.dumps(snapshots, indent=2), encoding="utf-8")
    return out


def _first_matching_column(columns: list[str], patterns: list[str]) -> str | None:
    normalized = {c: re.sub(r"[^a-z0-9]", "", c.lower()) for c in columns}
    for pat in patterns:
        rx = re.compile(pat)
        for col, norm in normalized.items():
            if rx.search(norm):
                return col
    return None


def collect_epoch(cfg: dict[str, Any], raw_dir: Path) -> list[Observation]:
    now = utc_now()[:10]
    out: list[Observation] = []
    for name, url in [("data_centers", cfg["data_centers_csv"]), ("models", cfg["models_csv"])]:
        r = requests.get(url, timeout=TIMEOUT); r.raise_for_status()
        path = raw_dir / f"epoch_{name}.csv"; path.write_bytes(r.content)
        df = pd.read_csv(path)
        out.append(Observation(now, "epoch", "dataset_rows", name, float(len(df)), "rows", provenance=url))
        if name == "data_centers":
            power_col = _first_matching_column(list(df.columns), [r"itpower", r"power.*mw", r"capacity.*mw"])
            h100_col = _first_matching_column(list(df.columns), [r"h100.*equiv", r"h100eq"])
            status_col = _first_matching_column(list(df.columns), [r"status", r"stage"])
            mask = pd.Series(True, index=df.index)
            if status_col:
                mask = df[status_col].astype(str).str.contains("operat|complete|active|online", case=False, regex=True, na=False)
            if power_col:
                values = pd.to_numeric(df.loc[mask, power_col].astype(str).str.replace(",", ""), errors="coerce")
                if values.notna().any():
                    out.append(Observation(now, "epoch", "operational_ai_datacenter_power", "global", float(values.sum()), "MW", quality="observed_aggregated", provenance=url))
            if h100_col:
                values = pd.to_numeric(df.loc[mask, h100_col].astype(str).str.replace(",", ""), errors="coerce")
                if values.notna().any():
                    out.append(Observation(now, "epoch", "operational_h100_equivalents", "global", float(values.sum()), "H100-equivalents", quality="observed_aggregated", provenance=url))
        else:
            date_col = _first_matching_column(list(df.columns), [r"publicationdate", r"releasedate", r"date"])
            compute_col = _first_matching_column(list(df.columns), [r"trainingcompute", r"compute.*flop"])
            model_col = _first_matching_column(list(df.columns), [r"modelname", r"system", r"name"])
            if date_col and compute_col:
                for _, row in df[[date_col, compute_col] + ([model_col] if model_col else [])].dropna(subset=[date_col, compute_col]).iterrows():
                    value = _safe_float(str(row[compute_col]).replace(",", ""))
                    if value is not None:
                        dim = str(row[model_col]) if model_col else "model"
                        out.append(Observation(str(row[date_col])[:10], "epoch", "training_compute", dim, value, "FLOP", provenance=url))
    return out


def collect_mlperf(cfg: dict[str, Any], raw_dir: Path) -> list[Observation]:
    r = requests.get(cfg["summary_url"], timeout=TIMEOUT); r.raise_for_status()
    body = r.json()
    (raw_dir / "mlperf_summary_results.json").write_text(json.dumps(body, indent=2), encoding="utf-8")
    # Keep a durable freshness/size observation; model-weight calibration is deliberately reviewed manually.
    count = 0
    def walk(x: Any) -> None:
        nonlocal count
        if isinstance(x, dict):
            count += 1
            for v in x.values(): walk(v)
        elif isinstance(x, list):
            for v in x: walk(v)
    walk(body)
    return [Observation(utc_now()[:10], "mlperf", "summary_objects", "inference_v6.0", float(count), "objects", provenance=cfg["summary_url"])]


SEC_CONCEPTS: dict[str, list[str]] = {
    "company_revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ],
    "company_capex": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
    ],
    "company_depreciation": [
        "DepreciationDepletionAndAmortization",
        "DepreciationDepletionAndAmortizationPropertyPlantAndEquipment",
        "Depreciation",
    ],
    "company_operating_income": ["OperatingIncomeLoss"],
    "company_operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
}


def _sec_filing_url(cik: str, accession: str) -> str:
    accession_compact = accession.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_compact}/{accession}-index.html"


def _sec_duration_kind(fact: dict[str, Any]) -> str | None:
    start = pd.to_datetime(fact.get("start"), utc=True, errors="coerce")
    end = pd.to_datetime(fact.get("end"), utc=True, errors="coerce")
    if pd.isna(start) or pd.isna(end):
        return None
    days = int((end - start).days)
    form = str(fact.get("form") or "")
    fiscal_period = str(fact.get("fp") or "")
    if 70 <= days <= 120:
        return "quarterly"
    if form.startswith("10-K") and (280 <= days <= 400 or fiscal_period == "FY"):
        return "annual"
    return None


def _sec_metric_facts(payload: dict[str, Any], tags: list[str]) -> tuple[str | None, list[dict[str, Any]]]:
    concepts = payload.get("facts", {}).get("us-gaap", {})
    candidates: list[tuple[str, str, list[dict[str, Any]]]] = []
    for tag in tags:
        units = concepts.get(tag, {}).get("units", {})
        facts = units.get("USD", [])
        recognized = []
        for fact in facts:
            value = _safe_float(fact.get("val"))
            period_kind = _sec_duration_kind(fact)
            if value is None or period_kind is None or not fact.get("accn"):
                continue
            recognized.append({**fact, "val": value, "period_kind": period_kind})
        if recognized:
            latest_end = max(str(fact.get("end") or "") for fact in recognized)
            candidates.append((latest_end, tag, recognized))
    if candidates:
        _, tag, recognized = max(candidates, key=lambda item: item[0])
        return tag, recognized
    return None, []


def collect_sec_companyfacts(cfg: dict[str, Any], raw_dir: Path) -> list[Observation]:
    user_agent = env("SEC_USER_AGENT") or cfg.get("user_agent")
    if not user_agent:
        raise RuntimeError("SEC_USER_AGENT is not configured")
    headers = {"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"}
    out: list[Observation] = []
    for ticker, company in cfg.get("companies", {}).items():
        cik = str(company["cik"]).zfill(10)
        url = cfg["url_template"].format(cik=cik)
        response = requests.get(url, headers=headers, timeout=TIMEOUT)
        response.raise_for_status()
        payload = response.json()
        (raw_dir / f"sec_companyfacts_{ticker.lower()}.json").write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )
        for metric, tags in SEC_CONCEPTS.items():
            tag, facts = _sec_metric_facts(payload, tags)
            seen: set[tuple[str, str]] = set()
            for fact in sorted(facts, key=lambda item: (str(item.get("end")), str(item.get("filed")))):
                key = (str(fact.get("end")), str(fact.get("period_kind")))
                if key in seen:
                    continue
                seen.add(key)
                accession = str(fact["accn"])
                filing_url = _sec_filing_url(cik, accession)
                out.append(Observation(
                    observed_at_utc=str(fact["end"]),
                    source="sec_companyfacts",
                    metric=metric,
                    dimension=ticker,
                    value=float(fact["val"]),
                    unit="USD",
                    quality="reported",
                    is_estimate=False,
                    provenance=url,
                    metadata_json=json_text({
                        "company": company.get("name"),
                        "cik": cik,
                        "tag": tag,
                        "form": fact.get("form"),
                        "fiscal_year": fact.get("fy"),
                        "fiscal_period": fact.get("fp"),
                        "filed": fact.get("filed"),
                        "accession": accession,
                        "period_kind": fact["period_kind"],
                        "filing_url": filing_url,
                    }),
                ))
    return out


def collect_company_disclosures(cfg: dict[str, Any], raw_dir: Path) -> list[Observation]:
    """Load normalized earnings-call disclosures from a remote feed or local fallback."""
    feed_url = env(str(cfg.get("url_env") or "")) if cfg.get("url_env") else None
    if feed_url:
        response = requests.get(feed_url, timeout=TIMEOUT)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "json" in content_type or feed_url.lower().endswith(".json"):
            body = response.json()
            rows = body.get("data", body) if isinstance(body, dict) else body
            frame = pd.DataFrame(rows)
            (raw_dir / "company_disclosures.json").write_text(json.dumps(body, indent=2), encoding="utf-8")
        else:
            frame = pd.read_csv(io.StringIO(response.text))
            (raw_dir / "company_disclosures.csv").write_text(response.text, encoding="utf-8")
    else:
        path = Path(cfg["path"])
        if not path.exists():
            raise RuntimeError(f"Company disclosure fallback does not exist: {path}")
        frame = pd.read_csv(path)
    required = {"observed_at_utc", "ticker", "metric", "value", "unit", "classification", "source_url"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise RuntimeError(f"Company disclosure feed is missing columns: {', '.join(missing)}")
    out: list[Observation] = []
    for _, row in frame.iterrows():
        value = _safe_float(row.get("value"))
        if value is None or not str(row.get("ticker") or "").strip() or not str(row.get("metric") or "").strip():
            continue
        classification = str(row.get("classification") or "estimated").strip().lower()
        source_url = str(row.get("source_url") or "").strip()
        out.append(Observation(
            observed_at_utc=str(row["observed_at_utc"]),
            source="company_disclosures",
            metric=str(row["metric"]).strip(),
            dimension=str(row["ticker"]).strip().upper(),
            value=value,
            unit=str(row["unit"]),
            quality=classification,
            is_estimate=classification in {"estimated", "user-supplied"},
            provenance=source_url,
            metadata_json=json_text({
                "source_label": str(row.get("source_label") or "Earnings call disclosure"),
                "filing_url": source_url,
                "notes": str(row.get("notes") or ""),
                "feed": feed_url or str(cfg["path"]),
            }),
        ))
    return out


COLLECTORS: dict[str, Callable[[dict[str, Any], Path], list[Observation]]] = {
    "openrouter_rankings": collect_openrouter_rankings,
    "openrouter_models": collect_openrouter_models,
    "artificial_analysis": collect_artificial_analysis,
    "vast_offers": collect_vast_offers,
    "vast_market_metrics": collect_vast_market_metrics,
    "eia_grid": collect_eia_grid,
    "weather": collect_weather,
    "epoch": collect_epoch,
    "mlperf": collect_mlperf,
    "sec_companyfacts": collect_sec_companyfacts,
    "company_disclosures": collect_company_disclosures,
}
