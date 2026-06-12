from __future__ import annotations

import time
from typing import Dict, List

import httpx

from providers.base import ProviderResponse
from providers.openai_compat import OpenAICompatAdapter

_BASE_URL = "https://openrouter.ai/api/v1"

_HINTS_MAP = {
    "sort": "sort",
    "order": "order",
    "allow_fallbacks": "allowFallbacks",
    "data_collection": "dataCollection",
}


def _build_provider_field(routing_hints: dict) -> dict:
    return {v: routing_hints[k] for k, v in _HINTS_MAP.items() if k in routing_hints}


class OpenRouterAdapter(OpenAICompatAdapter):
    provider_id = "openrouter"

    def __init__(self, api_key: str) -> None:
        super().__init__("openrouter", _BASE_URL, api_key)

    async def complete_messages(
        self,
        messages: List[Dict],
        model_id: str,
        thinking: bool = False,
        thinking_budget: int = 8000,
        extra_body: dict | None = None,
    ) -> ProviderResponse:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload: dict = {"model": model_id, "messages": messages}

        if thinking:
            payload.update(self._thinking_params(model_id, thinking_budget))

        if extra_body:
            routing_hints = extra_body.pop("_routing_hints", None)
            payload.update(extra_body)
            if routing_hints:
                provider_field = _build_provider_field(routing_hints)
                if provider_field:
                    payload.setdefault("provider", {}).update(provider_field)

        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self._base_url}/chat/completions", headers=headers, json=payload
            )
            resp.raise_for_status()
        latency_ms = round((time.perf_counter() - start) * 1000)
        data = resp.json()

        raw_content = data["choices"][0]["message"]["content"]
        content = self._extract_text(raw_content)

        usage = data.get("usage", {})
        # Capture the model OR actually used (may differ from requested when native failover fires)
        actual_model = data.get("model")
        return ProviderResponse(
            content=content,
            tokens_input=usage.get("prompt_tokens", 0),
            tokens_output=usage.get("completion_tokens", 0),
            latency_ms=latency_ms,
            actual_model=actual_model if actual_model != model_id else None,
        )

    async def check(self) -> bool:
        """OpenRouter's /models is public — use /auth/key which requires a valid key."""
        headers = {"Authorization": f"Bearer {self._api_key}"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{self._base_url}/auth/key", headers=headers)
        return resp.status_code == 200
