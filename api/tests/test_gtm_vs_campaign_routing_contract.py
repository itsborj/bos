from __future__ import annotations

from capability_manifest import build_dispatchable_manifest
from skills.loader import list_skill_manifests
from skills.router import route_chat_skills


def test_campaign_strategy_retired_absent_from_dispatchable_manifest() -> None:
    # campaign_strategy was retired (allowed_from_chat: false) in favour of
    # marketing.planning.strategy_workflow; it must not appear in the live capability list.
    manifest_ids = {e.module_id for e in build_dispatchable_manifest()}
    assert "marketing.plan.campaign_strategy" not in manifest_ids


def test_legacy_gtm_plan_retired_absent_from_dispatchable_manifest() -> None:
    manifest_ids = {e.module_id for e in build_dispatchable_manifest()}
    assert "marketing.planning.gtm_plan" not in manifest_ids


def test_strategy_workflow_visible_manifest_owns_launch_and_marketing_plan_language() -> None:
    entry = next(e for e in build_dispatchable_manifest() if e.module_id == "marketing.planning.strategy_workflow")
    visible = " ".join(entry.triggers).lower()

    assert "gtm" in visible
    assert "launch" in visible
    assert "plan a launch" in visible
    assert "market entry" in visible
    assert "marketing plan" in visible


def test_google_tag_manager_does_not_activate_for_go_to_market_gtm() -> None:
    routed = route_chat_skills("Create a GTM launch strategy for this brand")
    skill_ids = {route.skill.id for route in routed.routes}

    assert "marketing.planning.strategy_workflow" in skill_ids
    assert "marketing.analytics.google_tag_manager" not in skill_ids


def test_shorthand_another_gtm_routes_to_strategy_workflow() -> None:
    routed = route_chat_skills("lets do another gtm")
    skill_ids = {route.skill.id for route in routed.routes}

    assert "marketing.planning.strategy_workflow" in skill_ids
    assert "marketing.analytics.google_tag_manager" not in skill_ids


def test_need_gtm_with_brand_name_routes_to_strategy_workflow() -> None:
    routed = route_chat_skills("this is from Mactan Group, need gtm")
    skill_ids = {route.skill.id for route in routed.routes}

    assert "marketing.planning.strategy_workflow" in skill_ids
    assert "marketing.analytics.google_tag_manager" not in skill_ids


def test_marketing_plan_routes_to_strategy_workflow() -> None:
    routed = route_chat_skills("Create a marketing plan for this brand")
    skill_ids = {route.skill.id for route in routed.routes}

    assert "marketing.planning.strategy_workflow" in skill_ids


def test_campaign_strategy_retired_absent_from_skill_manifests() -> None:
    # Retired skills must not appear in list_skill_manifests() (status: retired
    # or allowed_from_chat: false drops them from the loader's active set).
    skill_ids = {s.id for s in list_skill_manifests()}
    assert "marketing.plan.campaign_strategy" not in skill_ids
    assert "marketing.planning.gtm_plan" not in skill_ids
