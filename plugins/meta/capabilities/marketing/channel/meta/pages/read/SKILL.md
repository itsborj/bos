---
id: marketing.channel.meta.pages.read
name: Meta Page Info
description: Use when the user asks to see their Facebook page details, followers, page info, or Instagram link status. Triggers on "show my facebook page", "facebook page info", "how many followers", "facebook stats", "check facebook", "meta page". Returns connected page name, category, follower count, and Instagram business account ID if linked. Read-only — never posts or modifies anything.
scope: module
status: active
version: 0.1.0
allowed_from_chat: true
module_id: marketing.channel.meta.pages.read
requires_intent:
  - diagnostic
  - discussion
triggers:
  - show my facebook page
  - facebook page info
  - how many followers
  - facebook stats
  - check facebook
  - meta page
  - facebook page details
  - my page info
  - facebook followers
  - page overview
excluded_triggers:
  - post on facebook
  - publish to facebook
  - draft a post
  - what did I post
  - recent posts
  - facebook comments
memory_slots:
  - brand_profile
related_modules:
  - marketing.channel.meta.posts.read
  - marketing.channel.meta.posts.draft
output_contract:
  - meta_page_inventory
quality_gates:
  - read_only_only
  - no_post_mutation
  - facebook_credentials_present
metadata:
  version: 0.1.0
  author: third_party_plugin_developer
  plugin_id: channel.meta
  implements: marketing.optimize
  artifact_type: intelligence_artifact
  platform: facebook
  output_contract: meta_page_inventory
  risk_policy: read_only_no_mutation
---

# Meta Page Info

## Purpose

Return a read-only intelligence artifact showing the connected Facebook Page's name, category, follower count, and Instagram Business Account link status.

## Hard boundaries

Never:
- publish posts
- update page settings
- create or delete anything

`changed_resources` must always be `[]`.

## CMO response behavior

```text
Pulling your Facebook page info.
RUN: marketing.channel.meta.pages.read
```

## Outcome contract

Artifact type: `intelligence_artifact`
Block type: `meta_page_inventory`
Platform: `facebook`
Risk policy: `read_only_no_mutation`
