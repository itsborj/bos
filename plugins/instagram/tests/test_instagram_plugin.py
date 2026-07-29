from __future__ import annotations

import asyncio
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

from plugin_loader import get_plugin_for_module
from provider_auth import InstagramOAuthHandler
from registry import get_module


MODULE_ID = "marketing.channel.instagram.connection.validate"
OFFICIAL_CONNECTION_SCOPES = {
    "instagram_basic",
    "pages_show_list",
}


def _settings():
    return SimpleNamespace(
        frontend_url="https://hq.klaroha.com",
        meta_app_id="",
        meta_redirect_uri="",
    )


def test_instagram_oauth_requests_only_official_connection_scopes():
    start = asyncio.run(
        InstagramOAuthHandler().start_login(
            _settings(),
            overrides={"META_APP_ID": "2498513223943482"},
        )
    )
    query = parse_qs(urlparse(start.authorize_url).query)

    assert set(query["scope"][0].split(",")) == OFFICIAL_CONNECTION_SCOPES
    assert "instagram_content_publish" not in query["scope"][0]
    assert "pages_read_user_content" not in query["scope"][0]
    assert start.redirect_uri == "https://hq.klaroha.com/social/instagram/callback"


def test_instagram_business_login_config_replaces_ad_hoc_scopes():
    start = asyncio.run(
        InstagramOAuthHandler().start_login(
            _settings(),
            overrides={
                "META_APP_ID": "2498513223943482",
                "META_INSTAGRAM_CONFIG_ID": "config_123",
            },
        )
    )
    query = parse_qs(urlparse(start.authorize_url).query)

    assert query["config_id"] == ["config_123"]
    assert "scope" not in query


def test_instagram_validator_registered_to_instagram_plugin():
    module_cls = get_module(MODULE_ID)
    assert module_cls is not None
    assert module_cls.id == MODULE_ID

    plugin = get_plugin_for_module(MODULE_ID)
    assert plugin is not None
    assert plugin.manifest.plugin_id == "channel.instagram"
    assert any(
        slot.type == "social_token" and slot.platform == "instagram"
        for slot in plugin.manifest.credential_slots
    )


def test_instagram_validator_missing_credentials_is_read_only():
    module_cls = get_module(MODULE_ID)
    attempt, result = module_cls().execute_tool_result({})

    assert attempt["status"] == "failed"
    assert result["block"]["reason_code"] == "missing_credentials"
    assert result["block"]["read_only"] is True
    assert result["block"]["changed_resources"] == []


def test_instagram_validator_reads_profile_without_mutation():
    module_cls = get_module(MODULE_ID)
    module = module_cls()
    module._get_json = lambda url, token: {
        "id": "17841400000000000",
        "username": "klarohahq",
        "name": "Klaroha HQ",
        "account_type": "BUSINESS",
        "followers_count": 120,
        "follows_count": 25,
        "media_count": 9,
    }

    attempt, result = module.execute_tool_result(
        {
            "_channel_credentials": {
                "instagram_page_token": "mock_page_token",
                "instagram_page_id": "17841400000000000",
            }
        }
    )

    assert attempt["status"] == "succeeded"
    assert result["block"]["type"] == "instagram_connection_check"
    assert result["block"]["account"]["username"] == "klarohahq"
    assert result["block"]["read_only"] is True
    assert result["block"]["changed_resources"] == []
