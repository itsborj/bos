# TikTok Specialist
Capability for validating TikTok posting access and directly publishing a video through TikTok's official Content Posting API.

---
id: tiktok.specialist
name: tiktok-specialist
description: Use when the user wants to validate TikTok posting access or publish a video to TikTok.
scope: execution
status: active
allowed_from_chat: true
requires_intent:
  - generation
  - execution
  - diagnostic
triggers:
  - upload to tiktok
  - publish tiktok video
  - post tiktok video
  - direct post to tiktok
  - validate tiktok connection
  - test tiktok api
memory_slots:
  - brand_profile
  - campaign_brand_kit
related_modules:
  - marketing.channel.tiktok.connection.validate
  - marketing.channel.tiktok.video.publish
---

## Operating Contract

### 1. Connection Validation Flow
1. Use `marketing.channel.tiktok.connection.validate`.
2. Confirm the TikTok account identity and creator posting settings.
3. Return a read-only `tiktok_connection_check` artifact.

### 2. Direct Post Flow
1. Use `marketing.channel.tiktok.video.publish` only when a real video file or URL is present.
2. Read the creator's latest privacy options before posting.
3. Initialize the TikTok posting request, upload the video, and poll publish status.

## Quality Gates
- **Video Asset Required**: Do not dispatch publish without a real video asset.
- **Scope Required**: The TikTok token must include `video.publish`.
- **Private-by-default**: Default to `SELF_ONLY` unless the operator explicitly chooses another permitted privacy level.
