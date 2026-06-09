#!/usr/bin/env python3
"""
Create a human-readable BOS ClickUp structure alongside the noisy BACKLOG.md mirror.

Non-destructive by design:
  - Creates missing folders/lists for Decision Ledger and Capability Map.
  - Seeds curated Decision / Capability / Plugin tasks.
  - Does not archive, delete, or move existing backlog-mirror tasks.

Usage:
    CLICKUP_API_TOKEN=pk_... CLICKUP_TEAM_ID=90161582949 python3 organize_bos_clickup.py --dry-run
    CLICKUP_API_TOKEN=pk_... CLICKUP_TEAM_ID=90161582949 python3 organize_bos_clickup.py --apply
    CLICKUP_API_TOKEN=pk_... CLICKUP_TEAM_ID=90161582949 python3 organize_bos_clickup.py --apply --space "Klaroha BOS" --decisions 20

The structure is documented in sample/clickup_decision_capability_system_v1.md.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[4]
BACKLOG_PATH = ROOT / "BACKLOG.md"
BRIEF_PATH = ROOT / "PROJECT_BRIEF.md"
SAMPLE_PATH = ROOT / "sample" / "clickup_decision_capability_system_v1.md"

WRITE_DELAY = 0.65

DESIRED_FOLDERS: dict[str, list[str]] = {
    "Execution Backlog": [
        "Agent Backlog Mirror",
        "Active Sprint",
        "Bugs / Regressions",
        "Release Checklist",
    ],
    "Decision Ledger": [
        "Architecture Decisions",
        "Capability Decisions",
        "Plugin Decisions",
        "Product UX Decisions",
        "Deployment Ops Decisions",
    ],
    "Capability Map": [
        "Core Capabilities",
        "First-Party Capabilities",
        "Plugin Capabilities",
        "Retired Capabilities",
    ],
}

CORE_CAPABILITY_CARDS = [
    {
        "name": "[CORE] CMO 7-step chat pipeline",
        "topic": "cmo-chat",
        "description": "Core owns receive → context → LLM → strip directives → dispatch → persist → return. Plugin-specific routing must not live here.",
    },
    {
        "name": "[CORE] Capability manifest",
        "topic": "capability-manifest",
        "description": "Runtime CMO capability list generated from eligible active SKILL.md/plugin registry state.",
    },
    {
        "name": "[CORE] BITE pipeline",
        "topic": "bite",
        "description": "Intent → Bridge → Transform → Evaluate. Core owns the harness; capabilities own workflow-specific behavior.",
    },
    {
        "name": "[CORE] Workspace Artifact Plane",
        "topic": "workspace-artifacts",
        "description": "Canonical artifact persistence/review plane. CMO chat returns concise narrative plus artifact references only.",
    },
    {
        "name": "[CORE] Extension Host (target)",
        "topic": "extension-host",
        "description": "Target plugin runtime boundary: validation, compatibility adapters, hook execution, installed-state registry, failure quarantine.",
    },
]


# ─── HTTP ─────────────────────────────────────────────────────────────────────


def _request(method: str, url: str, token: str, payload: dict | None = None) -> dict | list:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(
        url,
        data=data,
        headers={"Authorization": token, "Content-Type": "application/json"},
        method=method,
    )
    with urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body) if body else {}


def _get(url: str, token: str) -> dict | list:
    return _request("GET", url, token)


def _post(url: str, token: str, payload: dict) -> dict:
    return _request("POST", url, token, payload)  # type: ignore[return-value]


def _put(url: str, token: str, payload: dict) -> dict:
    return _request("PUT", url, token, payload)  # type: ignore[return-value]


# ─── Models ───────────────────────────────────────────────────────────────────


@dataclass
class Space:
    id: str
    name: str


@dataclass
class Folder:
    id: str
    name: str
    space_id: str


@dataclass
class ClickList:
    id: str
    name: str
    space_id: str
    folder_id: str | None = None


@dataclass
class SeedTask:
    name: str
    list_name: str
    description: str


# ─── Discovery ────────────────────────────────────────────────────────────────


def discover_spaces(token: str, team_id: str) -> list[Space]:
    data = _get(f"https://api.clickup.com/api/v2/team/{team_id}/space?archived=false", token)
    return [Space(id=str(s["id"]), name=str(s.get("name", s["id"]))) for s in data.get("spaces", [])]


def discover_workspace(token: str, team_id: str) -> tuple[list[Space], list[Folder], list[ClickList]]:
    spaces = discover_spaces(token, team_id)
    folders: list[Folder] = []
    lists: list[ClickList] = []
    for space in spaces:
        try:
            data = _get(f"https://api.clickup.com/api/v2/space/{space.id}/folder?archived=false", token)
            for f in data.get("folders", []):
                folder = Folder(id=str(f["id"]), name=str(f.get("name", f["id"])), space_id=space.id)
                folders.append(folder)
                for lst in f.get("lists", []):
                    lists.append(
                        ClickList(
                            id=str(lst["id"]),
                            name=str(lst.get("name", lst["id"])),
                            space_id=space.id,
                            folder_id=folder.id,
                        )
                    )
        except Exception as exc:
            print(f"  [warn] Could not fetch folders for space {space.name}: {exc}")
        try:
            data = _get(f"https://api.clickup.com/api/v2/space/{space.id}/list?archived=false", token)
            for lst in data.get("lists", []):
                lists.append(ClickList(id=str(lst["id"]), name=str(lst.get("name", lst["id"])), space_id=space.id))
        except Exception as exc:
            print(f"  [warn] Could not fetch folderless lists for space {space.name}: {exc}")
    return spaces, folders, lists


def choose_space(spaces: list[Space], lists: list[ClickList], requested: str | None) -> Space:
    if requested:
        match = next((s for s in spaces if s.name.lower() == requested.lower()), None)
        if not match:
            available = ", ".join(s.name for s in spaces)
            raise SystemExit(f"[error] Space '{requested}' not found. Available: {available}")
        return match

    # Prefer the space containing the existing BOS backlog mirror.
    mirror = next((l for l in lists if l.name.lower() in {"klaroha bos", "agent backlog mirror"}), None)
    if mirror:
        return next(s for s in spaces if s.id == mirror.space_id)
    if not spaces:
        raise SystemExit("[error] No ClickUp spaces found.")
    return spaces[0]


def fetch_task_index(token: str, lists: list[ClickList]) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for lst in lists:
        page = 0
        while True:
            try:
                data = _get(
                    f"https://api.clickup.com/api/v2/list/{lst.id}/task"
                    f"?archived=false&include_closed=true&subtasks=false&page={page}",
                    token,
                )
                tasks = data.get("tasks", []) if isinstance(data, dict) else []
                if not tasks:
                    break
                for task in tasks:
                    name = str(task.get("name", "")).strip()
                    if name:
                        index[name.lower()] = {
                            "id": str(task["id"]),
                            "name": name,
                            "list_id": lst.id,
                            "description": task.get("description") or task.get("text_content") or "",
                        }
                page += 1
                if len(tasks) < 100:
                    break
            except Exception as exc:
                print(f"  [warn] Could not fetch tasks from list '{lst.name}': {exc}")
                break
    return index


# ─── Content parsing ──────────────────────────────────────────────────────────


def _slug(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "general"


def infer_topic(text: str) -> str:
    t = text.lower()
    rules = [
        ("extension-host", ["extension host", "compatibility", "lockfile", "failure quarantine", "sdk/abi"]),
        ("plugin-lifecycle", ["plugin", "hook", "activation", "contribution", "specialist"]),
        ("strategy-workflow", ["strategy workflow", "gtm", "marketing plan", "campaign plan"]),
        ("creative-supply-chain", ["creative", "media", "image", "video", "composition", "brand-locked"]),
        ("google-drive", ["google drive", "drive"]),
        ("clickup", ["clickup"]),
        ("cmo-chat", ["cmo", "chat", "reply", "scope:", "run:"]),
        ("stream", ["stream", "approvalbundle", "artifact card"]),
        ("ai-providers", ["gemini", "openai", "openrouter", "nvidia", "provider"]),
        ("deployment-ops", ["deploy", "staging", "production", "oauth", "relay", "ci", "ghcr", "docker", "nginx"]),
    ]
    for topic, needles in rules:
        if any(n in t for n in needles):
            return topic
    return _slug(text[:60])


def decision_list_for(decision: str, rationale: str, topic: str) -> str:
    t = f"{decision} {rationale}".lower()
    if topic in {"plugin-lifecycle", "google-drive", "clickup"} or any(x in t for x in ["plugin", "google ads", "search console", "wordpress", "gmail"]):
        return "Plugin Decisions"
    if topic in {"stream", "cmo-chat"} or any(x in t for x in ["ui", "ux", "admin", "mobile", "surface"]):
        return "Product UX Decisions"
    if topic in {"deployment-ops", "ai-providers"} or any(x in t for x in ["deploy", "staging", "oauth", "provider", "docker"]):
        return "Deployment Ops Decisions"
    if any(x in t for x in ["capability", "strategy", "media.image", "media.video", "workflow"]):
        return "Capability Decisions"
    return "Architecture Decisions"


def parse_decisions(limit: int) -> list[SeedTask]:
    if not BACKLOG_PATH.exists():
        return []
    rows: list[tuple[str, str, str]] = []
    in_log = False
    for raw in BACKLOG_PATH.read_text(encoding="utf-8").splitlines():
        if raw.startswith("## Decisions Log"):
            in_log = True
            continue
        if in_log and raw.startswith("## "):
            break
        if not in_log or not raw.startswith("| 20"):
            continue
        parts = [p.strip() for p in raw.strip().strip("|").split("|")]
        if len(parts) >= 3:
            rows.append((parts[0], parts[1], parts[2]))
    tasks: list[SeedTask] = []
    for date, decision, rationale in rows[:limit]:
        topic = infer_topic(f"{decision} {rationale}")
        list_name = decision_list_for(decision, rationale, topic)
        name = f"[DECISION][{topic}] {decision}"
        desc = (
            "Record Type: Decision\n"
            f"Topic: {topic}\n"
            f"Decision Date: {date}\n"
            "Status: locked\n"
            "Source of Truth: BACKLOG.md Decisions Log"
        )
        if BRIEF_PATH.exists():
            desc += "; PROJECT_BRIEF.md"
        desc += (
            "\n\nDecision:\n"
            f"{decision}\n\n"
            "Rationale:\n"
            f"{rationale}\n\n"
            "How to review this topic:\n"
            f"Search ClickUp for: [{topic}]\n"
        )
        tasks.append(SeedTask(name=name, list_name=list_name, description=desc))
    return tasks


def parse_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    block = text[3:end]
    data: dict[str, str] = {}
    for line in block.splitlines():
        if ":" not in line or line.startswith(" "):
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def scan_capability_tasks() -> list[SeedTask]:
    tasks: list[SeedTask] = []

    for item in CORE_CAPABILITY_CARDS:
        tasks.append(
            SeedTask(
                name=item["name"],
                list_name="Core Capabilities",
                description=(
                    "Record Type: Core Capability\n"
                    f"Topic: {item['topic']}\n"
                    "Source of Truth: PROJECT_BRIEF.md / BITE.md\n\n"
                    f"Purpose:\n{item['description']}\n\n"
                    f"How to review this topic:\nSearch ClickUp for: [{item['topic']}]\n"
                ),
            )
        )

    for skill_path in sorted((ROOT / "api").glob("**/SKILL.md")):
        if "/.venv/" in str(skill_path):
            continue
        meta = parse_frontmatter(skill_path)
        module_id = meta.get("module_id") or meta.get("id")
        if not module_id or module_id.lower() in {"null", "none", "false"}:
            continue
        status = (meta.get("status") or "active").lower()
        allowed = meta.get("allowed_from_chat", "")
        rel = skill_path.relative_to(ROOT)
        is_plugin = "api/plugins/" in str(rel)
        if status in {"retired", "deprecated"}:
            list_name = "Retired Capabilities"
        elif is_plugin:
            list_name = "Plugin Capabilities"
        else:
            list_name = "First-Party Capabilities"
        topic = infer_topic(module_id)
        name = f"[CAPABILITY] {module_id}"
        desc = (
            "Record Type: Capability\n"
            f"Capability ID: {module_id}\n"
            f"Topic: {topic}\n"
            f"Source Path: {rel}\n"
            f"Status: {status}\n"
            f"Allowed From Chat: {allowed or 'unspecified'}\n"
            f"Surface: {'Plugin capability' if is_plugin else 'First-party capability'}\n\n"
            "How to review this capability:\n"
            f"Search ClickUp for: {module_id} OR [{topic}]\n"
        )
        tasks.append(SeedTask(name=name, list_name=list_name, description=desc))

    for manifest_path in sorted((ROOT / "api" / "plugins").glob("*/channel.json")):
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        plugin_id = str(data.get("plugin_id") or manifest_path.parent.name)
        topic = infer_topic(plugin_id)
        capability_ids = data.get("capability_ids") or data.get("capabilities") or []
        if isinstance(capability_ids, dict):
            capability_ids = list(capability_ids.keys())
        rel = manifest_path.relative_to(ROOT)
        name = f"[PLUGIN] {plugin_id}"
        desc = (
            "Record Type: Plugin\n"
            f"Plugin ID: {plugin_id}\n"
            f"Topic: {topic}\n"
            f"Source Path: {rel}\n"
            f"Version: {data.get('version', 'unspecified')}\n"
            f"Capabilities: {', '.join(map(str, capability_ids)) if capability_ids else 'unspecified'}\n"
            "Status: installed candidate; activation/readiness may be brand-scoped\n\n"
            "How to review this plugin:\n"
            f"Search ClickUp for: [PLUGIN] {plugin_id} OR [{topic}]\n"
        )
        tasks.append(SeedTask(name=name, list_name="Plugin Capabilities", description=desc))

    # Deduplicate by task name while preserving first occurrence.
    seen: set[str] = set()
    deduped: list[SeedTask] = []
    for task in tasks:
        key = task.name.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(task)
    return deduped


# ─── Mutations ────────────────────────────────────────────────────────────────


def ensure_structure(token: str, space: Space, folders: list[Folder], lists: list[ClickList], apply: bool) -> tuple[list[Folder], list[ClickList]]:
    folder_by_name = {f.name.lower(): f for f in folders if f.space_id == space.id}
    list_by_folder_and_name = {(l.folder_id, l.name.lower()): l for l in lists if l.space_id == space.id}

    for folder_name, list_names in DESIRED_FOLDERS.items():
        folder = folder_by_name.get(folder_name.lower())
        if folder:
            print(f"  ✓ folder exists: {folder_name}")
        else:
            print(f"  + folder missing: {folder_name}")
            if apply:
                created = _post(f"https://api.clickup.com/api/v2/space/{space.id}/folder", token, {"name": folder_name})
                folder = Folder(id=str(created["id"]), name=str(created.get("name", folder_name)), space_id=space.id)
                folders.append(folder)
                folder_by_name[folder.name.lower()] = folder
                time.sleep(WRITE_DELAY)
            else:
                folder = Folder(id=f"dry-folder-{_slug(folder_name)}", name=folder_name, space_id=space.id)
                folders.append(folder)
                folder_by_name[folder.name.lower()] = folder

        for list_name in list_names:
            if list_name == "Agent Backlog Mirror":
                existing_mirror = next(
                    (l for l in lists if l.space_id == space.id and l.name.lower() in {"agent backlog mirror", "klaroha bos"}),
                    None,
                )
                if existing_mirror:
                    print(f"    ✓ backlog mirror exists as: {existing_mirror.name}")
                    continue
            existing = list_by_folder_and_name.get((folder.id, list_name.lower()))
            if existing:
                print(f"    ✓ list exists: {list_name}")
                continue
            print(f"    + list missing: {list_name}")
            if apply and not folder.id.startswith("dry-folder-"):
                created = _post(f"https://api.clickup.com/api/v2/folder/{folder.id}/list", token, {"name": list_name})
                new_list = ClickList(id=str(created["id"]), name=str(created.get("name", list_name)), space_id=space.id, folder_id=folder.id)
                lists.append(new_list)
                list_by_folder_and_name[(folder.id, new_list.name.lower())] = new_list
                time.sleep(WRITE_DELAY)
            elif not apply:
                new_list = ClickList(
                    id=f"dry-list-{_slug(folder_name)}-{_slug(list_name)}",
                    name=list_name,
                    space_id=space.id,
                    folder_id=folder.id,
                )
                lists.append(new_list)
                list_by_folder_and_name[(folder.id, new_list.name.lower())] = new_list
    return folders, lists


def seed_tasks(token: str, lists: list[ClickList], tasks: list[SeedTask], apply: bool, update_existing: bool) -> None:
    desired_lists = {name for names in DESIRED_FOLDERS.values() for name in names}
    target_lists = [l for l in lists if l.name in desired_lists]
    list_by_name = {l.name.lower(): l for l in target_lists}
    task_index = fetch_task_index(token, target_lists)

    to_create: list[SeedTask] = []
    to_update: list[tuple[SeedTask, str]] = []
    skipped = 0

    for task in tasks:
        if task.list_name.lower() not in list_by_name:
            print(f"  [warn] Target list missing for seed task: {task.list_name} :: {task.name}")
            continue
        existing = task_index.get(task.name.lower())
        if existing:
            if update_existing:
                to_update.append((task, existing["id"]))
            else:
                skipped += 1
        else:
            to_create.append(task)

    print("\nSeed plan:")
    print(f"  Existing/skipped : {skipped}")
    print(f"  To create        : {len(to_create)}")
    print(f"  To update        : {len(to_update)}")

    for task in to_create[:40]:
        print(f"  + {task.list_name}: {task.name[:90]}")
    if len(to_create) > 40:
        print(f"  … and {len(to_create) - 40} more creations")

    if not apply:
        print("\n[DRY RUN] No ClickUp changes applied. Re-run with --apply to create folders/lists/tasks.")
        return

    created = 0
    errors = 0
    for task in to_create:
        target = list_by_name[task.list_name.lower()]
        try:
            _post(
                f"https://api.clickup.com/api/v2/list/{target.id}/task",
                token,
                {
                    "name": task.name,
                    "description": task.description,
                    "notify_all": False,
                },
            )
            created += 1
            print(f"  + created {task.name[:80]}")
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")[:300]
            errors += 1
            print(f"  ✗ create failed {task.name[:80]}: HTTP {exc.code} {body}")
        except Exception as exc:
            errors += 1
            print(f"  ✗ create failed {task.name[:80]}: {exc}")
        time.sleep(WRITE_DELAY)

    updated = 0
    if update_existing:
        for task, task_id in to_update:
            try:
                _put(
                    f"https://api.clickup.com/api/v2/task/{task_id}",
                    token,
                    {"description": task.description},
                )
                updated += 1
                print(f"  ↑ updated {task.name[:80]}")
            except Exception as exc:
                errors += 1
                print(f"  ✗ update failed {task.name[:80]}: {exc}")
            time.sleep(WRITE_DELAY)

    print("\nApplied:")
    print(f"  Created: {created}")
    print(f"  Updated: {updated}")
    print(f"  Errors : {errors}")


# ─── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Organize BOS ClickUp into Decision Ledger + Capability Map.")
    parser.add_argument("--apply", action="store_true", help="Apply changes. Default is dry-run.")
    parser.add_argument("--dry-run", action="store_true", help="Explicit dry-run; no changes applied.")
    parser.add_argument("--space", help="ClickUp space name. Defaults to the space containing 'Klaroha BOS'.")
    parser.add_argument("--decisions", type=int, default=20, help="Number of latest Decisions Log rows to seed.")
    parser.add_argument("--update-existing", action="store_true", help="Refresh descriptions for existing seeded tasks.")
    args = parser.parse_args()

    apply = bool(args.apply and not args.dry_run)

    token = os.environ.get("CLICKUP_API_TOKEN", "").strip()
    team_id = os.environ.get("CLICKUP_TEAM_ID", "").strip()
    if not token:
        raise SystemExit("[error] CLICKUP_API_TOKEN not set.")
    if not team_id:
        raise SystemExit("[error] CLICKUP_TEAM_ID not set.")

    print(f"Reference sample: {SAMPLE_PATH.relative_to(ROOT)}")
    print("Discovering ClickUp workspace…")
    spaces, folders, lists = discover_workspace(token, team_id)
    print(f"Found {len(spaces)} spaces, {len(folders)} folders, {len(lists)} lists.")
    space = choose_space(spaces, lists, args.space)
    print(f"Target space: {space.name} ({space.id})")

    print("\nEnsuring folder/list structure…")
    folders, lists = ensure_structure(token, space, folders, lists, apply=apply)

    if apply:
        # Refresh after folder/list creation so new list IDs are available.
        spaces, folders, lists = discover_workspace(token, team_id)

    seed = parse_decisions(args.decisions) + scan_capability_tasks()
    print(f"\nPrepared {len(seed)} curated seed tasks ({args.decisions} decision rows max + capability/plugin cards).")
    seed_tasks(token, lists, seed, apply=apply, update_existing=args.update_existing)

    print("\nNext manual ClickUp views to create:")
    print("  - Topic Timeline: search/filter task name or description contains [<topic>] or Capability ID")
    print("  - Decision Ledger by Topic: grouped by list, sorted newest first")
    print("  - Capability Map: grouped by list, search [CAPABILITY] or [PLUGIN]")


if __name__ == "__main__":
    main()
