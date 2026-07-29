from pathlib import Path

from campaign.api import CampaignRowWrite
from campaign.db import EDITABLE_FIELDS, normalize_row_data
from campaign.table import Campaign, CampaignRow

API_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = API_ROOT.parent


def test_campaign_identity_and_rows_are_owned_by_campaign_vertical():
    assert Campaign.__module__ == "campaign.table"
    assert Campaign.__table__.name == "campaigns"
    assert CampaignRow.__module__ == "campaign.table"
    assert CampaignRow.__table__.name == "campaign_rows"


def test_metricless_rows_default_to_needs_data_not_fake_performance():
    row = normalize_row_data({})
    assert row["objective_verdict"] == "needs_data"
    assert all(row.get(field) is None for field in ("reach", "clicks", "leads", "conversions", "spend", "revenue"))


def test_explicit_zero_is_preserved_as_reported_data():
    row = normalize_row_data({"reach": 0})
    assert row["reach"] == 0
    assert row["objective_verdict"] == "inconclusive"


def test_http_write_schema_does_not_invent_a_verdict():
    assert CampaignRowWrite().objective_verdict is None


def test_row_edits_cannot_reassign_campaign_identity_or_lifecycle():
    for field in ("workspace_id", "brand_id", "campaign_id", "campaign", "status", "objective_id"):
        assert field not in EDITABLE_FIELDS


def test_retired_campaign_rerouters_are_deleted():
    chat_source = (API_ROOT / "routers" / "chat_v2.py").read_text(encoding="utf-8")
    for retired in (
        "_looks_like_campaign_inventory_request",
        "_looks_like_campaign_context_request",
        "_campaign_context_reply",
        "_reports_context_reply",
        "_retired_social_post_draft",
    ):
        assert retired not in chat_source
    assert not (API_ROOT / "routers" / "chat.py.bak").exists()
    assert not (API_ROOT / "routers" / "cmo_prompt.py").exists()


def test_cmo_brand_scaffold_does_not_inject_reports_as_campaign_truth():
    source = (API_ROOT / "routers" / "cmo_tools.py").read_text(encoding="utf-8")
    assert 'lines.append("Campaign Reports excerpt:' not in source
    assert 'lines.append("Marketing Reports excerpt:' not in source


def test_runtime_producers_do_not_emit_daily_brief_campaign_truth():
    runtime_roots = (API_ROOT, REPO_ROOT / "plugins")
    matches: list[str] = []
    for root in runtime_roots:
        for path in root.rglob("*.py"):
            if "migrations" in path.parts or "tests" in path.parts:
                continue
            if "daily_brief_signal" in path.read_text(encoding="utf-8", errors="ignore"):
                matches.append(str(path))
    assert matches == []


def test_postcraft_modules_accept_only_canonical_alignment_field():
    module_root = REPO_ROOT / "plugins" / "postcraft" / "capabilities" / "postcraft"
    for name in ("draft", "create", "render"):
        source = (module_root / name / "module.py").read_text(encoding="utf-8")
        assert 'brief.get("campaign_context")' not in source
        assert 'brand_kit.get("campaign_alignment")' not in source
