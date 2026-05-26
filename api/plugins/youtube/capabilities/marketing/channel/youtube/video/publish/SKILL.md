---
id: marketing.channel.youtube.video.publish
name: youtube-video-publish
description: Use when the user explicitly asks the CMO to upload, post, or publish a specific video to YouTube. Requires a video_file, video_path, video_url, or asset_url plus title/description if provided. If no video asset is present, ask for the video file or URL instead of inventing one.
scope: module
status: active
version: 0.1.0
allowed_from_chat: true
module_id: marketing.channel.youtube.video.publish
requires_intent:
  - generation
  - approval
  - discussion
triggers:
  - upload to youtube
  - publish youtube video
  - post youtube video
  - post a youtube video
  - post youtube videos
  - can post youtube videos
  - upload youtube video
  - youtube shorts
excluded_triggers:
  - youtube analytics
  - check youtube
  - validate youtube
  - update youtube channel
memory_slots:
  - brand_profile
related_modules:
  - marketing.channel.youtube.video.publish
quality_gates:
  - video_asset_required
  - youtube_credentials_required
  - default_privacy_private
metadata:
  version: 0.1.0
  plugin_id: channel.youtube
  implements: marketing.execute
  artifact_type: action_artifact
  platform: youtube
  risk_policy: approval_gated
---

# YouTube Video Publish

When dispatching, include any known fields immediately after RUN:

```text
RUN: marketing.channel.youtube.video.publish
video_url: <url or file path>
title: <title>
description: <description>
privacy: private
```

If the user has not provided a video asset, ask for the MP4/file URL. Do not dispatch with a fake video.
