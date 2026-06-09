---
id: marketing.channel.linkedin.connection.validate
name: linkedin-connection-validate
description: Validate that the active brand has a working LinkedIn OAuth connection before any LinkedIn drafting or publishing workflow is attempted.
scope: module
status: active
version: 0.1.0
allowed_from_chat: true
module_id: marketing.channel.linkedin.connection.validate
requires_intent:
  - diagnostic
triggers:
  - check linkedin connection
  - validate linkedin connection
  - test linkedin connection
  - is linkedin connected
  - linkedin setup
  - connect linkedin
related_modules:
  - marketing.channel.linkedin.connection.validate
  - marketing.channel.linkedin.organic.post
output_contract:
  - linkedin_connection_check
quality_gates:
  - read_only_validation
  - credentials_present
  - no_external_action
  - changed_resources_empty
metadata:
  version: 0.1.0
  author: third-party-plugin-developer
  plugin_id: channel.linkedin
  implements: marketing.optimize
  artifact_type: action_result
  platform: linkedin
  risk_policy: connection_validate_is_read_only
---

## Activation

Use before any LinkedIn workflow, or whenever the operator asks whether LinkedIn is connected.

This capability checks the injected LinkedIn credentials for the active brand and performs a read-only validation call when an access token is available.

## Non-goals

- Do not draft a LinkedIn post.
- Do not publish to LinkedIn.
- Do not schedule content.
- Do not mutate LinkedIn profile, organization, page, post, campaign, or media resources.

## Output contract

Returns a `linkedin_connection_check` block with connection `status`, `reason_code` on failure, `read_only: true`, `changed_resources: []`, and `risk_policy: connection_validate_is_read_only`.
