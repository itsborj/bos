---
id: marketing.channel.meta.video.publish
module_id: marketing.channel.meta.video.publish
name: facebook-video-publish
description: Publishes a video file to the brand's Facebook Page. Invoked as a declared action from a creative_shortform_video artifact — do NOT dispatch directly from CMO chat. The brief is built automatically from the approved artifact block (video_path, description, title).
scope: module
status: active
version: 1.0.0
allowed_from_chat: false
requires_intent:
  - publish
excluded_triggers:
  - draft
  - generate
  - create
metadata:
  version: 1.0.0
  author: bos
  plugin_id: channel.meta
---

## When to activate

This module is invoked as a declared artifact action — NOT dispatched by the CMO LLM directly.
It is triggered when the operator clicks "Publish to Facebook" on a `creative_shortform_video` artifact in Stream.

The brief is built from the approved artifact block: `video_path`, `hook_text`, `cta_text`, `description`.

## Requirements

- Facebook Page connected for the active brand (Admin → Brands)
- `video_path` present in brief and pointing to an existing MP4 file

## Output contract

Returns a `fb_page_video_result` block:

```json
{
  "type": "fb_page_video_result",
  "platform": "facebook",
  "status": "succeeded",
  "video_id": "<Facebook video ID>",
  "page_id": "<page ID>",
  "description_preview": "<first 280 chars of caption>",
  "permalink": "https://www.facebook.com/<video_id>",
  "changed_resources": ["<video_id>"],
  "allowed_actions": ["view_on_facebook", "dismiss"]
}
```
