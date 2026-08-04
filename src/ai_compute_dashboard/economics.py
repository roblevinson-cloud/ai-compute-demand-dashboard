from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

METRIC_DEFINITIONS = [
    {
        "key": "project_irr_pct",
        "label": "Project IRR",
        "unit": "%",
        "classification": "calculated",
        "formula": "Discount rate that sets the modeled unlevered project cash flows, including residual value, to zero.",
    },
    {
        "key": "data_center_roic_pct",
        "label": "Data-center ROIC",
        "unit": "%",
        "classification": "calculated",
        "formula": "Year-one NOPAT divided by modeled AI project capital.",
    },
    {
        "key": "gpu_utilization_pct",
        "label": "GPU utilization",
        "unit": "%",
        "classification": "calculated",
        "formula": "Annual project revenue divided by GPU-equivalents × 8,760 hours × blended value per GPU-hour.",
    },
    {
        "key": "payback_years",
        "label": "Payback period",
        "unit": "years",
        "classification": "calculated",
        "formula": "First fractional year in which cumulative unlevered after-tax cash flow becomes positive.",
    },
    {
        "key": "depreciation_adjusted_return_pct",
        "label": "Depreciation-adjusted return",
        "unit": "%",
        "classification": "calculated",
        "formula": "Year-one NOPAT plus non-cash depreciation, divided by modeled AI project capital.",
    },
    {
        "key": "marginal_operating_margin_pct",
        "label": "Marginal operating margin",
        "unit": "%",
        "classification": "calculated",
        "formula": "Incremental project revenue less non-power operating cost, electricity, and depreciation, divided by revenue.",
    },
]


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        return number if np.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def _irr(cash_flows: list[float]) -> float | None:
    """Return the conventional project IRR using a bounded bisection search."""
    if not cash_flows or cash_flows[0] >= 0 or not any(x > 0 for x in cash_flows[1:]):
        return None

    def npv(rate: float) -> float:
        return sum(value / ((1 + rate) ** year) for year, value in enumerate(cash_flows))

    low, high = -0.9999, 10.0
    low_value, high_value = npv(low), npv(high)
    if low_value == 0:
        return low
    if high_value == 0:
        return high
    if low_value * high_value > 0:
        return None
    for _ in range(180):
        mid = (low + high) / 2
        value = npv(mid)
        if abs(value) < 1e-10:
            return mid
        if low_value * value <= 0:
            high = mid
        else:
            low, low_value = mid, value
    return (low + high) / 2


