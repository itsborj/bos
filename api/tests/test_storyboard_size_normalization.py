import importlib.util
from pathlib import Path


def _load_storyboard_core():
    path = Path(__file__).resolve().parents[2] / "plugins" / "storyboard" / "lib" / "json_image_storyboard.py"
    spec = importlib.util.spec_from_file_location("storyboard_json_image_core_test", str(path))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_storyboard_size_normalization_maps_unsupported_values():
    core = _load_storyboard_core()

    assert core._normalize_requested_size("3:4") == "1024x1536"
    assert core._normalize_requested_size("1152x1536") == "1024x1536"
    assert core._normalize_requested_size("1824x1024") == "1536x1024"
    assert core._normalize_requested_size("1:1") == "1024x1024"
