from __future__ import annotations

import json
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from klaroha_sdk import ChannelModule

_TIKTOK_USERINFO_URL = "https://open.tiktokapis.com/v2/user/info/?fields=open_id,avatar_url,display_name,profile_deep_link,is_verified"
_TIKTOK_CREATOR_INFO_URL = "https://open.tiktokapis.com/v2/post/publish/creator_info/query/"


class TikTokConnectionValidateModule(ChannelModule):
    """Read-only TikTok Content Posting API connection validator."""

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
            "model_id": "tiktok_content_posting_api",
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
                + "\n\nRead-only note: no TikTok posts, captions, privacy settings, drafts, or media were changed."
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

    def _post_json(self, url: str, headers: dict, payload: dict | None = None) -> dict:
        request = Request(
            url,
            data=json.dumps(payload or {}).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}

    def _username_from_deep_link(self, deep_link: str) -> str:
        match = re.search(r"/@([A-Za-z0-9._-]+)", str(deep_link or ""))
        return f"@{match.group(1)}" if match else ""

    def _account_summary(self, user: dict, injected_open_id: str | None) -> dict:
        deep_link = str(user.get("profile_deep_link") or "")
        username = self._username_from_deep_link(deep_link)
        return {
            "open_id": str(user.get("open_id") or injected_open_id or ""),
            "display_name": str(user.get("display_name") or ""),
            "username": username,
            "avatar_url": str(user.get("avatar_url") or ""),
            "profile_deep_link": deep_link,
            "is_verified": bool(user.get("is_verified")) if "is_verified" in user else None,
        }

    def _creator_readiness(self, data: dict) -> dict:
        privacy_options = [str(v) for v in (data.get("privacy_level_options") or []) if str(v)]
        return {
            "privacy_level_options": privacy_options,
            "comment_disabled": bool(data.get("comment_disabled")) if "comment_disabled" in data else None,
            "duet_disabled": bool(data.get("duet_disabled")) if "duet_disabled" in data else None,
            "stitch_disabled": bool(data.get("stitch_disabled")) if "stitch_disabled" in data else None,
            "max_video_post_duration_sec": data.get("max_video_post_duration_sec"),
            "can_publish_public_test_post": "PUBLIC_TO_EVERYONE" in privacy_options,
        }

    def execute_tool_result(self, brief: dict) -> tuple[dict, dict]:
        start = time.perf_counter()
        try:
            if not isinstance(brief, dict):
                return self._failure(start, "invalid_brief", "brief must be a dictionary")

            creds = self._creds(brief)
            token = creds.get("tiktok_page_token") or creds.get("page_token") or creds.get("access_token")
            open_id = creds.get("tiktok_page_id") or creds.get("page_id")
            if not token:
                return self._failure(start, "missing_credentials", "TikTok OAuth access token is not connected for this brand")

            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json; charset=UTF-8",
            }
            identity = self._get_json(_TIKTOK_USERINFO_URL, headers)
            user = (identity.get("data") or {}).get("user") or {}
            if not user:
                return self._failure(start, "no_account_returned", "TikTok user info API returned no account for the connected token")

            creator_info = self._post_json(_TIKTOK_CREATOR_INFO_URL, headers, {})
            error = creator_info.get("error") or {}
            if error.get("code") not in {None, "", "ok"}:
                code = str(error.get("code") or "api_call_failed")
                message = str(error.get("message") or "TikTok creator info query failed")
                if code == "scope_not_authorized":
                    return self._failure(start, "scope_not_authorized", "TikTok token is connected but missing the video.publish scope", {"api_error": creator_info})
                return self._failure(start, code, message, {"api_error": creator_info})

            creator_data = creator_info.get("data") or {}
            account = self._account_summary(user, open_id)
            readiness = self._creator_readiness(creator_data)
            content = (
                "# TikTok Connection Validated\n\n"
                f"Account: {account.get('display_name') or account.get('username') or account.get('open_id')}\n"
                f"Open ID: {account.get('open_id')}\n"
                "APIs: TikTok /v2/user/info/ + /v2/post/publish/creator_info/query/\n"
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
                    "test_post_readiness": readiness,
                    "changed_resources": [],
                    "allowed_actions": ["open_tiktok_profile", "dismiss"],
                },
            }

        except HTTPError as exc:
            try:
                body = exc.read().decode("utf-8")[:800]
            except Exception:
                body = ""
            reason = "scope_not_authorized" if exc.code == 401 else "api_call_failed"
            return self._failure(start, reason, f"TikTok API returned HTTP {exc.code}", {"http_status": exc.code, "response": body})
        except URLError as exc:
            return self._failure(start, "api_call_failed", "Network error calling TikTok API", {"error": str(exc)})
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
