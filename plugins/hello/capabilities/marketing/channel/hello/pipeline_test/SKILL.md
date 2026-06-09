---
id: marketing.channel.hello.pipeline_test
name: hello-pipeline-test
description: Use only when the operator explicitly asks to test, verify, or smoke-test the BOS plugin pipeline end-to-end. Produces a deterministic action_result artifact with no external connector, no publishing, and no spend.
scope: module
status: active
version: 0.1.0
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
  - test the plugin system
output_contract:
  - pipeline_test_result
quality_gates:
  - no_external_action
  - structured_block_present
metadata:
  version: 0.1.0
  plugin_id: channel.hello
  implements: marketing.execute
  artifact_type: action_result
  platform: hello
  risk_policy: test_only_no_external_action
---

## What this capability does

Runs a deterministic end-to-end test of the BOS external plugin pipeline.
Proves that plugin discovery, SDK execution, artifact block creation, and
the Stream approval flow all work correctly.

## When to invoke

- Operator asks to test, verify, or smoke-test the plugin pipeline
- Debugging plugin loading or artifact rendering

## When NOT to invoke

- Any real marketing request
- Any request involving a specific channel (email, social, ads)
- Any request that mentions a real product, campaign, or audience

## Output contract

Returns a `pipeline_test_result` artifact block:
- `read_only: true`
- `changed_resources: []`
- `risk_policy: test_only_no_external_action`
