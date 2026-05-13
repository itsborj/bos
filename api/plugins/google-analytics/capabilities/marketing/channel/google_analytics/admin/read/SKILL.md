---
id: marketing.channel.google_analytics.admin.read
name: Google Analytics Admin Read-Only Setup Check
description: Read-only GA4 Admin setup inspection MVP. Use only when the user explicitly asks to check, inspect, verify, audit, diagnose, or show Google Analytics or GA4 setup, property configuration, data streams, measurement ID, or tracking readiness. This plugin does not create audiences, edit properties, create streams, change conversions, alter tags, or mutate any external resource.
scope: module
status: active
version: 0.1.0
allowed_from_chat: true
module_id: marketing.channel.google_analytics.admin.read
requires_intent:
  - diagnostic
  - generation
  - discussion
triggers:
  - check google analytics setup
  - check ga4 setup
  - inspect google analytics setup
  - inspect ga4 setup
  - verify google analytics setup
  - verify ga4 setup
  - audit google analytics setup
  - audit ga4 setup
  - google analytics admin
  - ga4 admin
  - google analytics property setup
  - ga4 property setup
  - google analytics data stream
  - ga4 data stream
  - measurement id
  - analytics tracking readiness
  - ga4 tracking readiness
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
  - marketing.channel.google_analytics.admin.read
output_contract:
  - google_analytics_admin_readiness
quality_gates:
  - read_only_only
  - no_property_stream_audience_tag_or_conversion_mutation
  - google_analytics_credentials_present
  - property_metadata_returned_or_clear_failure
metadata:
  version: 0.1.0
  author: third_party_plugin_developer
  plugin_id: channel.google_analytics
  implements: marketing.optimize
  artifact_type: intelligence_artifact
  platform: google_analytics
  output_contract: google_analytics_admin_readiness
  risk_policy: read_only_no_mutation
---

# Google Analytics Admin Read-Only Setup Check

## Purpose

Inspect GA4 Admin metadata for the configured property and return a read-only setup/readiness artifact.

## Activation

Use this only when the user explicitly asks to inspect Google Analytics or GA4 setup, for example:

- "check GA setup"
- "verify Google Analytics tracking readiness"
- "show the GA4 data stream"
- "what measurement ID is configured"
- "audit Google Analytics setup"

## Hard boundaries

This MVP is read-only setup inspection only.

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
I’ll inspect the GA4 property setup read-only and create an Analytics Setup artifact.
RUN: marketing.channel.google_analytics.admin.read
```

Do not expose credentials, refresh tokens, access tokens, backend logs, property admin internals beyond the returned setup artifact, or provider details.

## Outcome contract

Artifact type: `intelligence_artifact`
Block/output contract: `google_analytics_admin_readiness`
Platform: `google_analytics`
Risk policy: `read_only_no_mutation`

The module returns a `google_analytics_admin_readiness` block and markdown content containing:

- GA4 property identifier
- property display name/timezone/currency when available
- data stream list
- web measurement IDs when available
- readiness checks
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
