---
id: marketing.channel.youtube.connection.validate
name: youtube-connection-validate
description: Use when the operator explicitly asks to validate, test, check, or troubleshoot the connected YouTube API/OAuth pipeline. This is a read-only connector health check; do not use for uploading, publishing, editing channel metadata, reading analytics, or creating video assets.
scope: diagnostic
status: active
version: 0.1.0
allowed_from_chat: true
module_id: marketing.channel.youtube.connection.validate
requires_intent:
  - diagnostic
  - discussion
triggers:
  - validate youtube api
  - test youtube connection
  - check youtube oauth
  - youtube connection
  - youtube api pipeline
  - troubleshoot youtube
excluded_triggers:
  - upload to youtube
  - publish youtube video
  - youtube shorts publish
  - update youtube channel
  - youtube analytics
memory_slots:
  - brand_profile
related_modules:
  - marketing.channel.youtube.connection.validate
resources:
  - sample/connection_validate_v1.md
output_contract:
  - youtube_connection_check
quality_gates:
  - read_only_no_mutation
  - credentials_required
  - channel_identity_returned
metadata:
  version: 0.1.0
  author: third_party_plugin_developer
  plugin_id: channel.youtube
  implements: marketing.optimize
  artifact_type: intelligence_artifact
  platform: youtube
  output_contract: youtube_connection_check
  risk_policy: read_only
---

# YouTube Connection Validate

## Purpose

Validate the brand-scoped YouTube OAuth and Data API pipeline without uploading or changing anything.

## Hard boundaries

- Read-only only.
- Calls `channels.list?part=id,snippet,statistics,status&mine=true` to prove the token works and identify the connected channel.
- Never uploads video, updates metadata, changes privacy, schedules content, comments, deletes, or edits channel fields.
- If credentials are missing or the API returns quota/permission errors, return a setup/blocker artifact instead of pretending the connection works.

## Outcome contract

Artifact/block type: `youtube_connection_check`
Risk policy: `read_only`
Changed resources: `[]`
Expected success fields: channel ID, channel title, endpoint checked, estimated quota units.
