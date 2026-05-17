from __future__ import annotations

import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from klaroha_sdk import ChannelModule


class ClickUpSyncBacklogItemModule(ChannelModule):
    id = "marketing.channel.clickup.tasks.sync_backlog_item"
    name = "ClickUp Backlog Sync"
    vertical = "marketing"
    capability = "marketing.execute"
    platform_hint = "clickup tasks sync"
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
            "content": f"Failed to sync backlog item: {message}",
            "sell_price": None,
            "block": {
                "type": "clickup_backlog_synced",
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

    def _get_json(self, url: str, token: str) -> dict | list:
        req = Request(url, headers={"Authorization": token, "Content-Type": "application/json"})
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _put_json(self, url: str, token: str, payload: dict) -> dict:
        req = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": token, "Content-Type": "application/json"},
            method="PUT",
        )
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _search_tasks(self, token: str, team_id: str, query: str) -> list[dict]:
        try:
            url = f"https://api.clickup.com/api/v2/team/{team_id}/task?query={quote(query)}&include_closed=true"
            data = self._get_json(url, token)
            if isinstance(data, dict):
                return data.get("tasks", [])
        except Exception:
            pass
        return []

    def _discover_all_lists(self, token: str, team_id: str) -> list[dict]:
        all_lists: list[dict] = []
        spaces_data = self._get_json(
            f"https://api.clickup.com/api/v2/team/{team_id}/space?archived=false", token
        )
        for space in spaces_data.get("spaces", []):
            space_name = str(space.get("name", space["id"]))
            folders_data = self._get_json(
                f"https://api.clickup.com/api/v2/space/{space['id']}/folder?archived=false", token
            )
            for folder in folders_data.get("folders", []):
                for lst in folder.get("lists", []):
                    all_lists.append({"id": lst["id"], "name": lst["name"], "space": space_name})
            flists_data = self._get_json(
                f"https://api.clickup.com/api/v2/space/{space['id']}/list?archived=false", token
            )
            for lst in flists_data.get("lists", []):
                all_lists.append({"id": lst["id"], "name": lst["name"], "space": space_name})
        return all_lists

    def _find_task_by_name(self, token: str, team_id: str, task_name: str) -> dict | None:
        needle = task_name.lower().strip()

        # Try ClickUp search API first
        results = self._search_tasks(token, team_id, task_name)
        for t in results:
            if str(t.get("name", "")).lower().strip() == needle:
                return t
        for t in results:
            if needle in str(t.get("name", "")).lower():
                return t

        # Full workspace scan as fallback
        for lst in self._discover_all_lists(token, team_id):
            try:
                url = f"https://api.clickup.com/api/v2/list/{lst['id']}/task?archived=false&include_closed=true"
                data = self._get_json(url, token)
                tasks = data.get("tasks", []) if isinstance(data, dict) else []
                for t in tasks:
                    if str(t.get("name", "")).lower().strip() == needle:
                        return t
            except Exception:
                continue

        # Partial match fallback
        for lst in self._discover_all_lists(token, team_id):
            try:
                url = f"https://api.clickup.com/api/v2/list/{lst['id']}/task?archived=false&include_closed=true"
                data = self._get_json(url, token)
                tasks = data.get("tasks", []) if isinstance(data, dict) else []
                for t in tasks:
                    if needle in str(t.get("name", "")).lower():
                        return t
            except Exception:
                continue

        return None

    def execute_tool_result(self, brief: dict) -> tuple[dict, dict]:
        start = time.perf_counter()
        try:
            if not isinstance(brief, dict):
                return self._failure(start, "invalid_brief", "brief must be a dictionary")

            creds = self._creds(brief)
            token = self._cred(creds, "clickup_api_token")
            team_id = self._cred(creds, "clickup_team_id")

            missing = []
            if not token:
                missing.append("CLICKUP_API_TOKEN")
            if not team_id:
                missing.append("CLICKUP_TEAM_ID")
            if missing:
                return self._failure(
                    start,
                    "missing_credentials",
                    "missing required plugin variables: " + ", ".join(missing),
                    {"missing": missing},
                )

            task_name = str(brief.get("task_name") or "").strip()
            new_status = str(brief.get("new_status") or "").strip()

            if not task_name:
                return self._failure(start, "missing_task_name", "brief must include task_name")
            if not new_status:
                return self._failure(start, "missing_status", "brief must include new_status")

            task = self._find_task_by_name(token, team_id, task_name)
            if not task:
                return self._failure(
                    start,
                    "task_not_found",
                    f"No ClickUp task found matching: {task_name!r}",
                    {"task_name": task_name},
                )

            task_id = str(task.get("id", ""))
            result = self._put_json(
                f"https://api.clickup.com/api/v2/task/{task_id}",
                token,
                {"status": new_status},
            )

            updated_status = (result.get("status") or {}).get("status") or new_status
            content = (
                f"# ClickUp Backlog Item Synced\n\n"
                f"Task: {result.get('name', task_name)}\n"
                f"Status: {updated_status}"
            )

            return self._attempt(start, "succeeded"), {
                "content": content,
                "sell_price": None,
                "block": {
                    "type": "clickup_backlog_synced",
                    "status": "succeeded",
                    "task_id": task_id,
                    "task_name": result.get("name", task_name),
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
        if "synced" not in lowered and "backlog" not in lowered:
            failures.append("missing_sync_heading")
        return ("fail" if failures else "pass"), failures
