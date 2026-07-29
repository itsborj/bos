---
id: marketing.channel.tiktok.video.publish
name: tiktok-video-publish
description: Use when the user explicitly asks the CMO to upload, post, or publish a specific video to TikTok. Requires a video_file, video_path, video_url, or asset_url. Defaults to private/self-only posting unless the operator explicitly asks for another permitted privacy level.
scope: module
status: active
version: 0.1.0
allowed_from_chat: true
module_id: marketing.channel.tiktok.video.publish
requires_intent:
  - generation
  - approval
  - discussion
triggers:
  - upload to tiktok
  - publish tiktok video
  - post tiktok video
  - post a tiktok video
  - post tiktok videos
  - direct post to tiktok
  - tiktok content posting api
excluded_triggers:
  - validate tiktok
  - check tiktok
  - tiktok analytics
  - tiktok photo post
  - publish image to tiktok
memory_slots:
  - brand_profile
related_modules:
  - marketing.channel.tiktok.video.publish
quality_gates:
  - video_asset_required
  - tiktok_credentials_required
  - default_privacy_self_only
metadata:
  version: 0.1.0
  plugin_id: channel.tiktok
  implements: marketing.execute
  artifact_type: action_artifact
  platform: tiktok
  risk_policy: approval_gated
---

# TikTok Video Publish

When dispatching, include any known fields immediately after RUN:

```text
RUN: marketing.channel.tiktok.video.publish
video_url: <url or file path>
caption: <caption or title>
description: <optional extra context>
privacy: private
```

Privacy mapping:
- `private` → `SELF_ONLY`
- `friends` → `MUTUAL_FOLLOW_FRIENDS`
- `followers` → `FOLLOWER_OF_CREATOR`
- `public` → `PUBLIC_TO_EVERYONE` when the creator account allows it

If the user has not provided a video asset, ask for the MP4/file URL. Do not dispatch with a fake video.
