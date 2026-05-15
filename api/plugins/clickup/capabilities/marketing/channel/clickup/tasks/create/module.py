from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from klaroha_sdk import ChannelModule


class ClickUpTasksCreateModule(ChannelModule):
    id = "marketing.channel.clickup.tasks.create"
    name = "ClickUp Task Creator"
    vertical = "marketing"
    capability = "marketing.execute"
    platform_hint = "clickup tasks create"
    policy_default = "approval_gated"
    template = "marketing/channel/clickup/tasks/create/template.j2"

    max_chars = 0
    must_mention = []
    banned_phrases = []

    _MAX_TASKS_PER_CALL = 20

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
            "content": f"Failed to create ClickUp tasks: {message}",
            "sell_price": None,
            "block": {
                "type": "clickup_tasks_created",
                "status": "failed",
                "reason_code": reason_code,
                "message": message,
                "details": details or {},
                "created": [],
                "created_count": 0,
                "failed": [],
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

    def _to_due_ms(self, value: str | int | float | None) -> int | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            v = int(value)
            return v * 1000 if v < 10_000_000_000 else v
        s = str(value).strip()
        if not s:
            return None
        if s.isdigit():
            v = int(s)
            return v * 1000 if v < 10_000_000_000 else v
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            return int(dt.timestamp() * 1000)
        except Exception:
            return None

    def _get_json(self, url: str, token: str) -> dict | list:
        req = Request(url, headers={"Authorization": token, "Content-Type": "application/json"})
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _post_json(self, url: str, token: str, payload: dict) -> dict:
        req = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": token, "Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _discover_all_lists(self, token: str, team_id: str) -> list[dict]:
        """Returns [{id, name, space, folder}] for every list in the workspace."""
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
                    all_lists.append({"id": lst["id"], "name": lst["name"], "space": space_name, "folder": folder["name"]})
            flists_data = self._get_json(
                f"https://api.clickup.com/api/v2/space/{space['id']}/list?archived=false", token
            )
            for lst in flists_data.get("lists", []):
                all_lists.append({"id": lst["id"], "name": lst["name"], "space": space_name, "folder": None})
        return all_lists

    def _resolve_list(self, token: str, team_id: str, list_id: str | None, list_name: str | None) -> tuple[str | None, str, list[dict]]:
        """Returns (resolved_list_id, resolved_list_name, available_lists).
        available_lists is populated only when resolution fails (for error context).
        """
        if list_id:
            try:
                data = self._get_json(f"https://api.clickup.com/api/v2/list/{list_id}", token)
                return str(list_id), str(data.get("name") or list_id), []
            except Exception:
                return str(list_id), str(list_id), []

        all_lists = self._discover_all_lists(token, team_id)

        if list_name:
            needle = list_name.lower().strip()
            for lst in all_lists:
                if lst["name"].lower().strip() == needle:
                    return lst["id"], lst["name"], []
            # partial match fallback
            for lst in all_lists:
                if needle in lst["name"].lower():
                    return lst["id"], lst["name"], []

        return None, "", all_lists

    def _build_content(self, list_name: str, created: list, failed: list) -> str:
        lines = [
            "# ClickUp Tasks Created",
            "",
            f"List: {list_name}  |  Created: {len(created)} tasks",
            "",
        ]
        if created:
            lines.append("Created:")
            for t in created:
                due = f" — due {t['due_date']}" if t.get("due_date") else ""
                status = t.get("status") or "to do"
                lines.append(f"✓ {t['name']} — {status}{due}")
        if failed:
            lines += ["", "Failed:"]
            for f in failed:
                lines.append(f"✗ {f['name']}: {f['error']}")
        return "\n".join(lines)

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
                    "missing required plugin environment variables: " + ", ".join(missing),
                    {"missing": missing},
                )

            list_id_from_brief = str(brief.get("list_id") or "").strip() or None
            list_name_from_brief = str(brief.get("list_name") or "").strip() or None

            resolved_id, resolved_name, available = self._resolve_list(
                token, team_id, list_id_from_brief, list_name_from_brief
            )

            if not resolved_id:
                list_hints = [f"{l['space']} › {l['name']} (id={l['id']})" for l in available]
                return self._failure(
                    start,
                    "no_list_specified",
                    "brief must include list_id or list_name to target a ClickUp list. Available lists: " + "; ".join(list_hints),
                    {"available_lists": available},
                )

            tasks_input: list = brief.get("tasks") or []
            if not tasks_input:
                fallback_content = str(brief.get("content") or brief.get("campaign_name") or "").strip()
                if not fallback_content:
                    return self._failure(
                        start,
                        "no_tasks",
                        "brief contains no tasks[] array and no content fallback. Populate brief['tasks'] with a list of task objects before dispatching.",
                    )
                tasks_input = [{"name": fallback_content, "description": "Created from BOS campaign brief."}]

            created: list = []
            failed: list = []

            for task_def in tasks_input[: self._MAX_TASKS_PER_CALL]:
                name = str(task_def.get("name") or "").strip()
                if not name:
                    continue
                payload: dict = {
                    "name": name,
                    "description": str(task_def.get("description") or ""),
                    "status": str(task_def.get("status") or "to do"),
                    "priority": int(task_def.get("priority") or 3),
                    "notify_all": False,
                }
                due_ms = self._to_due_ms(task_def.get("due_date"))
                if due_ms:
                    payload["due_date"] = due_ms
                    payload["due_date_time"] = False

                try:
                    result = self._post_json(
                        f"https://api.clickup.com/api/v2/list/{resolved_id}/task",
                        token,
                        payload,
                    )
                    created.append({
                        "id": str(result.get("id", "")),
                        "name": str(result.get("name", name)),
                        "url": result.get("url"),
                        "status": (result.get("status") or {}).get("status") or payload["status"],
                        "due_date": task_def.get("due_date"),
                    })
                except HTTPError as exc:
                    try:
                        body = exc.read().decode("utf-8")
                    except Exception:
                        body = ""
                    failed.append({"name": name, "error": f"HTTP {getattr(exc, 'code', 'error')}: {body[:200]}"})
                except Exception as exc:
                    failed.append({"name": name, "error": str(exc)})

            overall_status = "succeeded" if created else "failed"
            content = self._build_content(resolved_name, created, failed)

            return self._attempt(start, overall_status), {
                "content": content,
                "sell_price": None,
                "block": {
                    "type": "clickup_tasks_created",
                    "status": overall_status,
                    "list_id": resolved_id,
                    "list_name": resolved_name,
                    "created": created,
                    "created_count": len(created),
                    "failed": failed,
                    "changed_resources": [t["id"] for t in created if t.get("id")],
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
        if "clickup tasks created" not in lowered:
            failures.append("missing_created_heading")
        for term in ("task deleted", "task removed", "task updated without approval"):
            if term in lowered:
                failures.append(f"forbidden_action_claim:{term}")
        return ("fail" if failures else "pass"), failures