def calculate_project_metrics(inputs: dict[str, float]) -> dict[str, Any]:
    """Calculate project returns in USD billions from a resolved assumption set."""
    total_capex = max(_finite(inputs.get("total_capex_basis_usd_b")), 0.0)
    project_capex = total_capex * _finite(inputs.get("ai_capex_share_pct")) / 100
    hardware_capex = project_capex * _finite(inputs.get("gpu_hardware_share_pct")) / 100
    unit_cost = max(_finite(inputs.get("all_in_gpu_cost_usd")), 1.0)
    gpu_equivalents = hardware_capex * 1_000_000_000 / unit_cost
    revenue_per_hour = max(_finite(inputs.get("blended_revenue_per_gpu_hour_usd")), 0.0)
    max_revenue = gpu_equivalents * 8_760 * revenue_per_hour / 1_000_000_000
    first_year_revenue = max(_finite(inputs.get("annual_project_revenue_usd_b")), 0.0)
    utilization = first_year_revenue / max_revenue if max_revenue else np.nan

    power_kw = max(_finite(inputs.get("gpu_power_kw")), 0.0)
    pue = max(_finite(inputs.get("pue"), 1.0), 1.0)
    energy_price = max(_finite(inputs.get("energy_cost_per_kwh_usd")), 0.0)
    physical_utilization = min(max(utilization if np.isfinite(utilization) else 0.0, 0.0), 1.0)
    first_year_energy = (
        gpu_equivalents * power_kw * pue * 8_760 * physical_utilization * energy_price
        / 1_000_000_000
    )
    non_power_opex = first_year_revenue * _finite(inputs.get("non_power_opex_pct_revenue")) / 100
    depreciation_years = max(round(_finite(inputs.get("depreciation_years"), 5)), 1)
    annual_depreciation = project_capex / depreciation_years
    year_one_ebit = first_year_revenue - non_power_opex - first_year_energy - annual_depreciation
    tax_rate = _finite(inputs.get("tax_rate_pct")) / 100
    year_one_nopat = year_one_ebit * (1 - tax_rate)
    maintenance_rate = _finite(inputs.get("maintenance_capex_pct_revenue")) / 100

    life = max(round(_finite(inputs.get("project_life_years"), 8)), 1)
    growth = _finite(inputs.get("revenue_growth_pct")) / 100
    cash_flows = [-project_capex]
    cash_flow_rows = [{
        "year": 0,
        "revenue_usd_b": 0.0,
        "energy_cost_usd_b": 0.0,
        "depreciation_usd_b": 0.0,
        "free_cash_flow_usd_b": -project_capex,
        "cumulative_cash_flow_usd_b": -project_capex,
    }]
    cumulative = -project_capex
    payback: float | None = None
    previous_cumulative = cumulative

    for year in range(1, life + 1):
        revenue = first_year_revenue * ((1 + growth) ** (year - 1))
        year_utilization = revenue / max_revenue if max_revenue else 0.0
        energy = (
            gpu_equivalents * power_kw * pue * 8_760
            * min(max(year_utilization, 0.0), 1.0) * energy_price / 1_000_000_000
        )
        cash_opex = revenue * _finite(inputs.get("non_power_opex_pct_revenue")) / 100 + energy
        depreciation = annual_depreciation if year <= depreciation_years else 0.0
        ebit = revenue - cash_opex - depreciation
        cash_tax = max(ebit, 0.0) * tax_rate
        maintenance = revenue * maintenance_rate
        free_cash_flow = revenue - cash_opex - cash_tax - maintenance
        if year == life:
            free_cash_flow += project_capex * _finite(inputs.get("residual_value_pct")) / 100
        cash_flows.append(free_cash_flow)
        cumulative += free_cash_flow
        if payback is None and cumulative >= 0 and free_cash_flow > 0:
            payback = (year - 1) + (-previous_cumulative / free_cash_flow)
        cash_flow_rows.append({
            "year": year,
            "revenue_usd_b": revenue,
            "energy_cost_usd_b": energy,
            "depreciation_usd_b": depreciation,
            "free_cash_flow_usd_b": free_cash_flow,
            "cumulative_cash_flow_usd_b": cumulative,
        })
        previous_cumulative = cumulative

    discount_rate = _finite(inputs.get("discount_rate_pct")) / 100
    project_irr = _irr(cash_flows)
    project_npv = sum(value / ((1 + discount_rate) ** year) for year, value in enumerate(cash_flows))

    def ratio(numerator: float, denominator: float) -> float | None:
        return numerator / denominator * 100 if denominator else None

    return {
        "project_capex_usd_b": project_capex,
        "gpu_equivalents": gpu_equivalents,
        "maximum_revenue_usd_b": max_revenue,
        "annual_energy_cost_usd_b": first_year_energy,
        "project_irr_pct": None if project_irr is None else project_irr * 100,
        "data_center_roic_pct": ratio(year_one_nopat, project_capex),
        "gpu_utilization_pct": None if not np.isfinite(utilization) else utilization * 100,
        "payback_years": payback,
        "depreciation_adjusted_return_pct": ratio(year_one_nopat + annual_depreciation, project_capex),
        "marginal_operating_margin_pct": ratio(year_one_ebit, first_year_revenue),
        "project_npv_usd_b": project_npv,
        "cash_flows": cash_flow_rows,
    }


