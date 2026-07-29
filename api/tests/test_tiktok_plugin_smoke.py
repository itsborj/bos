try:
    from api.plugins.tiktok.capabilities.marketing.channel.tiktok.connection.validate.module import (
        TikTokConnectionValidateModule,
    )
    from api.plugins.tiktok.capabilities.marketing.channel.tiktok.video.publish.module import (
        TikTokVideoPublishModule,
    )
except ModuleNotFoundError:  # api container runs tests from /app
    from plugins.tiktok.capabilities.marketing.channel.tiktok.connection.validate.module import (
        TikTokConnectionValidateModule,
    )
    from plugins.tiktok.capabilities.marketing.channel.tiktok.video.publish.module import (
        TikTokVideoPublishModule,
    )
from plugin_loader import get_plugin_for_module
from registry import get_module, list_all
from skills.router import route_chat_skills


def test_tiktok_connection_validator_registered_in_plugin_pipeline():
    module_cls = get_module("marketing.channel.tiktok.connection.validate")
    assert module_cls is not None
    assert module_cls.id == "marketing.channel.tiktok.connection.validate"

    plugin = get_plugin_for_module("marketing.channel.tiktok.connection.validate")
    assert plugin is not None
    assert plugin.manifest.plugin_id == "channel.tiktok"
    social_token_platforms = [
        s.platform for s in plugin.manifest.credential_slots
        if s.type == "social_token" and s.platform
    ]
    assert "tiktok" in social_token_platforms


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
    module._post_json = lambda url, headers, payload: {
        "data": {
            "privacy_level_options": ["SELF_ONLY", "MUTUAL_FOLLOW_FRIENDS"],
            "comment_disabled": False,
            "duet_disabled": False,
            "stitch_disabled": True,
            "max_video_post_duration_sec": 300,
        },
        "error": {"code": "ok", "message": "", "log_id": "1"},
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


def test_tiktok_connection_skill_routes_from_cmo_chat():
    list_all()
    routed = route_chat_skills("Please test my TikTok connection for this brand")
    assert "marketing.channel.tiktok.connection.validate" in routed.module_ids


def test_tiktok_publish_registered_for_cmo_chat():
    module_cls = get_module("marketing.channel.tiktok.video.publish")
    assert module_cls is not None
    plugin = get_plugin_for_module("marketing.channel.tiktok.video.publish")
    assert plugin is not None
    social_token_platforms = [
        s.platform for s in plugin.manifest.credential_slots
        if s.type == "social_token" and s.platform
    ]
    assert "tiktok" in social_token_platforms


def test_cmo_chat_phrase_routes_to_tiktok_publish():
    list_all()
    assert "marketing.channel.tiktok.video.publish" in route_chat_skills(
        "we can post tiktok videos from cmo chat"
    ).module_ids


def test_tiktok_publish_missing_video_blocks_cleanly():
    module = TikTokVideoPublishModule()
    attempt, result = module.execute_tool_result({"_channel_credentials": {"access_token": "mock_token"}})
    assert attempt["status"] == "failed"
    assert result["block"]["reason_code"] == "missing_video"


def test_tiktok_publish_api_path_mocked(tmp_path):
    video = tmp_path / "short.mp4"
    video.write_bytes(b"fake mp4 bytes")
    module = TikTokVideoPublishModule()
    module._creator_info = lambda token: {
        "data": {
            "creator_username": "klaroha",
            "privacy_level_options": ["SELF_ONLY", "PUBLIC_TO_EVERYONE"],
        },
        "error": {"code": "ok", "message": "", "log_id": "1"},
    }
    module._init_publish = lambda token, payload: {
        "data": {
            "publish_id": "v_pub_file~v2-1.123456789",
            "upload_url": "https://upload.example/session",
        },
        "error": {"code": "ok", "message": "", "log_id": "2"},
    }
    module._upload_video = lambda upload_url, path, content_type: None
    module._fetch_status = lambda token, publish_id: {
        "data": {
            "status": "PUBLISH_COMPLETE",
            "publicaly_available_post_id": ["7355551112223334444"],
        },
        "error": {"code": "ok", "message": "", "log_id": "3"},
    }
    attempt, result = module.execute_tool_result({
        "_channel_credentials": {"access_token": "mock_token"},
        "video_file": str(video),
        "title": "Test TikTok",
        "privacy": "private",
    })
    assert attempt["status"] == "succeeded"
    assert result["block"]["type"] == "tiktok_publish_result"
    assert result["block"]["publish_id"] == "v_pub_file~v2-1.123456789"
    assert result["block"]["changed_resources"] == ["7355551112223334444"]


def test_tiktok_publish_reads_inline_cmo_fields(tmp_path):
    video = tmp_path / "short.mp4"
    video.write_bytes(b"fake mp4 bytes")
    module = TikTokVideoPublishModule()
    seen = {}

    def fake_download(url):
        seen["url"] = url
        return str(video)

    module._download = fake_download
    module._creator_info = lambda token: {
        "data": {
            "creator_username": "klaroha",
            "privacy_level_options": ["SELF_ONLY", "PUBLIC_TO_EVERYONE"],
        },
        "error": {"code": "ok", "message": "", "log_id": "1"},
    }
    captured = {}

    def start_publish(token, payload):
        captured.update(payload)
        return {
            "data": {
                "publish_id": "v_pub_file~v2-inline",
                "upload_url": "https://upload.example/session",
            },
            "error": {"code": "ok", "message": "", "log_id": "2"},
        }

    module._init_publish = start_publish
    module._upload_video = lambda upload_url, path, content_type: None
    module._fetch_status = lambda token, publish_id: {
        "data": {
            "status": "PUBLISH_COMPLETE",
            "publicaly_available_post_id": ["7355551112223334444"],
        },
        "error": {"code": "ok", "message": "", "log_id": "3"},
    }
    attempt, result = module.execute_tool_result({
        "_channel_credentials": {"access_token": "mock_token"},
        "conversation_context": (
            "USER: old video_url: http://old.example/video.mp4 title: Old\n"
            "USER: Post this TikTok video: video_url: http://example.com/video.mp4 "
            "title: BOS TikTok upload test description: Private test upload from Klaroha CMO chat. privacy: private"
        ),
    })
    assert attempt["status"] == "succeeded"
    assert seen["url"] == "http://example.com/video.mp4"
    assert captured["post_info"]["title"] == "BOS TikTok upload test\n\nPrivate test upload from Klaroha CMO chat."
    assert captured["post_info"]["privacy_level"] == "SELF_ONLY"
    assert result["block"]["publish_id"] == "v_pub_file~v2-inline"
