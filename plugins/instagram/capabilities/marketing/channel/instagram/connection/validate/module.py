from __future__ import annotations

import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from klaroha_sdk import ChannelModule

_GRAPH = "https://graph.facebook.com/v21.0"
_IG_FIELDS = "id,username,name,account_type,biography,website,followers_count,follows_count,media_count,profile_picture_url"


class InstagramConnectionValidateModule(ChannelModule):
    id = "marketing.channel.instagram.connection.validate"
    name = "Instagram Connection Validate"
    vertical = "marketing"
    capability = "marketing.optimize"
    platform_hint = "instagram connection validate"
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
            "content": f"Failed to validate Instagram connection: {message}",
            "sell_price": None,
            "block": {
                "type": "instagram_connection_check",
                "platform": "instagram",
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
            token = creds.get("instagram_page_token") or creds.get("page_token") or creds.get("access_token")
            ig_account_id = creds.get("instagram_page_id") or creds.get("ig_account_id") or creds.get("page_id")

            if not token:
                return self._failure(start, "missing_credentials", "Instagram is not connected — connect Instagram in Brand settings")
            if not ig_account_id:
                return self._failure(start, "missing_credentials", "Linked Instagram Business Account ID not found — reconnect Instagram in Brand settings")

            data = self._get_json(f"{_GRAPH}/{ig_account_id}?fields={_IG_FIELDS}&access_token={token}", token)

            profile = {
                "account_id": data.get("id", ig_account_id),
                "username": data.get("username") or data.get("name") or "",
                "display_name": data.get("name") or data.get("username") or "",
                "account_type": data.get("account_type") or "",
                "biography": data.get("biography") or "",
                "website": data.get("website") or "",
                "followers": data.get("followers_count"),
                "following": data.get("follows_count"),
                "media_count": data.get("media_count"),
                "profile_picture_url": data.get("profile_picture_url"),
            }

            lines = [
                "# Instagram Connection",
                "",
                f"**{profile['display_name'] or profile['account_id']}**",
            ]
            if profile["username"]:
                lines.append(f"Username: @{profile['username'].lstrip('@')}")
            if profile["account_type"]:
                lines.append(f"Account type: {profile['account_type']}")
            if profile["followers"] is not None:
                lines.append(f"Followers: {profile['followers']:,}")
            if profile["following"] is not None:
                lines.append(f"Following: {profile['following']:,}")
            if profile["media_count"] is not None:
                lines.append(f"Media count: {profile['media_count']:,}")
            if profile["website"]:
                lines.append(f"Website: {profile['website']}")

            return self._attempt(start, "succeeded"), {
                "content": "\n".join(lines),
                "sell_price": None,
                "block": {
                    "type": "instagram_connection_check",
                    "platform": "instagram",
                    "status": "succeeded",
                    "account": profile,
                    "read_only": True,
                    "changed_resources": [],
                    "allowed_actions": ["dismiss"],
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
            return self._failure(start, "api_call_failed", "Unexpected error validating Instagram connection", {"error": str(exc)})

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        failures = []
        lowered = content.lower()
        if "instagram" not in lowered and "username:" not in lowered:
            failures.append("missing_instagram_identity")
        return ("fail" if failures else "pass"), failures
