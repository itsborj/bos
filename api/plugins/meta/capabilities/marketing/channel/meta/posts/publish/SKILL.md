---
id: marketing.channel.meta.posts.publish
name: Facebook Post Publish
description: Use when the user explicitly instructs BOS to post/publish text directly to a Facebook Page, including low-risk test posts where the operator says the copy does not matter or gives exact text. The direct command itself is approval for that text-only external action. Also use when the user has approved a specific Facebook draft and asks to publish it. Never use for vague new creative drafting requests; those go to posts/draft first.
scope: module
status: active
version: 0.1.0
allowed_from_chat: true
module_id: marketing.channel.meta.posts.publish
requires_intent:
  - discussion
  - generation
triggers:
  - publish this post
  - post this to facebook
  - go ahead and publish
  - publish the approved post
  - publish to facebook
  - post it to facebook
  - publish this to my page
  - send this post
  - post in facebook
  - post on facebook
  - post to facebook
  - post in klaroha fb page
  - klaroha fb page
  - facebook test post
  - test post
  - text only
  - just testing
excluded_triggers:
  - draft a post
  - write a post
  - show my posts
  - what did I post
  - schedule a post
  - draft a facebook post
  - draft a post
  - write a post
  - write something
memory_slots:
  - brand_profile
related_modules:
  - marketing.channel.meta.posts.draft
output_contract:
  - fb_page_post_result
quality_gates:
  - explicit_approval_required
  - message_present_in_brief
  - facebook_credentials_present
metadata:
  version: 0.1.0
  author: third_party_plugin_developer
  plugin_id: channel.meta
  implements: marketing.execute
  artifact_type: action_artifact
  platform: facebook
  output_contract: fb_page_post_result
  risk_policy: approval_gated
---

# Facebook Post Publish

## Purpose

Publish text to the connected Facebook Page via the Graph API.

Direct text-only publish is allowed when the operator's message is itself an explicit instruction to post/publish, especially for test posts. In that case, the CMO must provide `message:` from either exact user text or a short safe test message derived from the instruction. Draft approval is still required for creative generation where the user asks to write/draft/create copy for review.

## Hard boundaries

- Never dispatch without post text in `brief["message"]` or a clear exact/direct test-post instruction that can be converted into post text.
- Never dispatch for vague creative drafting requests; use posts/draft instead.
- Never fabricate the response — if the Graph API call fails, surface the error

## CMO response behavior

Dispatch when the operator clearly says to post/publish to Facebook now. Output the `message:` param on the line immediately after `RUN:` — this is required:

```text
Posting this to Facebook now.
RUN: marketing.channel.meta.posts.publish
message: <exact text to publish — no quotes, no truncation>
```

For a low-risk test instruction where the operator says text-only/copy does not matter, create a short transparent test message, e.g. `Test post from Klaroha.` and pass that as `message:`. If the user asks to draft/write/create a polished post rather than post now, use `marketing.channel.meta.posts.draft`.

## Outcome contract

Artifact type: `action_artifact`
Block type: `fb_page_post_result`
Platform: `facebook`
Risk policy: `approval_gated`
`changed_resources`: `[post_id]`
