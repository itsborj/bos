---
id: marketing.channel.clickup.tasks.read
name: ClickUp Campaign Task Status
description: Use when the user asks to check, view, show, or pull ClickUp task status, campaign task progress, or execution health. Triggers on "check clickup", "what's in clickup", "are we on track", "show campaign tasks", "clickup status", "task status". This capability returns a read-only intelligence artifact showing blocked, overdue, in-progress, and done task counts with notable items. Never creates, updates, or deletes tasks. For task creation, see tasks.create.
scope: module
status: active
version: 0.1.0
allowed_from_chat: true
module_id: marketing.channel.clickup.tasks.read
requires_intent:
  - diagnostic
  - discussion
triggers:
  - check clickup
  - clickup status
  - clickup connection
  - check clickup connection
  - verify clickup
  - test clickup
  - what's in clickup
  - show clickup tasks
  - campaign task status
  - are we on track
  - clickup progress
  - task progress
  - show campaign tasks
  - pull clickup
  - clickup tasks
  - execution status
excluded_triggers:
  - create clickup tasks
  - push to clickup
  - add to clickup
  - create the tasks
  - update task
  - mark task complete
memory_slots:
  - brand_profile
related_modules:
  - marketing.channel.clickup.tasks.create
output_contract:
  - clickup_task_status
quality_gates:
  - read_only_only
  - no_task_mutation
  - clickup_credentials_present
metadata:
  version: 0.1.0
  author: third_party_plugin_developer
  plugin_id: channel.clickup
  implements: marketing.optimize
  artifact_type: intelligence_artifact
  platform: clickup
  output_contract: clickup_task_status
  risk_policy: read_only_no_mutation
---

# ClickUp Campaign Task Status

## Purpose

Return a read-only intelligence artifact showing the status of tasks in the configured ClickUp list. Classifies tasks into blocked, overdue, in-progress, to-do, and done buckets.

## Hard boundaries

Never:
- create tasks
- update tasks
- delete tasks
- change task status, assignees, due dates, or priorities

## CMO response behavior

Keep the visible reply short:

```text
Pulling your ClickUp campaign task status.
RUN: marketing.channel.clickup.tasks.read
```

## Outcome contract

Artifact type: `intelligence_artifact`
Block/output contract: `clickup_task_status`
Platform: `clickup`
Risk policy: `read_only_no_mutation`

The module returns:
- task counts by bucket (blocked, overdue, in_progress, todo, done)
- notable task details for blocked and overdue (up to 5 each)
- in-progress tasks with assignees and due dates (up to 5)
- `read_only: true`
- `changed_resources: []`
- allowed next actions: create_followup_tasks, dismiss
