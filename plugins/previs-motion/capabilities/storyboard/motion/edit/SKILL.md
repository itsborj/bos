---
id: storyboard.motion.edit
name: previs-motion-edit
module_id: storyboard.motion.edit
description: Revise an existing Previs Motion video using a JSON edit instruction and the prior generated video as reference. Consumes Storyboard JSON/video outputs; does not create its own storyboard.
scope: module
status: active
version: 0.1.0
allowed_from_chat: false
requires_intent:
  - revision
triggers:
  - revise previs video
  - edit previs video
  - json video edit
  - edit generated storyboard video
  - change storyboard motion video
excluded_triggers:
  - create storyboard
  - validate storyboard
  - image only
  - publish video
output_contract:
  - video_asset
  - previs_motion_video
metadata:
  plugin_id: channel.previs_motion
---

## Usage boundary

Artifact-action capability only. Use after a Previs Motion video artifact exists and
provides `reference_video_url` or `reference_video_url_path` plus an
`edit_instruction` / `revision_instruction`.

This is a capability alias over the Previs Motion renderer that forces
`mode: video_to_video`, sending the prior video as `reference_video` to Seedance
for a true video edit. If the reference video URL has expired, the render module
automatically falls back to image-to-video when a storyboard image is available.
