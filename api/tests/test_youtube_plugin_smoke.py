import asyncio
import pytest

from api.plugins.youtube.module import YouTubeModule
from api.plugins.youtube.capabilities.marketing.channel.youtube.connection.validate.module import (
    YouTubeConnectionValidateModule,
)
from api.plugins.youtube.capabilities.marketing.channel.youtube.video.publish.module import (
    YouTubeVideoPublishModule,
)
from plugin_loader import get_plugin_for_module
from registry import get_module, list_all
from skills.router import route_chat_skills

@pytest.mark.asyncio
async def test_youtube_publish_proposal():
    module = YouTubeModule()
    brief = {
        "module_id": "youtube.publish_video",
        "video_file": "test_video.mp4",
        "generated_title": "Test Title",
        "generated_description": "Test Description"
    }
    result = await module.execute(brief)
    assert result["artifact_type"] == "youtube_publish_proposal"
    assert result["payload"]["title"] == "Test Title"
    assert result["status"] == "pending_review"

@pytest.mark.asyncio
async def test_youtube_publish_execute():
    module = YouTubeModule()
    brief = {
        "module_id": "youtube.publish_video",
        "action": "execute",
        "_channel_credentials": {"access_token": "mock_token"},
        "proposal": {
            "video_file": "test_video.mp4",
            "title": "Test Title"
        }
    }
    result = await module.execute(brief)
    assert result["artifact_type"] == "youtube_action_result"
    assert result["payload"]["status"] == "success"
    assert "youtube.com/watch" in result["payload"]["url"]

@pytest.mark.asyncio
async def test_youtube_update_channel_proposal():
    module = YouTubeModule()
    brief = {
        "module_id": "youtube.update_channel",
        "current_description": "Old desc",
        "generated_description": "New desc"
    }
    result = await module.execute(brief)
    assert result["artifact_type"] == "youtube_channel_update_proposal"
    assert result["payload"]["proposed"] == "New desc"

@pytest.mark.asyncio
async def test_youtube_analytics():
    module = YouTubeModule()
    brief = {
        "module_id": "youtube.analytics",
        "_channel_credentials": {"access_token": "mock_token"}
    }
    result = await module.execute(brief)
    assert result["artifact_type"] == "video_intelligence"
    assert "channel_summary" in result["payload"]


def test_youtube_connection_validator_registered_in_plugin_pipeline():
    module_cls = get_module("marketing.channel.youtube.connection.validate")
    assert module_cls is not None
    assert module_cls.id == "marketing.channel.youtube.connection.validate"

    plugin = get_plugin_for_module("marketing.channel.youtube.connection.validate")
    assert plugin is not None
    assert plugin.manifest.plugin_id == "channel.youtube"
    assert plugin.manifest.requires_social_connection == ["youtube"]


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
    assert plugin.manifest.requires_social_connection == ["youtube"]


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
        "conversation_context": "USER: old video_url: http://old.example/video.mp4 title: Old\nUSER: Post this YouTube video: video_url: http://example.com/video.mp4 title: BOS YouTube upload test description: Private test upload from Klaroha CMO chat. privacy: private",
    })
    assert attempt["status"] == "succeeded"
    assert seen["url"] == "http://example.com/video.mp4"
    assert captured["snippet"]["title"] == "BOS YouTube upload test"
    assert captured["status"]["privacyStatus"] == "private"
    assert result["block"]["video_id"] == "inline123"

if __name__ == "__main__":
    async def main():
        print("Running YouTube plugin smoke tests...")
        await test_youtube_publish_proposal()
        await test_youtube_publish_execute()
        await test_youtube_update_channel_proposal()
        await test_youtube_analytics()
        test_youtube_connection_validator_registered_in_plugin_pipeline()
        test_youtube_connection_validator_missing_credentials()
        test_youtube_connection_validator_success_without_mutation()
        test_youtube_publish_registered_for_cmo_chat()
        test_cmo_chat_phrase_routes_to_youtube_publish()
        test_youtube_publish_missing_video_blocks_cleanly()
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            test_youtube_publish_api_path_mocked(Path(d))
            test_youtube_publish_reads_inline_cmo_fields(Path(d))
        print("All YouTube plugin smoke tests passed!")
    asyncio.run(main())
    print("All smoke tests passed!")
