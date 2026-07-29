---
id: marketing.channel.instagram.connection.validate
name: Instagram Connection Validate
description: Use when the user asks to check, verify, or debug the brand's Instagram connection. Triggers on "check instagram", "verify instagram connection", "is instagram connected", "debug instagram auth". Read-only — never publishes or mutates the account.
scope: module
status: active
version: 0.1.0
allowed_from_chat: true
module_id: marketing.channel.instagram.connection.validate
requires_intent:
  - diagnostic
  - discussion
triggers:
  - check instagram
  - verify instagram connection
  - is instagram connected
  - debug instagram auth
  - instagram connection
excluded_triggers:
  - publish to instagram
  - draft instagram post
memory_slots:
  - brand_profile
output_contract:
  - instagram_connection_check
quality_gates:
  - read_only_only
  - instagram_credentials_present
metadata:
  version: 0.1.0
  plugin_id: channel.instagram
  implements: marketing.optimize
  artifact_type: intelligence_artifact
  platform: instagram
  output_contract: instagram_connection_check
---

# Instagram Connection Validate

Return a read-only connection report for the brand's Instagram Business Account using the Meta Graph API.
