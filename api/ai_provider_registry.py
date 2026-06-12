"""Central AI provider registry.

Provider IDs are intentionally centralized here so UI/backend code can discover
supported first-class AI providers without scattering hard-coded provider lists.
Model IDs are not stored here; they are fetched from provider catalogs at runtime.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class AIProviderConfig:
    provider: str
    label: str
    api_key_setting: str | None = None
    auth_supported: tuple[str, ...] = ("api_key",)
    dominant_text: bool = False
    order: int = 100


_AI_PROVIDERS: tuple[AIProviderConfig, ...] = (
    AIProviderConfig("openai", "OpenAI", "platform_openai_key", ("api_key", "oauth"), True, 10),
    AIProviderConfig("anthropic", "Anthropic", "platform_anthropic_key", ("api_key",), True, 20),
    AIProviderConfig("gemini", "Google Gemini", "platform_gemini_key", ("api_key", "oauth"), True, 30),
    AIProviderConfig("openrouter", "OpenRouter", "platform_openrouter_key", ("api_key",), False, 40),
    AIProviderConfig("bytedance", "BytePlus", "platform_bytedance_key", ("api_key",), False, 50),
    AIProviderConfig("nvidia", "NVIDIA AI Cloud", "platform_nvidia_key", ("api_key",), False, 60),
)

_BY_ID = {p.provider: p for p in _AI_PROVIDERS}


def list_ai_providers() -> tuple[AIProviderConfig, ...]:
    return tuple(sorted(_AI_PROVIDERS, key=lambda p: p.order))


def list_ai_provider_ids() -> tuple[str, ...]:
    return tuple(p.provider for p in list_ai_providers())


def list_dominant_text_provider_ids() -> tuple[str, ...]:
    """The first-class CMO/provider picker providers.

    These are the major BYOK providers operators are most likely to bring. Their
    model choices must come from live provider catalogs, capped to a small set.
    """
    return tuple(p.provider for p in list_ai_providers() if p.dominant_text)


def get_ai_provider(provider: str) -> AIProviderConfig | None:
    return _BY_ID.get((provider or "").strip().lower())


def is_ai_provider(provider: str) -> bool:
    return get_ai_provider(provider) is not None


def get_ai_auth_supported(provider: str) -> list[str]:
    cfg = get_ai_provider(provider)
    return list(cfg.auth_supported) if cfg else []


def get_platform_key(provider: str, settings) -> str | None:
    cfg = get_ai_provider(provider)
    if not cfg or not cfg.api_key_setting:
        return None
    value = getattr(settings, cfg.api_key_setting, "")
    return value or None


def labels() -> dict[str, str]:
    return {p.provider: p.label for p in _AI_PROVIDERS}
