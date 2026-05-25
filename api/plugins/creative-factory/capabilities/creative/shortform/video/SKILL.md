---
id: creative.shortform.video
name: shortform-video
module_id: creative.shortform.video
description: THE default capability for producing a short-form video creative. Use for "make a video / prepare a video / create a short / video for YouTube / video for TikTok / video for Instagram". Module composes hook and CTA from brand context automatically — optionally pass hook_text (max 120 chars), cta_text, aspect_ratio (9:16 default), duration (default 15s), background_color hex. Do NOT also dispatch a publish module — production and publishing are separate. Do NOT use for image requests.
scope: module
status: active
version: 0.1.0
allowed_from_chat: true
requires_intent:
  - generation
triggers:
  - make a video
  - create a video
  - generate a video
  - prepare a video
  - prepare video
  - short-form video
  - shortform video
  - make a short
  - create a short
  - video for youtube
  - video for tiktok
  - video for instagram
  - video for reels
  - video for shorts
  - generate a reel
  - make a reel
  - video creative
  - video attachment
excluded_triggers:
  - image
  - photo
  - thumbnail
  - facebook post
  - instagram post
  - creative pack
  - publish video
  - upload video
  - post video
  - post to youtube
  - post to tiktok
memory_slots:
  - brand_profile
  - campaign_brand_kit
---

## When to activate

Activate when the operator wants to produce a short-form video creative. The module
composes hook and CTA automatically from brand context — no params required. Pass
overrides only when the operator explicitly specifies them.

```
RUN: creative.shortform.video
hook_text: <optional override — max 120 chars>
cta_text: <optional override>
aspect_ratio: <optional — 9:16 · 16:9 · 1:1 · 4:5>
duration: <optional — seconds, default 15, max 60>
background_color: <optional — hex, default #1a1a1a>
text_color: <optional — hex, default #ffffff>
```

All params are optional. `brand_name` is resolved automatically — do not pass it.

Do NOT also dispatch a publish module for the same request. Production and publishing are
separate explicit steps. The artifact's action button handles the publish handoff.

## When NOT to activate

- Image requests → use `creative.post.image`
- Publishing a video that already exists → use `marketing.channel.youtube.video.publish` or the relevant channel plugin
- The operator explicitly says "draft only" or "just the script" → respond with copy only, no dispatch

## Requirements

- Google Drive connected for the active brand (Admin → Brands). Drive upload is non-fatal — the video still renders if Drive is not connected, but it will not be durable across container restarts.

## Output contract

Returns a `creative_shortform_video` block:

```json
{
  "type": "creative_shortform_video",
  "status": "succeeded",
  "video_path": "<local /tmp path — used by video player endpoint>",
  "hook_text": "<hook used>",
  "cta_text": "<cta used>",
  "aspect_ratio": "9:16",
  "duration": 15,
  "file_size_kb": 1240,
  "drive_file_id": "<Drive file id — null if Drive not connected>",
  "drive_web_view_link": "<Drive web viewer URL — null if Drive not connected>",
  "drive_folder": "Creative Assets/Shortform Video",
  "reusable": true,
  "allowed_actions": ["publish_youtube", "publish_facebook", "regenerate", "dismiss"],
  "action_modules": {
    "publish_youtube": "marketing.channel.youtube.video.publish",
    "publish_facebook": "marketing.channel.meta.video.publish"
  }
}
```

After dispatch, tell the operator to review the video in Stream. The review card shows
"Publish to YouTube" and "Publish to Facebook" buttons. Publishing is a separate explicit
step after review — do NOT also dispatch a publish module.

Example CMO reply after dispatch:
```
Short-form video produced.
Review it in Stream — choose YouTube or Facebook to publish once you're happy with it.
```
