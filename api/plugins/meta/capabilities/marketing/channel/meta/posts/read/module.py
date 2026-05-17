from __future__ import annotations

import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from klaroha_sdk import ChannelModule

_GRAPH = "https://graph.facebook.com/v21.0"
_POST_FIELDS = "id,message,story,created_time,full_picture,permalink_url,likes.summary(true),comments.summary(true),shares"


class MetaPostsReadModule(ChannelModule):
    id = "marketing.channel.meta.posts.read"
    name = "Meta Page Posts"
    vertical = "marketing"
    capability = "marketing.optimize"
    platform_hint = "facebook posts read"
    policy_default = "read_only"
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
            "content": f"Failed to read Facebook posts: {message}",
            "sell_price": None,
            "block": {
                "type": "meta_page_posts",
                "status": "failed",
                "reason_code": reason_code,
                "message": message,
                "details": details or {},
                "read_only": True,
                "changed_resources": [],
            },
        }

    def _creds(self, brief: dict) -> dict:
        raw = brief.get("_channel_credentials", {}) if isinstance(brief, dict) else {}
        return raw if isinstance(raw, dict) else {}

    def _get_json(self, url: str) -> dict:
        req = Request(url)
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def execute_tool_result(self, brief: dict) -> tuple[dict, dict]:
        start = time.perf_counter()
        try:
            creds = self._creds(brief)
            token = creds.get("facebook_page_token") or creds.get("page_token") or creds.get("access_token")
            page_id = creds.get("facebook_page_id") or creds.get("page_id")
            limit = min(int(brief.get("limit", 10)), 25)

            if not token:
                return self._failure(start, "missing_credentials", "Facebook page token not connected")
            if not page_id:
                return self._failure(start, "missing_credentials", "Facebook page ID not found")

            url = f"{_GRAPH}/{page_id}/posts?fields={_POST_FIELDS}&limit={limit}&access_token={token}"
            data = self._get_json(url)

            posts = []
            for p in data.get("data", []):
                posts.append({
                    "post_id": p.get("id", ""),
                    "message": p.get("message") or p.get("story") or "",
                    "created_time": p.get("created_time", ""),
                    "permalink": p.get("permalink_url"),
                    "image": p.get("full_picture"),
                    "likes": (p.get("likes") or {}).get("summary", {}).get("total_count", 0),
                    "comments": (p.get("comments") or {}).get("summary", {}).get("total_count", 0),
                    "shares": (p.get("shares") or {}).get("count", 0),
                })

            if not posts:
                content = "No posts found on this Facebook Page."
            else:
                lines = [f"# Recent Facebook Posts ({len(posts)} shown)\n"]
                for p in posts[:5]:
                    preview = p["message"][:120] + "…" if len(p["message"]) > 120 else p["message"]
                    lines.append(f"- **{p['created_time'][:10]}** — {preview or '(no text)'} · ❤️ {p['likes']} 💬 {p['comments']}")
                content = "\n".join(lines)

            return self._attempt(start, "succeeded"), {
                "content": content,
                "sell_price": None,
                "block": {
                    "type": "meta_page_posts",
                    "platform": "facebook",
                    "page_id": page_id,
                    "status": "succeeded",
                    "posts": posts,
                    "read_only": True,
                    "changed_resources": [],
                    "allowed_actions": ["draft_post", "dismiss"],
                },
            }

        except HTTPError as exc:
            try:
                body = exc.read().decode("utf-8")[:300]
            except Exception:
                body = ""
            return self._failure(start, "api_call_failed", f"Graph API returned HTTP {exc.code}", {"response": body})
        except URLError as exc:
            return self._failure(start, "api_call_failed", "Network error calling Meta Graph API", {"error": str(exc)})
        except Exception as exc:
            return self._failure(start, "api_call_failed", "Unexpected error reading posts", {"error": str(exc)})

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        failures = []
        if "facebook" not in content.lower() and "posts" not in content.lower() and "no posts" not in content.lower():
            failures.append("missing_posts_content")
        return ("fail" if failures else "pass"), failures
