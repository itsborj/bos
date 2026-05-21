# YouTube Specialist
Capability for managing YouTube video publishing, channel branding, and performance intelligence.

---
id: youtube.specialist
name: youtube-specialist
description: Use when the user wants to upload a video to YouTube, update their channel's about section, or analyze video performance.
scope: execution
status: active
allowed_from_chat: true
requires_intent:
  - generation
  - execution
  - diagnostic
triggers:
  - upload to youtube
  - publish youtube video
  - update youtube channel
  - youtube analytics
  - youtube shorts
memory_slots:
  - brand_profile
  - campaign_brand_kit
resources:
  - sample/video_publish_proposal.md
  - sample/channel_update_proposal.md
related_modules:
  - youtube.publish_video
  - youtube.update_channel
  - youtube.analytics
---

## Operating Contract

### 1. Video Publishing Flow
When a user wants to publish a video:
1. **Proposal Phase**: The `youtube.publish_video` module generates a metadata proposal (Title, Description, Tags) based on the video's context and the Brand Voice. This is output as a `youtube_publish_proposal` artifact.
2. **Approval Phase**: The CMO reviews and approves the proposal in the Stream.
3. **Execution Phase**: Upon approval, the `youtube.publish_video` module executes the actual upload via the YouTube Data API.

### 2. Channel Management Flow
When updating the channel page (e.g., "About" section):
1. **Proposal Phase**: Generate a `youtube_channel_update_proposal` showing Current vs Proposed text.
2. **Approval Phase**: CMO approves the change.
3. **Execution Phase**: The module updates the channel metadata.

### 3. Intelligence Flow
When analyzing performance:
1. Fetch metrics via `youtube.analytics`.
2. Return a `video_intelligence` artifact with actionable findings.

## Quality Gates
- **Metadata Length**: Titles must be $\le 100$ characters.
- **Brand Alignment**: Descriptions must include the primary brand CTA and match the Campaign Brand Kit's tone.
- **Shorts Detection**: If the video is $\le 60$s and vertical, automatically include `#Shorts` in the title or description.
