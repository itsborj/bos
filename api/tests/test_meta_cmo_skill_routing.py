from __future__ import annotations

from registry import list_all
from skills.router import route_chat_skills


def _ensure_plugins_loaded() -> None:
    list_all()


def test_explicit_publish_command_with_copy_routes_to_publish() -> None:
    _ensure_plugins_loaded()
    # Operator provides explicit publish command with the post text inline.
    routed = route_chat_skills(
        "post this to facebook: BOS is live — testing our infrastructure."
    )

    assert "marketing.channel.meta.posts.publish" in routed.module_ids
    assert "marketing.channel.meta.posts.draft" not in routed.module_ids



def test_copy_only_request_routes_to_draft() -> None:
    _ensure_plugins_loaded()
    # Explicit copy-only still goes to the draft capability.
    routed = route_chat_skills("just write facebook copy only, no image")

    assert "marketing.channel.meta.posts.draft" in routed.module_ids


def test_page_insights_report_routes_to_meta_report_not_postcraft() -> None:
    _ensure_plugins_loaded()
    routed = route_chat_skills("generate a Facebook page insights report")

    assert "marketing.channel.meta.pages.insights.report" in routed.module_ids
    assert "postcraft.render" not in routed.module_ids


def test_generic_report_request_does_not_route_to_meta_report() -> None:
    _ensure_plugins_loaded()
    routed = route_chat_skills("let me have report")

    assert "marketing.channel.meta.pages.insights.report" not in routed.module_ids
