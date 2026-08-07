from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def _load_module_class():
    path = Path(__file__).resolve().parents[1] / "plugins" / "media-video" / "capabilities" / "media" / "video" / "generate" / "module.py"
    spec = importlib.util.spec_from_file_location("media_video_generate_module", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.MediaVideoGenerateModule


@pytest.mark.skip(reason="media.video.generate module was never implemented/committed (no module.py under api/plugins/media-video/)")
def test_video_generation_failure_self_check_fails() -> None:
    module = _load_module_class()()

    verdict, failures = module.self_check("Video generation failed: Not Found", {})

    assert verdict == "fail"
    assert "generation_failed" in failures


@pytest.mark.skip(reason="media.video.generate module was never implemented/committed (no module.py under api/plugins/media-video/)")
def test_video_generation_success_self_check_passes() -> None:
    module = _load_module_class()()

    verdict, failures = module.self_check("Video generated.\n\nHook: Test hook\nFormat: 9:16 / 10s", {})

    assert verdict == "pass"
    assert failures == []
