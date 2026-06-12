from __future__ import annotations
import base64
import json
import time
from typing import Any, List, Dict, Optional, Tuple

import httpx

from providers.base import ProviderResponse

_BASE_URL = "https://chatgpt.com/backend-api"
_JWT_CLAIM_PATH = "https://api.openai.com/auth"


class OpenAICodexAdapter:
    provider_id = "openai"

    def __init__(self, access_token: str) -> None:
        self._access_token = access_token
        self._base_url = _BASE_URL
        self._account_id = _extract_account_id(access_token)

    async def complete(self, prompt: str, model_id: str, extra_body: dict | None = None) -> ProviderResponse:
        return await self.complete_messages([
            {"role": "user", "content": prompt}
        ], model_id, extra_body=extra_body)

    async def complete_messages(self, messages: List[Dict], model_id: str, extra_body: dict | None = None) -> ProviderResponse:
        instructions, input_items = _convert_messages(messages)
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "chatgpt-account-id": self._account_id,
            "originator": "pi",
            "OpenAI-Beta": "responses=experimental",
            "accept": "text/event-stream",
            "content-type": "application/json",
            "User-Agent": "pi (browser)",
        }
        body: Dict[str, Any] = {
            "model": _codex_model(model_id),
            "store": False,
            "stream": True,
            "input": input_items,
            "text": {"verbosity": "low"},
            "include": ["reasoning.encrypted_content"],
            "tool_choice": "auto",
            "parallel_tool_calls": True,
        }
        if instructions:
            body["instructions"] = instructions
        else:
            body["instructions"] = "Respond concisely."

        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", f"{self._base_url}/codex/responses", headers=headers, json=body) as resp:
                if resp.status_code >= 400:
                    body_bytes = await resp.aread()
                    detail = body_bytes.decode(errors="replace")[:300]
                    raise ValueError(f"OpenAI Codex request failed ({resp.status_code}): {detail or resp.reason_phrase}")
                full_content: List[str] = []
                usage: Dict[str, Any] = {}
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    event_type = data.get("type")
                    if event_type == "error":
                        message = data.get("message") or data.get("code") or json.dumps(data)[:300]
                        raise ValueError(f"OpenAI Codex stream error: {message}")
                    if event_type == "response.failed":
                        response = data.get("response") or {}
                        error = response.get("error") if isinstance(response, dict) else None
                        message = (error or {}).get("message") if isinstance(error, dict) else None
                        raise ValueError(f"OpenAI Codex response failed: {message or json.dumps(data)[:300]}")

                    if event_type == "response.output_text.delta":
                        delta = data.get("delta")
                        if isinstance(delta, str):
                            full_content.append(delta)
                        continue

                    if event_type == "response.output_text.done":
                        text = data.get("text")
                        if isinstance(text, str) and not full_content:
                            full_content.append(text)
                        continue

                    if event_type in {"response.completed", "response.done", "response.incomplete"}:
                        response = data.get("response") if isinstance(data.get("response"), dict) else data
                        usage = response.get("usage", {}) if isinstance(response, dict) else {}
                        text = _extract_text(response) if isinstance(response, dict) and not full_content else ""
                        if text:
                            full_content.append(text)
                        continue

                    if event_type in {"message", "response.output_item.done"}:
                        item = data.get("item") if event_type == "response.output_item.done" else data
                        text = _extract_text(item) if isinstance(item, dict) else ""
                        if text:
                            full_content.append(text)
                        continue

                    if isinstance(data.get("output_text"), str):
                        full_content.append(data["output_text"])

        latency_ms = round((time.perf_counter() - start) * 1000)
        input_tokens = usage.get("input_tokens") or usage.get("prompt_tokens") or 0
        output_tokens = usage.get("output_tokens") or usage.get("completion_tokens") or 0
        return ProviderResponse(
            content="".join(full_content).strip(),
            tokens_input=input_tokens,
            tokens_output=output_tokens,
            latency_ms=latency_ms,
        )

    async def check(self) -> bool:
        try:
            response = await self.complete_messages([
                {"role": "user", "content": "ping"}
            ], "gpt-5.3-codex")
            return bool(response.content.strip())
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:300] if exc.response is not None else str(exc)
            raise ValueError(f"OpenAI auth check failed ({exc.response.status_code}): {detail}") from exc
        except Exception as exc:
            raise ValueError(f"OpenAI auth check failed: {exc}") from exc


def _codex_model(model_id: str) -> str:
    normalized = (model_id or "").strip()
    if normalized.startswith("openai/"):
        normalized = normalized.split("/", 1)[1]
    if not normalized:
        return "gpt-5.3-codex"
    if "codex" in normalized:
        return normalized
    if normalized.startswith("gpt-5.1") or normalized.startswith("gpt-5.2") or normalized.startswith("gpt-5.3"):
        return "gpt-5.3-codex"
    return normalized


def _extract_account_id(token: str) -> str:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("invalid token")
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(payload.encode()).decode())
        account_id = decoded.get(_JWT_CLAIM_PATH, {}).get("chatgpt_account_id")
        if not account_id:
            raise ValueError("missing account id")
        return str(account_id)
    except Exception as exc:
        raise ValueError("Failed to extract accountId from token") from exc


def _convert_messages(messages: List[Dict]) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    instructions_parts: List[str] = []
    input_items: List[Dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content") or ""
        if not isinstance(content, str):
            content = str(content)
        if role == "system":
            if content.strip():
                instructions_parts.append(content.strip())
            continue
        input_items.append({"role": role, "content": content})
    instructions = "\n\n".join(instructions_parts).strip() or None
    return instructions, input_items


def _extract_text(data: dict[str, Any]) -> str:
    if isinstance(data.get("output_text"), str) and data["output_text"].strip():
        return data["output_text"]
    texts: list[str] = []
    for item in data.get("output", []) or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "message":
            for content in item.get("content", []) or []:
                if isinstance(content, dict):
                    text = content.get("text")
                    if isinstance(text, str) and text:
                        texts.append(text)
        text = item.get("text")
        if isinstance(text, str) and text:
            texts.append(text)
    if texts:
        return "\n".join(texts)
    return ""
