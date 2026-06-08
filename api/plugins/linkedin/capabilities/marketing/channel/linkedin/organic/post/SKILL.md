---
id: marketing.channel.linkedin.organic.post
name: linkedin-organic-post-draft
description: Draft a reviewable LinkedIn organic feed post artifact for thought leadership, offer education, launch awareness, or B2B conversation-starting without publishing or calling LinkedIn APIs.
scope: module
status: active
version: 0.1.0
allowed_from_chat: true
module_id: marketing.channel.linkedin.organic.post
requires_intent:
  - generation
triggers:
  - linkedin post
  - LinkedIn post
  - linkedin update
  - LinkedIn update
  - linkedin organic
  - LinkedIn organic
  - thought leadership post
  - company page post
excluded_triggers:
  - publish to linkedin
  - send to linkedin
  - linkedin ads
  - linkedin campaign manager
memory_slots:
  - brand_profile
  - campaign_brand_kit
related_modules:
  - marketing.channel.linkedin.organic.post
output_contract:
  - linkedin_connection_check
  - linkedin_post_draft
quality_gates:
  - native_linkedin_post_fields_present
  - no_external_action
  - no_fake_proof
  - approval_policy_present
metadata:
  version: 0.1.0
  author: third-party-plugin-developer
  plugin_id: channel.linkedin
  implements: marketing.execute
  artifact_type: draft_artifact
  platform: linkedin
  risk_policy: draft_only_no_external_action
---

## Activation

Use when the operator asks for a LinkedIn organic post, company page update, founder/thought-leadership style post, or B2B social draft.

LinkedIn connection must be checked first. If no LinkedIn credentials are injected for the active brand, this module returns a `linkedin_connection_check` failure instead of drafting.

The CMO supplies intent and context. With a connected LinkedIn account, this module returns a native `linkedin_post_draft` artifact for review.

## Non-goals

- Do not publish to LinkedIn.
- Do not call LinkedIn APIs.
- Do not create LinkedIn ads or Campaign Manager assets.
- Do not claim a post was scheduled, sent, or published.
- Do not invent customer proof, metrics, guarantees, discounts, or urgency claims.

## Output contract

Returns either a `linkedin_connection_check` failure when LinkedIn is not connected, or a `linkedin_post_draft` block with `message`, `hashtags`, `character_count`, `allowed_actions`, `changed_resources: []`, and `risk_policy: draft_only_no_external_action`.
