from __future__ import annotations

import json
import time

from attachment_context import build_payload
from module_base import ModuleBase


class WorkspaceAttachmentExtractModule(ModuleBase):
    """Deterministic attachment → JSON context extractor.

    This module does not ask an LLM to interpret files. It converts already
    supplied/enriched attachment references into the canonical JSON handoff
    contract used by downstream specialists.
    """

    id = "workspace.attachment.extract"
    name = "Attachment Context Extract"
    vertical = "workspace"
    capability = "workspace.context.extract"
    platform_hint = "attachment_context"
    policy_default = "generate_only"
    template = ""
    internal = True

    def _attempt(self, start: float, status: str, error=None) -> dict:
        return {
            "provider": "attachment_context",
            "model_id": self.id,
            "mode": "tool",
            "status": status,
            "tokens_input": 0,
            "tokens_output": 0,
            "provider_cost": 0.0,
            "latency_ms": round((time.perf_counter() - start) * 1000),
            "error": error,
        }

    def execute_tool_result(self, brief: dict) -> tuple[dict, dict]:
        start = time.perf_counter()
        references = brief.get("references") or brief.get("chat_references") or []
        payload = build_payload(references)
        content = json.dumps(payload, ensure_ascii=False, indent=2)
        return self._attempt(start, "succeeded"), {
            "content": content,
            "block": {
                "type": "attachment_context",
                "artifact_type": "intelligence_artifact",
                "status": "succeeded",
                "schema": payload["schema"],
                "summary": payload["summary"],
                "context": payload,
                "allowed_actions": ["use", "dismiss"],
            },
        }

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        failures: list[str] = []
        try:
            payload = json.loads(content)
        except Exception as exc:
            return "fail", [f"invalid_json:{exc}"]
        if payload.get("schema") != "bos.operator_reference_context.v1":
            failures.append("wrong_schema")
        if not isinstance(payload.get("items"), list):
            failures.append("missing_items")
        return ("fail" if failures else "pass"), failures
