"""Capability manifest — structured catalog of all CMO-dispatchable capabilities.

The CMO reads this at system prompt build time to know exactly what it can deploy.
No platform-specific logic lives here — every entry is derived directly from SKILL.md.

Plugin capabilities are filtered by per-brand activation state (D5).
First-party capabilities (not owned by any plugin) are always included.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from skills.loader import list_skill_manifests


def _ensure_plugins_registered() -> None:
    """Trigger registry scan so plugin SKILL.md roots are registered before manifest is built."""
    from registry import _ensure
    _ensure()


@dataclass(frozen=True)
class CapabilityEntry:
    module_id: str
    label: str
    description: str
    run_directive: str  # the exact line the LLM should output to invoke this
    requires_intent: tuple[str, ...]
    triggers: tuple[str, ...]
    excluded_triggers: tuple[str, ...]


def build_dispatchable_manifest(
    active_plugin_ids: Optional[set[str]] = None,
) -> list[CapabilityEntry]:
    """Return all capabilities the CMO LLM is allowed to deploy, ordered by module_id.

    active_plugin_ids: when provided, plugin-owned capabilities are filtered to
    active plugins only. None means no filter (all capabilities included).
    First-party capabilities (not in any plugin) are always included.
    """
    _ensure_plugins_registered()
    from plugin_loader import _module_to_plugin

    entries: list[CapabilityEntry] = []
    for skill in sorted(list_skill_manifests(), key=lambda s: s.module_id or ""):
        if not skill.allowed_from_chat or not skill.module_id:
            continue

        # Filter plugin-owned capabilities by activation state
        if active_plugin_ids is not None:
            owner_plugin_id = _module_to_plugin.get(skill.module_id)
            if owner_plugin_id is not None and owner_plugin_id not in active_plugin_ids:
                continue

        label = (skill.name or skill.module_id.rsplit(".", 1)[-1]).replace("_", " ").title()
        desc = (skill.description or "").strip()
        entries.append(CapabilityEntry(
            module_id=skill.module_id,
            label=label,
            description=desc,
            run_directive=f"RUN: {skill.module_id}",
            requires_intent=tuple(skill.requires_intent),
            triggers=tuple(skill.triggers),
            excluded_triggers=tuple(skill.excluded_triggers),
        ))
    return entries


def _format_entries(entries: list[CapabilityEntry]) -> str:
    if not entries:
        return "  (no capabilities installed)"
    lines = []
    for e in entries:
        line = f"  {e.run_directive}  [{e.label}]"
        if e.description:
            line += f" — {e.description}"
        if e.requires_intent:
            line += f" Requires intent: {', '.join(e.requires_intent)}."
        if e.triggers:
            line += f" Use only for: {', '.join(e.triggers[:8])}."
        if e.excluded_triggers:
            line += f" Do not use for: {', '.join(e.excluded_triggers[:8])}."
        lines.append(line)
    return "\n".join(lines)


def format_manifest_for_prompt() -> str:
    """Format the dispatchable capability list without brand filtering.

    Used by non-brand contexts (label lookups, fallback). Prefer
    format_manifest_for_brand() inside async request handlers.
    """
    return _format_entries(build_dispatchable_manifest())


async def format_manifest_for_brand(db, brand_id=None) -> str:
    """Format the dispatchable capability list filtered by brand activation state.

    Plugin capabilities are included only when the plugin is active for brand_id
    (or at org-level). First-party capabilities are always included.
    """
    from plugin_loader import get_active_plugin_ids
    active_ids = await get_active_plugin_ids(db, brand_id)
    entries = build_dispatchable_manifest(active_plugin_ids=active_ids)
    return _format_entries(entries)
