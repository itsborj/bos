from __future__ import annotations

import time

import httpx

from providers.base import ProviderResponse
from providers.openai_compat import OpenAICompatAdapter

_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
_NATIVE_BASE = "https://generativelanguage.googleapis.com/v1beta"


class GeminiAdapter(OpenAICompatAdapter):
    provider_id = "gemini"

    def __init__(self, api_key: str) -> None:
        super().__init__("gemini", _BASE_URL, api_key)


class GeminiOAuthAdapter:
    """Gemini adapter for OAuth token (cloud-platform scope).

    The OpenAI-compat endpoint only accepts API keys — it rejects OAuth tokens
    with 'Please pass a valid API key'. The native Gemini REST API accepts OAuth
    Bearer tokens, so OAuth mode routes through /v1beta instead of /v1beta/openai.
    """
    provider_id = "gemini"

    def __init__(self, access_token: str) -> None:
        self._token = access_token

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}"}

    async def check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(f"{_NATIVE_BASE}/models", headers=self._headers())
            return r.status_code == 200
        except Exception:
            return False

    async def complete(self, prompt: str, model_id: str, extra_body: dict | None = None) -> ProviderResponse:
        clean_model = model_id.removeprefix("google/").removeprefix("gemini/")

        body: dict = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 4096},
        }
        if extra_body:
            body.update(extra_body)

        t0 = time.perf_counter()
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(
                f"{_NATIVE_BASE}/models/{clean_model}:generateContent",
                headers={**self._headers(), "Content-Type": "application/json"},
                json=body,
            )
            r.raise_for_status()
        latency_ms = round((time.perf_counter() - t0) * 1000)

        data = r.json()
        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        content = "".join(p.get("text", "") for p in parts)
        usage = data.get("usageMetadata", {})

        return ProviderResponse(
            content=content,
            tokens_input=usage.get("promptTokenCount", 0),
            tokens_output=usage.get("candidatesTokenCount", 0),
            latency_ms=latency_ms,
            actual_model=model_id,
        )
