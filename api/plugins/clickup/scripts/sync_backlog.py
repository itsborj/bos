#!/usr/bin/env python3
"""
Sync BACKLOG.md → ClickUp workspace.

Reads BACKLOG.md, parses all tasks, then:
  - Creates tasks not found in ClickUp (in the target list)
  - Updates status of tasks whose status has changed
  - Skips tasks already in sync

Usage:
    CLICKUP_API_TOKEN=pk_... CLICKUP_TEAM_ID=9012345678 python sync_backlog.py
    CLICKUP_API_TOKEN=pk_... CLICKUP_TEAM_ID=9012345678 python sync_backlog.py --dry-run
    CLICKUP_API_TOKEN=pk_... CLICKUP_TEAM_ID=9012345678 python sync_backlog.py --list Development

Environment vars:
    CLICKUP_API_TOKEN   ClickUp personal API token (pk_...)
    CLICKUP_TEAM_ID     ClickUp Workspace ID (called team_id in API)

Status mapping (matches initial export):
    [x]  → shipped
    [~]  → in development
    [!]  → blocked
    [-]  → cancelled
    [ ]  → backlog
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# ─── Config ──────────────────────────────────────────────────────────────────

BACKLOG_PATH = Path(__file__).resolve().parents[4] / "BACKLOG.md"

STATUS_MAP: dict[str, str] = {
    "x": "shipped",
    "~": "in development",
    "!": "blocked",
    "-": "cancelled",
    " ": "backlog",
}

# Fallback chain when a status isn't configured in the target list.
# Keys are the preferred status; values are ordered fallbacks to try.
STATUS_FALLBACKS: dict[str, list[str]] = {
    "blocked": ["backlog", "in development"],
}

# Seconds between write calls — ClickUp rate limit is 100 req/min
WRITE_DELAY = 0.65

# ─── HTTP ─────────────────────────────────────────────────────────────────────


def _get(url: str, token: str) -> dict | list:
    req = Request(url, headers={"Authorization": token, "Content-Type": "application/json"})
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _put(url: str, token: str, payload: dict) -> dict:
    req = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": token, "Content-Type": "application/json"},
        method="PUT",
    )
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _post(url: str, token: str, payload: dict) -> dict:
    req = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": token, "Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ─── BACKLOG.md parser ────────────────────────────────────────────────────────


def parse_backlog(text: str) -> list[dict]:
    """Parse BACKLOG.md into structured task list preserving phase/section context."""
    tasks: list[dict] = []
    phase = ""
    section = ""
    for line in text.splitlines():
        m = re.match(r"^## (.+)", line)
        if m:
            phase = m.group(1).strip()
            section = ""
            continue
        m = re.match(r"^### (.+)", line)
        if m:
            section = m.group(1).strip()
            continue
        m = re.match(r"^\s*-\s+\[([x~! \-])\]\s+(.+)", line)
        if m:
            marker = m.group(1)
            name = m.group(2).strip()
            tasks.append(
                {
                    "name": name,
                    "status": STATUS_MAP.get(marker, "backlog"),
                    "phase": phase,
                    "section": section,
                }
            )
    return tasks


# ─── ClickUp workspace discovery ─────────────────────────────────────────────


def discover_lists(token: str, team_id: str) -> list[dict]:
    all_lists: list[dict] = []
    spaces = _get(f"https://api.clickup.com/api/v2/team/{team_id}/space?archived=false", token)
    for space in spaces.get("spaces", []):
        space_name = str(space.get("name", space["id"]))
        try:
            folders = _get(
                f"https://api.clickup.com/api/v2/space/{space['id']}/folder?archived=false", token
            )
            for folder in folders.get("folders", []):
                for lst in folder.get("lists", []):
                    all_lists.append({"id": lst["id"], "name": lst["name"], "space": space_name})
        except Exception as exc:
            print(f"  [warn] Could not fetch folders for space {space_name}: {exc}")
        try:
            flists = _get(
                f"https://api.clickup.com/api/v2/space/{space['id']}/list?archived=false", token
            )
            for lst in flists.get("lists", []):
                all_lists.append({"id": lst["id"], "name": lst["name"], "space": space_name})
        except Exception as exc:
            print(f"  [warn] Could not fetch lists for space {space_name}: {exc}")
    return all_lists


def fetch_all_tasks(token: str, lists: list[dict]) -> dict[str, dict]:
    """Build lowercase-name → task dict for the entire workspace. Handles pagination."""
    index: dict[str, dict] = {}
    for lst in lists:
        page = 0
        while True:
            try:
                url = (
                    f"https://api.clickup.com/api/v2/list/{lst['id']}/task"
                    f"?archived=false&include_closed=true&subtasks=false&page={page}"
                )
                data = _get(url, token)
                tasks = data.get("tasks", []) if isinstance(data, dict) else []
                if not tasks:
                    break
                for t in tasks:
                    name = str(t.get("name", "")).strip()
                    if name:
                        index[name.lower()] = {
                            "id": t["id"],
                            "name": name,
                            "status": (t.get("status") or {}).get("status", ""),
                            "list_id": lst["id"],
                        }
                page += 1
                if len(tasks) < 100:
                    break
            except Exception as exc:
                print(f"  [warn] Could not fetch page {page} of list '{lst['name']}': {exc}")
                break
    return index


# ─── Sync ────────────────────────────────────────────────────────────────────


def sync(token: str, team_id: str, target_list_name: str, dry_run: bool) -> None:
    print(f"Reading {BACKLOG_PATH}")
    if not BACKLOG_PATH.exists():
        print(f"[error] BACKLOG.md not found at {BACKLOG_PATH}")
        sys.exit(1)

    backlog = parse_backlog(BACKLOG_PATH.read_text(encoding="utf-8"))
    print(f"Parsed {len(backlog)} backlog items.")

    print("Discovering ClickUp workspace…")
    lists = discover_lists(token, team_id)
    if not lists:
        print("[error] No lists found in workspace. Check CLICKUP_TEAM_ID.")
        sys.exit(1)
    print(f"Found {len(lists)} lists across {len({l['space'] for l in lists})} spaces.")

    target_list = next(
        (l for l in lists if l["name"].lower() == target_list_name.lower()), None
    )
    if not target_list:
        print(f"[error] List '{target_list_name}' not found. Available: {', '.join(l['name'] for l in lists)}")
        sys.exit(1)
    print(f"New tasks → '{target_list['name']}' (id: {target_list['id']})")

    # Discover valid statuses for this list so we can apply fallbacks
    try:
        list_meta = _get(f"https://api.clickup.com/api/v2/list/{target_list['id']}", token)
        valid_statuses = {s["status"].lower() for s in list_meta.get("statuses", [])}
    except Exception:
        valid_statuses = set()

    def resolve_status(status: str) -> str:
        if not valid_statuses or status in valid_statuses:
            return status
        for fallback in STATUS_FALLBACKS.get(status, []):
            if fallback in valid_statuses:
                return fallback
        return "backlog"

    print(f"Fetching all tasks from {len(lists)} lists…")
    cu_index = fetch_all_tasks(token, lists)
    print(f"Indexed {len(cu_index)} ClickUp tasks.")

    to_update: list[dict] = []
    to_create: list[dict] = []
    already_synced = 0

    for task in backlog:
        key = task["name"].lower()
        target_status = task["status"]

        if key in cu_index:
            current = cu_index[key]["status"].lower().strip()
            resolved = resolve_status(target_status)
            if current != resolved:
                to_update.append(
                    {
                        "task_id": cu_index[key]["id"],
                        "name": cu_index[key]["name"],
                        "old_status": cu_index[key]["status"],
                        "new_status": resolved,
                    }
                )
            else:
                already_synced += 1
        else:
            to_create.append(
                {
                    "name": task["name"],
                    "status": resolve_status(target_status),
                    "phase": task["phase"],
                    "section": task["section"],
                    "list_id": target_list["id"],
                }
            )

    print("\nSync plan:")
    print(f"  Already in sync : {already_synced}")
    print(f"  Status updates  : {len(to_update)}")
    print(f"  New tasks       : {len(to_create)}")

    if to_update:
        print("\nStatus updates:")
        for t in to_update[:30]:
            print(f"  {t['name'][:65]}  [{t['old_status']}] → [{t['new_status']}]")
        if len(to_update) > 30:
            print(f"  … and {len(to_update) - 30} more")

    if to_create:
        print(f"\nNew tasks (first 30 of {len(to_create)}):")
        for t in to_create[:30]:
            print(f"  [{t['status']}] {t['name'][:70]}")
        if len(to_create) > 30:
            print(f"  … and {len(to_create) - 30} more")

    if dry_run:
        print("\n[DRY RUN] No changes applied. Remove --dry-run to apply.")
        return

    if not to_update and not to_create:
        print("\nEverything already in sync. Nothing to do.")
        return

    print(f"\nApplying {len(to_update)} updates…")
    updated = 0
    update_errors: list[dict] = []
    for t in to_update:
        try:
            _put(
                f"https://api.clickup.com/api/v2/task/{t['task_id']}",
                token,
                {"status": t["new_status"]},
            )
            print(f"  ✓ {t['name'][:65]}  → {t['new_status']}")
            updated += 1
        except HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8")[:200]
            except Exception:
                pass
            msg = f"HTTP {exc.code}: {body}"
            print(f"  ✗ {t['name'][:65]}: {msg}")
            update_errors.append({"name": t["name"], "error": msg})
        except Exception as exc:
            print(f"  ✗ {t['name'][:65]}: {exc}")
            update_errors.append({"name": t["name"], "error": str(exc)})
        time.sleep(WRITE_DELAY)

    print(f"\nCreating {len(to_create)} new tasks…")
    created = 0
    create_errors: list[dict] = []
    for t in to_create:
        desc_parts = [f"Phase: {t['phase']}"]
        if t["section"]:
            desc_parts.append(f"Section: {t['section']}")
        try:
            _post(
                f"https://api.clickup.com/api/v2/list/{t['list_id']}/task",
                token,
                {
                    "name": t["name"],
                    "status": t["status"],
                    "description": "\n".join(desc_parts),
                    "notify_all": False,
                },
            )
            print(f"  + [{t['status']}] {t['name'][:65]}")
            created += 1
        except HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8")[:200]
            except Exception:
                pass
            msg = f"HTTP {exc.code}: {body}"
            print(f"  ✗ {t['name'][:65]}: {msg}")
            create_errors.append({"name": t["name"], "error": msg})
        except Exception as exc:
            print(f"  ✗ {t['name'][:65]}: {exc}")
            create_errors.append({"name": t["name"], "error": str(exc)})
        time.sleep(WRITE_DELAY)

    total_errors = len(update_errors) + len(create_errors)
    print("\n─────────────────────────────────")
    print(f"Updated : {updated} / {len(to_update)}")
    print(f"Created : {created} / {len(to_create)}")
    print(f"Errors  : {total_errors}")
    if total_errors:
        print("\nFailed items:")
        for e in update_errors + create_errors:
            print(f"  {e['name'][:70]}: {e['error']}")


# ─── Entry point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv

    target_list = "Development"
    if "--list" in sys.argv:
        idx = sys.argv.index("--list")
        if idx + 1 < len(sys.argv):
            target_list = sys.argv[idx + 1]

    token = os.environ.get("CLICKUP_API_TOKEN", "").strip()
    team_id = os.environ.get("CLICKUP_TEAM_ID", "").strip()

    if not token:
        print("[error] CLICKUP_API_TOKEN not set.")
        print("  export CLICKUP_API_TOKEN=pk_...")
        sys.exit(1)
    if not team_id:
        print("[error] CLICKUP_TEAM_ID not set.")
        print("  export CLICKUP_TEAM_ID=<your workspace ID>")
        sys.exit(1)

    sync(token, team_id, target_list, dry_run)
