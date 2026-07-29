---
id: marketing.channel.meta.posts.publish
name: Facebook Post Publish
description: "Use ONLY when the user gives an explicit publish/schedule command with the post text already decided — e.g. 'post this to facebook: <text>', 'publish this exact text', 'schedule this approved post for tomorrow at 9'. The operator's message or artifact action must contain both the intent to publish/schedule AND the copy or source artifact. For scheduling, pass `scheduled_at` as ISO-8601 in the brief/overrides. Never use for any generate/create/make request — those go to creative.post.image. Never co-dispatch alongside creative.post.image. REQUIRED: include the exact post text when no source artifact is used — write the actual copy, never a placeholder."
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
  - post on facebook now
  - post to facebook now
  - schedule approved post
  - schedule this post to facebook
excluded_triggers:
  - generate a post
  - make a post
  - create a post
  - make a facebook post
  - create a facebook post
  - draft a post
  - write a post
  - show my posts
  - what did I post
  - this is a test
  - just testing
  - test post
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
  action_type: publish
  direct_action_allowed: true
  payload_text_field: message
  generated_content_requires_review: true
---

# Facebook Post Publish

## Purpose

Publish or schedule an explicit, operator-approved text/image post to the connected Facebook Page.

## When to use

Only when the operator's message contains both a publish/schedule command AND the post text, or when an existing artifact action provides the approved post/image. Example valid triggers:
- "post this to facebook: Our summer sale starts today. Shop now at klaroha.com"
- "publish this to the page: [specific copy the operator provided]"
- "schedule the approved Postcraft image for 2026-07-06T09:00:00+08:00"

Never use when the operator asks to generate, create, make, or draft a post. That goes to `creative.post.image`.

## CMO response behavior

Write the actual post copy in the `message:` field — never a placeholder:

```
Posting to Facebook now.
RUN: marketing.channel.meta.posts.publish
message: Our summer sale starts today. Shop now at klaroha.com
```

If scheduling, include `scheduled_at` as ISO-8601. If the operator has not provided the post text/source artifact, do not dispatch this module. Ask for the text or offer to generate a reviewable creative instead.

## Hard boundaries

- Never dispatch alongside `creative.post.image` for the same request.
- Never use a placeholder as the message value — write the actual copy.
- Never dispatch for generate/create/make/draft requests.
- Never fabricate the response — surface Graph API errors directly.
