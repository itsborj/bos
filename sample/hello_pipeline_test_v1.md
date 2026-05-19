# Sample — Hello Pipeline Test v1

User request:

```text
Run the hello world plugin test for Klaroha.
```

Expected run content:

```text
Klaroha plugin pipeline test passed for Klaroha.

Job: marketing.execute
Artifact: pipeline_test_result
Risk policy: test_only_no_external_action
Marker: staging-smoke-2026-05-19
Message: Marketing, engineered for clarity — the specialist plugin loaded, executed, produced an artifact block, and is ready for approval testing.
```

Expected block:

```json
{
  "type": "pipeline_test_result",
  "artifact_type": "action_result",
  "platform": "hello",
  "status": "succeeded",
  "job": "marketing.execute",
  "brand_name": "Klaroha",
  "message": "Plugin discovery, execution, artifact block creation, and approval flow are working.",
  "marker": "staging-smoke-2026-05-19",
  "read_only": true,
  "changed_resources": [],
  "allowed_actions": ["approve", "dismiss"],
  "risk_policy": "test_only_no_external_action"
}
```
