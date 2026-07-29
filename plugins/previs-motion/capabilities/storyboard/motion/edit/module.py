from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_render_module():
    path = Path(__file__).resolve().parents[1] / "render" / "module.py"
    spec = importlib.util.spec_from_file_location("previs_motion_render_module", str(path))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_render = _load_render_module()


class PrevisMotionEditModule(_render.PrevisMotionRenderModule):
    """JSON-based video-to-video edit alias for Previs Motion.

    Forces mode="video_to_video" so Seedance receives the prior video as a
    reference_video and applies edit_instruction / revision_instruction as a
    true video edit rather than regenerating from scratch.

    If the reference video URL has expired, the render module falls back to
    image_to_video automatically when a storyboard image is available.
    """

    id = "storyboard.motion.edit"
    name = "Previs Motion Edit"
    capability = "storyboard.motion.edit"

    def execute_tool_result(self, brief: dict) -> tuple[dict, dict]:
        if not isinstance(brief, dict):
            brief = {}
        else:
            brief = dict(brief)
        brief["mode"] = "video_to_video"
        return super().execute_tool_result(brief)
