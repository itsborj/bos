from __future__ import annotations

# Backward-compatible alias for BOS manifests that route to storyboard.generate.
# The official JSON-first image workflow is implemented by storyboard.render.

import importlib.util
from pathlib import Path


def _load_render_class():
    path = Path(__file__).resolve().parents[1] / "render" / "module.py"
    spec = importlib.util.spec_from_file_location("storyboard_render_module", str(path))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.StoryboardRenderModule


_Base = _load_render_class()


class StoryboardGenerateModule(_Base):
    id = "storyboard.generate"
    name = "Storyboard Generate"
    capability = "storyboard.generate"


# Prevent BOS registry from also registering the imported base render class from
# this alias module; it registers every subclass type found in module globals.
_Base = None
