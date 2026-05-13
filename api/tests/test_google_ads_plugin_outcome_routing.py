from __future__ import annotations

from registry import list_all
from skills.router import route_chat_skills


GOOGLE_ADS_READ = "marketing.channel.google_ads.performance.read"
GMAIL_DRAFT = "marketing.channel.gmail.outreach.draft"


def _ensure_plugins_loaded() -> None:
    list_all()


def test_google_ads_read_request_routes_to_read_only_plugin() -> None:
    _ensure_plugins_loaded()
    routed = route_chat_skills("check google ads performance")

    assert GOOGLE_ADS_READ in routed.module_ids


def test_google_ads_generation_or_control_request_does_not_route_to_read_only_plugin() -> None:
    _ensure_plugins_loaded()

    assert GOOGLE_ADS_READ not in route_chat_skills("create google ads campaign").module_ids
    assert GOOGLE_ADS_READ not in route_chat_skills("change google ads budget").module_ids
    assert GOOGLE_ADS_READ not in route_chat_skills("turn on google ads campaign").module_ids


def test_mixed_email_and_google_ads_sample_routes_only_installed_draft_artifact() -> None:
    _ensure_plugins_loaded()
    routed = route_chat_skills("show me sample email and google ads")

    assert GMAIL_DRAFT in routed.module_ids
    assert GOOGLE_ADS_READ not in routed.module_ids
