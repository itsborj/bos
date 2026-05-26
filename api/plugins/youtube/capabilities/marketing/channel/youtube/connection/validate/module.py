from __future__ import annotations

import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from klaroha_sdk import ChannelModule

_YOUTUBE_API = "https://www.googleapis.com/youtube/v3"


class YouTubeConnectionValidateModule(ChannelModule):
    """Read-only YouTube Data API connection validator."""

    id = "marketing.channel.youtube.connection.validate"
    name = "YouTube Connection Validate"
    vertical = "marketing"
    capability = "marketing.optimize"
    platform_hint = "youtube connection"
    policy_default = "read_only"
    template = ""

    max_chars = 0
    must_mention = []
    banned_phrases = []

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
            "content": (
                "Failed to validate YouTube connection: "
                + message
                + "\n\nRead-only note: no YouTube videos, playlists, channel fields, thumbnails, or comments were changed."
            ),
            "sell_price": None,
            "block": {
                "type": "youtube_connection_check",
                "platform": "youtube",
                "status": "failed",
                "reason_code": reason_code,
                "message": message,
                "details": details or {},
                "read_only": True,
                "changed_resources": [],
                "allowed_actions": ["connect_youtube", "retry", "dismiss"],
            },
        }

    def _creds(self, brief: dict) -> dict:
        raw = brief.get("_channel_credentials", {}) if isinstance(brief, dict) else {}
        return raw if isinstance(raw, dict) else {}

    def _get_json(self, url: str, headers: dict) -> dict:
        request = Request(url, headers=headers, method="GET")
        with urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}

    def _channel_summary(self, item: dict, injected_page_id: str | None) -> dict:
        snippet = item.get("snippet") or {}
        statistics = item.get("statistics") or {}
        status = item.get("status") or {}
        channel_id = str(item.get("id") or injected_page_id or "")
        return {
            "channel_id": channel_id,
            "title": str(snippet.get("title") or ""),
            "custom_url": str(snippet.get("customUrl") or ""),
            "published_at": str(snippet.get("publishedAt") or ""),
            "privacy_status": str(status.get("privacyStatus") or ""),
            "made_for_kids": bool(status.get("madeForKids")) if "madeForKids" in status else None,
            "view_count": str(statistics.get("viewCount") or ""),
            "subscriber_count": str(statistics.get("subscriberCount") or ""),
            "video_count": str(statistics.get("videoCount") or ""),
        }

    def execute_tool_result(self, brief: dict) -> tuple[dict, dict]:
        start = time.perf_counter()
        try:
            if not isinstance(brief, dict):
                return self._failure(start, "invalid_brief", "brief must be a dictionary")

            creds = self._creds(brief)
            token = creds.get("youtube_page_token") or creds.get("page_token") or creds.get("access_token")
            page_id = creds.get("youtube_page_id") or creds.get("page_id")
            if not token:
                return self._failure(start, "missing_credentials", "YouTube OAuth access token is not connected for this brand")

            params = urlencode({"part": "id,snippet,statistics,status", "mine": "true"})
            data = self._get_json(
                f"{_YOUTUBE_API}/channels?{params}",
                {"Authorization": f"Bearer {token}", "Accept": "application/json"},
            )
            items = data.get("items") or []
            if not items:
                return self._failure(start, "no_channel_returned", "YouTube API returned no channel for the connected account", {"page_id": page_id})

            channel = self._channel_summary(items[0], page_id)
            quota = {"endpoint": "channels.list", "estimated_units": 1}
            content = (
                "# YouTube Connection Validated\n\n"
                f"Channel: {channel.get('title') or channel.get('channel_id')}\n"
                f"Channel ID: {channel.get('channel_id')}\n"
                "API: YouTube Data API v3 channels.list\n"
                "Mutation: none — read-only validation only"
            )
            return self._attempt(start, "succeeded"), {
                "content": content,
                "sell_price": None,
                "block": {
                    "type": "youtube_connection_check",
                    "platform": "youtube",
                    "status": "succeeded",
                    "read_only": True,
                    "channel": channel,
                    "quota": quota,
                    "changed_resources": [],
                    "allowed_actions": ["view_channel", "dismiss"],
                },
            }

        except HTTPError as exc:
            try:
                body = exc.read().decode("utf-8")[:600]
            except Exception:
                body = ""
            reason = "quota_or_permission_error" if exc.code in {403, 429} else "api_call_failed"
            return self._failure(start, reason, f"YouTube API returned HTTP {exc.code}", {"http_status": exc.code, "response": body})
        except URLError as exc:
            return self._failure(start, "api_call_failed", "Network error calling YouTube Data API", {"error": str(exc)})
        except Exception as exc:
            return self._failure(start, "api_call_failed", "Unexpected error validating YouTube connection", {"error": str(exc)})

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        failures: list[str] = []
        lowered = content.lower() if isinstance(content, str) else ""
        if "youtube connection validated" not in lowered and "failed to validate youtube connection" not in lowered:
            failures.append("missing_connection_validation_summary")
        if "mutation: none" not in lowered and "read-only note" not in lowered:
            failures.append("missing_read_only_boundary")
        return ("fail" if failures else "pass"), failures
