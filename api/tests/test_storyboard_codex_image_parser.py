import base64
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path("/external_plugins/storyboard/lib/json_image_storyboard.py")
if not PLUGIN_ROOT.exists():
    PLUGIN_ROOT = ROOT / "plugins/storyboard/lib/json_image_storyboard.py"
spec = importlib.util.spec_from_file_location("storyboard_image", PLUGIN_ROOT)
assert spec and spec.loader
storyboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(storyboard)


def test_storyboard_codex_parser_accepts_completed_response(monkeypatch):
    payload = base64.b64encode(b"png-bytes").decode()
    lines = [
        ("data: " + json.dumps({
            "type": "response.completed",
            "response": {"output": [{"type": "image_generation_call", "result": payload}]},
        }) + "\n").encode(),
        b"data: [DONE]\n",
    ]

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def __iter__(self):
            return iter(lines)

    monkeypatch.setattr(storyboard, "urlopen", lambda *_args, **_kwargs: FakeResponse())
    assert storyboard._call_openai_codex_image_generation("prompt", {}, "token", "gpt-5.5", "1024x1024") == b"png-bytes"


def test_storyboard_codex_parser_accepts_nested_data_array(monkeypatch):
    payload = base64.b64encode(b"png-bytes").decode()
    lines = [
        ("data: " + json.dumps({
            "type": "response.completed",
            "response": {"output": [{"type": "image_generation_call", "result": {"data": [{"b64_json": payload}]}}]},
        }) + "\n").encode(),
        b"data: [DONE]\n",
    ]

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def __iter__(self):
            return iter(lines)

    monkeypatch.setattr(storyboard, "urlopen", lambda *_args, **_kwargs: FakeResponse())
    assert storyboard._call_openai_codex_image_generation("prompt", {}, "token", "gpt-5.5", "1024x1024") == b"png-bytes"


def test_storyboard_codex_parser_accepts_output_text_json(monkeypatch):
    lines = [
        ("data: " + json.dumps({
            "type": "response.output_text.done",
            "text": json.dumps({"url": "https://example.com/generated.png"}),
        }) + "\n").encode(),
        b"data: [DONE]\n",
    ]

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def __iter__(self):
            return iter(lines)

    class FakeDownloadResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b"png-bytes"

    def fake_urlopen(req, *_args, **_kwargs):
        if getattr(req, "full_url", "").endswith("generated.png"):
            return FakeDownloadResponse()
        return FakeResponse()

    monkeypatch.setattr(storyboard, "urlopen", fake_urlopen)
    assert storyboard._call_openai_codex_image_generation("prompt", {}, "token", "gpt-5.5", "1024x1024") == b"png-bytes"
