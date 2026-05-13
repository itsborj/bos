from __future__ import annotations

from registry import list_all
from skills.router import route_chat_skills


def _ensure_plugins_loaded() -> None:
    # Startup does this in the app lifespan; tests call it explicitly so plugin
    # SKILL.md files are registered before routing assertions.
    list_all()


def test_email_capability_question_routes_to_overview_only() -> None:
    _ensure_plugins_loaded()
    routed = route_chat_skills("what can you do with email")

    assert "discussion" in routed.intents
    assert "workspace.email_specialist_overview" in [route.skill.id for route in routed.routes]
    assert "marketing.email.campaign_plan" not in routed.module_ids
    assert "marketing.channel.gmail.outreach.draft" not in routed.module_ids
    assert "marketing.channel.gmail_auth.email.receive" not in routed.module_ids
    assert "marketing.channel.gmail_auth.email.send" not in routed.module_ids


def test_email_plan_request_routes_to_plan_artifact() -> None:
    _ensure_plugins_loaded()
    routed = route_chat_skills("plan an email campaign for dormant leads")

    assert "marketing.email.campaign_plan" in routed.module_ids
    assert "marketing.channel.gmail.outreach.draft" not in routed.module_ids
    assert "marketing.channel.gmail_auth.email.send" not in routed.module_ids


def test_email_draft_request_routes_to_draft_artifact() -> None:
    _ensure_plugins_loaded()
    routed = route_chat_skills("draft an email for dormant leads")

    assert "marketing.channel.gmail.outreach.draft" in routed.module_ids
    assert "marketing.channel.gmail_auth.email.send" not in routed.module_ids
