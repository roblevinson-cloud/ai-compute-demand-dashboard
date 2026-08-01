import json
import subprocess

import pytest

from ai_compute_dashboard.collectors import collect_openrouter_rankings


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
