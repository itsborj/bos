---
id: storyboard.motion.render
name: previs-motion-storyboard-video-renderer
description: Consume an approved storyboard JSON/image from the Storyboard plugin and render or revise a Seedance previs/animatic video. Use for storyboard-to-video, image-to-video from storyboard frames, or JSON-based video edits using a prior generated video as reference.
scope: module
status: active
version: 0.1.0
allowed_from_chat: true
module_id: storyboard.motion.render
requires_intent:
  - generation
  - revision
triggers:
  - previs motion
  - render previs
  - animate storyboard
  - storyboard to video
  - render storyboard video
  - make storyboard move
  - animatic render
  - generate animatic
  - seedance storyboard
  - json video edit
  - edit generated storyboard video
excluded_triggers:
  - create storyboard
  - generate storyboard json
  - validate storyboard
  - image only
  - publish video
  - upload youtube
output_contract:
  - video_asset
  - previs_motion_video
metadata:
  plugin_id: channel.previs_motion
---

## What this plugin does

Previs Motion turns an already-approved storyboard output into a motion previs / animatic video. It does **not** create its own storyboard. It consumes the existing Storyboard plugin's `storyboard_json` and `image_asset` outputs, then sends a JSON target-state prompt plus references to Seedance 2.0 through BytePlus ModelArk.

## When to invoke

Invoke when the operator asks to:

- Animate an approved storyboard image or act sheet.
- Convert storyboard JSON + contact sheet/keyframe sheet into video.
- Generate a previs/animatic from Storyboard plugin output.
- Perform a JSON-based edit on a generated video using the previous video as `reference_video`.
- Preserve storyboard continuity while changing a specific motion/detail field.

## Inputs to pass when available

```yaml
RUN: storyboard.motion.render
storyboard_spec: <approved Storyboard JSON object>
spec_path: <optional path to Storyboard JSON>
source_image_path: <optional approved storyboard/keyframe image path for I2V>
source_image_data_b64: <optional image data>
reference_video_url: <optional prior Seedance temporary URL for V2V edit>
reference_video_url_path: <optional file containing prior temporary URL>
edit_instruction: <optional user edit for V2V JSON edit>
mode: <optional image_to_video | video_to_video | auto>
duration: <optional seconds, default 15, max 15>
ratio: <optional 16:9 | 9:16 | 1:1 | 4:3 | 3:4 | 21:9>
resolution: <optional 480p | 720p | 1080p>
model: <optional Seedance model id; Admin backend setting wins when configured>
generate_audio: <optional boolean, default true>
```

## Routing rules

- If `reference_video_url` or `reference_video_url_path` is present, run JSON-based video-to-video edit.
- Else if `source_image_path` or `source_image_data_b64` is present, run storyboard image-to-video.
- Do not invent a storyboard. If no storyboard spec/image/video reference is available, ask for the Storyboard output first.

## Known Issue — OutputAudioSensitiveContentDetected

Seedance audio generation can trigger a content safety error (`OutputAudioSensitiveContentDetected`)
when the storyboard prompt contains sensitive themes.

`generate_audio` defaults to `True`. To force a visual-only render or avoid audio moderation
on sensitive content, pass `generate_audio: false` explicitly in the brief.

---

## Voice-over localization note

Seedance 2 can generate short Filipino/Tagalog voice-over in a fresh generation when the Filipino script is stated directly. In V2V edits, requests like “translate/localize the voice-over to Filipino” may not replace the existing audio because the reference video is treated as locked. For localization revisions, prefer editing the canonical Storyboard/Previs JSON voice-over script first, then pass the revised Filipino script explicitly near the top of the prompt. For production-grade dubbing, use a separate TTS/dubbing step and mux the audio onto the Seedance-rendered video.

## Output contract

Returns a native BOS `video_asset` block plus Previs Motion audit fields:

- `video_path`
- `video_url`
- `task_id`
- `target_json_path`
- `payload_path`
- `task_path`
- `storyboard_spec`
- `mode`
- `provider`
- `model`
- allowed actions: `publish_review`, `revise`, `regenerate`, `dismiss`
