---
id: marketing.channel.linkedin.organic.publish
name: linkedin-organic-post-publish
description: Publish an approved LinkedIn organic post draft to the connected LinkedIn account or organization page via the LinkedIn UGC Posts API.
scope: module
status: active
version: 0.1.0
allowed_from_chat: true
module_id: marketing.channel.linkedin.organic.publish
requires_intent:
  - publish
triggers:
  - publish to linkedin
  - post to linkedin
  - send to linkedin
  - publish this linkedin post
  - post this linkedin draft
  - go live on linkedin
  - publish the linkedin draft
excluded_triggers:
  - draft a linkedin post
  - write a linkedin post
  - linkedin ads
  - linkedin campaign manager
  - schedule linkedin
related_modules:
  - marketing.channel.linkedin.organic.post
  - marketing.channel.linkedin.organic.publish
  - marketing.channel.linkedin.connection.validate
output_contract:
  - linkedin_publish_result
quality_gates:
  - post_created_on_platform
  - changed_resources_present_on_success
  - no_fake_publish_claim
  - mutation_declaration_present
metadata:
  version: 0.1.0
  author: third-party-plugin-developer
  plugin_id: channel.linkedin
  implements: marketing.execute
  artifact_type: action_result
  platform: linkedin
  risk_policy: publish_requires_explicit_approval
---

## Activation

Use only when the operator explicitly requests publishing a LinkedIn post to the live platform. Requires an approved `linkedin_post_draft` artifact and a configured `LINKEDIN_ACCESS_TOKEN`.

Run `marketing.channel.linkedin.connection.validate` first if connection status is unknown.

## Non-goals

- Do not draft content — use `marketing.channel.linkedin.organic.post` for drafts.
- Do not schedule posts.
- Do not publish LinkedIn ads or Campaign Manager assets.
- Do not claim a publish occurred if the API call failed.

## Output contract

Returns a `linkedin_publish_result` block with `status` (published or failed), `post_id`, `post_url`, `author_urn`, `changed_resources`, and `risk_policy: publish_requires_explicit_approval`. On failure, returns `reason_code` and `allowed_actions: ["retry", "dismiss"]`.
