from __future__ import annotations
import time

import httpx

from providers.base import ProviderResponse
from typing import List, Dict

_BASE_URL = "https://api.openai.com/v1"


class OpenAIAdapter:
    provider_id = "openai"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._base_url = _BASE_URL

    async def complete(self, prompt: str, model_id: str) -> ProviderResponse:
        return await self.complete_messages([
            {"role": "user", "content": prompt}
        ], model_id)

    from typing import List, Dict
    async def complete_messages(self, messages: List[Dict], model_id: str) -> ProviderResponse:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": model_id, "messages": messages}
        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{self._base_url}/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
        latency_ms = round((time.perf_counter() - start) * 1000)
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return ProviderResponse(
            content=content,
            tokens_input=usage.get("prompt_tokens", 0),
            tokens_output=usage.get("completion_tokens", 0),
            latency_ms=latency_ms,
        )

    async def check(self) -> bool:
        headers = {"Authorization": f"Bearer {self._api_key}"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{self._base_url}/models", headers=headers)
        return resp.status_code == 200
