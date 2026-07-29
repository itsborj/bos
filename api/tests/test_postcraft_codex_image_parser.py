import base64
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path("/external_plugins/postcraft/lib/openai_client.py")
if not PLUGIN_ROOT.exists():
    PLUGIN_ROOT = ROOT / "plugins/postcraft/lib/openai_client.py"
spec = importlib.util.spec_from_file_location("postcraft_openai_client", PLUGIN_ROOT)
assert spec and spec.loader
openai_client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(openai_client)


def test_codex_image_payload_accepts_partial_event():
    payload = base64.b64encode(b"png-bytes").decode()
    event = {
        "type": "response.image_generation_call.partial_image",
        "partial_image_b64": payload,
    }
    assert openai_client._decode_codex_image(openai_client._codex_image_payload(event)) == b"png-bytes"


def test_codex_image_payload_accepts_completed_output_item():
    payload = base64.b64encode(b"png-bytes").decode()
    event = {
        "type": "response.output_item.done",
        "item": {"type": "image_generation_call", "status": "completed", "result": payload},
    }
    assert openai_client._decode_codex_image(openai_client._codex_image_payload(event)) == b"png-bytes"


def test_codex_image_payload_accepts_wrapped_result():
    payload = base64.b64encode(b"png-bytes").decode()
    event = {
        "type": "response.output_item.done",
        "item": {"type": "image_generation_call", "result": {"b64_json": payload}},
    }
    assert openai_client._decode_codex_image(openai_client._codex_image_payload(event)) == b"png-bytes"


def test_codex_image_generation_reads_completed_response(monkeypatch):
    payload = base64.b64encode(b"png-bytes").decode()
    lines = [
        b'data: {"type":"response.output_item.added","item":{"type":"image_generation_call"}}\n',
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

    monkeypatch.setattr(openai_client, "urlopen", lambda *_args, **_kwargs: FakeResponse())
    assert openai_client.generate_image_codex("prompt", "token") == b"png-bytes"


def test_codex_image_generation_reads_nested_data_array(monkeypatch):
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

    monkeypatch.setattr(openai_client, "urlopen", lambda *_args, **_kwargs: FakeResponse())
    assert openai_client.generate_image_codex("prompt", "token") == b"png-bytes"


def test_codex_image_generation_downloads_image_url(monkeypatch):
    lines = [
        ("data: " + json.dumps({
            "type": "response.completed",
            "response": {"output": [{"type": "image_generation_call", "result": {"url": "https://example.com/generated.png"}}]},
        }) + "\n").encode(),
        b"data: [DONE]\n",
    ]

    class FakeStreamResponse:
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
        return FakeStreamResponse()

    monkeypatch.setattr(openai_client, "urlopen", fake_urlopen)
    assert openai_client.generate_image_codex("prompt", "token") == b"png-bytes"


def test_codex_image_generation_reads_output_text_json(monkeypatch):
    lines = [
        ("data: " + json.dumps({
            "type": "response.output_text.done",
            "text": json.dumps({"url": "https://example.com/generated.png"}),
        }) + "\n").encode(),
        b"data: [DONE]\n",
    ]

    class FakeStreamResponse:
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
        return FakeStreamResponse()

    monkeypatch.setattr(openai_client, "urlopen", fake_urlopen)
    assert openai_client.generate_image_codex("prompt", "token") == b"png-bytes"
