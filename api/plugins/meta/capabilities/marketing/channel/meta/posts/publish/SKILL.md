---
id: marketing.channel.meta.posts.publish
name: Facebook Post Publish
description: Use ONLY when the user has explicitly approved a specific Facebook post draft and is now asking to publish that exact approved text. Never use for new post creation — even casual ones like "post hello world" or "say hi". Those always go to posts/draft first. Only triggers after a draft artifact exists and the user says to go ahead.
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
excluded_triggers:
  - draft a post
  - write a post
  - show my posts
  - what did I post
  - schedule a post
  - post on facebook
  - post in facebook
  - post on
  - just say
  - say hi
  - say hello
  - post something
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

Publish an approved Facebook post draft to the connected Page via the Graph API. Only dispatches after explicit user confirmation.

## Hard boundaries

- Never dispatch without the approved post text in `brief["message"]`
- Never dispatch on a bare user request without prior draft approval
- Never fabricate the response — if the Graph API call fails, surface the error

## CMO response behavior

Only dispatch after the user has confirmed they want to publish the specific post.
Output the `message:` param on the line immediately after `RUN:` — this is required:

```text
Publishing your approved post to Facebook.
RUN: marketing.channel.meta.posts.publish
message: <paste the exact approved post text here — no quotes, no truncation>
```

If the approved post text is not available in context, ask the user to confirm the
post text before dispatching. Never dispatch with a blank or placeholder message.

## Outcome contract

Artifact type: `action_artifact`
Block type: `fb_page_post_result`
Platform: `facebook`
Risk policy: `approval_gated`
`changed_resources`: `[post_id]`
