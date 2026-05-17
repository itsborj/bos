from __future__ import annotations

import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from klaroha_sdk import ChannelModule


class ClickUpTasksUpdateModule(ChannelModule):
    id = "marketing.channel.clickup.tasks.update"
    name = "ClickUp Task Updater"
    vertical = "marketing"
    capability = "marketing.execute"
    platform_hint = "clickup tasks update"
    policy_default = "approval_gated"
    template = ""

    max_chars = 0
    must_mention = []
    banned_phrases = []

    def _latency_ms(self, start: float) -> int:
        return round((time.perf_counter() - start) * 1000)

    def _attempt(self, start: float, status: str, error: str | None = None) -> dict:
        return {
            "provider": "clickup",
            "model_id": "clickup_rest_api_v2",
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
            "content": f"Failed to update ClickUp task: {message}",
            "sell_price": None,
            "block": {
                "type": "clickup_task_updated",
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

    def _cred(self, creds: dict, *names: str) -> str | None:
        for name in names:
            for key in (name.lower(), name.upper(), name):
                value = creds.get(key)
                if value:
                    return str(value).strip()
        return None

    def _put_json(self, url: str, token: str, payload: dict) -> dict:
        req = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": token, "Content-Type": "application/json"},
            method="PUT",
        )
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def execute_tool_result(self, brief: dict) -> tuple[dict, dict]:
        start = time.perf_counter()
        try:
            if not isinstance(brief, dict):
                return self._failure(start, "invalid_brief", "brief must be a dictionary")

            creds = self._creds(brief)
            token = self._cred(creds, "clickup_api_token")

            if not token:
                return self._failure(
                    start,
                    "missing_credentials",
                    "missing required plugin variable: CLICKUP_API_TOKEN",
                    {"missing": ["CLICKUP_API_TOKEN"]},
                )

            task_id = str(brief.get("task_id") or brief.get("clickup_task_id") or "").strip()
            new_status = str(brief.get("new_status") or "").strip()

            if not task_id:
                return self._failure(start, "missing_task_id", "brief must include task_id")
            if not new_status:
                return self._failure(start, "missing_status", "brief must include new_status")

            payload: dict = {"status": new_status}
            if brief.get("name"):
                payload["name"] = str(brief["name"]).strip()
            if brief.get("description"):
                payload["description"] = str(brief["description"]).strip()

            result = self._put_json(
                f"https://api.clickup.com/api/v2/task/{task_id}",
                token,
                payload,
            )

            updated_status = (result.get("status") or {}).get("status") or new_status
            content = (
                f"# ClickUp Task Updated\n\n"
                f"Task: {result.get('name', task_id)}\n"
                f"New status: {updated_status}"
            )

            return self._attempt(start, "succeeded"), {
                "content": content,
                "sell_price": None,
                "block": {
                    "type": "clickup_task_updated",
                    "status": "succeeded",
                    "task_id": task_id,
                    "task_name": result.get("name", task_id),
                    "new_status": updated_status,
                    "url": result.get("url"),
                    "changed_resources": [task_id],
                    "allowed_actions": ["view_in_clickup", "dismiss"],
                },
            }

        except HTTPError as exc:
            try:
                error_body = exc.read().decode("utf-8")
            except Exception:
                error_body = ""
            return self._failure(
                start,
                "api_call_failed",
                f"ClickUp API returned HTTP {getattr(exc, 'code', 'error')}",
                {"http_status": getattr(exc, "code", None), "response": error_body},
            )
        except URLError as exc:
            return self._failure(start, "api_call_failed", "network error calling ClickUp API", {"error": str(exc)})
        except Exception as exc:
            return self._failure(start, "api_call_failed", "unexpected error calling ClickUp API", {"error": str(exc)})

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        failures = []
        lowered = content.lower() if isinstance(content, str) else ""
        if "clickup task updated" not in lowered:
            failures.append("missing_updated_heading")
        return ("fail" if failures else "pass"), failures
