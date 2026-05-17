---
id: marketing.channel.meta.posts.draft
name: Facebook Post Draft
description: Use when the user asks to draft, write, or create a Facebook post. Triggers on "draft a facebook post", "write a post for my page", "create a facebook post", "write a post about X". Generates post copy using the brand's voice, tone, and values. Returns a draft artifact — never publishes. For publishing, the user must explicitly approve the draft and ask to publish.
scope: module
status: active
version: 0.1.0
allowed_from_chat: true
module_id: marketing.channel.meta.posts.draft
requires_intent:
  - sample
  - discussion
triggers:
  - draft a facebook post
  - write a post for my page
  - create a facebook post
  - write a post about
  - facebook post draft
  - write a facebook post
  - compose a post
  - draft a post for facebook
  - write a post
  - post copy
excluded_triggers:
  - publish to facebook
  - post on facebook now
  - publish this post
  - what did I post
  - show my posts
  - show facebook posts
memory_slots:
  - brand_profile
  - products
  - audiences
related_modules:
  - marketing.channel.meta.posts.publish
  - marketing.channel.meta.posts.read
output_contract:
  - fb_page_post_draft
quality_gates:
  - draft_only
  - no_api_mutation
  - within_length_limits
metadata:
  version: 0.1.0
  author: third_party_plugin_developer
  plugin_id: channel.meta
  implements: marketing.execute
  artifact_type: draft_artifact
  platform: facebook
  output_contract: fb_page_post_draft
  risk_policy: draft_only_until_approved
---

# Facebook Post Draft

## Purpose

Generate Facebook post copy using the brand's voice, tone, and values. Returns a `fb_page_post_draft` artifact. The draft is shown in Workspace for review — never auto-published.

## Hard boundaries

Never:
- call the Graph API
- publish or schedule posts
- fabricate engagement metrics

`changed_resources` must always be `[]`.

## CMO response behavior

Show a brief acknowledgment, then dispatch:

```text
Drafting a Facebook post for you.
RUN: marketing.channel.meta.posts.draft
task_name: <what the post is about>
```

Do NOT paste the post copy in chat. The draft goes to Workspace for review. After the user approves, they can publish via `posts.publish`.

## Outcome contract

Artifact type: `draft_artifact`
Block type: `fb_page_post_draft`
Platform: `facebook`
Risk policy: `draft_only_until_approved`
`allowed_actions`: `["revise", "dismiss", "approve", "publish"]`
