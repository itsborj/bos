from __future__ import annotations

import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from klaroha_sdk import ChannelModule

_GRAPH = "https://graph.facebook.com/v21.0"


class MetaVideoPublishModule(ChannelModule):
    id = "marketing.channel.meta.video.publish"
    name = "Facebook Video Publish"
    vertical = "marketing"
    capability = "marketing.execute"
    platform_hint = "facebook video publish"
    policy_default = "approval_gated"
    template = ""

    max_chars = 0
    must_mention = []
    banned_phrases = []

    def _latency_ms(self, start: float) -> int:
        return round((time.perf_counter() - start) * 1000)

    def _attempt(self, start: float, status: str, error: str | None = None) -> dict:
        return {
            "provider": "meta",
            "model_id": "meta_graph_api_v21",
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
            "content": f"Failed to publish Facebook video: {message}",
            "sell_price": None,
            "block": {
                "type": "fb_page_video_result",
                "platform": "facebook",
                "status": "failed",
                "reason_code": reason_code,
                "message": message,
                "details": details or {},
                "changed_resources": [],
            },
        }

    def _creds(self, brief: dict) -> dict:
        raw = brief.get("_channel_credentials", {}) if isinstance(brief, dict) else {}
        return raw if isinstance(raw, dict) else {}

    def _post_video_binary(self, url: str, video_data: bytes, mime: str, fields: dict) -> dict:
        boundary = b"klaroha_fb_video_boundary_7c3e2a"
        body = b""
        for key, val in fields.items():
            body += b"--" + boundary + b"\r\n"
            body += f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode()
            body += str(val).encode() + b"\r\n"
        body += b"--" + boundary + b"\r\n"
        body += b'Content-Disposition: form-data; name="source"; filename="video.mp4"\r\n'
        body += f"Content-Type: {mime}\r\n\r\n".encode()
        body += video_data + b"\r\n"
        body += b"--" + boundary + b"--\r\n"
        req = Request(url, data=body, method="POST")
        req.add_header("Content-Type", f"multipart/form-data; boundary={boundary.decode()}")
        with urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _description_from_brief(self, brief: dict) -> str:
        for key in ("description", "caption", "post_text", "message", "hook_text"):
            value = str(brief.get(key, "")).strip()
            if value:
                return value
        return ""

    def execute_tool_result(self, brief: dict) -> tuple[dict, dict]:
        start = time.perf_counter()
        try:
            if not isinstance(brief, dict):
                return self._failure(start, "invalid_brief", "brief must be a dictionary")

            creds = self._creds(brief)
            token = creds.get("facebook_page_token") or creds.get("page_token") or creds.get("access_token")
            page_id = creds.get("facebook_page_id") or creds.get("page_id")

            if not token:
                return self._failure(start, "missing_credentials", "Facebook page token not connected")
            if not page_id:
                return self._failure(start, "missing_credentials", "Facebook page ID not found")

            video_path = str(brief.get("video_path") or "").strip()
            if not video_path:
                return self._failure(start, "missing_video", "No video_path in brief — ensure the video was generated first")
            if not os.path.exists(video_path):
                return self._failure(
                    start, "video_not_found",
                    f"Video file not found at {video_path} — it may have been cleaned up. Re-generate the video."
                )

            description = self._description_from_brief(brief)
            title = str(brief.get("title") or brief.get("hook_text") or "").strip()[:255] or "Shortform video"

            with open(video_path, "rb") as fh:
                video_data = fh.read()

            fields: dict = {"access_token": token, "published": "true"}
            if description:
                fields["description"] = description[:2200]
            if title:
                fields["title"] = title

            result = self._post_video_binary(
                f"{_GRAPH}/{page_id}/videos",
                video_data,
                "video/mp4",
                fields,
            )

            video_id = str(result.get("id", ""))
            permalink = f"https://www.facebook.com/{video_id}" if video_id else None

            content = (
                f"# Facebook Video Published\n\n"
                f"{description[:200]}{'…' if len(description) > 200 else ''}\n\n"
                f"Video ID: {video_id}"
            )

            return self._attempt(start, "succeeded"), {
                "content": content,
                "sell_price": None,
                "block": {
                    "type": "fb_page_video_result",
                    "platform": "facebook",
                    "status": "succeeded",
                    "video_id": video_id,
                    "page_id": page_id,
                    "description_preview": description[:280],
                    "permalink": permalink,
                    "changed_resources": [video_id],
                    "allowed_actions": ["view_on_facebook", "dismiss"],
                },
            }

        except HTTPError as exc:
            try:
                body = exc.read().decode("utf-8")[:400]
            except Exception:
                body = ""
            return self._failure(
                start, "api_call_failed",
                f"Graph API returned HTTP {exc.code}",
                {"http_status": exc.code, "response": body},
            )
        except URLError as exc:
            return self._failure(start, "api_call_failed", "Network error calling Meta Graph API", {"error": str(exc)})
        except Exception as exc:
            return self._failure(start, "api_call_failed", "Unexpected error publishing video", {"error": str(exc)})

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        failures = []
        lowered = content.lower() if isinstance(content, str) else ""
        if "published" not in lowered and "video id" not in lowered:
            failures.append("missing_publish_confirmation")
        return ("fail" if failures else "pass"), failures
