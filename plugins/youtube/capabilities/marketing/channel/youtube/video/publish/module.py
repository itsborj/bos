from __future__ import annotations

import json
import mimetypes
import os
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from klaroha_sdk import ChannelModule

_UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"


class YouTubeVideoPublishModule(ChannelModule):
    id = "marketing.channel.youtube.video.publish"
    name = "YouTube Video Publish"
    vertical = "marketing"
    capability = "marketing.execute"
    platform_hint = "youtube video publish"
    policy_default = "approval_gated"
    template = ""

    def _latency_ms(self, start: float) -> int:
        return round((time.perf_counter() - start) * 1000)

    def _attempt(self, start: float, status: str, error: str | None = None) -> dict:
        return {
            "provider": "youtube",
            "model_id": "youtube_data_api_v3",
            "mode": "tool",
            "status": status,
            "tokens_input": 0,
            "tokens_output": 0,
            "provider_cost": 0.0,
            "latency_ms": self._latency_ms(start),
            "error": error,
        }

    def _failure(self, start: float, reason_code: str, message: str, details: dict | None = None) -> tuple[dict, dict]:
        return self._attempt(start, "failed", reason_code), {
            "content": "YouTube publish failed: " + message,
            "sell_price": None,
            "block": {
                "type": "youtube_publish_result",
                "platform": "youtube",
                "status": "failed",
                "reason_code": reason_code,
                "message": message,
                "details": details or {},
                "changed_resources": [],
                "allowed_actions": ["retry", "dismiss"],
            },
        }

    def _creds(self, brief: dict) -> dict:
        raw = brief.get("_channel_credentials", {}) if isinstance(brief, dict) else {}
        return raw if isinstance(raw, dict) else {}

    def _download(self, url: str) -> str:
        suffix = Path(url.split("?", 1)[0]).suffix or ".mp4"
        fd, path = tempfile.mkstemp(prefix="youtube_upload_", suffix=suffix)
        os.close(fd)
        req = Request(url, headers={"User-Agent": "Klaroha/1.0"}, method="GET")
        with urlopen(req, timeout=120) as response, open(path, "wb") as fh:
            fh.write(response.read())
        return path

    def _field_from_context(self, brief: dict, key: str) -> str:
        import re

        ctx = str(brief.get("conversation_context") or brief.get("request") or "")
        pattern = re.compile(
            rf"\b{re.escape(key)}\s*:\s*(.*?)(?=\s+\b(?:video_url|video_file|video_path|asset_url|title|description|privacy|privacy_status)\s*:|$)",
            re.IGNORECASE | re.DOTALL,
        )
        matches = list(pattern.finditer(ctx))
        return matches[-1].group(1).strip() if matches else ""

    def _brief_value(self, brief: dict, *keys: str) -> str:
        for key in keys:
            value = brief.get(key)
            if value:
                return str(value).strip()
        for key in keys:
            value = self._field_from_context(brief, key)
            if value:
                return value
        return ""

    def _video_path(self, brief: dict) -> tuple[str | None, bool]:
        path = self._brief_value(brief, "video_file", "video_path")
        if path:
            return path, False
        url = self._brief_value(brief, "video_url", "asset_url")
        if url:
            return self._download(url), True
        return None, False

    def _start_resumable_upload(self, token: str, metadata: dict, content_type: str, size: int) -> str:
        params = urlencode({"uploadType": "resumable", "part": "snippet,status"})
        req = Request(
            f"{_UPLOAD_URL}?{params}",
            data=json.dumps(metadata).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=UTF-8",
                "X-Upload-Content-Type": content_type,
                "X-Upload-Content-Length": str(size),
            },
            method="POST",
        )
        with urlopen(req, timeout=45) as response:
            location = response.headers.get("Location")
        if not location:
            raise RuntimeError("YouTube did not return an upload session URL")
        return location

    def _put_video(self, upload_url: str, path: str, content_type: str) -> dict:
        with open(path, "rb") as fh:
            data = fh.read()
        req = Request(
            upload_url,
            data=data,
            headers={"Content-Type": content_type, "Content-Length": str(len(data))},
            method="PUT",
        )
        with urlopen(req, timeout=300) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}

    def execute_tool_result(self, brief: dict) -> tuple[dict, dict]:
        start = time.perf_counter()
        temp_path: str | None = None
        try:
            if not isinstance(brief, dict):
                return self._failure(start, "invalid_brief", "brief must be a dictionary")

            token = self._creds(brief).get("youtube_page_token") or self._creds(brief).get("page_token") or self._creds(brief).get("access_token")
            if not token:
                return self._failure(start, "missing_credentials", "Connect YouTube for this brand first")

            path, is_temp = self._video_path(brief)
            temp_path = path if is_temp else None
            if not path:
                return self._failure(start, "missing_video", "Send a video_file, video_path, video_url, or asset_url")
            if not os.path.exists(path):
                return self._failure(start, "video_not_found", f"Video file not found: {path}")

            title = (self._brief_value(brief, "title", "video_title") or "Klaroha video")[:100]
            description = self._brief_value(brief, "description", "video_description")
            tags_raw = brief.get("tags") or self._field_from_context(brief, "tags") or ""
            tags = tags_raw if isinstance(tags_raw, list) else [t.strip() for t in str(tags_raw).split(",") if t.strip()]
            privacy = (self._brief_value(brief, "privacy", "privacy_status") or "public").lower()
            if privacy not in {"private", "unlisted", "public"}:
                privacy = "public"

            size = os.path.getsize(path)
            content_type = mimetypes.guess_type(path)[0] or "video/mp4"
            metadata = {
                "snippet": {"title": title, "description": description, "tags": tags, "categoryId": str(brief.get("category_id") or "22")},
                "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": bool(brief.get("made_for_kids", False))},
            }

            upload_url = self._start_resumable_upload(token, metadata, content_type, size)
            data = self._put_video(upload_url, path, content_type)
            video_id = str(data.get("id") or "")
            if not video_id:
                return self._failure(start, "api_call_failed", "YouTube upload completed without returning a video ID", {"response": data})

            url = f"https://www.youtube.com/watch?v={video_id}"
            return self._attempt(start, "succeeded"), {
                "content": f"YouTube video published.\n\nTitle: {title}\nURL: {url}",
                "sell_price": None,
                "block": {
                    "type": "youtube_publish_result",
                    "platform": "youtube",
                    "status": "succeeded",
                    "video_id": video_id,
                    "url": url,
                    "title": title,
                    "privacy_status": privacy,
                    "changed_resources": [video_id],
                    "allowed_actions": ["view_on_youtube", "dismiss"],
                },
            }

        except HTTPError as exc:
            try:
                body = exc.read().decode("utf-8")[:800]
            except Exception:
                body = ""
            return self._failure(start, "api_call_failed", f"YouTube API returned HTTP {exc.code}", {"http_status": exc.code, "response": body})
        except (URLError, OSError, RuntimeError) as exc:
            return self._failure(start, "api_call_failed", str(exc))
        finally:
            if temp_path:
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        failures: list[str] = []
        lowered = content.lower() if isinstance(content, str) else ""
        if "youtube video published" not in lowered and "youtube publish failed" not in lowered:
            failures.append("missing_youtube_publish_status")
        return ("fail" if failures else "pass"), failures
