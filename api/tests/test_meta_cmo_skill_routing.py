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


def test_facebook_post_with_visual_routes_to_creative_for_review() -> None:
    _ensure_plugins_loaded()
    # "Make a Facebook post with visual" → creative.post.image for operator review.
    # Approval is mandatory — never route direct to publish for creative requests.
    routed = route_chat_skills(
        "make a Facebook post for dormant prospects with a matching visual"
    )

    assert "creative.post.image" in routed.module_ids
    assert "marketing.channel.meta.posts.publish" not in routed.module_ids


def test_copy_only_request_routes_to_draft() -> None:
    _ensure_plugins_loaded()
    # Explicit copy-only still goes to the draft capability.
    routed = route_chat_skills("just write facebook copy only, no image")

    assert "marketing.channel.meta.posts.draft" in routed.module_ids
