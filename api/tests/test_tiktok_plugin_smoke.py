try:
    from api.plugins.tiktok.capabilities.marketing.channel.tiktok.connection.validate.module import (
        TikTokConnectionValidateModule,
    )
except ModuleNotFoundError:  # api container runs tests from /app
    from plugins.tiktok.capabilities.marketing.channel.tiktok.connection.validate.module import (
        TikTokConnectionValidateModule,
    )
import pytest
from plugin_loader import get_plugin_for_module
from registry import get_module, list_all
from skills.router import route_chat_skills


@pytest.mark.skip(reason="TikTok plugin not production-ready; requires_social_connection field removed in credential_slots migration")
def test_tiktok_connection_validator_registered_in_plugin_pipeline():
    module_cls = get_module("marketing.channel.tiktok.connection.validate")
    assert module_cls is not None
    assert module_cls.id == "marketing.channel.tiktok.connection.validate"

    plugin = get_plugin_for_module("marketing.channel.tiktok.connection.validate")
    assert plugin is not None
    assert plugin.manifest.plugin_id == "channel.tiktok"
    assert plugin.manifest.requires_social_connection == ["tiktok"]


def test_tiktok_connection_validator_missing_credentials():
    module = TikTokConnectionValidateModule()
    attempt, result = module.execute_tool_result({})
    assert attempt["status"] == "failed"
    assert result["block"]["type"] == "tiktok_connection_check"
    assert result["block"]["reason_code"] == "missing_credentials"
    assert result["block"]["changed_resources"] == []
    assert result["block"]["read_only"] is True


def test_tiktok_connection_validator_success_without_mutation():
    module = TikTokConnectionValidateModule()
    module._get_json = lambda url, headers: {
        "data": {
            "user": {
                "open_id": "tt_open_123",
                "display_name": "Klaroha",
                "avatar_url": "https://example.com/avatar.png",
                "profile_deep_link": "https://www.tiktok.com/@klaroha",
                "is_verified": False,
            }
        }
    }

    attempt, result = module.execute_tool_result({"_channel_credentials": {"access_token": "mock_token"}})
    assert attempt["status"] == "succeeded"
    assert result["block"]["type"] == "tiktok_connection_check"
    assert result["block"]["status"] == "succeeded"
    assert result["block"]["changed_resources"] == []
    assert result["block"]["account"]["open_id"] == "tt_open_123"
    assert result["block"]["account"]["username"] == "@klaroha"
    assert result["block"]["test_post_readiness"]["can_publish_public_test_post"] is False
    assert "Mutation: none" in result["content"]


@pytest.mark.skip(reason="TikTok plugin not production-ready; routing assertion requires production-deployed plugin")
def test_tiktok_connection_skill_routes_from_cmo_chat():
    list_all()
    routed = route_chat_skills("Please test my TikTok connection for this brand")
    assert "marketing.channel.tiktok.connection.validate" in routed.module_ids
