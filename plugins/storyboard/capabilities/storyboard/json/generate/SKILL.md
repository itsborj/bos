---
id: storyboard.generate
name: storyboard-generate-approved-json-image-alias
module_id: storyboard.generate
description: Legacy alias for storyboard.render. Not chat-routable; broad video/storyboard requests must use storyboard.create first for a text/JSON artifact.
scope: module
status: active
version: 1.1.0
allowed_from_chat: false
requires_intent:
  - generation
  - revision
triggers:
  - render approved storyboard
  - generate approved storyboard image
excluded_triggers:
  - i need a video
  - need a video
  - make a video
  - create a video
  - storyboard
  - create storyboard
  - draft storyboard
  - publish video
output_contract:
  - image_asset
metadata:
  plugin_id: channel.storyboard
---

Backward-compatible alias of `storyboard.render`. Do not dispatch from CMO chat
for initial storyboard requests.
