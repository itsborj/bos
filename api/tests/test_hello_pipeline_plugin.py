from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "plugins/hello/capabilities/marketing/channel/hello/pipeline_test/module.py"
)
SKILL_PATH = MODULE_PATH.with_name("SKILL.md")


def _module_class():
    spec = importlib.util.spec_from_file_location("hello_pipeline_test_module", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.HelloPipelineTestModule


def test_hello_pipeline_plugin_returns_deterministic_artifact_block():
    from module_base import register_template_root

    register_template_root(str(API_ROOT / "plugins/hello/capabilities"))
    trace, result = _module_class()().execute_tool_result({"brand_name": "Klaroha"})

    assert trace["mode"] == "tool"
    assert trace["status"] == "succeeded"
    assert "Klaroha plugin pipeline test passed for Klaroha" in result["content"]
    assert result["block"] == {
        "type": "pipeline_test_result",
        "artifact_type": "action_result",
        "platform": "hello",
        "status": "succeeded",
        "job": "marketing.execute",
        "brand_name": "Klaroha",
        "message": "Plugin discovery, execution, artifact block creation, and approval flow are working.",
        "read_only": True,
        "changed_resources": [],
        "allowed_actions": ["approve", "dismiss"],
        "risk_policy": "test_only_no_external_action",
    }


def test_hello_pipeline_plugin_has_chat_manifest_contract():
    skill = SKILL_PATH.read_text()

    assert "allowed_from_chat: true" in skill
    assert "module_id: marketing.channel.hello.pipeline_test" in skill
    assert "Do not call an external platform" in skill
