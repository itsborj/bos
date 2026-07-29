---
id: storyboard.render
name: storyboard-render
module_id: storyboard.render
description: Render an operator-approved storyboard or video script into an image, or revise an existing storyboard image. The CMO writes the script as a conversational reply first; only call this after the operator explicitly approves.
scope: module
status: active
version: 2.0.0
allowed_from_chat: true
requires_intent:
  - approval
  - revision
triggers:
  - yes render it
  - proceed with render
  - go ahead render
  - use that version
  - approved render
  - render storyboard
  - revise storyboard image
output_contract:
  - image_asset
metadata:
  plugin_id: channel.storyboard
---

## Workflow

The CMO writes the full storyboard or video script as a plain text reply. The operator reads and reacts — revisions happen in chat. When the operator approves, the CMO calls `storyboard_render` with the approved text.

**Step 1 — Write the script (text reply, no tool call)**
Compose the full storyboard using loaded brand, product/offer, audience, and campaign context. Do not ask the operator for scenes or visuals. Do not call any tool.

**Step 2 — Iterate in chat**
Operator revises in chat. CMO rewrites. No tool calls until the operator approves.

**Step 3 — Operator approves**
Operator says "yes", "proceed", "go", "use that", or pastes a version they want.

**Step 4 — Call storyboard_render**
Pass the full approved text as `storyboard_text`. Brand logo and assets are auto-injected from Drive.

## Revision (image already rendered)

When the operator asks to change an existing storyboard image, call `storyboard_render` again with:
- `source_run_id` — run ID of the current image
- `revision_prompt` — precise, panel-referenced instruction (what to change, what to preserve)
- `storyboard_text` — updated script if the copy changed
