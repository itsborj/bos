---
id: storyboard.motion.render
name: previs-motion-render
module_id: storyboard.motion.render
description: Render or revise a motion previs/animatic final-cut candidate from an approved Storyboard JSON/image. Consumes storyboard output; does not create its own storyboard.
scope: module
status: active
version: 0.1.0
allowed_from_chat: false
requires_intent:
  - generation
  - revision
triggers:
  - previs motion
  - animate storyboard
  - storyboard to video
  - render storyboard video
  - animatic render
  - json video edit
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

Artifact-action capability only. Do not dispatch from a first-pass CMO chat turn.
Use after a reviewed Storyboard Image artifact declares `generate_video` and passes
`source_image_path` or `source_image_data_b64` from the Storyboard plugin output.
The Storyboard Image artifact should also carry the approved production blueprint
(`production_blueprint` / `storyboard_text` / `storyboard_spec.production_blueprint`).
The final video prompt must consume both the approved image storyboard and the
approved blueprint text/JSON; do not treat the image alone as the full brief.
In the current product, treat this render as the final-cut candidate for client
review, not as a throwaway rough cut.

Consumes `storyboard_spec`/`spec_path` plus either a storyboard `source_image_path` for image-to-video, a `reference_video_url` for JSON video edits, or an explicit `mode: text_to_video` direct prompt (`seedance_prompt`, `raw_prompt`, `direct_prompt`, `text_to_video_prompt`, or `prompt`). Direct T2V prompts are passed to Seedance as the single text content item without prompt splitting/sanitization so large Markdown timing/audio constraints are preserved. Returns a `video_asset` with audit paths and next-edit reference metadata.
