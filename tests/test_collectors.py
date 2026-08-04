import json
import subprocess

import pytest

from ai_compute_dashboard.collectors import (
    collect_openrouter_rankings,
    collect_sec_companyfacts,
)


def test_openrouter_rankings_parses_current_dataset_response(monkeypatch, tmp_path):
    payload = {
        "data": [
            {
                "date": "2026-07-30",
                "model_permaslug": "openai/test-model",
                "prompt_tokens": 100,
                "completion_tokens": 25,
            }
        ]
    }
    api_key = "test-openrouter-key"
    monkeypatch.setenv("OPENROUTER_API_KEY", api_key)

    def fake_run(command, **kwargs):
        assert command == ["node", "scripts/fetch_openrouter.mjs"]
        assert kwargs["check"] is False
        assert kwargs["env"]["OPENROUTER_API_KEY"] == api_key
        return subprocess.CompletedProcess(
            command, returncode=0, stdout=json.dumps(payload), stderr=""
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    observations = collect_openrouter_rankings(
        {"node_script": "scripts/fetch_openrouter.mjs"}, tmp_path
    )

    assert len(observations) == 1
    assert observations[0].observed_at_utc == "2026-07-30"
    assert observations[0].dimension == "openai/test-model"
    assert observations[0].value == 125
    assert json.loads((tmp_path / "openrouter_rankings.json").read_text()) == payload


def test_openrouter_rankings_surfaces_safe_script_error(monkeypatch, tmp_path):
    api_key = "secret-openrouter-key"
    monkeypatch.setenv("OPENROUTER_API_KEY", api_key)

    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(
            command,
            returncode=1,
            stdout="",
            stderr=f"request rejected for {api_key}: unauthorized",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RuntimeError) as exc_info:
        collect_openrouter_rankings(
            {"node_script": "scripts/fetch_openrouter.mjs"}, tmp_path
        )

    message = str(exc_info.value)
    assert "unauthorized" in message
    assert "[REDACTED]" in message
    assert api_key not in message


def test_sec_companyfacts_keeps_quarterly_and_annual_reported_facts(monkeypatch, tmp_path):
    payload = {
        "facts": {
            "us-gaap": {
                "PaymentsToAcquirePropertyPlantAndEquipment": {
                    "units": {
                        "USD": [
                            {
                                "start": "2026-01-01", "end": "2026-03-31",
                                "val": 10_000_000_000, "form": "10-Q", "fp": "Q1",
                                "fy": 2026, "filed": "2026-04-25", "accn": "0000000000-26-000001",
                            },
                            {
                                "start": "2026-01-01", "end": "2026-06-30",
                                "val": 25_000_000_000, "form": "10-Q", "fp": "Q2",
                                "fy": 2026, "filed": "2026-07-25", "accn": "0000000000-26-000002",
                            },
                            {
                                "start": "2025-01-01", "end": "2025-12-31",
                                "val": 36_000_000_000, "form": "10-K", "fp": "FY",
                                "fy": 2025, "filed": "2026-02-01", "accn": "0000000000-26-000003",
                            },
                        ]
                    }
                }
            }
        }
    }

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return payload

    def fake_get(url, **kwargs):
        assert url.endswith("CIK0000789019.json")
        assert "User-Agent" in kwargs["headers"]
        return Response()

    monkeypatch.setattr("ai_compute_dashboard.collectors.requests.get", fake_get)
    observations = collect_sec_companyfacts(
        {
            "url_template": "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
            "user_agent": "test@example.com",
            "companies": {"MSFT": {"name": "Microsoft", "cik": "0000789019"}},
        },
        tmp_path,
    )

    assert len(observations) == 2
    assert {json.loads(item.metadata_json)["period_kind"] for item in observations} == {
        "quarterly", "annual"
    }
    assert {item.quality for item in observations} == {"reported"}
