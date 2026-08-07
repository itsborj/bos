from __future__ import annotations

import pytest


@pytest.mark.skip(reason="anthropic BYOK support was never implemented/committed (not in ai_provider_registry)")
def test_registry_contains_major_byok_providers_without_model_ids():
    from ai_provider_registry import get_ai_provider, list_dominant_text_provider_ids

    assert list_dominant_text_provider_ids() == ("openai", "anthropic", "gemini")
    assert get_ai_provider("openai").auth_supported == ("api_key", "oauth")
    assert get_ai_provider("anthropic").auth_supported == ("api_key",)
    assert get_ai_provider("gemini").auth_supported == ("api_key", "oauth")
    assert get_ai_provider("google") is None
    assert not hasattr(get_ai_provider("openai"), "models")


def test_openai_codex_oauth_aliases_use_chatgpt_model_slug():
    from providers.openai_codex import _codex_model

    assert _codex_model("gpt-5.3-codex") == "gpt-5.5"
    assert _codex_model("openai/gpt-5.3") == "gpt-5.5"
    assert _codex_model("gpt-5.5") == "gpt-5.5"


def test_openai_live_parser_returns_top_three_released_text_models():
    from routers.providers import _openai_text_models_from_payload

    models = _openai_text_models_from_payload({"data": [
        {"id": "gpt-image-2", "created": 999},
        {"id": "gpt-5.1-mini", "created": 998},
        {"id": "gpt-4o", "created": 10},
        {"id": "gpt-4.1", "created": 20},
        {"id": "gpt-5.1", "created": 30},
        {"id": "gpt-5", "created": 25},
        {"id": "gpt-4.1-preview", "created": 40},
    ]})

    assert [m.model_id for m in models] == ["gpt-5.1", "gpt-5", "gpt-4.1"]
    assert all(m.provider == "openai" and m.modality == "text" for m in models)


@pytest.mark.skip(reason="_anthropic_text_models_from_payload was never implemented/committed in routers/providers.py")
def test_anthropic_live_parser_returns_latest_three_claude_models():
    from routers.providers import _anthropic_text_models_from_payload

    models = _anthropic_text_models_from_payload({"data": [
        {"id": "claude-3-haiku-20240307", "display_name": "Claude 3 Haiku", "created_at": "2024-03-07T00:00:00Z"},
        {"id": "not-claude", "display_name": "Other", "created_at": "2030-01-01T00:00:00Z"},
        {"id": "claude-sonnet-4-20250514", "display_name": "Claude Sonnet 4", "created_at": "2025-05-14T00:00:00Z"},
        {"id": "claude-opus-4-20250514", "display_name": "Claude Opus 4", "created_at": "2025-05-15T00:00:00Z"},
        {"id": "claude-3-5-sonnet-20241022", "display_name": "Claude 3.5 Sonnet", "created_at": "2024-10-22T00:00:00Z"},
    ]})

    assert [m.model_id for m in models] == [
        "claude-opus-4-20250514",
        "claude-sonnet-4-20250514",
        "claude-3-5-sonnet-20241022",
    ]
    assert models[0].quality_tier == "high"


def test_gemini_live_parser_filters_to_generate_content_text_models():
    from routers.providers import _gemini_text_models_from_payload

    models = _gemini_text_models_from_payload({"models": [
        {"name": "models/gemini-1.5-pro", "displayName": "Gemini 1.5 Pro", "supportedGenerationMethods": ["generateContent"], "inputTokenLimit": 1000},
        {"name": "models/gemini-2.0-flash", "displayName": "Gemini 2.0 Flash", "supportedGenerationMethods": ["generateContent"], "inputTokenLimit": 2000},
        {"name": "models/gemini-2.5-flash", "displayName": "Gemini 2.5 Flash", "supportedGenerationMethods": ["generateContent"], "inputTokenLimit": 3000},
        {"name": "models/gemini-2.5-pro", "displayName": "Gemini 2.5 Pro", "supportedGenerationMethods": ["generateContent"], "inputTokenLimit": 4000},
        {"name": "models/text-embedding-004", "supportedGenerationMethods": ["embedContent"]},
        {"name": "models/veo-3.0-generate-001", "supportedGenerationMethods": ["predictLongRunning"]},
    ]})

    assert [m.model_id for m in models] == ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash"]
    assert models[0].context_length == 4000
    assert all(m.provider == "gemini" and m.modality == "text" for m in models)


def test_gemini_live_parser_returns_veo_video_models():
    from routers.providers import _gemini_video_models_from_payload

    models = _gemini_video_models_from_payload({"models": [
        {"name": "models/gemini-2.5-pro", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/veo-3.1-lite-generate-preview", "displayName": "Veo 3.1 lite", "supportedGenerationMethods": ["predictLongRunning"]},
        {"name": "models/veo-3.1-generate-preview", "displayName": "Veo 3.1", "supportedGenerationMethods": ["predictLongRunning"]},
        {"name": "models/veo-3.1-fast-generate-preview", "displayName": "Veo 3.1 fast", "supportedGenerationMethods": ["predictLongRunning"]},
    ]})

    assert [m.model_id for m in models] == [
        "veo-3.1-generate-preview",
        "veo-3.1-fast-generate-preview",
        "veo-3.1-lite-generate-preview",
    ]
    assert all(m.provider == "gemini" and m.modality == "video" for m in models)
