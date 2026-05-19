---
id: marketing.channel.hello.pipeline_test
name: hello-pipeline-test
description: Use only when the operator explicitly asks to test, verify, or smoke-test the BOS plugin pipeline end-to-end. Produces a deterministic action_result artifact with no external connector, no publishing, and no spend.
scope: module
status: active
version: 0.2.0
allowed_from_chat: true
module_id: marketing.channel.hello.pipeline_test
requires_intent:
  - generation
triggers:
  - hello world
  - plugin test
  - pipeline test
  - smoke test plugin
  - verify plugin pipeline
output_contract:
  - pipeline_test_result
quality_gates:
  - deterministic_no_llm_call
  - no_external_action
  - structured_block_present
  - approval_flow_testable
metadata:
  version: 0.2.0
  author: kibanu
  plugin_id: channel.hello
  implements: marketing.execute
  artifact_type: action_result
  platform: hello
  risk_policy: test_only_no_external_action
---

## Activation

Use only for explicit local/staging plugin pipeline verification.

This capability proves the current BOS contract from the project brief:

1. plugin discovery from `channel.json`
2. capability manifest visibility through `SKILL.md`
3. deterministic Transform execution through `ChannelModule`
4. structured Workspace artifact block creation
5. pending-review approval flow

## Non-goals

- Do not call an LLM.
- Do not call an external platform.
- Do not publish, send, mutate, spend, or create real campaign assets.
- Do not use this as a customer-facing marketing capability.

## Output contract

Returns a `pipeline_test_result` block with `artifact_type: action_result`, `read_only: true`, `changed_resources: []`, and `risk_policy: test_only_no_external_action`.