def _metadata(row: pd.Series) -> dict[str, Any]:
    try:
        parsed = json.loads(row.get("metadata_json") or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


def _latest_reported(
    df: pd.DataFrame,
    ticker: str,
    metric: str,
    *,
    prefer_annual: bool = False,
) -> dict[str, Any] | None:
    rows = df[(df["metric"] == metric) & (df["dimension"] == ticker)].copy()
    if rows.empty:
        return None
    rows["date"] = pd.to_datetime(rows["observed_at_utc"], utc=True, errors="coerce")
    rows = rows.dropna(subset=["date", "value"]).sort_values(["date", "collected_at_utc"])
    if rows.empty:
        return None
    if prefer_annual:
        annual = rows[rows["metadata_json"].astype(str).str.contains('"period_kind": "annual"', regex=False)]
        if not annual.empty:
            rows = annual
    row = rows.iloc[-1]
    meta = _metadata(row)
    return {
        "value": float(row["value"]),
        "unit": row.get("unit") or "USD",
        "classification": "reported" if row.get("quality") == "reported" else str(row.get("quality") or "estimated"),
        "period": str(row["date"].date()),
        "source": meta.get("source_label") or ("SEC filing" if row.get("source") == "sec_companyfacts" else str(row.get("source"))),
        "source_url": meta.get("filing_url") or row.get("provenance") or "",
        "note": meta.get("notes") or meta.get("basis") or "",
    }


def _capex_basis(df: pd.DataFrame, ticker: str) -> dict[str, Any] | None:
    rows = df[(df["metric"] == "company_capex") & (df["dimension"] == ticker)].copy()
    if rows.empty:
        return None
    rows["date"] = pd.to_datetime(rows["observed_at_utc"], utc=True, errors="coerce")
    rows = rows.dropna(subset=["date", "value"]).sort_values(["date", "collected_at_utc"])
    annual = rows[rows["metadata_json"].astype(str).str.contains('"period_kind": "annual"', regex=False)]
    quarterly = rows[rows["metadata_json"].astype(str).str.contains('"period_kind": "quarterly"', regex=False)]
    latest_annual_date = annual["date"].max() if not annual.empty else pd.NaT
    latest_quarter_date = quarterly["date"].max() if not quarterly.empty else pd.NaT
    if not annual.empty and (pd.isna(latest_quarter_date) or latest_annual_date >= latest_quarter_date):
        row = annual.iloc[-1]
        meta = _metadata(row)
        return {
            "value": float(row["value"]) / 1_000_000_000,
            "classification": "reported",
            "period": str(row["date"].date()),
            "source": "SEC filing",
            "source_url": meta.get("filing_url") or row.get("provenance") or "",
            "note": "Latest reported fiscal-year capital expenditure; scenario allocation is modeled separately.",
        }
    if not quarterly.empty:
        quarterly = quarterly.drop_duplicates(subset=["date"], keep="last").tail(4)
        multiplier = 1.0 if len(quarterly) == 4 else 4.0 / len(quarterly)
        row = quarterly.iloc[-1]
        meta = _metadata(row)
        return {
            "value": float(quarterly["value"].sum()) * multiplier / 1_000_000_000,
            "classification": "reported",
            "period": str(row["date"].date()),
            "source": "SEC filing",
            "source_url": meta.get("filing_url") or row.get("provenance") or "",
            "note": "Trailing four quarters when available; otherwise annualized from available reported quarters.",
        }
    return None


def _apply_modifiers(values: dict[str, float], modifiers: dict[str, Any]) -> dict[str, float]:
    resolved = deepcopy(values)
    for key, change in modifiers.items():
        if key not in resolved:
            continue
        value = _finite(resolved[key])
        if "multiply" in change:
            value *= _finite(change["multiply"], 1.0)
        if "add" in change:
            value += _finite(change["add"])
        resolved[key] = value
    return resolved


def build_infrastructure_economics(
    df: pd.DataFrame,
    config_path: str | Path,
) -> dict[str, Any]:
    path = Path(config_path)
    with path.open("r", encoding="utf-8") as stream:
        config = yaml.safe_load(stream)

    assumption_definitions = []
    for key, definition in config["assumptions"].items():
        assumption_definitions.append({"key": key, **definition})

    companies = []
    for ticker, company in config["companies"].items():
        base_values = {key: _finite(value) for key, value in company["values"].items()}
        capex = _capex_basis(df, ticker)
        if capex:
            base_values["total_capex_basis_usd_b"] = capex["value"]
        else:
            capex = {
                "value": base_values["total_capex_basis_usd_b"],
                "classification": "estimated",
                "period": config.get("as_of"),
                "source": "Model fallback",
                "source_url": company.get("fallback_source_url", ""),
                "note": "Fallback used until the SEC collector has enough recognized facts.",
            }

        ai_revenue = _latest_reported(df, ticker, "company_ai_infrastructure_revenue")
        if ai_revenue:
            base_values["annual_project_revenue_usd_b"] = ai_revenue["value"] / 1_000_000_000

        scenario_rows: dict[str, Any] = {}
        for scenario in ("bear", "base", "bull"):
            values = _apply_modifiers(base_values, config.get("scenario_modifiers", {}).get(scenario, {}))
            inputs = {}
            for key, value in values.items():
                if key == "total_capex_basis_usd_b":
                    classification = capex["classification"]
                    source = capex["source"]
                    source_url = capex["source_url"]
                    period = capex["period"]
                    note = capex["note"]
                elif key == "annual_project_revenue_usd_b" and ai_revenue and scenario == "base":
                    classification = "reported"
                    source = ai_revenue["source"]
                    source_url = ai_revenue["source_url"]
                    period = ai_revenue["period"]
                    note = ai_revenue["note"]
                else:
                    classification = "estimated"
                    source = "Scenario model"
                    source_url = ""
                    period = config.get("as_of")
                    note = config.get("scenario_labels", {}).get(scenario, "")
                inputs[key] = {
                    "value": value,
                    "classification": classification,
                    "source": source,
                    "source_url": source_url,
                    "period": period,
                    "note": note,
                }
            scenario_rows[scenario] = {
                "inputs": inputs,
                "metrics": calculate_project_metrics(values),
            }

        reported_context = []
        for metric, label in [
            ("company_revenue", "Company revenue"),
            ("company_operating_income", "Operating income"),
            ("company_depreciation", "Depreciation & amortization"),
            ("company_operating_cash_flow", "Operating cash flow"),
            ("company_active_power_mw", "Active data-center power"),
            ("company_gpu_utilization", "Disclosed GPU utilization"),
        ]:
            item = _latest_reported(df, ticker, metric)
            if item:
                reported_context.append({"metric": metric, "label": label, **item})

        companies.append({
            "ticker": ticker,
            "name": company["name"],
            "color": company["color"],
            "cik": company["cik"],
            "investor_relations_url": company["investor_relations_url"],
            "reported_context": reported_context,
            "scenarios": scenario_rows,
        })

    return {
        "meta": {
            "version": config.get("version", "1.0.0"),
            "as_of": config.get("as_of"),
            "generated_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "disclaimer": "Scenario analysis, not investment advice. Project-level economics are not company guidance or consolidated forecasts.",
        },
        "scenario_labels": config.get("scenario_labels", {}),
        "assumptions": assumption_definitions,
        "metrics": METRIC_DEFINITIONS,
        "companies": companies,
    }
