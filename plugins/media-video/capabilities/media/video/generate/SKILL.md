---
id: media.video.generate
name: video-generate
module_id: media.video.generate
description: Generate video or short-form motion creative from brand context or a prompt. Use for "make a video", "create a short", "video for YouTube", "video for TikTok", "video for Instagram", reels, shorts, and video creative requests. Dispatch immediately; hook, CTA, aspect ratio, and duration can be auto-resolved.
scope: module
status: active
version: 1.0.0
allowed_from_chat: true
requires_intent:
  - generation
triggers:
  - make a video
  - create a video
  - generate a video
  - prepare a video
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
excluded_triggers:
  - image
  - photo
  - thumbnail
  - facebook post
  - instagram post
  - publish video
  - upload video
  - post video
  - post to youtube
  - post to tiktok
memory_slots:
  - brand_profile
  - campaign_brand_kit
metadata:
  plugin_id: media.video
  legacy_module_ids:
    - creative.shortform.video
---

## When to activate

Activate when the operator wants a generated video or short-form motion asset. Pass
overrides only when the operator explicitly specifies them.

```
RUN: media.video.generate
video_prompt: <optional override>
hook_text: <optional override - max 120 chars>
cta_text: <optional override>
aspect_ratio: <optional - 9:16, 16:9, 1:1, 4:5>
duration: <optional - seconds, default 15, max 60>
background_color: <optional - hex, default #1a1a1a>
text_color: <optional - hex, default #ffffff>
```

Do not also dispatch a publish module. Production and publishing are separate.

## Requirements

Configure the video provider in Admin -> Specialists -> Video Generation. Google
Drive is optional but recommended for durable assets.

## Output contract

Returns a `video_asset` block with local playback metadata and optional Drive metadata.
