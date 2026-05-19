from __future__ import annotations

import time

from klaroha_sdk import ChannelModule


class HelloPipelineTestModule(ChannelModule):
    id = "marketing.channel.hello.pipeline_test"
    name = "Hello Pipeline Test"
    vertical = "marketing"
    capability = "marketing.copywriting"
    platform_hint = "hello"
    policy_default = "balanced"
    template = "marketing/channel/hello/pipeline_test/template.j2"

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        failures: list[str] = []
        required = [
            "Klaroha plugin pipeline test passed",
            "pipeline_test_result",
            "test_only_no_external_action",
        ]
        for phrase in required:
            if phrase not in content:
                failures.append(f"missing_required_phrase:{phrase}")
        block = brief.get("_expected_block")
        if block and block != "pipeline_test_result":
            failures.append("unexpected_expected_block")
        return ("fail" if failures else "pass", failures)

    def execute_tool_result(self, brief: dict) -> tuple[dict, dict]:
        start = time.perf_counter()
        safe_brief = dict(brief or {})
        safe_brief.setdefault("job", "marketing.execute")
        safe_brief["_expected_block"] = "pipeline_test_result"
        content = self.build_prompt(safe_brief).strip()
        latency_ms = round((time.perf_counter() - start) * 1000)

        return {
            "provider": "hello",
            "model_id": "deterministic_pipeline_test",
            "mode": "tool",
            "status": "succeeded",
            "tokens_input": 0,
            "tokens_output": 0,
            "provider_cost": 0.0,
            "latency_ms": latency_ms,
            "error": None,
        }, {
            "content": content,
            "sell_price": None,
            "block": {
                "type": "pipeline_test_result",
                "artifact_type": "action_result",
                "platform": "hello",
                "status": "succeeded",
                "job": safe_brief["job"],
                "brand_name": safe_brief.get("brand_name", "BOS"),
                "message": "Plugin discovery, execution, artifact block creation, and approval flow are working.",
                "read_only": True,
                "changed_resources": [],
                "allowed_actions": ["approve", "dismiss"],
                "risk_policy": "test_only_no_external_action",
            },
        }
