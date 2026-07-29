"""Central AI provider registry — the single source of truth for all AI provider info.

Every static fact about a supported AI provider lives here:
  - identity (id, label, order)
  - auth (api_key_setting, auth_supported)
  - API connectivity (base_url, header_key, header_prefix, header_version, extra_headers)
  - defaults (default_model)
  - routing hints (dominant_text)

Model IDs are NOT stored here; they are fetched from live provider catalogs at runtime.
Adapter classes and OAuth handlers are resolved separately because they carry
runtime imports, but their provider-to-class mappings are derived from this registry.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass(frozen=True)
class AIProviderConfig:
    """All static information about a supported AI provider.

    This is the single place to add, remove, or change an AI provider.
    Every other module (cmo_providers, executor, provider_auth, frontend)
    should derive its provider-specific facts from here.
    """
    provider: str
    label: str
    # ── Auth ────────────────────────────────────────────────────────────────
    api_key_setting: str | None = None
    auth_supported: tuple[str, ...] = ("api_key",)
    # ── API connectivity (used by cmo_providers.call_cmo) ───────────────────
    # api_root is the provider's canonical REST root. base_url may point at a
    # specific text endpoint (for CMO Brain); media tools derive sibling OpenAI
    # image endpoints from api_root so they do not drift to a different host.
    api_root: str | None = None
    base_url: str | None = None
    header_key: str | None = None
    header_prefix: str | None = None
    header_version: str | None = None
    version_value: str | None = None
    extra_headers: dict[str, str] = field(default_factory=dict)
    # ── Defaults ────────────────────────────────────────────────────────────
    default_model: str | None = None
    # ── Routing ─────────────────────────────────────────────────────────────
    dominant_text: bool = False
    order: int = 100


_AI_PROVIDERS: tuple[AIProviderConfig, ...] = (
    AIProviderConfig(
        provider="openai",
        label="OpenAI",
        api_key_setting="platform_openai_key",
        auth_supported=("api_key", "oauth"),
        api_root="https://api.openai.com/v1",
        base_url="https://api.openai.com/v1/chat/completions",
        header_key="Authorization",
        header_prefix="Bearer ",
        default_model="gpt-4o-mini",
        dominant_text=True,
        order=10,
    ),
    AIProviderConfig(
        provider="gemini",
        label="Google Gemini",
        api_key_setting="platform_gemini_key",
        auth_supported=("api_key", "oauth"),
        api_root="https://generativelanguage.googleapis.com/v1beta/openai",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        header_key="Authorization",
        header_prefix="Bearer ",
        default_model="gemini-2.5-flash",
        dominant_text=True,
        order=20,
    ),
    AIProviderConfig(
        provider="bytedance",
        label="BytePlus",
        api_key_setting="platform_bytedance_key",
        auth_supported=("api_key",),
        default_model="seed-2-0-pro-260328",
        dominant_text=False,
        order=30,
    ),
    AIProviderConfig(
        provider="openrouter",
        label="OpenRouter",
        api_key_setting="platform_openrouter_key",
        auth_supported=("api_key",),
        api_root="https://openrouter.ai/api/v1",
        base_url="https://openrouter.ai/api/v1/chat/completions",
        header_key="Authorization",
        header_prefix="Bearer ",
        extra_headers={
            "HTTP-Referer": "https://github.com/bos-cmo",
            "X-Title": "BOS CMO",
        },
        default_model="anthropic/claude-sonnet-4-6",
        dominant_text=False,
        order=40,
    ),
    AIProviderConfig(
        provider="nvidia",
        label="NVIDIA AI Cloud",
        api_key_setting="platform_nvidia_key",
        auth_supported=("api_key",),
        dominant_text=False,
        order=50,
    ),
)

_BY_ID = {p.provider: p for p in _AI_PROVIDERS}


# ── Query functions ────────────────────────────────────────────────────────────

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


# ── Derived mappings (used by cmo_providers, executor, provider_auth) ──────────

def get_provider_api_root(provider: str) -> str | None:
    """Return the canonical REST API root for a provider, when known."""
    cfg = get_ai_provider(provider)
    return cfg.api_root if cfg else None


def get_provider_api_config(provider: str) -> dict | None:
    """Return the API connectivity config dict used by cmo_providers.call_cmo().

    This replaces the hardcoded PROVIDERS dict in cmo_providers.py.
    """
    cfg = get_ai_provider(provider)
    if not cfg or not cfg.base_url:
        return None
    result: dict = {"base_url": cfg.base_url}
    if cfg.api_root:
        result["api_root"] = cfg.api_root
    if cfg.header_key:
        result["header_key"] = cfg.header_key
    if cfg.header_prefix:
        result["header_prefix"] = cfg.header_prefix
    if cfg.header_version:
        result["header_version"] = cfg.header_version
        if cfg.version_value is not None:
            result["version_value"] = cfg.version_value
    if cfg.extra_headers:
        result["extra_headers"] = dict(cfg.extra_headers)
    return result


def get_default_model(provider: str) -> str | None:
    """Return the default model for a provider, used by cmo_providers."""
    cfg = get_ai_provider(provider)
    return cfg.default_model if cfg else None


def get_all_api_configs() -> dict[str, dict]:
    """Return {provider: api_config_dict} for all providers that have API configs.

    This replaces the hardcoded PROVIDERS dict in cmo_providers.py.
    """
    result: dict[str, dict] = {}
    for p in _AI_PROVIDERS:
        api = get_provider_api_config(p.provider)
        if api:
            result[p.provider] = api
    return result
