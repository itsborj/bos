from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
API_PATH = ROOT / "api"
sys.path = [p for p in sys.path if p not in {"", str(ROOT)}]
sys.path.insert(0, str(API_PATH))

from model_overrides import BackendRef
from routers.runs import _apply_backend_ref_to_brief


def test_tool_backend_override_overwrites_stale_artifact_model():
    brief = {"model": "gpt-image-2", "title": "Storyboard action"}
    ref = BackendRef(
        provider="byteplus_modelark",
        model_id="dreamina-seedance-2-0-260128",
        modality="video",
        strict=True,
    )

    out = _apply_backend_ref_to_brief(brief, ref)

    assert out["model"] == "dreamina-seedance-2-0-260128"
    assert out["backend_model_id"] == "dreamina-seedance-2-0-260128"
    assert out["backend_provider"] == "byteplus_modelark"
    assert out["_backend_override"]["model_id"] == "dreamina-seedance-2-0-260128"
    assert brief["model"] == "gpt-image-2"
