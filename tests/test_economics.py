import json

import pandas as pd

from ai_compute_dashboard.economics import (
    build_infrastructure_economics,
    calculate_project_metrics,
)


def _inputs() -> dict[str, float]:
    return {
        "total_capex_basis_usd_b": 100,
        "ai_capex_share_pct": 50,
        "gpu_hardware_share_pct": 50,
        "all_in_gpu_cost_usd": 50_000,
        "annual_project_revenue_usd_b": 10.95,
        "blended_revenue_per_gpu_hour_usd": 5,
        "non_power_opex_pct_revenue": 20,
        "energy_cost_per_kwh_usd": 0.06,
        "pue": 1.2,
        "gpu_power_kw": 0.8,
        "depreciation_years": 5,
        "revenue_growth_pct": 8,
        "tax_rate_pct": 20,
        "maintenance_capex_pct_revenue": 4,
        "discount_rate_pct": 10,
        "project_life_years": 8,
        "residual_value_pct": 10,
    }


def test_project_economics_are_internally_consistent():
    result = calculate_project_metrics(_inputs())

    assert result["project_capex_usd_b"] == 50
    assert result["gpu_equivalents"] == 500_000
    assert round(result["gpu_utilization_pct"], 8) == 50
    assert len(result["cash_flows"]) == 9
    assert result["project_irr_pct"] is not None
    assert result["payback_years"] is not None


def test_reported_sec_capex_replaces_estimated_fallback():
    row = {
        "observed_at_utc": "2026-06-30",
        "source": "sec_companyfacts",
        "metric": "company_capex",
        "dimension": "MSFT",
        "value": 12_300_000_000,
        "unit": "USD",
        "quality": "reported",
        "is_estimate": False,
        "collected_at_utc": "2026-07-25T00:00:00Z",
        "provenance": "https://data.sec.gov/example",
        "metadata_json": json.dumps({
            "period_kind": "annual",
            "filing_url": "https://www.sec.gov/example-filing",
        }),
    }

    economics = build_infrastructure_economics(
        pd.DataFrame([row]), "config/infrastructure_economics.yml"
    )
    microsoft = next(item for item in economics["companies"] if item["ticker"] == "MSFT")
    capex = microsoft["scenarios"]["base"]["inputs"]["total_capex_basis_usd_b"]

    assert capex["value"] == 12.3
    assert capex["classification"] == "reported"
    assert capex["source_url"] == "https://www.sec.gov/example-filing"
    assert {metric["classification"] for metric in economics["metrics"]} == {"calculated"}
