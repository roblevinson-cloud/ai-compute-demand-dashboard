
from datetime import datetime

from dc_intel.brief_archive import (
    EASTERN,
    build_archive_brief,
    due_digest_types,
    load_brief_archive,
    save_brief_archive,
)
from dc_intel.demo import build_demo_data
from dc_intel.digest import render_digest
from dc_intel.extraction import deterministic_extract
from dc_intel.resolution import compare_project
from dc_intel.scoring import score_confidence, score_materiality, score_novelty
from dc_intel.source_registry import load_source_registry, source_summary


def test_extraction_uses_fixed_schema_and_preserves_boundaries():
    result = deterministic_extract(
        document_id="doc-1",
        title="Project Atlas files air quality permit",
        text="Project Atlas in Lea County, New Mexico proposes 2.45 GW of generation on 1,400 acres under permit 10883.",
        published_at="2026-09-18T10:00:00Z",
    )

    payload = result.to_dict()
    assert payload["schema_version"] == "1.0"
    assert payload["project_name"] == "Project Atlas"
    assert payload["location"] == {"county": "Lea", "state": "NM"}
    assert next(fact for fact in payload["facts"] if fact["field"] == "generation_capacity_mw")["value"] == 2450
    assert payload["permit_numbers"] == ["10883"]
    assert payload["event_type"] == "environmental_permit"


def test_entity_resolution_keeps_google_lea_separate_from_jupiter():
    signal = {"state": "NM", "county": "Lea", "developer": ["Google"], "tenant": ["Google"]}
    jupiter = {
        "id": "jupiter", "state": "NM", "county": "Doña Ana",
        "developer": ["BorderPlex Digital Assets"], "tenant": ["OpenAI"],
        "alias": ["Project Jupiter", "YGI Microgrid"],
    }

    result = compare_project(signal, jupiter)

    assert result.recommendation == "likely_new_project"
    assert result.score < 20
    assert "Different counties" in result.conflicts
    assert "Different named tenant/customer" in result.conflicts


def test_entity_resolution_can_recommend_link_without_erasing_evidence():
    signal = {
        "state": "NM", "county": "Doña Ana", "developer": ["Yucca Growth Infrastructure"],
        "tenant": ["OpenAI"], "alias": ["YGI Microgrid"], "mw": 2450,
    }
    project = {
        "id": "jupiter", "state": "NM", "county": "Doña Ana",
        "developer": ["Yucca Growth Infrastructure", "BorderPlex Digital Assets"],
        "tenant": ["OpenAI"], "alias": ["Project Jupiter", "YGI Microgrid"], "mw": 2450,
    }

    result = compare_project(signal, project)

    assert result.score >= 88
    assert result.recommendation == "candidate_auto_link"
    assert result.supporting
    assert result.conflicts == []


def test_scores_are_bounded_and_transparent():
    event = {
        "event_type": "generation_storage", "mw": 2450, "capex_usd_b": 165,
        "stage_weight": 10, "regulatory_weight": 8, "risk_weight": 4, "major_party": True,
        "new_fact_count": 4, "changed_fact_count": 2, "first_primary_record": True,
        "duplicate_similarity": 0, "source_type": "primary_regulatory",
        "extraction_confidence": 94, "match_confidence": 92, "corroborating_sources": 2,
    }
    scores = [score_materiality(event), score_novelty(event), score_confidence(event)]

    assert all(0 <= score.value <= 100 for score in scores)
    assert all(score.factors for score in scores)
    assert score_materiality(event).value >= 85
    assert score_novelty({**event, "duplicate_similarity": 1}).value < score_novelty(event).value


def test_source_registry_covers_primary_local_company_and_trade_sources():
    sources = load_source_registry("config/sources.yml")
    summary = source_summary(sources)

    assert summary["total"] >= 20
    assert summary["by_type"]["primary_regulatory"] >= 3
    assert summary["by_type"]["local_media"] >= 2
    assert summary["by_type"]["company"] >= 3
    assert summary["by_type"]["trade_media"] >= 2
    assert any(source["key"] == "nm-courts-case-lookup" for source in sources)


def test_demo_is_project_centric_and_cites_every_event():
    data = build_demo_data()
    projects = {project["id"]: project for project in data["projects"]}

    assert len(projects) >= 60
    assert {"project-jupiter", "google-lea-county", "portfolio-meridian-arc", "portfolio-galaxy-helios-ii"} <= set(projects)
    assert len({project["slug"] for project in projects.values()}) == len(projects)
    assert sum(project["name"] == "Project Jupiter" for project in projects.values()) == 1
    assert projects["project-jupiter"]["mw"] == 2450
    assert projects["project-jupiter"]["it_mw"] is None
    assert projects["portfolio-meridian-arc"]["it_mw"] == 430
    assert projects["portfolio-meridian-arc"]["mw"] == 620
    assert all(event["project_id"] in projects for event in data["events"])
    assert all(event["source_url"].startswith("https://") for event in data["events"])
    google_match = next(item for item in data["review_queue"] if item["id"] == "match-google-jupiter")
    assert google_match["recommendation"] == "likely_new_project"


def test_nine_month_research_backfill_is_substantial_and_source_linked():
    data = build_demo_data()
    backfill_events = [
        event for event in data["events"]
        if "2025-12-19" <= event["occurred_at"][:10] <= "2026-09-19"
    ]

    assert len(data["events"]) >= 120
    assert len(backfill_events) >= 110
    assert sum(len(event["numbers"]) for event in data["events"]) >= 240
    assert len({event["id"] for event in data["events"]}) == len(data["events"])
    assert all(event["source_url"].startswith("https://") for event in backfill_events)


def test_email_digest_explains_change_and_links_evidence():
    data = build_demo_data()
    subject, text_body, html_body = render_digest(data["events"], "morning", "2026-09-18T10:30:00-04:00")

    assert subject.startswith("Morning Brief")
    assert "What changed:" in html_body
    assert "Why it matters:" in html_body
    assert "Underlying evidence" in html_body
    assert "https://" in text_body


def test_public_brief_schedule_uses_eastern_time_and_is_idempotent_by_id(tmp_path):
    before_morning = datetime(2026, 9, 19, 6, 29, tzinfo=EASTERN)
    morning = datetime(2026, 9, 19, 6, 30, tzinfo=EASTERN)
    evening = datetime(2026, 9, 19, 18, 0, tzinfo=EASTERN)

    assert due_digest_types(before_morning) == []
    assert due_digest_types(morning) == ["morning"]
    assert due_digest_types(evening) == ["morning", "evening"]

    data = build_demo_data(brief_archive_path=None)
    brief = build_archive_brief(data["events"], "morning", morning)
    assert brief["id"] == "brief-morning-2026-09-19"
    assert brief["event_ids"] == []
    assert "No new developments" in brief["body_text"]

    archive = tmp_path / "briefs.json"
    save_brief_archive([brief], archive)
    assert load_brief_archive(archive)[0]["id"] == brief["id"]
