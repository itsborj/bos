from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module_class():
    path = Path(__file__).resolve().parents[1] / "plugins" / "media-image" / "capabilities" / "media" / "image" / "generate" / "module.py"
    spec = importlib.util.spec_from_file_location("media_image_generate_module", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.MediaImageGenerateModule


def test_local_image_renderer_returns_real_png_block() -> None:
    module = _load_module_class()()

    attempt, result = module.execute_tool_result({
        "image_prompt": "sample Klaroha dashboard image",
        "_channel_credentials": {"image_gen_provider": "local"},
    })

    block = result["block"]
    assert attempt["status"] == "succeeded"
    assert attempt["provider"] == "local"
    assert block["status"] == "succeeded"
    assert block["mime_type"] == "image/png"
    assert block["byte_size"] > 1000
    assert isinstance(block["image_data_b64"], str) and len(block["image_data_b64"]) > 1000
    assert module.self_check(result["content"], {})[0] == "pass"
