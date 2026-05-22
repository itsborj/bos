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


def test_facebook_post_for_review_routes_to_draft_not_publish() -> None:
    _ensure_plugins_loaded()
    routed = route_chat_skills(
        "draft a Facebook post for dormant prospects and generate a matching visual direction"
    )

    assert "marketing.channel.meta.posts.draft" in routed.module_ids
    assert "marketing.channel.meta.posts.publish" not in routed.module_ids
