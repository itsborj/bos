---
id: workspace.attachment_extract
name: attachment-context-extract
description: Internal deterministic capability that converts uploaded/Drive attachment references into the canonical JSON source-context payload for specialist handoff. Not directly dispatched from CMO chat.
version: 1.0.0
status: active
scope: module
allowed_from_chat: false
module_id: workspace.attachment.extract
requires_intent:
  - internal
triggers: []
metadata:
  artifact_type: intelligence_artifact
  output_schema: bos.operator_reference_context.v1
quality_gates:
  - deterministic_json_output
  - extraction_status_explicit
  - no_llm_interpretation
---

# Attachment Context Extract

Converts attachment references into `bos.operator_reference_context.v1` JSON.

This capability is infrastructure. CMO chat should not own the JSON schema or extraction status rules.
