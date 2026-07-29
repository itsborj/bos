---
id: marketing.channel.tiktok.connection.validate
name: tiktok-connection-validate
description: Use when the operator explicitly asks to validate, test, check, or troubleshoot the connected TikTok posting API / OAuth pipeline. This is a read-only connector health check; do not use for publishing, uploading, editing profile fields, or generating content.
scope: diagnostic
status: active
version: 0.1.0
allowed_from_chat: true
module_id: marketing.channel.tiktok.connection.validate
requires_intent:
  - diagnostic
  - discussion
triggers:
  - validate tiktok api
  - test tiktok connection
  - check tiktok oauth
  - tiktok connection
  - tiktok posting api
  - troubleshoot tiktok
excluded_triggers:
  - upload to tiktok
  - publish tiktok video
  - post tiktok video
  - tiktok content draft
  - tiktok photo post
memory_slots:
  - brand_profile
related_modules:
  - marketing.channel.tiktok.connection.validate
output_contract:
  - tiktok_connection_check
quality_gates:
  - read_only_no_mutation
  - credentials_required
  - creator_posting_options_returned
metadata:
  version: 0.1.0
  plugin_id: channel.tiktok
  implements: marketing.optimize
  artifact_type: intelligence_artifact
  platform: tiktok
  output_contract: tiktok_connection_check
  risk_policy: read_only
---

# TikTok Connection Validate

## Purpose

Validate the brand-scoped TikTok OAuth and Content Posting API pipeline without uploading or changing anything.

## Hard boundaries

- Read-only only.
- Calls `/v2/user/info/` and `/v2/post/publish/creator_info/query/` to prove the token works and that `video.publish` is authorized.
- Never uploads video, creates drafts, posts content, changes privacy, comments, or edits any creator fields.
- If credentials are missing or the token lacks `video.publish`, return a setup/blocker artifact instead of pretending the connection works.

## Outcome contract

Artifact/block type: `tiktok_connection_check`
Risk policy: `read_only`
Changed resources: `[]`
Expected success fields: open ID, account identity, privacy level options, duet/comment/stitch settings, max post duration.
