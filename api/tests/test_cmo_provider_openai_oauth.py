import base64
import json
from types import SimpleNamespace

import httpx
import pytest

from routers import cmo_providers


def _fake_openai_jwt() -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').decode().rstrip("=")
    payload = base64.urlsafe_b64encode(json.dumps({
        "https://api.openai.com/auth": {"chatgpt_account_id": "acct_test"}
    }).encode()).decode().rstrip("=")
    return f"{header}.{payload}.sig"


@pytest.mark.asyncio
async def test_openai_oauth_credential_is_preserved_for_cmo(monkeypatch):
    async def fake_resolve(*_args, **_kwargs):
        return _fake_openai_jwt(), "oauth"

    monkeypatch.setattr(cmo_providers, "resolve_stored_provider_credential", fake_resolve)

    cfg = await cmo_providers._provider_config_for(
        db=object(),
        ws=SimpleNamespace(id="workspace"),
        settings=object(),
        provider="openai",
        model="gpt-5.5",
    )

    assert cfg is not None
    assert cfg["provider"] == "openai"
    assert cfg["auth_mode"] == "oauth"
    assert cfg["api_key"]


@pytest.mark.asyncio
async def test_openai_oauth_cmo_uses_codex_endpoint_and_parses_tool_call(monkeypatch):
    seen = {}

    class FakeStreamResponse:
        is_error = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return False

        async def aiter_lines(self):
            yield 'data: {"type":"response.output_item.done","item":{"type":"function_call","call_id":"call_1","name":"look_up","arguments":"{\\"q\\":\\"x\\"}"}}'
            yield 'data: [DONE]'

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return False

        def stream(self, method, url, headers=None, json=None, **kwargs):
            seen["method"] = method
            seen["url"] = url
            seen["headers"] = headers or {}
            seen["body"] = json or {}
            return FakeStreamResponse()

    monkeypatch.setattr(cmo_providers.httpx, "AsyncClient", FakeClient)

    result = await cmo_providers.call_cmo(
        messages=[{"role": "user", "content": "Use a tool"}],
        config={
            "provider": "openai",
            "model": "gpt-5.5",
            "api_key": _fake_openai_jwt(),
            "auth_mode": "oauth",
            "system_prompt": "system rules",
        },
        tools={
            "look_up": {
                "description": "Lookup data",
                "parameters": {"q": {"type": "string", "description": "query"}},
                "required": ["q"],
            }
        },
    )

    assert seen["url"] == "https://chatgpt.com/backend-api/codex/responses"
    assert seen["url"] != "https://api.openai.com/v1/chat/completions"
    assert seen["headers"]["chatgpt-account-id"] == "acct_test"
    assert seen["body"]["tools"][0]["name"] == "look_up"
    assert result["type"] == "tool_calls"
    assert result["tool_calls"] == [{"id": "call_1", "name": "look_up", "args": {"q": "x"}}]


def test_runtime_fallbacks_skip_duplicate_openai_oauth_surface():
    primary = {
        "provider": "openai", "model": "gpt-5.5", "auth_mode": "oauth", "api_key": "oauth-token",
    }
    cfg = cmo_providers._with_runtime_fallbacks(primary, [
        {"provider": "openai", "model": "gpt-4o-mini", "auth_mode": "oauth", "api_key": "oauth-token"},
        {"provider": "gemini", "model": "gemini-2.5-flash", "api_key": "gemini-key"},
    ])

    assert [(item["provider"], item["model"]) for item in cfg["fallbacks"]] == [
        ("gemini", "gemini-2.5-flash"),
    ]


@pytest.mark.asyncio
async def test_openai_oauth_retries_transient_503_before_fallback(monkeypatch):
    attempts = 0

    async def transient_then_ok(*_args, **_kwargs):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            request = httpx.Request("POST", "https://chatgpt.com/backend-api/codex/responses")
            response = httpx.Response(503, request=request, content=b"upstream timeout")
            raise httpx.HTTPStatusError("unavailable", request=request, response=response)
        return {"type": "text", "text": "recovered", "provider": "openai", "model": "gpt-5.5"}

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(cmo_providers, "_call_openai_codex_oauth", transient_then_ok)
    monkeypatch.setattr(cmo_providers.asyncio, "sleep", no_sleep)

    result = await cmo_providers.call_cmo(
        messages=[{"role": "user", "content": "what campaigns do you have"}],
        config={
            "provider": "openai", "model": "gpt-5.5", "api_key": _fake_openai_jwt(),
            "auth_mode": "oauth", "system_prompt": "", "fallbacks": [],
        },
        tools={},
    )

    assert attempts == 3
    assert result["text"] == "recovered"


@pytest.mark.asyncio
async def test_openai_api_key_cmo_still_uses_native_openai_registry(monkeypatch):
    called = {}

    async def fake_with_retry(_client, url, _headers, body, provider, _on_text):
        called["url"] = url
        called["provider"] = provider
        called["model"] = body["model"]
        return {"type": "text", "text": "ok"}

    monkeypatch.setattr(cmo_providers, "_with_retry", fake_with_retry)

    result = await cmo_providers.call_cmo(
        messages=[{"role": "user", "content": "hello"}],
        config={"provider": "openai", "model": "gpt-test", "api_key": "sk-test", "auth_mode": "api_key", "system_prompt": ""},
        tools={},
    )

    assert called == {
        "url": "https://api.openai.com/v1/chat/completions",
        "provider": "openai",
        "model": "gpt-test",
    }
    assert result["provider"] == "openai"
    assert result["model"] == "gpt-test"
