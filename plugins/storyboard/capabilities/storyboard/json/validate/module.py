from __future__ import annotations

import importlib.util
import time
from pathlib import Path

from klaroha_sdk import ChannelModule


def _load_core():
    path = Path(__file__).resolve().parents[4] / "lib" / "json_image_storyboard.py"
    spec = importlib.util.spec_from_file_location("storyboard_json_image_core", str(path))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class StoryboardValidateModule(ChannelModule):
    id = "storyboard.validate"
    name = "Storyboard JSON Validate"
    vertical = "storyboard"
    capability = "storyboard.validate"
    platform_hint = "storyboard"
    policy_default = "draft_only"
    template = ""

    def _attempt(self, start: float, status: str, error=None) -> dict:
        return {
            "provider": "storyboard",
            "model_id": "json_storyboard_validator_v1",
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
        try:
            core = _load_core()
            spec = core.spec_from_brief(brief if isinstance(brief, dict) else {})
            ok, errors, warnings = core.validate_spec(spec)
        except Exception as exc:
            return self._attempt(start, "failed", type(exc).__name__), {
                "content": f"Storyboard validation failed: {exc}",
                "block": {"type": "storyboard_validation", "status": "failed", "message": str(exc), "allowed_actions": ["retry", "dismiss"]},
            }

        status = "passed" if ok else "failed"
        return self._attempt(start, "succeeded" if ok else "failed"), {
            "content": f"Storyboard validation {status}: {len(errors)} errors, {len(warnings)} warnings.",
            "block": {
                "type": "storyboard_validation",
                "status": status,
                "ok": ok,
                "errors": errors,
                "warnings": warnings,
                "storyboard_spec": spec,
                "allowed_actions": ["render", "revise", "dismiss"] if ok else ["revise", "dismiss"],
                "action_modules": {"render": "storyboard.render", "revise": "storyboard.render"},
            },
        }

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        if not isinstance(content, str):
            return "fail", ["content_not_string"]
        return "pass", []
