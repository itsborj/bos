from __future__ import annotations

import base64
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _load_publish_module():
    module_path = Path(__file__).resolve().parents[2] / "plugins/meta/capabilities/marketing/channel/meta/posts/publish/module.py"
    spec = importlib.util.spec_from_file_location("meta_posts_publish_for_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _load_draft_module():
    module_path = Path(__file__).resolve().parents[2] / "plugins/meta/capabilities/marketing/channel/meta/posts/draft/module.py"
    spec = importlib.util.spec_from_file_location("meta_posts_draft_for_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _brief(**extra):
    data = {
        "_channel_credentials": {
            "facebook_page_token": "page-token",
            "facebook_page_id": "12345",
        },
        "message": "Approved copy for a scheduled Facebook post.",
    }
    data.update(extra)
    return data


def test_meta_draft_declares_schedule_action_when_page_connected():
    module = _load_draft_module()

    block = module.MetaPostsDraftModule()._build_block("Approved draft copy", {
        "_channel_credentials": {"facebook_page_id": "12345", "facebook_page_name": "Test Page"}
    })

    assert "schedule_facebook" in block["allowed_actions"]
    assert block["action_modules"]["schedule_facebook"] == "marketing.channel.meta.posts.publish"



def test_meta_publish_schedules_feed_post(monkeypatch):
    module = _load_publish_module()
    scheduled_at = (datetime.now(timezone.utc) + timedelta(days=1)).replace(microsecond=0)
    captured = {}

    def fake_post_json(self, url, payload):
        captured["url"] = url
        captured["payload"] = payload
        return {"id": "12345_67890"}

    monkeypatch.setattr(module.MetaPostsPublishModule, "_post_json", fake_post_json)

    attempt, result = module.MetaPostsPublishModule().execute_tool_result(_brief(scheduled_at=scheduled_at.isoformat()))

    assert attempt["status"] == "succeeded"
    assert result["block"]["status"] == "scheduled"
    assert result["block"]["scheduled_publish_time"] == int(scheduled_at.timestamp())
    assert captured["url"].endswith("/12345/feed")
    assert captured["payload"]["published"] == "false"
    assert captured["payload"]["scheduled_publish_time"] == str(int(scheduled_at.timestamp()))


def test_meta_publishes_image_url_as_feed_image_link_post(monkeypatch):
    module = _load_publish_module()
    captured = {}

    def fake_post_json(self, url, payload):
        captured["url"] = url
        captured["payload"] = payload
        return {"id": "12345_222"}

    monkeypatch.setattr(module.MetaPostsPublishModule, "_post_json", fake_post_json)

    attempt, result = module.MetaPostsPublishModule().execute_tool_result(_brief(
        image_url="https://example.com/klaroha-test-image.png",
    ))

    assert attempt["status"] == "succeeded"
    assert result["block"]["status"] == "succeeded"
    assert captured["url"].endswith("/12345/feed")
    assert captured["payload"] == {
        "message": "Approved copy for a scheduled Facebook post.",
        "link": "https://example.com/klaroha-test-image.png",
        "access_token": "page-token",
    }
    assert "media_fbid" not in result["block"]
    assert result["block"]["post_id"] == "12345_222"



def test_meta_publishes_photo_as_feed_post(monkeypatch):
    module = _load_publish_module()
    captured = {"json_calls": []}

    def fake_photo_binary(self, url, image_data, mime, fields):
        captured["photo_url"] = url
        captured["image_data"] = image_data
        captured["mime"] = mime
        captured["fields"] = fields
        return {"id": "media_111"}

    def fake_post_json(self, url, payload):
        captured["json_calls"].append({"url": url, "payload": payload})
        return {"id": "12345_111"}

    monkeypatch.setattr(module.MetaPostsPublishModule, "_post_photo_binary", fake_photo_binary)
    monkeypatch.setattr(module.MetaPostsPublishModule, "_post_json", fake_post_json)

    attempt, result = module.MetaPostsPublishModule().execute_tool_result(_brief(
        image_data_b64=base64.b64encode(b"fake image bytes").decode("ascii"),
        mime_type="image/jpeg",
    ))

    assert attempt["status"] == "succeeded"
    assert result["block"]["status"] == "succeeded"
    assert captured["photo_url"].endswith("/12345/photos")
    assert captured["fields"] == {"access_token": "page-token", "published": "false"}
    assert captured["json_calls"][-1]["url"].endswith("/12345/feed")
    assert captured["json_calls"][-1]["payload"]["message"] == "Approved copy for a scheduled Facebook post."
    assert captured["json_calls"][-1]["payload"]["attached_media[0]"] == '{"media_fbid": "media_111"}'
    assert "published" not in captured["json_calls"][-1]["payload"]
    assert result["block"]["post_id"] == "12345_111"
    assert result["block"]["media_fbid"] == "media_111"


def test_meta_publish_schedules_photo_as_feed_post(monkeypatch):
    module = _load_publish_module()
    scheduled_at = datetime.now(timezone.utc) + timedelta(days=2)
    captured = {"json_calls": []}

    def fake_photo_binary(self, url, image_data, mime, fields):
        captured["photo_url"] = url
        captured["image_data"] = image_data
        captured["mime"] = mime
        captured["fields"] = fields
        return {"id": "media_98765"}

    def fake_post_json(self, url, payload):
        captured["json_calls"].append({"url": url, "payload": payload})
        return {"id": "12345_98765"}

    monkeypatch.setattr(module.MetaPostsPublishModule, "_post_photo_binary", fake_photo_binary)
    monkeypatch.setattr(module.MetaPostsPublishModule, "_post_json", fake_post_json)

    attempt, result = module.MetaPostsPublishModule().execute_tool_result(_brief(
        scheduled_at=scheduled_at.isoformat(),
        image_data_b64=base64.b64encode(b"fake image bytes").decode("ascii"),
        mime_type="image/jpeg",
    ))

    assert attempt["status"] == "succeeded"
    assert result["block"]["status"] == "scheduled"
    assert captured["photo_url"].endswith("/12345/photos")
    assert captured["image_data"] == b"fake image bytes"
    assert captured["mime"] == "image/jpeg"
    assert captured["fields"]["published"] == "false"
    assert "message" not in captured["fields"]
    assert "scheduled_publish_time" not in captured["fields"]
    assert captured["json_calls"][-1]["url"].endswith("/12345/feed")
    assert captured["json_calls"][-1]["payload"]["attached_media[0]"] == '{"media_fbid": "media_98765"}'
    assert captured["json_calls"][-1]["payload"]["published"] == "false"
    assert captured["json_calls"][-1]["payload"]["scheduled_publish_time"] == str(result["block"]["scheduled_publish_time"])
    assert result["block"]["media_fbid"] == "media_98765"


def test_meta_publish_rejects_schedule_action_without_time():
    module = _load_publish_module()

    attempt, result = module.MetaPostsPublishModule().execute_tool_result(_brief(action="schedule_facebook", artifact_action="schedule_facebook"))

    assert attempt["status"] == "failed"
    assert attempt["error"] == "missing_schedule_time"
    assert result["block"]["reason_code"] == "missing_schedule_time"



def test_meta_publish_rejects_too_soon_schedule():
    module = _load_publish_module()
    scheduled_at = datetime.now(timezone.utc) + timedelta(minutes=2)

    attempt, result = module.MetaPostsPublishModule().execute_tool_result(_brief(scheduled_at=scheduled_at.isoformat()))

    assert attempt["status"] == "failed"
    assert attempt["error"] == "invalid_schedule"
    assert result["block"]["reason_code"] == "invalid_schedule"
