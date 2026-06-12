from __future__ import annotations

import time
from typing import List, Dict

import httpx

from providers.base import ProviderResponse


class OpenAICompatAdapter:
    """Reusable base for any provider that speaks the OpenAI chat completions protocol."""

    provider_id: str

    def __init__(self, provider_id: str, base_url: str, api_key: str) -> None:
        self.provider_id = provider_id
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key

    async def complete(
        self,
        prompt: str,
        model_id: str,
        extra_body: dict | None = None,
    ) -> ProviderResponse:
        return await self.complete_messages(
            [{"role": "user", "content": prompt}], model_id, extra_body=extra_body
        )

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
            payload.update(extra_body)

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
        return ProviderResponse(
            content=content,
            tokens_input=usage.get("prompt_tokens", 0),
            tokens_output=usage.get("completion_tokens", 0),
            latency_ms=latency_ms,
        )

    def _thinking_params(self, model_id: str, budget: int) -> dict:
        """Return provider-specific params to enable extended thinking."""
        # Claude models via OpenRouter or direct Anthropic compat
        if "claude" in model_id.lower():
            return {
                "thinking": {"type": "enabled", "budget_tokens": budget},
                "temperature": 1,  # required for Claude extended thinking
            }
        # Gemini 2.5 thinking is always-on — just upgrade to the thinking model
        if "gemini" in model_id.lower():
            return {}  # handled by model upgrade in _upgrade_for_thinking
        # OpenAI o-series has built-in reasoning; for others, no-op
        return {}

    def _upgrade_for_thinking(self, model_id: str) -> str:
        """Return the best thinking-capable variant of the given model."""
        if "gemini-2.0" in model_id:
            return "gemini-2.5-pro"
        if "gemini-2.5-flash" in model_id:
            return "gemini-2.5-pro"
        return model_id  # all other models: use as-is

    def _extract_text(self, raw: object) -> str:
        """Handle both plain string and block-array content (extended thinking responses)."""
        if isinstance(raw, str):
            return raw
        if isinstance(raw, list):
            parts = [
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in raw
                if not (isinstance(block, dict) and block.get("type") == "thinking")
            ]
            return "".join(parts).strip()
        return str(raw)

    async def check(self) -> bool:
        """Verify key via GET /models (authenticated on most providers)."""
        headers = {"Authorization": f"Bearer {self._api_key}"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{self._base_url}/models", headers=headers)
        return resp.status_code == 200
