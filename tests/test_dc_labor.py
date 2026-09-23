from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import collect_dc_labor_v2 as labor
import collect_dc_labor_v3 as hardened
from datetime import datetime, timezone


def test_active_snapshot_rows_uses_latest_scrape_and_deduplicates_source_sections():
    base = {
        "market": "Kansas City",
        "source_date": "2026-09-17",
        "local": "124",
        "project": "Google",
        "openings": "10",
        "source_text": "10 - CAPITAL - GOOGLE NRD",
    }
    rows = [
        {**base, "observed_at": "2026-09-17T10:00:00+00:00"},
        {**base, "observed_at": "2026-09-17T12:00:00+00:00"},
        {**base, "observed_at": "2026-09-17T12:00:00+00:00"},
    ]

    active = labor.active_snapshot_rows(rows)

    assert len(active) == 1
    assert active[0]["observed_at"] == "2026-09-17T12:00:00+00:00"


def test_updated_local_without_data_center_calls_has_explicit_zero():
    observed = datetime(2026, 9, 23, tzinfo=timezone.utc)
    text = (
        "LU-347 DES MOINES, IA (9-21)\n"
        "2 - BAKER GROUP - REG JW CALL FOR SERVICE TRUCK\n"
        "LU-583 EL PASO, TX (9-21)\n"
        "5 - MASS ELECTRIC - PROJECT MINER SANTA TERESA DATA CENTER\n"
    )
    rows = hardened.validated_parse_calls(text, observed, {
        "locals": {"347": {"market": "Des Moines–Altoona"},
                   "583": {"market": "El Paso–Santa Teresa"}}
    })
    assert [(r.local, r.openings) for r in rows] == [("583", 5), ("347", 0)]
    assert rows[-1].source_date == "2026-09-21"
