---
id: storyboard.render
name: storyboard-render-image
module_id: storyboard.render
description: Render an operator-approved storyboard or video script into an image. Call ONLY after writing the script in chat AND the operator explicitly approves. Never call on the initial request.
scope: module
status: active
version: 2.0.0
allowed_from_chat: true
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

## When to call

Only after both conditions are met:
1. The CMO has already written the storyboard script as a text reply in this conversation
2. The operator has explicitly approved it ("yes", "proceed", "go", "use that")

A request for a video ("need video", "make a video") is NOT approval — write the script first.

## Parameters

**render action:**
- `storyboard_text` (required) — the full approved script from the conversation
- `title` (optional) — short label
- `image_quality` (optional) — low / medium / high / auto (default: medium)
- `size` (optional) — default 1792x1024

**revise action:**
- `source_run_id` (required) — run ID of the existing storyboard image
- `revision_prompt` (required) — precise, panel-referenced instruction
- `storyboard_text` (optional) — updated script if copy changed
