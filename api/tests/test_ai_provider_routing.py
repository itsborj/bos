"""
AIPR — AI Provider Routing tests.

Covers:
  - parse_backend_ref: recursive fallbacks + routing_hints
  - BackendRef dataclass contract
  - FallbackModel / BackendOverrideIn / BackendOverrideOut schemas
  - _row_to_backendref helper
  - get_plugin_default_backend via channel.json default_backend
  - OR-native models[] queue construction logic
  - routing_hints → extra_body flow
  - ProviderResponse.actual_model field
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

import model_overrides as mo
from model_overrides import BackendRef, parse_backend_ref
from schemas.backend_settings import BackendOverrideIn, BackendOverrideOut, FallbackModel


# ── parse_backend_ref ─────────────────────────────────────────────────────────

class TestParseBackendRef:
    def test_string_ref_basic(self):
        ref = parse_backend_ref("openrouter:openai/gpt-4o-mini")
        assert ref is not None
        assert ref.provider == "openrouter"
        assert ref.model_id == "openai/gpt-4o-mini"
        assert ref.fallbacks == ()
        assert ref.routing_hints == {}

    def test_string_ref_invalid_no_colon(self):
        assert parse_backend_ref("openai") is None

    def test_string_ref_empty(self):
        assert parse_backend_ref("") is None
        assert parse_backend_ref(None) is None

    def test_dict_ref_basic(self):
        ref = parse_backend_ref({"provider": "openai", "model_id": "gpt-4.1"})
        assert ref is not None
        assert ref.provider == "openai"
        assert ref.model_id == "gpt-4.1"
        assert ref.fallbacks == ()
        assert ref.routing_hints == {}

    def test_dict_ref_with_routing_hints(self):
        ref = parse_backend_ref({
            "provider": "openrouter",
            "model_id": "anthropic/claude-sonnet-4-6",
            "routing_hints": {"sort": "price", "allow_fallbacks": True},
        })
        assert ref is not None
        assert ref.routing_hints == {"sort": "price", "allow_fallbacks": True}

    def test_dict_ref_with_fallbacks(self):
        ref = parse_backend_ref({
            "provider": "openrouter",
            "model_id": "anthropic/claude-opus-4-8",
            "fallbacks": [
                {"provider": "openrouter", "model_id": "anthropic/claude-sonnet-4-6"},
                {"provider": "openai", "model_id": "gpt-4.1"},
            ],
        })
        assert ref is not None
        assert len(ref.fallbacks) == 2
        assert ref.fallbacks[0].provider == "openrouter"
        assert ref.fallbacks[0].model_id == "anthropic/claude-sonnet-4-6"
        assert ref.fallbacks[1].provider == "openai"
        assert ref.fallbacks[1].model_id == "gpt-4.1"

    def test_dict_ref_fallback_with_own_routing_hints(self):
        ref = parse_backend_ref({
            "provider": "openrouter",
            "model_id": "primary/model",
            "fallbacks": [
                {
                    "provider": "openrouter",
                    "model_id": "fallback/model",
                    "routing_hints": {"sort": "throughput"},
                }
            ],
        })
        assert ref is not None
        assert ref.fallbacks[0].routing_hints == {"sort": "throughput"}

    def test_dict_ref_empty_fallbacks(self):
        ref = parse_backend_ref({"provider": "openai", "model_id": "gpt-4.1", "fallbacks": []})
        assert ref is not None
        assert ref.fallbacks == ()

    def test_dict_ref_missing_model_id_and_tool_id(self):
        assert parse_backend_ref({"provider": "openai"}) is None

    def test_dict_ref_with_tool_id(self):
        ref = parse_backend_ref({"provider": "python", "tool_id": "pandas_profile"})
        assert ref is not None
        assert ref.tool_id == "pandas_profile"
        assert ref.model_id is None

    def test_dict_ref_strict_field(self):
        ref = parse_backend_ref({"provider": "openai", "model_id": "gpt-4.1", "strict": False})
        assert ref is not None
        assert ref.strict is False

    def test_dict_ref_non_dict_fallbacks_ignored(self):
        # Fallback entries that aren't dicts are skipped safely
        ref = parse_backend_ref({
            "provider": "openai",
            "model_id": "gpt-4.1",
            "fallbacks": ["not-a-dict", 42, None],
        })
        assert ref is not None
        assert ref.fallbacks == ()

    def test_dict_ref_invalid_fallback_skipped_valid_kept(self):
        ref = parse_backend_ref({
            "provider": "openai",
            "model_id": "gpt-4.1",
            "fallbacks": [
                {"provider": "bad_entry_no_model"},          # invalid → skip
                {"provider": "openrouter", "model_id": "x/y"},  # valid → keep
            ],
        })
        assert ref is not None
        assert len(ref.fallbacks) == 1
        assert ref.fallbacks[0].model_id == "x/y"

    def test_routing_hints_non_dict_treated_as_empty(self):
        ref = parse_backend_ref({"provider": "openai", "model_id": "gpt-4.1", "routing_hints": "bad"})
        assert ref is not None
        assert ref.routing_hints == {}


# ── BackendRef dataclass ──────────────────────────────────────────────────────

class TestBackendRef:
    def test_immutable(self):
        ref = BackendRef(provider="openai", model_id="gpt-4.1")
        with pytest.raises((AttributeError, TypeError)):
            ref.provider = "changed"  # type: ignore[misc]

    def test_display_id_with_model(self):
        ref = BackendRef(provider="openrouter", model_id="openai/gpt-4o-mini")
        assert ref.display_id == "openrouter/openai/gpt-4o-mini"

    def test_display_id_with_tool(self):
        ref = BackendRef(provider="python", tool_id="pandas_profile")
        assert ref.display_id == "python/pandas_profile"

    def test_execution_id_prefers_model(self):
        ref = BackendRef(provider="openai", model_id="gpt-4.1", tool_id="some_tool")
        assert ref.execution_id == "gpt-4.1"

    def test_execution_id_tool_only(self):
        ref = BackendRef(provider="python", tool_id="pandas_profile")
        assert ref.execution_id == "pandas_profile"

    def test_fallbacks_defaults_to_empty_tuple(self):
        ref = BackendRef(provider="openai", model_id="gpt-4.1")
        assert ref.fallbacks == ()

    def test_routing_hints_defaults_to_empty_dict(self):
        ref = BackendRef(provider="openai", model_id="gpt-4.1")
        assert ref.routing_hints == {}


# ── Schemas ───────────────────────────────────────────────────────────────────

class TestFallbackModel:
    def test_valid_with_model_id(self):
        f = FallbackModel(provider="openai", model_id="gpt-4.1")
        assert f.provider == "openai"
        assert f.model_id == "gpt-4.1"

    def test_valid_with_tool_id(self):
        f = FallbackModel(provider="python", tool_id="pandas_profile")
        assert f.tool_id == "pandas_profile"

    def test_requires_model_or_tool(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            FallbackModel(provider="openai")

    def test_routing_hints_optional_defaults_empty(self):
        f = FallbackModel(provider="openai", model_id="gpt-4.1")
        assert f.routing_hints == {}

    def test_routing_hints_passthrough(self):
        f = FallbackModel(provider="openrouter", model_id="x/y", routing_hints={"sort": "price"})
        assert f.routing_hints == {"sort": "price"}


class TestBackendOverrideIn:
    def test_valid_minimal(self):
        b = BackendOverrideIn(provider="openai", model_id="gpt-4.1")
        assert b.fallbacks == []
        assert b.routing_hints == {}
        assert b.strict is True

    def test_requires_model_or_tool(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            BackendOverrideIn(provider="openai")

    def test_accepts_fallbacks(self):
        b = BackendOverrideIn(
            provider="openrouter",
            model_id="primary/model",
            fallbacks=[
                FallbackModel(provider="openrouter", model_id="fallback/model"),
            ],
        )
        assert len(b.fallbacks) == 1
        assert b.fallbacks[0].model_id == "fallback/model"

    def test_accepts_routing_hints(self):
        b = BackendOverrideIn(
            provider="openrouter",
            model_id="x/y",
            routing_hints={"sort": "throughput"},
        )
        assert b.routing_hints == {"sort": "throughput"}


class TestBackendOverrideOut:
    def test_serializes_fallbacks(self):
        out = BackendOverrideOut(
            target="workspace.council.seats.c1",
            provider="openrouter",
            model_id="primary/model",
            modality="text",
            strict=True,
            fallbacks=[FallbackModel(provider="openrouter", model_id="fallback/model")],
            routing_hints={"sort": "price"},
        )
        data = out.model_dump()
        assert data["fallbacks"][0]["model_id"] == "fallback/model"
        assert data["routing_hints"] == {"sort": "price"}

    def test_defaults_to_empty_fallbacks(self):
        out = BackendOverrideOut(
            target="cmo.main",
            provider="openai",
            model_id="gpt-4.1",
            modality="text",
            strict=True,
        )
        assert out.fallbacks == []
        assert out.routing_hints == {}


# ── _row_to_backendref ────────────────────────────────────────────────────────
# Replicated here as a pure function — the router module imports SQLAlchemy at
# module level so it can't be imported outside Docker; the conversion logic
# depends only on BackendRef and parse_backend_ref.

def _row_to_backendref(row) -> BackendRef:
    raw_fallbacks = row.fallbacks_json or []
    fallbacks = tuple(
        f for f in (parse_backend_ref(fb) for fb in raw_fallbacks if isinstance(fb, dict))
        if f is not None
    )
    routing_hints = row.routing_hints_json or {}
    if not isinstance(routing_hints, dict):
        routing_hints = {}
    return BackendRef(
        provider=row.provider,
        model_id=row.model_id,
        tool_id=row.tool_id,
        modality=row.modality,
        strict=row.strict,
        fallbacks=fallbacks,
        routing_hints=routing_hints,
    )


class TestRowToBackendRef:
    def _make_row(self, **kwargs):
        defaults = {
            "provider": "openrouter",
            "model_id": "openai/gpt-4o-mini",
            "tool_id": None,
            "modality": "text",
            "strict": True,
            "fallbacks_json": [],
            "routing_hints_json": {},
        }
        defaults.update(kwargs)
        return SimpleNamespace(**defaults)

    def test_basic_row(self):
        row = self._make_row()
        ref = _row_to_backendref(row)
        assert ref.provider == "openrouter"
        assert ref.model_id == "openai/gpt-4o-mini"
        assert ref.fallbacks == ()
        assert ref.routing_hints == {}

    def test_row_with_fallbacks(self):
        row = self._make_row(fallbacks_json=[
            {"provider": "openai", "model_id": "gpt-4.1"},
            {"provider": "gemini", "model_id": "gemini-2.5-pro"},
        ])
        ref = _row_to_backendref(row)
        assert len(ref.fallbacks) == 2
        assert ref.fallbacks[0].provider == "openai"
        assert ref.fallbacks[1].model_id == "gemini-2.5-pro"

    def test_row_with_routing_hints(self):
        row = self._make_row(routing_hints_json={"sort": "price", "allow_fallbacks": True})
        ref = _row_to_backendref(row)
        assert ref.routing_hints == {"sort": "price", "allow_fallbacks": True}

    def test_row_null_json_fields_safe(self):
        row = self._make_row(fallbacks_json=None, routing_hints_json=None)
        ref = _row_to_backendref(row)
        assert ref.fallbacks == ()
        assert ref.routing_hints == {}

    def test_row_strict_false(self):
        row = self._make_row(strict=False)
        ref = _row_to_backendref(row)
        assert ref.strict is False

    def test_row_tool_id(self):
        row = self._make_row(model_id=None, tool_id="pandas_profile", provider="python")
        ref = _row_to_backendref(row)
        assert ref.tool_id == "pandas_profile"
        assert ref.model_id is None

    def test_row_invalid_fallback_entry_skipped(self):
        row = self._make_row(fallbacks_json=[
            {"provider": "openai"},          # missing model_id — invalid
            {"provider": "openai", "model_id": "gpt-4.1"},  # valid
        ])
        ref = _row_to_backendref(row)
        assert len(ref.fallbacks) == 1
        assert ref.fallbacks[0].model_id == "gpt-4.1"

    def test_row_fallback_preserves_nested_routing_hints(self):
        row = self._make_row(fallbacks_json=[
            {"provider": "openrouter", "model_id": "x/y", "routing_hints": {"sort": "throughput"}},
        ])
        ref = _row_to_backendref(row)
        assert ref.fallbacks[0].routing_hints == {"sort": "throughput"}


# ── get_plugin_default_backend ────────────────────────────────────────────────

class TestGetPluginDefaultBackend:
    def test_plugin_with_default_backend_returns_backendref(self):
        import plugin_loader as pl

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plugin_dir = root / "test_default_backend"
            plugin_dir.mkdir()
            (plugin_dir / "channel.json").write_text(json.dumps({
                "plugin_id": "media.test_image",
                "name": "Test Image",
                "version": "1.0.0",
                "klaroha_min_version": "3.4",
                "capability_ids": ["media.test_image.generate"],
                "default_backend": {
                    "provider": "openrouter",
                    "model_id": "openai/gpt-image-1",
                    "strict": False,
                },
            }))
            cap_dir = plugin_dir / "capabilities" / "media" / "test_image" / "generate"
            cap_dir.mkdir(parents=True)
            (cap_dir / "SKILL.md").write_text(
                "module_id: media.test_image.generate\nallowed_from_chat: false\n"
            )

            old_loaded = dict(pl._loaded)
            old_map = dict(pl._module_to_plugin)
            try:
                states = pl._scan_root(root, source="external")
                for s in states:
                    pl._loaded[s.manifest.plugin_id] = s
                    for cap_id in s.manifest.capability_ids:
                        pl._module_to_plugin[cap_id] = s.manifest.plugin_id

                ref = pl.get_plugin_default_backend("media.test_image.generate")
                assert ref is not None
                assert ref.provider == "openrouter"
                assert ref.model_id == "openai/gpt-image-1"
                assert ref.strict is False
            finally:
                pl._loaded.clear()
                pl._loaded.update(old_loaded)
                pl._module_to_plugin.clear()
                pl._module_to_plugin.update(old_map)

    def test_plugin_without_default_backend_returns_none(self):
        import plugin_loader as pl

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plugin_dir = root / "no_default_backend"
            plugin_dir.mkdir()
            (plugin_dir / "channel.json").write_text(json.dumps({
                "plugin_id": "media.no_default",
                "name": "No Default",
                "version": "1.0.0",
                "klaroha_min_version": "3.4",
                "capability_ids": ["media.no_default.generate"],
            }))

            old_loaded = dict(pl._loaded)
            old_map = dict(pl._module_to_plugin)
            try:
                states = pl._scan_root(root, source="external")
                for s in states:
                    pl._loaded[s.manifest.plugin_id] = s
                    for cap_id in s.manifest.capability_ids:
                        pl._module_to_plugin[cap_id] = s.manifest.plugin_id

                assert pl.get_plugin_default_backend("media.no_default.generate") is None
            finally:
                pl._loaded.clear()
                pl._loaded.update(old_loaded)
                pl._module_to_plugin.clear()
                pl._module_to_plugin.update(old_map)

    def test_unknown_module_returns_none(self):
        import plugin_loader as pl
        assert pl.get_plugin_default_backend("nonexistent.module.id") is None


# ── OR-native queue construction logic ───────────────────────────────────────

class TestORNativeQueueConstruction:
    """
    Tests the all_or condition and candidate construction logic that lives in runs.py.
    We replicate the logic here as a pure function to make it unit-testable.
    """

    def _build_candidates(self, override: BackendRef, original_candidates: list) -> list:
        """Mirrors the queue construction block in runs.py execute_run()."""
        from model_overrides import effective_strict

        class _FakeSettings:
            strict_model_overrides = True

        override_is_strict = effective_strict(_FakeSettings(), override)

        def _override_candidate(ref) -> dict:
            c: dict = {"provider": ref.provider, "model_id": ref.model_id}
            if ref.routing_hints:
                c["extra_body"] = {"_routing_hints": dict(ref.routing_hints)}
            return c

        all_or = (
            override.provider == "openrouter"
            and bool(override.fallbacks)
            and all(f.provider == "openrouter" for f in override.fallbacks)
        )
        if all_or:
            model_ids = [override.model_id] + [f.model_id for f in override.fallbacks if f.model_id]
            extra: dict = {"models": model_ids}
            if override.routing_hints:
                extra["_routing_hints"] = dict(override.routing_hints)
            return [{"provider": "openrouter", "model_id": model_ids[0], "extra_body": extra}]
        else:
            explicit_queue = [_override_candidate(override)] + [_override_candidate(f) for f in override.fallbacks]
            return explicit_queue if override_is_strict else explicit_queue + original_candidates

    def test_all_or_fallbacks_produces_single_candidate_with_models_array(self):
        override = parse_backend_ref({
            "provider": "openrouter",
            "model_id": "anthropic/claude-opus-4-8",
            "fallbacks": [
                {"provider": "openrouter", "model_id": "anthropic/claude-sonnet-4-6"},
                {"provider": "openrouter", "model_id": "openai/gpt-4o-mini"},
            ],
        })
        candidates = self._build_candidates(override, [])
        assert len(candidates) == 1
        assert candidates[0]["provider"] == "openrouter"
        assert candidates[0]["model_id"] == "anthropic/claude-opus-4-8"
        assert candidates[0]["extra_body"]["models"] == [
            "anthropic/claude-opus-4-8",
            "anthropic/claude-sonnet-4-6",
            "openai/gpt-4o-mini",
        ]

    def test_all_or_includes_routing_hints(self):
        override = parse_backend_ref({
            "provider": "openrouter",
            "model_id": "anthropic/claude-opus-4-8",
            "routing_hints": {"sort": "price"},
            "fallbacks": [
                {"provider": "openrouter", "model_id": "anthropic/claude-sonnet-4-6"},
            ],
        })
        candidates = self._build_candidates(override, [])
        assert "_routing_hints" in candidates[0]["extra_body"]
        assert candidates[0]["extra_body"]["_routing_hints"] == {"sort": "price"}

    def test_mixed_providers_not_or_native(self):
        override = parse_backend_ref({
            "provider": "openrouter",
            "model_id": "anthropic/claude-opus-4-8",
            "fallbacks": [
                {"provider": "openai", "model_id": "gpt-4.1"},  # non-OR fallback
            ],
        })
        candidates = self._build_candidates(override, [])
        # Not OR-native → explicit queue, each candidate separate
        assert len(candidates) == 2
        assert candidates[0]["provider"] == "openrouter"
        assert candidates[1]["provider"] == "openai"
        assert "models" not in candidates[0].get("extra_body", {})

    def test_no_fallbacks_not_or_native(self):
        override = parse_backend_ref({
            "provider": "openrouter",
            "model_id": "anthropic/claude-opus-4-8",
            # no fallbacks
        })
        candidates = self._build_candidates(override, [])
        assert len(candidates) == 1
        assert candidates[0]["provider"] == "openrouter"
        assert "models" not in candidates[0].get("extra_body", {})

    def test_non_or_primary_not_or_native_even_if_fallbacks_are_or(self):
        override = parse_backend_ref({
            "provider": "openai",
            "model_id": "gpt-4.1",
            "fallbacks": [
                {"provider": "openrouter", "model_id": "anthropic/claude-sonnet-4-6"},
            ],
        })
        candidates = self._build_candidates(override, [])
        assert len(candidates) == 2
        assert candidates[0]["provider"] == "openai"
        assert candidates[1]["provider"] == "openrouter"

    def test_strict_true_drops_catalog_candidates(self):
        override = BackendRef(provider="openai", model_id="gpt-4.1", strict=True)
        catalog = [{"provider": "openrouter", "model_id": "catalog-model"}]
        candidates = self._build_candidates(override, catalog)
        assert all(c["provider"] == "openai" for c in candidates)
        assert len(candidates) == 1

    def test_strict_false_appends_catalog_candidates(self):
        override = BackendRef(provider="openai", model_id="gpt-4.1", strict=False)
        catalog = [{"provider": "openrouter", "model_id": "catalog-model"}]
        candidates = self._build_candidates(override, catalog)
        assert candidates[0]["provider"] == "openai"
        assert candidates[-1]["model_id"] == "catalog-model"

    def test_override_candidate_with_routing_hints_sets_extra_body(self):
        override = BackendRef(
            provider="openrouter",
            model_id="openai/gpt-4o-mini",
            routing_hints={"sort": "throughput"},
        )
        candidates = self._build_candidates(override, [])
        assert candidates[0]["extra_body"] == {"_routing_hints": {"sort": "throughput"}}

    def test_override_candidate_without_routing_hints_no_extra_body(self):
        override = BackendRef(provider="openai", model_id="gpt-4.1")
        candidates = self._build_candidates(override, [])
        assert "extra_body" not in candidates[0]


# ── ProviderResponse.actual_model ─────────────────────────────────────────────

class TestProviderResponseActualModel:
    def test_actual_model_defaults_to_none(self):
        from providers.base import ProviderResponse
        r = ProviderResponse(content="hi", tokens_input=10, tokens_output=5, latency_ms=100)
        assert r.actual_model is None

    def test_actual_model_can_be_set(self):
        from providers.base import ProviderResponse
        r = ProviderResponse(
            content="hi", tokens_input=10, tokens_output=5, latency_ms=100,
            actual_model="anthropic/claude-sonnet-4-6",
        )
        assert r.actual_model == "anthropic/claude-sonnet-4-6"


# ── OpenRouter routing_hints → provider field ─────────────────────────────────

class TestOpenRouterRoutingHintsMapping:
    def test_build_provider_field_sort(self):
        from providers.openrouter import _build_provider_field
        result = _build_provider_field({"sort": "price"})
        assert result == {"sort": "price"}

    def test_build_provider_field_allow_fallbacks(self):
        from providers.openrouter import _build_provider_field
        result = _build_provider_field({"allow_fallbacks": False})
        assert result == {"allowFallbacks": False}

    def test_build_provider_field_data_collection(self):
        from providers.openrouter import _build_provider_field
        result = _build_provider_field({"data_collection": "deny"})
        assert result == {"dataCollection": "deny"}

    def test_build_provider_field_order(self):
        from providers.openrouter import _build_provider_field
        result = _build_provider_field({"order": ["Anthropic", "OpenAI"]})
        assert result == {"order": ["Anthropic", "OpenAI"]}

    def test_build_provider_field_unknown_keys_ignored(self):
        from providers.openrouter import _build_provider_field
        result = _build_provider_field({"sort": "price", "unknown_key": "whatever"})
        assert "unknown_key" not in result
        assert result == {"sort": "price"}

    def test_build_provider_field_empty(self):
        from providers.openrouter import _build_provider_field
        assert _build_provider_field({}) == {}
