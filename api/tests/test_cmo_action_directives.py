from __future__ import annotations

from routers import chat as chat_router


def test_action_directive_is_hidden_from_visible_reply() -> None:
    raw = """SCOPE:
conversation_brand: Klaroha
execution_brand: Klaroha
mode: single_brand_action
confidence: high

Publishing the approved artifact now.
ACTION: 11111111-1111-1111-1111-111111111111 publish
"""

    assert chat_router._extract_action_directives(raw) == [
        ("11111111-1111-1111-1111-111111111111", "publish")
    ]
    visible = chat_router._strip_control_directives(raw)

    assert "ACTION:" not in visible
    assert "SCOPE:" not in visible
    assert "Publishing the approved artifact now." in visible


def test_actionable_artifact_directive_does_not_look_like_run_directive() -> None:
    raw = "ACTION: 22222222-2222-2222-2222-222222222222 send"

    assert chat_router._RUN_RE.findall(raw) == []
    assert chat_router._extract_action_directives(raw) == [
        ("22222222-2222-2222-2222-222222222222", "send")
    ]


def test_artifact_actions_require_latest_user_authorization() -> None:
    assert chat_router._user_authorized_artifact_action("Create a GTM launch strategy") is False
    assert chat_router._user_authorized_artifact_action("Approve that plan and go ahead") is True
    assert chat_router._user_authorized_artifact_action("send the approved email") is True


def test_duplicate_run_directives_are_deduped_per_turn() -> None:
    assert chat_router._dedupe_preserve_order([
        "marketing.planning.gtm_plan",
        "marketing.planning.gtm_plan",
        "marketing.email.sequence",
    ]) == ["marketing.planning.gtm_plan", "marketing.email.sequence"]
