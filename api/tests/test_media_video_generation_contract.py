from __future__ import annotations

import importlib.util
import os
import shutil
from pathlib import Path

import pytest


def _load_module_class():
    path = Path(__file__).resolve().parents[1] / "plugins" / "media-video" / "capabilities" / "media" / "video" / "generate" / "module.py"
    spec = importlib.util.spec_from_file_location("media_video_generate_module", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.MediaVideoGenerateModule


def test_video_generation_failure_self_check_fails() -> None:
    module = _load_module_class()()

    verdict, failures = module.self_check("Video generation failed: Not Found", {})

    assert verdict == "fail"
    assert "generation_failed" in failures


@pytest.mark.skipif(
    not shutil.which(os.environ.get("FFMPEG_PATH", "ffmpeg")),
    reason="ffmpeg not available in this environment",
)
def test_local_ffmpeg_video_generation_returns_reviewable_asset() -> None:
    module = _load_module_class()()

    attempt, result = module.execute_tool_result({
        "brand_name": "Klaroha",
        "hook_text": "Pipeline dormant prospects",
        "cta_text": "Review the workflow",
        "duration": 5,
        "aspect_ratio": "9:16",
        "_channel_credentials": {"video_gen_provider": "local_ffmpeg"},
    })

    block = result["block"]
    assert attempt["status"] == "succeeded"
    assert attempt["provider"] == "local_ffmpeg"
    assert block["type"] == "video_asset"
    assert block["status"] == "succeeded"
    assert block["video_path"] and block["video_path"].endswith(".mp4")
    assert block["file_size_kb"] and block["file_size_kb"] > 0
    assert module.self_check(result["content"], {})[0] == "pass"
