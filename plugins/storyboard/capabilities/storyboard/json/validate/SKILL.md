---
id: storyboard.validate
name: storyboard-validate-json-spec
module_id: storyboard.validate
description: Validate a JSON-first storyboard spec before render or revision.
scope: module
status: active
version: 1.0.0
allowed_from_chat: true
requires_intent:
  - diagnostic
triggers:
  - validate storyboard
  - check storyboard json
  - storyboard qa
  - inspect storyboard spec
excluded_triggers:
  - publish video
output_contract:
  - storyboard_validation
metadata:
  plugin_id: channel.storyboard
---

## Validation workflow

Checks for required storyboard sections, acts, shots, duplicate shot numbers, and missing render-control fields such as `image_prompt`, `composition`, `action`, `must_include`, and `must_avoid`.
