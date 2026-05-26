from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from klaroha_sdk import ChannelModule

_TIKTOK_API = "https://open.tiktokapis.com/v2"
_TIKTOK_FIELDS = "open_id,union_id,avatar_url,display_name,profile_deep_link,is_verified"


class TikTokConnectionValidateModule(ChannelModule):
    """Read-only TikTok Open API connection validator."""

    id = "marketing.channel.tiktok.connection.validate"
    name = "TikTok Connection Validate"
    vertical = "marketing"
    capability = "marketing.optimize"
    platform_hint = "tiktok connection"
    policy_default = "read_only"
    template = ""

    max_chars = 0
    must_mention = []
    banned_phrases = []

    def _latency_ms(self, start: float) -> int:
        return round((time.perf_counter() - start) * 1000)

    def _attempt(self, start: float, status: str, error: str | None = None) -> dict:
        return {
            "provider": "tiktok",
            "model_id": "tiktok_open_api_v2",
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
                "Failed to validate TikTok connection: "
                + message
                + "\n\nRead-only note: no TikTok videos, posts, schedules, comments, follows, ads, budgets, pixels, or profile fields were changed."
            ),
            "sell_price": None,
            "block": {
                "type": "tiktok_connection_check",
                "platform": "tiktok",
                "status": "failed",
                "reason_code": reason_code,
                "message": message,
                "details": details or {},
                "read_only": True,
                "changed_resources": [],
                "allowed_actions": ["connect_tiktok", "retry", "dismiss"],
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

    def _account_summary(self, data: dict, injected_page_id: str | None) -> dict:
        user = (data.get("data") or {}).get("user") or data.get("user") or {}
        open_id = str(user.get("open_id") or injected_page_id or "")
        profile_url = str(user.get("profile_deep_link") or "")
        username = ""
        if profile_url and "/@" in profile_url:
            username = "@" + profile_url.rsplit("/@", 1)[-1].split("?", 1)[0].strip("/")
        return {
            "open_id": open_id,
            "union_id": str(user.get("union_id") or ""),
            "display_name": str(user.get("display_name") or ""),
            "username": username,
            "avatar_url": str(user.get("avatar_url") or ""),
            "profile_url": profile_url,
            "is_verified": bool(user.get("is_verified")) if "is_verified" in user else None,
        }

    def execute_tool_result(self, brief: dict) -> tuple[dict, dict]:
        start = time.perf_counter()
        try:
            if not isinstance(brief, dict):
                return self._failure(start, "invalid_brief", "brief must be a dictionary")

            creds = self._creds(brief)
            token = creds.get("tiktok_page_token") or creds.get("page_token") or creds.get("access_token")
            page_id = creds.get("tiktok_page_id") or creds.get("page_id")
            if not token:
                return self._failure(start, "missing_credentials", "TikTok OAuth access token is not connected for this brand")

            params = urlencode({"fields": _TIKTOK_FIELDS})
            endpoint = f"{_TIKTOK_API}/user/info/?{params}"
            data = self._get_json(
                endpoint,
                {"Authorization": f"Bearer {token}", "Accept": "application/json"},
            )
            account = self._account_summary(data, page_id)
            if not account.get("open_id"):
                return self._failure(start, "no_account_returned", "TikTok API returned no account identity for the connected token", {"page_id": page_id})

            checked_at = datetime.now(timezone.utc).isoformat()
            content = (
                "# TikTok Connection Validated\n\n"
                f"Account: {account.get('username') or account.get('display_name') or account.get('open_id')}\n"
                f"Open ID: {account.get('open_id')}\n"
                "API: TikTok Open API v2 user/info\n"
                "Mutation: none — read-only validation only"
            )
            return self._attempt(start, "succeeded"), {
                "content": content,
                "sell_price": None,
                "block": {
                    "type": "tiktok_connection_check",
                    "platform": "tiktok",
                    "status": "succeeded",
                    "read_only": True,
                    "account": account,
                    "api_check": {
                        "endpoint": "user/info",
                        "checked_at": checked_at,
                    },
                    "test_post_readiness": {
                        "can_read_account": True,
                        "can_prepare_test_post_draft": True,
                        "can_publish_public_test_post": False,
                        "publish_blocker": "Publishing requires explicit approval, an attached video asset, and approved TikTok Content Posting API scopes.",
                    },
                    "changed_resources": [],
                    "allowed_actions": ["view_account", "create_test_post_draft", "dismiss"],
                },
            }

        except HTTPError as exc:
            try:
                body = exc.read().decode("utf-8")[:600]
            except Exception:
                body = ""
            reason = "quota_or_permission_error" if exc.code in {403, 429} else "api_call_failed"
            return self._failure(start, reason, f"TikTok API returned HTTP {exc.code}", {"http_status": exc.code, "response": body})
        except URLError as exc:
            return self._failure(start, "api_call_failed", "Network error calling TikTok Open API", {"error": str(exc)})
        except Exception as exc:
            return self._failure(start, "api_call_failed", "Unexpected error validating TikTok connection", {"error": str(exc)})

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        failures: list[str] = []
        lowered = content.lower() if isinstance(content, str) else ""
        if "tiktok connection validated" not in lowered and "failed to validate tiktok connection" not in lowered:
            failures.append("missing_connection_validation_summary")
        if "mutation: none" not in lowered and "read-only note" not in lowered:
            failures.append("missing_read_only_boundary")
        return ("fail" if failures else "pass"), failures
