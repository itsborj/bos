# ClickUp Decision + Capability System v1 — Sample

Purpose: split ClickUp into a human-readable control plane while preserving the existing BACKLOG.md → ClickUp task mirror for AI/dev coordination.

## Desired ClickUp shape

```text
Space: Klaroha BOS

Folder: Execution Backlog
  List: Agent Backlog Mirror       # existing noisy BACKLOG.md sync target may remain here
  List: Active Sprint              # optional curated sprint list
  List: Bugs / Regressions         # optional curated incident/bug list
  List: Release Checklist          # optional per-release checklist

Folder: Decision Ledger
  List: Architecture Decisions
  List: Capability Decisions
  List: Plugin Decisions
  List: Product UX Decisions
  List: Deployment Ops Decisions

Folder: Capability Map
  List: Core Capabilities
  List: First-Party Capabilities
  List: Plugin Capabilities
  List: Retired Capabilities
```

## Decision task sample

Task name:

```text
[DECISION][extension-host] BOS needs Extension Host + compatibility/release-integrity layer for true plugin backwards compatibility
```

Task description:

```text
Record Type: Decision
Topic: extension-host
Decision Date: 2026-06-07
Status: locked
Source of Truth: BACKLOG.md Decisions Log; PROJECT_BRIEF.md v3.55

Decision:
BOS needs an Extension Host + compatibility/release-integrity layer for true plugin backwards compatibility.

Rationale:
Hooks, activation, and contribution points are necessary but not sufficient. Mature extensible systems preserve old behavior through a stable public SDK/ABI, compatibility adapters, installed-state registry/lockfile, capability manifest diffing, explicit retirement/uninstall ledger, and plugin failure quarantine. This prevents plugin updates or core changes from silently breaking, disappearing, or rolling back capabilities.

How to review this topic:
Search ClickUp for: [extension-host]
Expected result: latest 10–20 decisions/actions/bugs/releases tagged in task names or descriptions.
```

## Capability card sample

Task name:

```text
[CAPABILITY] marketing.planning.strategy_workflow
```

Task description:

```text
Record Type: Capability
Capability ID: marketing.planning.strategy_workflow
Topic: strategy-workflow
Source Path: api/capabilities/marketing/planning/strategy_workflow/SKILL.md
Status: active
Allowed From Chat: true
Surface: First-party capability

Purpose:
Canonical strategy/marketing-plan workflow. Produces a persisted WorkflowRun with component rows.

How to review this capability:
Search ClickUp for: marketing.planning.strategy_workflow OR [strategy-workflow]
```

## Plugin card sample

Task name:

```text
[PLUGIN] google-drive
```

Task description:

```text
Record Type: Plugin
Plugin ID: google-drive
Topic: google-drive
Source Path: api/plugins/google-drive/channel.json
Capabilities: drive.folder.setup, drive.asset.upload, drive.asset.list, drive.asset.get
Status: installed
Activation: per-brand connection required
```

## Topic timeline sample

ClickUp search/filter target:

```text
Topic = extension-host
or search text: [extension-host]
```

Expected human output:

| Date | Type | Item | Status | Source |
|---|---|---|---|---|
| 2026-06-07 | Decision | BOS needs Extension Host + compatibility layer | locked | PROJECT_BRIEF v3.55 |
| 2026-06-07 | Action | Create BITE sample for plugin lockfile | backlog | sample needed |
| 2026-06-07 | Action | Define PluginManifestV1 schema | backlog | pending |
| 2026-06-07 | Risk | Filesystem scan can mimic rollback | open | PROJECT_BRIEF v3.55 |

## Cleanup rule

The current noisy backlog mirror is not deleted. If the existing sync list is named `Klaroha BOS`, it remains the live sync target until deliberately renamed/moved later. Treat it as the Agent Backlog Mirror rather than duplicating or deleting it.

Human-facing review happens through:

```text
Decision Ledger
Capability Map
Topic search: [topic]
Capability search: [CAPABILITY] <module_id>
Plugin search: [PLUGIN] <plugin_id>
```

No destructive archive/delete action should run until the new structure is verified by the operator.
