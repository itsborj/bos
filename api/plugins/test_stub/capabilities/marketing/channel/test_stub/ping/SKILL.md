---
id: marketing.channel.test_stub.ping
name: test-stub-ping
description: Minimal plugin stub for verifying 3rd party plugin discovery and skill routing.
scope: module
status: active
version: 0.1.0
allowed_from_chat: false
requires_intent:
  - generation
triggers:
  - test stub ping
metadata:
  version: 0.1.0
  author: klaroha
  plugin_id: channel.test_stub
---

## Activation

Activate only for explicit plugin discovery testing. Not for production use.

## Output contract

Returns a `test_stub_ping_result` block with `status: ok` and the resolved brand context.
