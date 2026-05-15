---
id: marketing.channel.clickup.tasks.create
name: ClickUp Task Creator
description: Use only when the user explicitly confirms creating tasks in ClickUp. Before dispatching, tell the user what tasks will be created and ask for confirmation. Only dispatch RUN after the user confirms. Triggers on "create clickup tasks", "push to clickup", "add to clickup", "create the tasks", "push campaign plan to clickup". This capability creates tasks in the configured ClickUp list. Excluded triggers include reading, checking, or viewing tasks.
scope: module
status: active
version: 0.1.0
allowed_from_chat: true
module_id: marketing.channel.clickup.tasks.create
requires_intent:
  - action
  - generation
triggers:
  - create clickup tasks
  - push to clickup
  - add to clickup
  - create the tasks
  - push campaign plan to clickup
  - add campaign tasks to clickup
  - create tasks in clickup
  - push these to clickup
excluded_triggers:
  - check clickup
  - clickup status
  - show clickup tasks
  - what's in clickup
  - read clickup
  - view clickup tasks
memory_slots:
  - brand_profile
  - campaign_brand_kit
related_modules:
  - marketing.channel.clickup.tasks.read
output_contract:
  - clickup_tasks_created
quality_gates:
  - approval_confirmed_before_create
  - no_create_on_read_intent
  - task_list_non_empty
metadata:
  version: 0.1.0
  author: third_party_plugin_developer
  plugin_id: channel.clickup
  implements: marketing.execute
  artifact_type: action_result_artifact
  platform: clickup
  output_contract: clickup_tasks_created
  risk_policy: approval_gated_write
---

# ClickUp Task Creator

## Purpose

Create tasks in the configured ClickUp list from an approved campaign plan or explicit task list. This is an approval-gated write operation.

## Hard boundaries

Never:
- dispatch RUN without explicit user confirmation in the same turn
- create tasks from a capability question or discussion request
- delete or overwrite existing tasks

## CMO response behavior

Before dispatching, always show what will be created and ask for confirmation:

```text
I'll create these tasks in ClickUp:
- Google Ads copy draft — due May 20
- Email sequence #1 — due May 21
- Landing page headline variants — due May 22

Confirm?
```

Only after confirmation:
```text
Creating the tasks now.
RUN: marketing.channel.clickup.tasks.create
```

## Brief contract

The CMO should populate `brief["tasks"]` with an array of task objects before dispatching:

```json
[
  {
    "name": "Google Ads RSA copy draft",
    "description": "Draft 15 headlines and 4 descriptions for the Q2 launch campaign.",
    "due_date": "2026-05-20",
    "priority": 2,
    "status": "to do"
  }
]
```

If `brief["tasks"]` is empty, the module creates a single task from `brief["content"]` as a fallback.

## Outcome contract

Artifact type: `action_result_artifact`
Block/output contract: `clickup_tasks_created`
Platform: `clickup`
Risk policy: `approval_gated_write`

The module returns:
- `created[]` — array of created task objects with id, name, url, status, due_date
- `created_count` — integer
- `failed[]` — tasks that could not be created with error details
- `changed_resources` — list of created task IDs
- allowed next actions: view_in_clickup, dismiss
