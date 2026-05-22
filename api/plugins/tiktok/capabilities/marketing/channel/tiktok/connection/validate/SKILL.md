---
id: marketing.channel.tiktok.connection.validate
name: tiktok-connection-validate
description: Use when the operator explicitly asks to validate, test, verify, check, or troubleshoot the connected TikTok API/OAuth pipeline. This is a read-only connector health check; do not use for uploading, publishing, scheduling, ads, analytics, comments, DMs, or creating video assets.
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
  - verify tiktok connection
  - check tiktok oauth
  - tiktok connection
  - tiktok api pipeline
  - troubleshoot tiktok
  - connected to our tiktok account
excluded_triggers:
  - publish tiktok
  - post to tiktok
  - upload tiktok video
  - schedule tiktok
  - tiktok ads
  - create tiktok campaign
  - tiktok analytics
memory_slots:
  - brand_profile
related_modules:
  - marketing.channel.tiktok.connection.validate
resources:
  - sample/connection_validate_v1.md
output_contract:
  - tiktok_connection_check
quality_gates:
  - read_only_no_mutation
  - credentials_required
  - account_identity_returned
metadata:
  version: 0.1.0
  author: third_party_plugin_developer
  plugin_id: channel.tiktok
  implements: marketing.optimize
  artifact_type: intelligence_artifact
  platform: tiktok
  output_contract: tiktok_connection_check
  risk_policy: read_only
---

# TikTok Connection Validate

## Purpose

Validate the brand-scoped TikTok OAuth and Open API pipeline without uploading, publishing, scheduling, or changing anything.

## Hard boundaries

- Read-only only.
- Calls TikTok `user/info` to prove the token works and identify the connected account.
- Never uploads video, publishes a post, schedules content, edits profile fields, comments, likes, follows, creates ads, changes budgets, or modifies pixels/audiences.
- If credentials are missing or TikTok returns quota/permission errors, return a setup/blocker artifact instead of pretending the connection works.
- Public test posting belongs to a separate approval-gated capability after a video asset is attached.

## Outcome contract

Artifact/block type: `tiktok_connection_check`
Risk policy: `read_only`
Changed resources: `[]`
Expected success fields: TikTok open_id, display name, endpoint checked, checked_at timestamp, test post readiness.
