"""Helpers for operator-configured execution backend selection.

Simple model refs use `provider:model_id` so provider names stay unambiguous
even when model IDs contain slashes, e.g. `openrouter:openai/gpt-4o-mini`.

The newer EXECUTION_BACKEND_OVERRIDES format supports modality-aware backends:
{
  "cmo.main": {"provider": "openai", "model_id": "gpt-5.1", "modality": "text"},
  "marketing.creative.image.generate": {"provider": "openai", "model_id": "gpt-image-1", "modality": "image"},
  "marketing.analytics.summary": {"provider": "python", "tool_id": "pandas_profile", "modality": "data_analysis"}
}
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("bos.model_overrides")


@dataclass(frozen=True)
class BackendRef:
    provider: str
    model_id: str | None = None
    modality: str = "text"
    tool_id: str | None = None
    strict: bool | None = None
    fallbacks: tuple["BackendRef", ...] = field(default_factory=tuple)
    routing_hints: dict = field(default_factory=dict)

    @property
    def execution_id(self) -> str | None:
        return self.model_id or self.tool_id

    @property
    def display_id(self) -> str:
        target = self.model_id or self.tool_id or "unknown"
        return f"{self.provider}/{target}"


# Backward-compatible alias used by older text-only call sites/tests.
ModelRef = BackendRef


def _parse_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y"}:
            return True
        if lowered in {"false", "0", "no", "n"}:
            return False
    return None


def parse_backend_ref(value: str | dict[str, Any] | None) -> BackendRef | None:
    if value is None:
        return None

    if isinstance(value, dict):
        provider = str(value.get("provider") or "").strip()
        model_id = str(value.get("model_id") or value.get("model") or "").strip() or None
        tool_id = str(value.get("tool_id") or value.get("tool") or "").strip() or None
        modality = str(value.get("modality") or "text").strip() or "text"
        strict = _parse_bool(value.get("strict"))
        routing_hints = value.get("routing_hints") or {}
        if not isinstance(routing_hints, dict):
            routing_hints = {}
        raw_fallbacks = value.get("fallbacks") or []
        fallbacks: tuple[BackendRef, ...] = tuple(
            f for f in (parse_backend_ref(fb) for fb in raw_fallbacks if isinstance(fb, dict))
            if f is not None
        )
        if provider and (model_id or tool_id):
            return BackendRef(
                provider=provider, model_id=model_id, modality=modality, tool_id=tool_id,
                strict=strict, fallbacks=fallbacks, routing_hints=routing_hints,
            )
        return None

    raw = str(value).strip()
    if not raw:
        return None
    if ":" not in raw:
        logger.warning("Invalid backend ref '%s'; expected provider:model_id", raw)
        return None
    provider, model_id = raw.split(":", 1)
    provider = provider.strip()
    model_id = model_id.strip()
    if not provider or not model_id:
        logger.warning("Invalid backend ref '%s'; expected provider:model_id", raw)
        return None
    return BackendRef(provider=provider, model_id=model_id, modality="text")


def parse_model_ref(value: str | dict[str, Any] | None) -> BackendRef | None:
    """Backward-compatible text model parser."""
    return parse_backend_ref(value)


def parse_backend_overrides(value: str | None) -> dict[str, BackendRef]:
    raw = (value or "").strip()
    if not raw:
        return {}

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("Invalid execution backend override JSON: %s", exc)
        return {}

    if not isinstance(data, dict):
        logger.warning("Execution backend overrides must be a JSON object")
        return {}

    overrides: dict[str, BackendRef] = {}
    for target, ref_value in data.items():
        ref = parse_backend_ref(ref_value)
        if ref:
            overrides[str(target)] = ref
        else:
            logger.warning("Skipping invalid backend override for target '%s'", target)
    return overrides


def parse_module_model_overrides(value: str | None) -> dict[str, BackendRef]:
    """Backward-compatible parser for MODULE_MODEL_OVERRIDES."""
    return parse_backend_overrides(value)


def get_backend_override(settings, target: str) -> BackendRef | None:
    return parse_backend_overrides(getattr(settings, "execution_backend_overrides", "")).get(target)


def get_module_model_override(settings, module_id: str) -> BackendRef | None:
    # New modality-aware overrides take precedence over old text-only module overrides.
    return (
        get_backend_override(settings, module_id)
        or parse_module_model_overrides(getattr(settings, "module_model_overrides", "")).get(module_id)
    )


def effective_strict(settings, override: BackendRef) -> bool:
    return override.strict if override.strict is not None else bool(getattr(settings, "strict_model_overrides", True))


def reorder_candidates_for_model_override(
    candidates: list[dict],
    override: BackendRef,
    *,
    strict: bool = True,
) -> list[dict]:
    """Move or filter the configured text model to the front of candidate routing.

    In strict mode, only the exact provider/model candidate is returned. In
    non-strict mode, the configured model is tried first and normal waterfall
    candidates remain as fallback.
    """
    if not override.model_id:
        return [] if strict else candidates

    matches = [
        candidate
        for candidate in candidates
        if candidate.get("provider") == override.provider and candidate.get("model_id") == override.model_id
    ]
    if not matches:
        return [] if strict else candidates

    if strict:
        return matches

    rest = [
        candidate
        for candidate in candidates
        if not (candidate.get("provider") == override.provider and candidate.get("model_id") == override.model_id)
    ]
    return matches + rest
