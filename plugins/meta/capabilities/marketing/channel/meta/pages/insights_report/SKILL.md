---
id: marketing.channel.meta.pages.insights.report
name: Meta Page Insights Report
description: Use only when the user explicitly asks for a Facebook/Meta page insights report, Meta page snapshot, Facebook page performance report, scheduled Facebook post status, recent Facebook performance, Facebook followers, or Meta channel health. Do not use for a generic "report" request unless Meta/Facebook/page-insights context is explicit. Read-only. Returns connected page profile, scheduled posts, recent posts when permissions allow, and Page Insights metrics when Meta permissions/metrics are available. Never posts or modifies anything.
scope: module
status: active
version: 0.1.0
allowed_from_chat: true
module_id: marketing.channel.meta.pages.insights.report
requires_intent:
  - discussion
  - diagnostic
  - generation
triggers:
  - page insights report
  - page insights
  - facebook insights
  - meta insights
  - facebook page insights report
  - facebook page report
  - meta page report
  - facebook page performance report
  - meta page performance report
  - facebook performance
  - scheduled facebook posts
  - meta channel health report
  - facebook channel health report
  - report for facebook page
excluded_triggers:
  - publish post
  - schedule post
  - create post
  - generic report
  - marketing report
  - draft post
  - delete post
memory_slots:
  - brand_profile
related_modules:
  - marketing.channel.meta.pages.read
  - marketing.channel.meta.posts.read
output_contract:
  - meta_page_insights_report
quality_gates:
  - read_only
  - facebook_credentials_present
metadata:
  version: 0.1.0
  author: third_party_plugin_developer
  plugin_id: channel.meta
  implements: marketing.optimize
  artifact_type: intelligence_artifact
  platform: facebook
  output_contract: meta_page_insights_report
  risk_policy: read_only
---

# Meta Page Insights Report

## Purpose

Build a read-only Facebook Page insights report for the active brand.

## What it reads

- Connected Page profile and follower count.
- Scheduled posts from `/{page_id}/scheduled_posts`.
- Recent posts and engagement counts from `/{page_id}/posts` when the connected token has the required permissions.
- Page Insights metrics from `/{page_id}/insights` when the connected token/app has available metrics.

## Inputs

Optional brief fields:

- `days` — reporting window, default 28, max 90.
- `limit` — max recent/scheduled posts, default 10, max 25.
- `metrics` — optional list of Meta Page Insights metric names to try.

## Output

Returns a `meta_page_insights_report` block with:

- `report_scope` — `channel_snapshot` unless campaign evidence is explicitly bound
- `campaign_binding`
- `coverage_label` and per-source `coverage`
- `metrics_overview` — counts/metrics overview only, not interpretation
- `insight_bullets` — campaign-anchored insights with evidence, confidence, and coverage labels
- `page`
- `window`
- `insights`
- `recent_posts`
- `scheduled_posts`
- `content_intelligence`
- `not_available`
- `recommended_next_step`
- `daily_brief_signal`
- `warnings`
- `read_only: true`
- `changed_resources: []`

Warnings are expected when Meta permissions or metric availability are limited. Do not fabricate missing metrics. Metrics should appear as an overview; the value of the artifact is the bulleted insight layer. Anchor insight bullets to the selected existing campaign when `campaign_id`/`campaign_name` is present. If no campaign is bound, explicitly say the artifact is a channel snapshot and cannot be treated as campaign evaluation. When only post copy is readable, produce content intelligence only; do not claim performance improvement/decline.

## Hard boundaries

- Read-only only.
- Never publish, schedule, delete, update, comment, or mutate Meta resources.
- Never invent engagement/reach metrics. If Meta denies a metric or returns no data, include a warning.
