from __future__ import annotations

import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from klaroha_sdk import ChannelModule

_GRAPH = "https://graph.facebook.com/v21.0"


class MetaPostsPublishModule(ChannelModule):
    id = "marketing.channel.meta.posts.publish"
    name = "Facebook Post Publish"
    vertical = "marketing"
    capability = "marketing.execute"
    platform_hint = "facebook post publish"
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
            "content": f"Failed to publish Facebook post: {message}",
            "sell_price": None,
            "block": {
                "type": "fb_page_post_result",
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

    def _post_json(self, url: str, payload: dict) -> dict:
        data = urlencode(payload).encode("utf-8")
        req = Request(url, data=data, method="POST")
        with urlopen(req, timeout=35) as resp:
            return json.loads(resp.read().decode("utf-8"))

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

            message = str(brief.get("message", "")).strip()
            if not message:
                return self._failure(start, "missing_message", "brief must include message (the approved post text)")

            link = brief.get("link") or None

            payload: dict = {"message": message, "access_token": token}
            if link:
                payload["link"] = link

            result = self._post_json(f"{_GRAPH}/{page_id}/feed", payload)

            post_id = result.get("id", "")
            permalink = f"https://www.facebook.com/{post_id.replace('_', '/posts/')}" if post_id else None

            content = (
                f"# Facebook Post Published\n\n"
                f"{message[:200]}{'…' if len(message) > 200 else ''}\n\n"
                f"Post ID: {post_id}"
            )

            return self._attempt(start, "succeeded"), {
                "content": content,
                "sell_price": None,
                "block": {
                    "type": "fb_page_post_result",
                    "platform": "facebook",
                    "status": "succeeded",
                    "post_id": post_id,
                    "page_id": page_id,
                    "message_preview": message[:280],
                    "permalink": permalink,
                    "changed_resources": [post_id],
                    "allowed_actions": ["view_on_facebook", "dismiss"],
                },
            }

        except HTTPError as exc:
            try:
                body = exc.read().decode("utf-8")[:400]
            except Exception:
                body = ""
            return self._failure(start, "api_call_failed", f"Graph API returned HTTP {exc.code}", {"http_status": exc.code, "response": body})
        except URLError as exc:
            return self._failure(start, "api_call_failed", "Network error calling Meta Graph API", {"error": str(exc)})
        except Exception as exc:
            return self._failure(start, "api_call_failed", "Unexpected error publishing post", {"error": str(exc)})

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        failures = []
        lowered = content.lower() if isinstance(content, str) else ""
        if "published" not in lowered and "post id" not in lowered:
            failures.append("missing_publish_confirmation")
        return ("fail" if failures else "pass"), failures
