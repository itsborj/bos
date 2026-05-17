---
id: marketing.channel.meta.posts.publish
name: Facebook Post Publish
description: Use ONLY when the user has explicitly approved a Facebook post draft and is asking to publish it. Triggers on "publish this post", "post this to facebook", "go ahead and publish", "publish the approved post". Requires explicit user confirmation with the post text in the brief. Never dispatches on a vague "post it" without the approved message present. Approval-gated — only dispatch after the user has reviewed and confirmed the draft.
scope: module
status: active
version: 0.1.0
allowed_from_chat: true
module_id: marketing.channel.meta.posts.publish
requires_intent:
  - action
triggers:
  - publish this post
  - post this to facebook
  - go ahead and publish
  - publish the approved post
  - publish to facebook
  - post it to facebook
  - publish this to my page
  - send this post
excluded_triggers:
  - draft a post
  - write a post
  - show my posts
  - what did I post
  - schedule a post
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

Publish an approved Facebook post draft to the connected Page via the Graph API. Only dispatches after explicit user confirmation.

## Hard boundaries

- Never dispatch without the approved post text in `brief["message"]`
- Never dispatch on a bare user request without prior draft approval
- Never fabricate the response — if the Graph API call fails, surface the error

## CMO response behavior

Only dispatch after the user has confirmed they want to publish the specific post:

```text
Publishing your approved post to Facebook.
RUN: marketing.channel.meta.posts.publish
message: <exact approved post text>
```

## Outcome contract

Artifact type: `action_artifact`
Block type: `fb_page_post_result`
Platform: `facebook`
Risk policy: `approval_gated`
`changed_resources`: `[post_id]`
