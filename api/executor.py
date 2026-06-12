from __future__ import annotations
import logging
from typing import Optional, Tuple, Dict
import time

from ai_provider_registry import get_platform_key as registry_platform_key
from providers.anthropic import AnthropicAdapter
from providers.bytedance import ByteDanceAdapter
from providers.gemini import GeminiAdapter, GeminiOAuthAdapter
from providers.nvidia import NvidiaAdapter
from providers.openai import OpenAIAdapter
from providers.openai_codex import OpenAICodexAdapter
from providers.openrouter import OpenRouterAdapter

logger = logging.getLogger("bos.executor")

_ADAPTERS = {
    "openrouter": OpenRouterAdapter,
    "gemini": GeminiAdapter,
    "nvidia": NvidiaAdapter,
    "openai": OpenAIAdapter,
    "anthropic": AnthropicAdapter,
    "bytedance": ByteDanceAdapter,
}


class _GoogleIdentityAdapter:
    """Lightweight adapter for the 'google' login provider.
    Validates the OAuth access token by calling the userinfo endpoint.
    Google is not an AI model provider so complete() is not supported.
    """

    def __init__(self, api_key: str):
        self._token = api_key

    async def check(self) -> bool:
        import httpx
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(
                    "https://www.googleapis.com/oauth2/v1/userinfo",
                    headers={"Authorization": f"Bearer {self._token}"},
                )
                return r.status_code == 200
        except Exception:
            return False

    async def complete(self, prompt: str, model_id: str):
        raise NotImplementedError("Google is a login provider — it does not support AI completions")


def get_adapter(provider: str, api_key: str, auth_mode: Optional[str] = None):
    if provider == "openai" and auth_mode == "oauth":
        return OpenAICodexAdapter(api_key)
    if provider == "gemini" and auth_mode == "oauth":
        # The OpenAI-compat endpoint only accepts API keys; OAuth tokens need
        # the native Gemini REST API (/v1beta/models/...:generateContent).
        return GeminiOAuthAdapter(api_key)
    if provider == "google":
        # Google is a login/identity provider, not an AI model provider.
        # Return a lightweight adapter that validates the OAuth token.
        return _GoogleIdentityAdapter(api_key)
    adapter_cls = _ADAPTERS.get(provider)
    if not adapter_cls:
        raise ValueError(f"No live adapter registered for provider '{provider}'")
    return adapter_cls(api_key)


def get_adapter_class(provider: str):
    return _ADAPTERS.get(provider)


def get_platform_key(provider: str, settings) -> Optional[str]:
    """Return the configured platform key for a provider, or None if not set."""
    return registry_platform_key(provider, settings)


def execute_mock(
    candidate: dict,
    brief: dict,
    module_id: str,
    markup_multiplier: float = 1.35,
) -> Tuple[Dict, Dict]:
    """Simulate a provider call without hitting a real API."""
    start = time.perf_counter()
    content = _mock_content(module_id, brief)
    latency_ms = round((time.perf_counter() - start) * 1000 + 180)

    attempt = {
        "provider": candidate["provider"],
        "model_id": candidate["model_id"],
        "mode": "mock",
        "status": "succeeded",
        "tokens_input": 0,
        "tokens_output": 0,
        "provider_cost": 0.0,
        "latency_ms": latency_ms,
        "error": None,
    }

    result = {
        "content": content,
        "sell_price": None,
    }

    return attempt, result


async def execute_live(
    candidate: dict,
    prompt: str,
    api_key: str,
    markup_multiplier: float = 1.35,
    byok: bool = False,
    auth_mode: Optional[str] = None,
) -> Tuple[Dict, Dict]:
    """Call a real provider adapter and return the same shape as execute_mock."""
    provider = candidate["provider"]
    adapter = get_adapter(provider, api_key, auth_mode)
    extra_body = candidate.get("extra_body")
    response = await adapter.complete(prompt, candidate["model_id"], extra_body=extra_body)

    # Cost fields are present for catalog-sourced candidates; absent for override-constructed ones.
    provider_cost = round(
        response.tokens_input * candidate.get("input_cost_per_token", 0.0)
        + response.tokens_output * candidate.get("output_cost_per_token", 0.0),
        6,
    )

    # Use the model OR actually served (differs from requested when OR-native failover fired).
    actual_model_id = response.actual_model or candidate["model_id"]

    attempt = {
        "provider": candidate["provider"],
        "model_id": actual_model_id,
        "mode": auth_mode if auth_mode == "oauth" else ("byok" if byok else "platform"),
        "status": "succeeded",
        "tokens_input": response.tokens_input,
        "tokens_output": response.tokens_output,
        "provider_cost": provider_cost,
        "latency_ms": response.latency_ms,
        "error": None,
    }

    result = {
        "content": response.content,
        "sell_price": None if byok or auth_mode == "oauth" else round(provider_cost * markup_multiplier, 6),
    }

    return attempt, result


def _mock_content(module_id: str, brief: dict) -> str:
    product = brief.get("product_name", "the product")
    audience = brief.get("audience", "your audience")
    benefit = brief.get("key_benefit", "")
    b = f" — {benefit}" if benefit else ""
    # module_id tail (e.g. "draft") is available as module_id.rsplit(".", 1)[-1]
    # but is not currently used in the generic mock template.

    return f"[mock] {product}{b} — crafted for {audience}."
