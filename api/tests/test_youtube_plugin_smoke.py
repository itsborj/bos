import asyncio
import pytest
from api.plugins.youtube.module import YouTubeModule

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

if __name__ == "__main__":
    async def main():
        print("Running YouTube plugin smoke tests...")
        await test_youtube_publish_proposal()
        await test_youtube_publish_execute()
        await test_youtube_update_channel_proposal()
        await test_youtube_analytics()
        print("All YouTube plugin smoke tests passed!")
    asyncio.run(main())
    print("All smoke tests passed!")
