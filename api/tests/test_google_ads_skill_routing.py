from __future__ import annotations

import registry
from capability_manifest import build_dispatchable_manifest
from skills.router import route_chat_skills


MODULE_ID = "marketing.channel.google_ads.performance.read"


def _ensure_plugins_registered() -> None:
    # Plugin skill roots are registered as part of registry scanning.
    registry.list_all()


def test_google_ads_performance_read_is_manifest_dispatchable() -> None:
    _ensure_plugins_registered()
    entries = {entry.module_id: entry for entry in build_dispatchable_manifest()}

    assert MODULE_ID in entries
    assert "diagnostic" in entries[MODULE_ID].requires_intent
    assert "google ads performance" in entries[MODULE_ID].triggers


def test_explicit_google_ads_performance_routes_to_read_module() -> None:
    _ensure_plugins_registered()
    routed = route_chat_skills("check google ads performance")

    assert "diagnostic" in routed.intents
    assert MODULE_ID in routed.module_ids


def test_generic_mcp_system_question_does_not_route_to_google_ads_module() -> None:
    _ensure_plugins_registered()
    routed = route_chat_skills("check mcp system for my system")

    assert "diagnostic" in routed.intents
    assert MODULE_ID not in routed.module_ids
