import httpx
import pytest

from routers import cmo_providers


@pytest.mark.asyncio
async def test_call_cmo_does_not_mask_streaming_http_errors(monkeypatch):
    async def raise_unread_stream_error(*_args, **_kwargs):
        request = httpx.Request("POST", "https://provider.example/v1/chat")
        response = httpx.Response(
            500,
            request=request,
            stream=httpx.ByteStream(b'{"error":"provider failed"}'),
        )
        # Accessing response.text here would raise httpx.ResponseNotRead. The
        # provider boundary must not let that mask the real HTTP status.
        raise httpx.HTTPStatusError("provider failed", request=request, response=response)

    monkeypatch.setattr(cmo_providers, "_with_retry", raise_unread_stream_error)

    result = await cmo_providers.call_cmo(
        messages=[{"role": "user", "content": "hello"}],
        config={"provider": "openai", "model": "gpt-test", "api_key": "test", "system_prompt": ""},
        tools={},
    )

    assert result == {"type": "error", "text": "Provider error (500)"}


@pytest.mark.asyncio
async def test_call_cmo_falls_back_on_runtime_429(monkeypatch):
    calls: list[str] = []

    async def rate_limit_primary_then_succeed(_client, _url, _headers, body, provider, on_text):
        calls.append(provider)
        if provider == "openai":
            request = httpx.Request("POST", "https://provider.example/v1/chat")
            response = httpx.Response(
                429,
                request=request,
                stream=httpx.ByteStream(b'{"error":"rate limited"}'),
            )
            raise httpx.HTTPStatusError("rate limited", request=request, response=response)
        assert provider == "gemini"
        assert body["model"] == "gemini-test"
        if on_text:
            on_text("fallback ok")
        return {"type": "text", "text": "fallback ok"}

    monkeypatch.setattr(cmo_providers, "_with_retry", rate_limit_primary_then_succeed)

    result = await cmo_providers.call_cmo(
        messages=[{"role": "user", "content": "hello"}],
        config={
            "provider": "openai",
            "model": "gpt-test",
            "api_key": "test",
            "system_prompt": "system rules",
            "fallbacks": [{"provider": "gemini", "model": "gemini-test", "api_key": "fallback", "max_tokens": 4096}],
        },
        tools={},
    )

    assert calls == ["openai", "gemini"]
    assert result["type"] == "text"
    assert result["text"] == "fallback ok"
    assert result["provider"] == "gemini"
    assert result["model"] == "gemini-test"


@pytest.mark.asyncio
async def test_call_cmo_returns_clear_rate_limit_without_fallback(monkeypatch):
    async def always_rate_limited(*_args, **_kwargs):
        request = httpx.Request("POST", "https://provider.example/v1/chat")
        response = httpx.Response(429, request=request, stream=httpx.ByteStream(b'{"error":"rate limited"}'))
        raise httpx.HTTPStatusError("rate limited", request=request, response=response)

    monkeypatch.setattr(cmo_providers, "_with_retry", always_rate_limited)

    result = await cmo_providers.call_cmo(
        messages=[{"role": "user", "content": "hello"}],
        config={"provider": "openai", "model": "gpt-test", "api_key": "test", "system_prompt": ""},
        tools={},
    )

    assert result == {
        "type": "error",
        "text": "Provider rate limited (429). Try again shortly or switch the CMO Brain provider/model.",
    }


@pytest.mark.asyncio
async def test_stream_status_helper_buffers_error_body_before_raise():
    request = httpx.Request("POST", "https://provider.example/v1/chat")
    response = httpx.Response(
        429,
        request=request,
        stream=httpx.ByteStream(b'{"error":"rate limited"}'),
    )

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await cmo_providers._raise_for_stream_status(response)

    assert exc_info.value.response.text == '{"error":"rate limited"}'
