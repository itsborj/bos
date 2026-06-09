---
id: marketing.channel.meta.posts.draft
name: Facebook Post Draft
description: Use ONLY when the user EXPLICITLY asks for Facebook copy/text ALONE — e.g. "just write the copy", "caption only", "draft the words, no image". A plain "make a Facebook post" or "create a post about X" is NOT this — that is a COMPLETE post (copy + visual); use creative.post.image instead. Never pair this with image generation. Do not use when the operator says to post/publish now; that belongs to posts/publish.
scope: module
status: active
version: 0.1.0
allowed_from_chat: true
module_id: marketing.channel.meta.posts.draft
requires_intent:
  - discussion
  - generation
triggers:
  - draft facebook copy
  - write facebook copy
  - facebook copy only
  - post copy only
  - just the copy
  - draft the post copy
  - facebook caption
excluded_triggers:
  - make a facebook post
  - create a facebook post
  - facebook post
  - instagram post
  - post for our facebook page
  - matching visual
  - visual direction
  - with an image
  - with a visual
  - publish to facebook
  - publish this post
  - go live on facebook
  - post to facebook
  - facebook test post
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

Show a brief acknowledgment, then dispatch with `task_name:` on the next line. If the user asks for a matching visual/image, also dispatch `media.image.generate` with an image prompt derived from the same campaign angle.

```text
Drafting a Facebook post for you.
RUN: marketing.channel.meta.posts.draft
task_name: <specific topic or instruction from the user — be precise>
```

```text
Drafting the Facebook post and matching visual direction.
RUN: marketing.channel.meta.posts.draft
task_name: <specific topic or instruction from the user — be precise>
RUN: media.image.generate
image_prompt: <visual prompt based on the same campaign angle and active brand>
```

Do NOT paste the post copy in chat. The draft goes to Workspace for review. After the user approves, they can publish via `posts.publish`.

## Outcome contract

Artifact type: `draft_artifact`
Block type: `fb_page_post_draft`
Platform: `facebook`
Risk policy: `draft_only_until_approved`
`allowed_actions`: `["revise", "dismiss", "approve"]`; add `"publish"` only when the owning Brand has a connected Facebook page in the injected credentials.
`action_modules`: `{ "publish": "marketing.channel.meta.posts.publish" }` only when `publish` is present.
