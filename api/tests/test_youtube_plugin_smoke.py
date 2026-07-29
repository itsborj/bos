from plugins.youtube.capabilities.marketing.channel.youtube.connection.validate.module import (
    YouTubeConnectionValidateModule,
)
from plugins.youtube.capabilities.marketing.channel.youtube.video.publish.module import (
    YouTubeVideoPublishModule,
)
from plugin_loader import get_plugin_for_module
from registry import get_module, list_all
from skills.router import route_chat_skills


def test_youtube_connection_validator_registered_in_plugin_pipeline():
    module_cls = get_module("marketing.channel.youtube.connection.validate")
    assert module_cls is not None
    assert module_cls.id == "marketing.channel.youtube.connection.validate"

    plugin = get_plugin_for_module("marketing.channel.youtube.connection.validate")
    assert plugin is not None
    assert plugin.manifest.plugin_id == "channel.youtube"
    social_token_platforms = [
        s.platform for s in plugin.manifest.credential_slots
        if s.type == "social_token" and s.platform
    ]
    assert "youtube" in social_token_platforms


def test_youtube_connection_validator_missing_credentials():
    module = YouTubeConnectionValidateModule()
    attempt, result = module.execute_tool_result({})
    assert attempt["status"] == "failed"
    assert result["block"]["type"] == "youtube_connection_check"
    assert result["block"]["reason_code"] == "missing_credentials"
    assert result["block"]["changed_resources"] == []


def test_youtube_connection_validator_success_without_mutation():
    module = YouTubeConnectionValidateModule()
    module._get_json = lambda url, headers: {
        "items": [
            {
                "id": "UC123",
                "snippet": {"title": "Klaroha Official", "customUrl": "@klaroha"},
                "statistics": {"viewCount": "100", "subscriberCount": "10", "videoCount": "3"},
                "status": {"privacyStatus": "public"},
            }
        ]
    }

    attempt, result = module.execute_tool_result({"_channel_credentials": {"access_token": "mock_token"}})
    assert attempt["status"] == "succeeded"
    assert result["block"]["type"] == "youtube_connection_check"
    assert result["block"]["status"] == "succeeded"
    assert result["block"]["changed_resources"] == []
    assert result["block"]["channel"]["channel_id"] == "UC123"
    assert "Mutation: none" in result["content"]


def test_youtube_publish_registered_for_cmo_chat():
    module_cls = get_module("marketing.channel.youtube.video.publish")
    assert module_cls is not None
    plugin = get_plugin_for_module("marketing.channel.youtube.video.publish")
    assert plugin is not None
    social_token_platforms = [
        s.platform for s in plugin.manifest.credential_slots
        if s.type == "social_token" and s.platform
    ]
    assert "youtube" in social_token_platforms


def test_cmo_chat_phrase_routes_to_youtube_publish():
    list_all()
    assert "marketing.channel.youtube.video.publish" in route_chat_skills(
        "we can post youtube videos from cmo chat"
    ).module_ids


def test_youtube_publish_missing_video_blocks_cleanly():
    module = YouTubeVideoPublishModule()
    attempt, result = module.execute_tool_result({"_channel_credentials": {"access_token": "mock_token"}})
    assert attempt["status"] == "failed"
    assert result["block"]["reason_code"] == "missing_video"


def test_youtube_publish_api_path_mocked(tmp_path):
    video = tmp_path / "short.mp4"
    video.write_bytes(b"fake mp4 bytes")
    module = YouTubeVideoPublishModule()
    module._start_resumable_upload = lambda token, metadata, content_type, size: "https://upload.example/session"
    module._put_video = lambda upload_url, path, content_type: {"id": "abc123"}
    attempt, result = module.execute_tool_result({
        "_channel_credentials": {"access_token": "mock_token"},
        "video_file": str(video),
        "title": "Test Short",
        "privacy": "private",
    })
    assert attempt["status"] == "succeeded"
    assert result["block"]["type"] == "youtube_publish_result"
    assert result["block"]["video_id"] == "abc123"
    assert result["block"]["changed_resources"] == ["abc123"]


def test_youtube_publish_defaults_to_public(tmp_path):
    video = tmp_path / "short.mp4"
    video.write_bytes(b"fake mp4 bytes")
    module = YouTubeVideoPublishModule()
    captured = {}

    def start_upload(token, metadata, content_type, size):
        captured.update(metadata)
        return "https://upload.example/session"

    module._start_resumable_upload = start_upload
    module._put_video = lambda upload_url, path, content_type: {"id": "public123"}
    attempt, result = module.execute_tool_result({
        "_channel_credentials": {"access_token": "mock_token"},
        "video_file": str(video),
        "title": "Test Short",
    })
    assert attempt["status"] == "succeeded"
    assert captured["status"]["privacyStatus"] == "public"
    assert result["block"]["privacy_status"] == "public"


def test_youtube_publish_reads_inline_cmo_fields(tmp_path):
    video = tmp_path / "short.mp4"
    video.write_bytes(b"fake mp4 bytes")
    module = YouTubeVideoPublishModule()
    seen = {}
    def fake_download(url):
        seen["url"] = url
        return str(video)
    module._download = fake_download
    captured = {}
    def start_upload(token, metadata, content_type, size):
        captured.update(metadata)
        return "https://upload.example/session"
    module._start_resumable_upload = start_upload
    module._put_video = lambda upload_url, path, content_type: {"id": "inline123"}
    attempt, result = module.execute_tool_result({
        "_channel_credentials": {"access_token": "mock_token"},
        "conversation_context": (
            "USER: old video_url: http://old.example/video.mp4 title: Old\n"
            "USER: Post this YouTube video: video_url: http://example.com/video.mp4 "
            "title: BOS YouTube upload test description: Private test upload from Klaroha CMO chat. privacy: private"
        ),
    })
    assert attempt["status"] == "succeeded"
    assert seen["url"] == "http://example.com/video.mp4"
    assert captured["snippet"]["title"] == "BOS YouTube upload test"
    assert captured["status"]["privacyStatus"] == "private"
    assert result["block"]["video_id"] == "inline123"


