from __future__ import annotations

from capability_manifest import build_dispatchable_manifest
from skills.loader import list_skill_manifests
from skills.router import route_chat_skills


def test_campaign_plan_visible_manifest_defers_launch_to_gtm() -> None:
    entry = next(e for e in build_dispatchable_manifest() if e.module_id == "marketing.plan.campaign_strategy")
    visible = " ".join(entry.excluded_triggers[:8]).lower()

    assert "gtm" in visible
    assert "launch" in visible
    assert "market entry" in visible
    assert "plan for" not in entry.triggers


def test_gtm_plan_visible_manifest_owns_launch_language() -> None:
    entry = next(e for e in build_dispatchable_manifest() if e.module_id == "marketing.planning.gtm_plan")
    visible = " ".join(entry.triggers[:8]).lower()

    assert "gtm" in visible
    assert "launch" in visible
    assert "plan a launch" in visible
    assert "market entry" in visible


def test_google_tag_manager_does_not_activate_for_go_to_market_gtm() -> None:
    routed = route_chat_skills("Create a GTM launch strategy for this brand")
    skill_ids = {route.skill.id for route in routed.routes}

    assert "marketing.planning.gtm_plan" in skill_ids
    assert "marketing.analytics.google_tag_manager" not in skill_ids


def test_shorthand_another_gtm_routes_to_go_to_market_plan() -> None:
    routed = route_chat_skills("lets do another gtm")
    skill_ids = {route.skill.id for route in routed.routes}

    assert "marketing.planning.gtm_plan" in skill_ids
    assert "marketing.analytics.google_tag_manager" not in skill_ids


def test_need_gtm_with_brand_name_routes_to_go_to_market_plan() -> None:
    routed = route_chat_skills("this is from Mactan Group, need gtm")
    skill_ids = {route.skill.id for route in routed.routes}

    assert "marketing.planning.gtm_plan" in skill_ids
    assert "marketing.analytics.google_tag_manager" not in skill_ids


def test_campaign_skill_body_names_gtm_handoff() -> None:
    skill = next(s for s in list_skill_manifests() if s.id == "marketing.plan.campaign_strategy")

    assert "marketing.planning.gtm_plan" in skill.description
    assert "launch strategy" in skill.excluded_triggers
    assert "launch plan" in skill.excluded_triggers
    assert "gtm plan" in skill.excluded_triggers
