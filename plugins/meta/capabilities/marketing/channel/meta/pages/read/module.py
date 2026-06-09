from __future__ import annotations

import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from klaroha_sdk import ChannelModule

_GRAPH = "https://graph.facebook.com/v21.0"
_PAGE_FIELDS = "id,name,category,fan_count,link,picture.type(normal),instagram_business_account"


class MetaPagesReadModule(ChannelModule):
    id = "marketing.channel.meta.pages.read"
    name = "Meta Page Info"
    vertical = "marketing"
    capability = "marketing.optimize"
    platform_hint = "facebook pages read"
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
            "content": f"Failed to read Facebook page: {message}",
            "sell_price": None,
            "block": {
                "type": "meta_page_inventory",
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

    def _get_json(self, url: str, token: str) -> dict:
        req = Request(url, headers={"Authorization": f"Bearer {token}"})
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def execute_tool_result(self, brief: dict) -> tuple[dict, dict]:
        start = time.perf_counter()
        try:
            creds = self._creds(brief)
            token = creds.get("facebook_page_token") or creds.get("page_token") or creds.get("access_token")
            page_id = creds.get("facebook_page_id") or creds.get("page_id")

            if not token:
                return self._failure(start, "missing_credentials", "Facebook page token not connected — link a Facebook Page in Brand settings")
            if not page_id:
                return self._failure(start, "missing_credentials", "Facebook page ID not found — reconnect the Facebook Page in Brand settings")

            data = self._get_json(f"{_GRAPH}/{page_id}?fields={_PAGE_FIELDS}&access_token={token}", token)

            page = {
                "page_id": data.get("id", page_id),
                "name": data.get("name", ""),
                "category": data.get("category", ""),
                "followers": data.get("fan_count", 0),
                "url": data.get("link", ""),
                "picture": (data.get("picture") or {}).get("data", {}).get("url"),
                "ig_business_account_id": (data.get("instagram_business_account") or {}).get("id"),
            }

            content = (
                f"# Facebook Page\n\n"
                f"**{page['name']}** — {page['category']}\n"
                f"Followers: {page['followers']:,}\n"
                + (f"Instagram: linked (ID {page['ig_business_account_id']})\n" if page["ig_business_account_id"] else "")
            )

            return self._attempt(start, "succeeded"), {
                "content": content,
                "sell_price": None,
                "block": {
                    "type": "meta_page_inventory",
                    "platform": "facebook",
                    "status": "succeeded",
                    "pages": [page],
                    "read_only": True,
                    "changed_resources": [],
                    "allowed_actions": ["view_posts", "draft_post", "dismiss"],
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
            return self._failure(start, "api_call_failed", "Unexpected error reading page", {"error": str(exc)})

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        failures = []
        if "facebook page" not in content.lower() and "followers" not in content.lower():
            failures.append("missing_page_info")
        return ("fail" if failures else "pass"), failures
