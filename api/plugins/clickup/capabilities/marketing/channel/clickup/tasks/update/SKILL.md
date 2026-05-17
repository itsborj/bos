---
id: marketing.channel.clickup.tasks.update
module_id: marketing.channel.clickup.tasks.update
name: clickup-task-update
description: Update the status or details of an existing ClickUp task by task ID. Use when a BOS run is approved or rejected and the linked ClickUp task needs its status changed.
scope: module
status: active
version: 1.0.0
allowed_from_chat: true
triggers:
  - update clickup task
  - mark task done in clickup
  - set clickup task status
  - change task status in clickup
  - clickup task approved
  - clickup task rejected
excluded_triggers:
  - create task
  - new task
  - read tasks
  - list tasks
---
