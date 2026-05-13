---
id: marketing.channel.google_analytics.realtime.read
name: Google Analytics Realtime Read-Only Tracking Check
description: Read-only GA4 realtime tracking check. Use only when the user explicitly asks whether Google Analytics, GA4, tracking, events, or active users are live/firing right now, or asks for realtime GA status. This plugin does not create audiences, edit properties, create streams, change conversions, alter tags, install tracking code, or mutate any external resource.
scope: module
status: active
version: 0.1.0
allowed_from_chat: true
module_id: marketing.channel.google_analytics.realtime.read
requires_intent:
  - diagnostic
  - generation
  - discussion
triggers:
  - check if google analytics is live
  - check if ga4 is live
  - check if analytics tracking is live
  - check if google analytics tracking is firing
  - check if ga4 tracking is firing
  - realtime google analytics
  - realtime ga4
  - active users in google analytics
  - active users in ga4
  - is google analytics working right now
  - is ga4 working right now
  - verify tracking right now
  - test analytics tracking
  - realtime tracking check
excluded_triggers:
  - what can you do
  - what can you do with google analytics
  - google analytics capabilities
  - ga4 capabilities
  - create google analytics audience
  - create ga4 audience
  - create data stream
  - edit google analytics property
  - change google analytics conversion
  - configure google analytics
  - install google analytics
  - setup tag manager
memory_slots:
  - brand_profile
  - campaign_brand_kit
related_modules:
  - marketing.channel.google_analytics.realtime.read
  - marketing.channel.google_analytics.admin.read
  - marketing.channel.google_analytics.performance.read
output_contract:
  - google_analytics_realtime_check
quality_gates:
  - read_only_only
  - no_property_stream_audience_tag_or_conversion_mutation
  - google_analytics_credentials_present
  - realtime_report_returned_or_clear_failure
metadata:
  version: 0.1.0
  author: third_party_plugin_developer
  plugin_id: channel.google_analytics
  implements: marketing.optimize
  artifact_type: intelligence_artifact
  platform: google_analytics
  output_contract: google_analytics_realtime_check
  risk_policy: read_only_no_mutation
---

# Google Analytics Realtime Read-Only Tracking Check

## Purpose

Run a GA4 Data API realtime report and return a read-only tracking-status artifact.

## Activation

Use this only when the user explicitly asks to check realtime GA4 activity, for example:

- "check if GA tracking is live"
- "is Google Analytics firing right now?"
- "show active users in GA4"
- "test analytics tracking"
- "realtime GA status"

## Hard boundaries

This MVP is read-only realtime inspection only.

Never claim to:

- create or edit GA properties
- create, edit, or delete data streams
- create audiences
- alter conversion/key-event settings
- configure tags or triggers
- install site code
- change campaign budgets
- publish, pause, or enable campaigns
- mutate any Google Analytics, GTM, site, or campaign resource

## CMO response behavior

If running this capability, keep the visible reply short, such as:

```text
I’ll run a read-only GA4 realtime tracking check and create an Analytics Realtime artifact.
RUN: marketing.channel.google_analytics.realtime.read
```

Do not expose credentials, refresh tokens, access tokens, backend logs, or provider internals.

## Outcome contract

Artifact type: `intelligence_artifact`
Block/output contract: `google_analytics_realtime_check`
Platform: `google_analytics`
Risk policy: `read_only_no_mutation`

The module returns a `google_analytics_realtime_check` block and markdown content containing:

- GA4 property identifier
- active users
- recent realtime event counts
- realtime page/screen signals when available
- tracking readiness/status
- read-only note confirming no changes were made
- `read_only: true`
- `changed_resources: []`

This contract must never return audience creation, property edits, data stream writes, tag changes, conversion setting changes, campaign budget/status changes, or write-action results. Those require separate capabilities with their own approval/risk contracts.

## Credential contract

This third-party plugin uses host-injected environment values from `channel.json`:

- `GOOGLE_ANALYTICS_CLIENT_ID`
- `GOOGLE_ANALYTICS_CLIENT_SECRET`
- `GOOGLE_ANALYTICS_REFRESH_TOKEN`
- `GOOGLE_ANALYTICS_PROPERTY_ID`

Optional request/brief fields for advanced tests:

- `google_analytics_property_id`
