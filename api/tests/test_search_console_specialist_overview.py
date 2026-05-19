from __future__ import annotations

import registry
from skills.loader import list_skill_manifests
from skills.router import route_chat_skills


SEARCH_CONSOLE_MODULE_IDS = {
    "marketing.channel.search_console.properties.list",
    "marketing.channel.search_console.performance.query",
    "marketing.channel.search_console.url.inspect",
    "marketing.channel.search_console.sitemaps.read",
    "marketing.channel.search_console.opportunities.plan",
}


def _ensure_plugins_registered() -> None:
    registry.list_all()


def test_search_console_specialist_overview_is_loaded() -> None:
    _ensure_plugins_registered()
    skills = {skill.id: skill for skill in list_skill_manifests()}

    skill = skills["workspace.search_console_specialist_overview"]

    assert skill.allowed_from_chat is True
    assert skill.module_id is None
    assert "discussion" in skill.requires_intent
    assert "generation" in skill.requires_intent
    assert "what can you do with search console" in skill.triggers
    assert "what do i need for search console" in skill.triggers


def test_search_console_capability_question_routes_to_overview_only() -> None:
    _ensure_plugins_registered()
    routed = route_chat_skills("what can you do with search console")

    route_ids = [route.skill.id for route in routed.routes]

    assert "workspace.search_console_specialist_overview" in route_ids
    assert SEARCH_CONSOLE_MODULE_IDS.isdisjoint(set(routed.module_ids))


def test_search_console_setup_question_routes_to_overview_only() -> None:
    _ensure_plugins_registered()
    routed = route_chat_skills("what do I need for Search Console setup")

    route_ids = [route.skill.id for route in routed.routes]

    assert "workspace.search_console_specialist_overview" in route_ids
    assert SEARCH_CONSOLE_MODULE_IDS.isdisjoint(set(routed.module_ids))


def test_explicit_search_console_performance_still_routes_to_module() -> None:
    _ensure_plugins_registered()
    routed = route_chat_skills("check search console performance")

    assert "marketing.channel.search_console.performance.query" in routed.module_ids
    assert "workspace.search_console_specialist_overview" not in [route.skill.id for route in routed.routes]
