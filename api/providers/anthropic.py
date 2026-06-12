from __future__ import annotations

import time
from typing import Any, Dict, List

import httpx

from providers.base import ProviderResponse

_BASE_URL = "https://api.anthropic.com/v1"
_ANTHROPIC_VERSION = "2023-06-01"


class AnthropicAdapter:
    provider_id = "anthropic"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._base_url = _BASE_URL

    async def complete(self, prompt: str, model_id: str, extra_body: dict | None = None) -> ProviderResponse:
        return await self.complete_messages([
            {"role": "user", "content": prompt}
        ], model_id, extra_body=extra_body)

    async def complete_messages(
        self,
        messages: List[Dict],
        model_id: str,
        extra_body: dict | None = None,
    ) -> ProviderResponse:
        system_parts: list[str] = []
        anthropic_messages: list[dict[str, Any]] = []
        for message in messages:
            role = str(message.get("role") or "user")
            content = message.get("content", "")
            if role in {"system", "developer"}:
                text = _content_to_text(content)
                if text:
                    system_parts.append(text)
                continue
            if role not in {"user", "assistant"}:
                role = "user"
            anthropic_messages.append({"role": role, "content": _content_to_text(content)})

        if not anthropic_messages:
            anthropic_messages.append({"role": "user", "content": ""})

        body: dict[str, Any] = {
            "model": model_id,
            "max_tokens": 4096,
            "messages": anthropic_messages,
        }
        if system_parts:
            body["system"] = "\n\n".join(system_parts)
        if extra_body:
            body.update({k: v for k, v in extra_body.items() if k != "_routing_hints"})

        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": _ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{self._base_url}/messages", headers=headers, json=body)
            resp.raise_for_status()
        latency_ms = round((time.perf_counter() - start) * 1000)
        data = resp.json()
        usage = data.get("usage", {})
        return ProviderResponse(
            content=_anthropic_content_to_text(data.get("content")),
            tokens_input=usage.get("input_tokens", 0),
            tokens_output=usage.get("output_tokens", 0),
            latency_ms=latency_ms,
        )

    async def check(self) -> bool:
        headers = {"x-api-key": self._api_key, "anthropic-version": _ANTHROPIC_VERSION}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{self._base_url}/models", headers=headers)
        return resp.status_code == 200


def _content_to_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") in {"text", None}:
                    parts.append(str(item.get("text") or ""))
            else:
                parts.append(str(item))
        return "".join(parts)
    return str(content)


def _anthropic_content_to_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text") or ""))
        return "".join(parts).strip()
    return str(content or "")
