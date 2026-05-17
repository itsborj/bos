---
id: marketing.channel.clickup.tasks.sync_backlog_item
module_id: marketing.channel.clickup.tasks.sync_backlog_item
name: clickup-sync-backlog-item
description: Find a ClickUp task by name and update its status. Used by AI agents to mirror BACKLOG.md completions to ClickUp — search by task text, patch status to complete/in-progress/etc.
scope: module
status: active
version: 1.0.0
allowed_from_chat: true
triggers:
  - sync backlog item to clickup
  - mark backlog task complete in clickup
  - backlog item done
  - update clickup by task name
excluded_triggers:
  - create task
  - read tasks
  - list tasks
---
