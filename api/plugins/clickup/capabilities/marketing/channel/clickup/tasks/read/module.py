from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from klaroha_sdk import ChannelModule


class ClickUpTasksReadModule(ChannelModule):
    id = "marketing.channel.clickup.tasks.read"
    name = "ClickUp Workspace Status"
    vertical = "marketing"
    capability = "marketing.optimize"
    platform_hint = "clickup tasks read"
    policy_default = "read_only"
    template = "marketing/channel/clickup/tasks/read/template.j2"

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
            "content": f"Failed to read ClickUp workspace: {message}\n\nRead-only note: no tasks were created, edited, or deleted.",
            "sell_price": None,
            "block": {
                "type": "clickup_task_status",
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

    def _get_list_tasks(self, token: str, list_id: str) -> list:
        try:
            url = (
                f"https://api.clickup.com/api/v2/list/{list_id}/task"
                "?archived=false&include_closed=true&subtasks=false&page=0"
            )
            data = self._get_json(url, token)
            return data.get("tasks", []) if isinstance(data, dict) else []
        except Exception:
            return []

    def _fetch_workspace(self, token: str, team_id: str) -> tuple[list, list]:
        """Returns (all_tasks_with_context, list_index).
        Each task gets _space and _list injected for grouping.
        """
        spaces_data = self._get_json(
            f"https://api.clickup.com/api/v2/team/{team_id}/space?archived=false", token
        )
        all_tasks: list = []
        list_index: list = []

        for space in spaces_data.get("spaces", []):
            space_name = str(space.get("name", space["id"]))

            folders_data = self._get_json(
                f"https://api.clickup.com/api/v2/space/{space['id']}/folder?archived=false", token
            )
            for folder in folders_data.get("folders", []):
                for lst in folder.get("lists", []):
                    tasks = self._get_list_tasks(token, lst["id"])
                    for t in tasks:
                        t["_space"] = space_name
                        t["_list"] = lst["name"]
                        t["_list_id"] = lst["id"]
                    all_tasks.extend(tasks)
                    list_index.append({"space": space_name, "list": lst["name"], "id": lst["id"], "count": len(tasks)})

            flists_data = self._get_json(
                f"https://api.clickup.com/api/v2/space/{space['id']}/list?archived=false", token
            )
            for lst in flists_data.get("lists", []):
                tasks = self._get_list_tasks(token, lst["id"])
                for t in tasks:
                    t["_space"] = space_name
                    t["_list"] = lst["name"]
                    t["_list_id"] = lst["id"]
                all_tasks.extend(tasks)
                list_index.append({"space": space_name, "list": lst["name"], "id": lst["id"], "count": len(tasks)})

        return all_tasks, list_index

    def _classify_tasks(self, tasks: list) -> dict:
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        buckets: dict = {"blocked": [], "overdue": [], "in_progress": [], "todo": [], "done": []}
        _done = {"complete", "completed", "done", "closed", "resolved"}
        _blocked = {"blocked", "on hold", "waiting", "blocked by"}
        _in_progress = {"in progress", "in review", "review", "active", "doing", "in-progress"}

        for task in tasks:
            status_str = ((task.get("status") or {}).get("status") or "").lower().strip()
            due_raw = task.get("due_date")
            due_ms = int(due_raw) if due_raw and str(due_raw).isdigit() else None
            assignees = [a.get("username", "") for a in (task.get("assignees") or []) if a.get("username")]
            due_formatted = (
                datetime.fromtimestamp(due_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
                if due_ms else None
            )
            row = {
                "id": str(task.get("id", "")),
                "name": str(task.get("name", "")),
                "status": status_str,
                "assignees": assignees,
                "due_date": due_formatted,
                "url": task.get("url"),
                "space": task.get("_space", ""),
                "list": task.get("_list", ""),
                "overdue": bool(due_ms and due_ms < now_ms and status_str not in _done),
            }
            if status_str in _done:
                buckets["done"].append(row)
            elif status_str in _blocked:
                buckets["blocked"].append(row)
            elif row["overdue"]:
                buckets["overdue"].append(row)
            elif status_str in _in_progress:
                buckets["in_progress"].append(row)
            else:
                buckets["todo"].append(row)

        return buckets

    def _build_content(self, list_index: list, buckets: dict, total: int) -> str:
        spaces: dict[str, dict] = {}
        for entry in list_index:
            s = entry["space"]
            if s not in spaces:
                spaces[s] = {"lists": 0, "tasks": 0}
            spaces[s]["lists"] += 1
            spaces[s]["tasks"] += entry["count"]

        lines = [
            "# ClickUp Workspace Status",
            "",
            f"{len(spaces)} space(s)  |  {len(list_index)} list(s)  |  {total} tasks total",
            "",
            "Status summary:",
            f"- In Progress: {len(buckets['in_progress'])} tasks",
            f"- To Do: {len(buckets['todo'])} tasks",
        ]
        if buckets["blocked"]:
            lines.append(f"- Blocked: {len(buckets['blocked'])} tasks  ← needs attention")
        if buckets["overdue"]:
            lines.append(f"- Overdue: {len(buckets['overdue'])} tasks  ← needs attention")
        lines.append(f"- Done: {len(buckets['done'])} tasks")

        if spaces:
            lines += ["", "By space:"]
            for space_name, counts in spaces.items():
                lines.append(f"  {space_name}: {counts['lists']} list(s), {counts['tasks']} task(s)")

        if buckets["blocked"]:
            lines += ["", "Blocked:"]
            for t in buckets["blocked"][:5]:
                loc = f" — {t['space']} › {t['list']}" if t.get("list") else ""
                due = f" — due {t['due_date']}" if t["due_date"] else ""
                lines.append(f'- "{t["name"]}"{loc}{due}')

        if buckets["overdue"]:
            lines += ["", "Overdue:"]
            for t in buckets["overdue"][:5]:
                loc = f" — {t['space']} › {t['list']}" if t.get("list") else ""
                assigned = f" — {', '.join(t['assignees'])}" if t["assignees"] else ""
                lines.append(f'- "{t["name"]}"{loc}{assigned} — due {t["due_date"]}')

        if buckets["in_progress"]:
            lines += ["", "In Progress:"]
            for t in buckets["in_progress"][:5]:
                loc = f" — {t['space']} › {t['list']}" if t.get("list") else ""
                assigned = f" — assigned: {', '.join(t['assignees'])}" if t["assignees"] else ""
                due = f" — due {t['due_date']}" if t["due_date"] else ""
                lines.append(f'- "{t["name"]}"{loc}{assigned}{due}')

        lines += ["", "Read-only note: no tasks were created, edited, or deleted."]
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

            all_tasks, list_index = self._fetch_workspace(token, team_id)
            buckets = self._classify_tasks(all_tasks)
            content = self._build_content(list_index, buckets, len(all_tasks))

            return self._attempt(start, "succeeded"), {
                "content": content,
                "sell_price": None,
                "block": {
                    "type": "clickup_task_status",
                    "status": "succeeded",
                    "workspace_id": team_id,
                    "space_count": len({e["space"] for e in list_index}),
                    "list_count": len(list_index),
                    "list_index": list_index,
                    "task_count": len(all_tasks),
                    "blocked": buckets["blocked"],
                    "overdue": buckets["overdue"],
                    "in_progress": buckets["in_progress"],
                    "todo_count": len(buckets["todo"]),
                    "done_count": len(buckets["done"]),
                    "read_only": True,
                    "changed_resources": [],
                    "allowed_actions": ["create_followup_tasks", "dismiss"],
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
        if "clickup workspace status" not in lowered:
            failures.append("missing_workspace_status_heading")
        if "read-only note" not in lowered:
            failures.append("missing_read_only_note")
        for term in ("task created", "task deleted", "task updated", "task edited", "created task"):
            if term in lowered:
                failures.append(f"mutation_claim_found:{term}")
        return ("fail" if failures else "pass"), failures
