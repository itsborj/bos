---
id: marketing.channel.meta.posts.read
name: Meta Page Posts
description: Use when the user asks to see recent Facebook posts, post history, or engagement metrics for their page. Triggers on "what did I post on facebook", "recent facebook posts", "show my posts", "facebook post history", "post engagement", "how did my posts do". Returns up to 25 recent posts with likes, comments, and share counts. Read-only — never creates or modifies posts.
scope: module
status: active
version: 0.1.0
allowed_from_chat: true
module_id: marketing.channel.meta.posts.read
requires_intent:
  - diagnostic
  - discussion
triggers:
  - what did I post on facebook
  - recent facebook posts
  - show my posts
  - facebook post history
  - post engagement
  - how did my posts do
  - facebook posts
  - show posts
  - recent posts
  - post performance
excluded_triggers:
  - publish to facebook
  - draft a post
  - write a post
  - create a post
  - post on facebook now
memory_slots:
  - brand_profile
related_modules:
  - marketing.channel.meta.pages.read
  - marketing.channel.meta.posts.draft
output_contract:
  - meta_page_posts
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
  output_contract: meta_page_posts
  risk_policy: read_only_no_mutation
---

# Meta Page Posts

## Purpose

Return the last N posts from the connected Facebook Page with engagement metrics (likes, comments, shares). Default limit is 10; max 25.

## Hard boundaries

Never:
- create posts
- update or delete posts
- change engagement data

`changed_resources` must always be `[]`.

## CMO response behavior

```text
Pulling your recent Facebook posts.
RUN: marketing.channel.meta.posts.read
```

## Outcome contract

Artifact type: `intelligence_artifact`
Block type: `meta_page_posts`
Platform: `facebook`
Risk policy: `read_only_no_mutation`
