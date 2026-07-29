from __future__ import annotations

import importlib.util
from pathlib import Path

from ai_provider_registry import get_provider_api_config, get_provider_api_root


ROOT = Path(__file__).resolve().parents[2]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_openai_registry_exposes_same_api_root_for_cmo_and_media_tools():
    cfg = get_provider_api_config("openai")

    assert cfg is not None
    assert cfg["base_url"] == "https://api.openai.com/v1/chat/completions"
    assert cfg["api_root"] == "https://api.openai.com/v1"
    assert get_provider_api_root("openai") == cfg["api_root"]


def test_postcraft_openai_client_derives_image_endpoints_from_cmo_api_root():
    client = _load_module("postcraft_openai_client_test", ROOT / "plugins/postcraft/lib/openai_client.py")

    assert client._endpoint("images/generations", "https://api.openai.com/v1/chat/completions") == "https://api.openai.com/v1/images/generations"
    assert client._endpoint("images/edits", "https://api.openai.com/v1") == "https://api.openai.com/v1/images/edits"


def test_storyboard_normalizes_openai_base_url_from_channel_credentials():
    storyboard = _load_module("storyboard_json_image_test", ROOT / "plugins/storyboard/lib/json_image_storyboard.py")

    brief = {"_channel_credentials": {"openai_api_base_url": "https://api.openai.com/v1/chat/completions"}}
    assert storyboard._openai_base_url_from_brief(brief) == "https://api.openai.com/v1"


def test_storyboard_direct_render_uses_postcraft_openai_api_root(monkeypatch):
    render = _load_module(
        "storyboard_direct_render_endpoint_test",
        ROOT / "plugins/storyboard/capabilities/storyboard/json/render/module.py",
    )
    seen = {}

    class FakeCore:
        RUNS_ROOT = "/tmp/bos-storyboard-runs"

        @staticmethod
        def _get_image_creds(_brief):
            return "openai", "gpt-image-2", "fake-key"

        @staticmethod
        def _openai_base_url_from_brief(brief):
            return brief["_channel_credentials"]["openai_api_base_url"].removesuffix("/chat/completions")

        @staticmethod
        def _normalize_requested_size(_value):
            return "1536x1024"

        @staticmethod
        def _call_openai_generate(_spec, _prompt, _brief, _api_key, _model, size, base_url=None):
            seen["size"] = size
            seen["base_url"] = base_url
            return {"data": [{"b64_json": "ZmFrZQ=="}]}

        @staticmethod
        def _image_response_to_bytes(_response):
            return b"fake-image", {}

    monkeypatch.setattr(render, "_load_core", lambda: FakeCore)
    monkeypatch.setattr(render, "_inject_logo_reference", lambda brief, brand_spec: [])
    monkeypatch.setattr(render, "_store_in_drive", lambda brief, image_bytes, output_path: {"drive_file_id": "drive123"})

    attempt, result = render.StoryboardRenderModule().execute_tool_result({
        "storyboard_text": "Approved storyboard with enough visual detail to render a clean reference sheet.",
        "_channel_credentials": {
            "openai_api_base_url": "https://api.openai.com/v1/chat/completions",
            "provider_api_key": "fake-key",
            "provider_api_key_auth_mode": "api_key",
            "google_drive_page_token": "drive-token",
            "drive_root_folder_id": "root-folder",
        },
    })

    assert attempt["status"] == "succeeded"
    assert result["block"]["status"] == "succeeded"
    assert seen == {"size": "1536x1024", "base_url": "https://api.openai.com/v1"}


def test_postcraft_and_storyboard_accept_openai_oauth_credential():
    postcraft = _load_module(
        "postcraft_render_oauth_test",
        ROOT / "plugins/postcraft/capabilities/postcraft/render/module.py",
    )
    storyboard = _load_module("storyboard_oauth_test", ROOT / "plugins/storyboard/lib/json_image_storyboard.py")
    brief = {
        "_channel_credentials": {
            "image_gen_provider": "openai",
            "image_gen_model": "gpt-image-2",
            "provider_api_key": "oauth-token",
            "provider_api_key_auth_mode": "oauth",
        }
    }

    assert postcraft._get_image_creds(brief) == ("openai", "gpt-image-2", "oauth-token")
    assert storyboard._get_image_creds(brief) == ("openai", "gpt-image-2", "oauth-token")
