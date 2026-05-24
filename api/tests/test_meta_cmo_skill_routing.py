from __future__ import annotations

from registry import list_all
from skills.router import route_chat_skills


def _ensure_plugins_loaded() -> None:
    list_all()


def test_direct_facebook_test_post_routes_to_publish_not_draft() -> None:
    _ensure_plugins_loaded()
    routed = route_chat_skills(
        "lets post facebook test for mactan group text only will do no image, just testing"
    )

    assert "marketing.channel.meta.posts.publish" in routed.module_ids
    assert "marketing.channel.meta.posts.draft" not in routed.module_ids


def test_facebook_post_with_visual_routes_to_bundle_not_split() -> None:
    _ensure_plugins_loaded()
    # A complete post (copy + visual) is ONE bundle (creative.post.image),
    # not a separate copy draft, and never an unrequested publish.
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
