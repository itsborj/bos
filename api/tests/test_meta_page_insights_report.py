from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module():
    module_path = Path(__file__).resolve().parents[2] / "plugins/meta/capabilities/marketing/channel/meta/pages/insights_report/module.py"
    spec = importlib.util.spec_from_file_location("meta_page_insights_report_for_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _brief(**extra):
    data = {
        "_channel_credentials": {
            "facebook_page_token": "page-token",
            "facebook_page_id": "page-1",
            "facebook_page_name": "Test Page",
        }
    }
    data.update(extra)
    return data


def test_meta_page_insights_report_builds_read_only_block(monkeypatch):
    module = _load_module()

    def fake_get_json(self, path, params):
        if path == "page-1":
            return {"id": "page-1", "name": "Test Page", "category": "Brand", "fan_count": 12, "link": "https://facebook.com/page-1"}
        if path == "page-1/scheduled_posts":
            return {"data": [{"id": "page-1_post-1", "message": "Scheduled", "scheduled_publish_time": 1893456000}]}
        if path == "page-1/posts":
            return {"data": [{"id": "page-1_post-2", "message": "Recent", "likes": {"summary": {"total_count": 3}}, "comments": {"summary": {"total_count": 1}}, "shares": {"count": 2}}]}
        if path == "page-1/insights":
            return {"data": [{"name": params["metric"], "title": "Page views", "period": "day", "values": [{"value": 2}, {"value": 5}]}]}
        raise AssertionError(path)

    monkeypatch.setattr(module.MetaPageInsightsReportModule, "_get_json", fake_get_json)

    attempt, result = module.MetaPageInsightsReportModule().execute_tool_result(_brief(metrics=["page_views_total"]))

    assert attempt["status"] == "succeeded"
    block = result["block"]
    assert block["type"] == "meta_page_insights_report"
    assert block["read_only"] is True
    assert block["changed_resources"] == []
    assert block["page"]["followers"] == 12
    assert len(block["scheduled_posts"]) == 1
    assert len(block["recent_posts"]) == 1
    assert block["insights"][0]["total"] == 7
    assert block["coverage_label"] == "full"
    assert block["coverage"]["recent_posts_engagement"]["state"] == "fresh"
    assert block["report_scope"] == "channel_snapshot"
    assert block["metrics_overview"]["insight_metrics_reported"] == 1
    assert block["insight_bullets"][0]["coverage"] == "campaign_binding_missing"
    assert "Metrics overview" in result["content"]
    assert "Channel insights (not campaign-bound)" in result["content"]
    assert "Content intelligence" in result["content"]
    assert "Strategist next step" in result["content"]


def test_meta_page_insights_report_uses_nested_posts_when_engagement_edge_blocked(monkeypatch):
    module = _load_module()

    def fake_optional_get(self, path, params, label, warnings):
        if path == "page-1":
            return {
                "id": "page-1",
                "name": "Test Page",
                "fan_count": 12,
                "posts": {"data": [{"id": "page-1_nested", "message": "Nested post", "created_time": "2026-07-01T00:00:00+0000"}]},
            }
        if path == "page-1/posts":
            warnings.append({"scope": label, "message": "permission denied"})
            return None
        return {"data": []}

    monkeypatch.setattr(module.MetaPageInsightsReportModule, "_optional_get", fake_optional_get)

    attempt, result = module.MetaPageInsightsReportModule().execute_tool_result(_brief())

    assert attempt["status"] == "succeeded"
    block = result["block"]
    assert block["recent_posts_source"] == "page_profile_nested_posts_basic"
    assert block["recent_posts"][0]["message"] == "Nested post"
    assert block["coverage"]["recent_post_copy"]["state"] == "fresh"
    assert block["coverage"]["recent_posts_engagement"]["state"] == "blocked"
    assert block["coverage_label"] == "partial"
    assert "Recent readable activity pulled from Meta" in result["content"]
    assert "Not available yet" in result["content"]


def test_meta_page_insights_report_anchors_to_campaign_index_when_no_campaign_selected(monkeypatch):
    module = _load_module()

    def fake_get_json(self, path, params):
        if path == "page-1":
            return {"id": "page-1", "name": "Test Page", "fan_count": 12}
        if path == "page-1/scheduled_posts":
            return {"data": []}
        if path == "page-1/posts":
            return {"data": [
                {"id": "p1", "message": "Plan ahead to protect your family and secure peace of mind.", "created_time": "2026-07-01T00:00:00+0000"},
            ]}
        if path == "page-1/insights":
            return {"data": []}
        raise AssertionError(path)

    monkeypatch.setattr(module.MetaPageInsightsReportModule, "_get_json", fake_get_json)

    attempt, result = module.MetaPageInsightsReportModule().execute_tool_result(_brief(_campaign_index=[{
        "campaign_id": "camp-family",
        "name": "Family Planning Campaign",
        "audience": "future planners",
        "message_focus": "family protection planning ahead",
    }]))

    assert attempt["status"] == "succeeded"
    block = result["block"]
    assert block["report_scope"] == "campaign_candidate"
    assert block["campaign_binding"]["campaign_id"] == "camp-family"
    assert any("Family Planning Campaign" in item["insight"] for item in block["insight_bullets"])


def test_meta_page_insights_report_does_not_misclassify_generic_marketing_future_as_family_planning(monkeypatch):
    module = _load_module()

    def fake_get_json(self, path, params):
        if path == "page-1":
            return {"id": "page-1", "name": "Klarohahq", "fan_count": 2}
        if path == "page-1/scheduled_posts":
            return {"data": []}
        if path == "page-1/posts":
            return {"data": [
                {"id": "p1", "message": "Turn Intent Into Conversations", "created_time": "2026-06-06T00:00:00+0000"},
                {"id": "p2", "message": "The future of marketing is here", "created_time": "2026-05-25T00:00:00+0000"},
            ]}
        if path == "page-1/insights":
            return {"data": []}
        raise AssertionError(path)

    monkeypatch.setattr(module.MetaPageInsightsReportModule, "_get_json", fake_get_json)

    attempt, result = module.MetaPageInsightsReportModule().execute_tool_result(_brief())

    assert attempt["status"] == "succeeded"
    themes = [t["theme"] for t in result["block"]["content_intelligence"]["themes"]]
    audiences = result["block"]["content_intelligence"]["audiences_implied"]
    assert "marketing ops / lead generation" in themes
    assert "intent-to-conversation messaging" in themes
    assert "family protection / planning ahead" not in themes
    assert "future planners" not in audiences


def test_meta_page_insights_report_is_channel_snapshot_when_no_campaign_is_bound(monkeypatch):
    module = _load_module()

    def fake_get_json(self, path, params):
        if path == "page-1":
            return {"id": "page-1", "name": "Golden Gate", "fan_count": 2033}
        if path == "page-1/scheduled_posts":
            return {"data": []}
        if path == "page-1/posts":
            return {"data": [
                {"id": "p1", "message": "Be the trusted guide families remember. Message us to plan ahead.", "created_time": "2026-07-01T00:00:00+0000"},
            ]}
        if path == "page-1/insights":
            return {"data": []}
        raise AssertionError(path)

    monkeypatch.setattr(module.MetaPageInsightsReportModule, "_get_json", fake_get_json)

    attempt, result = module.MetaPageInsightsReportModule().execute_tool_result(_brief())

    assert attempt["status"] == "succeeded"
    block = result["block"]
    assert block["report_scope"] == "channel_snapshot"
    assert block["objective_feedback"] == []
    assert "Channel insights (not campaign-bound)" in result["content"]
    assert "campaign_binding_missing" in result["content"]


def test_meta_page_insights_report_produces_content_intelligence(monkeypatch):
    module = _load_module()

    def fake_get_json(self, path, params):
        if path == "page-1":
            return {"id": "page-1", "name": "Test Page", "fan_count": 12}
        if path == "page-1/scheduled_posts":
            return {"data": []}
        if path == "page-1/posts":
            return {"data": [
                {"id": "p1", "message": "Be the trusted guide families remember. Message us to plan ahead.", "created_time": "2026-07-01T00:00:00+0000"},
                {"id": "p2", "message": "Secure your family's future with dignity and peace of mind.", "created_time": "2026-07-02T00:00:00+0000"},
            ]}
        if path == "page-1/insights":
            return {"data": []}
        raise AssertionError(path)

    monkeypatch.setattr(module.MetaPageInsightsReportModule, "_get_json", fake_get_json)

    attempt, result = module.MetaPageInsightsReportModule().execute_tool_result(_brief(campaign_id="camp-1", campaign_name="Pre-Need"))

    assert attempt["status"] == "succeeded"
    block = result["block"]
    assert block["report_scope"] == "campaign_evidence"
    assert block["campaign_binding"]["campaign_id"] == "camp-1"
    assert block["content_intelligence"]["intelligence_type"] == "content_intelligence_not_performance"
    assert "family protection / planning ahead" in [t["theme"] for t in block["content_intelligence"]["themes"]]
    assert "trusted advisor / community connector" in [t["theme"] for t in block["content_intelligence"]["themes"]]
    assert any("Pre-Need" in item["insight"] for item in block["insight_bullets"])
    assert block["campaign_signal"]["campaign_id"] == "camp-1"
    assert "Lead, message, call, form, or revenue attribution" in block["not_available"]



def test_meta_page_insights_report_requires_credentials():
    module = _load_module()

    attempt, result = module.MetaPageInsightsReportModule().execute_tool_result({})

    assert attempt["status"] == "failed"
    assert result["block"]["reason_code"] == "missing_credentials"
