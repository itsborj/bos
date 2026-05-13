"""Capability manifest — structured catalog of all CMO-dispatchable capabilities.

The CMO reads this at system prompt build time to know exactly what it can deploy.
No platform-specific logic lives here — every entry is derived directly from SKILL.md.
"""
from __future__ import annotations

from dataclasses import dataclass

from skills.loader import list_skill_manifests


@dataclass(frozen=True)
class CapabilityEntry:
    module_id: str
    label: str
    description: str
    run_directive: str  # the exact line the LLM should output to invoke this
    requires_intent: tuple[str, ...]
    triggers: tuple[str, ...]
    excluded_triggers: tuple[str, ...]


def build_dispatchable_manifest() -> list[CapabilityEntry]:
    """Return all capabilities the CMO LLM is allowed to deploy, ordered by module_id."""
    entries: list[CapabilityEntry] = []
    for skill in sorted(list_skill_manifests(), key=lambda s: s.module_id or ""):
        if not skill.allowed_from_chat or not skill.module_id:
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


def format_manifest_for_prompt() -> str:
    """Format the dispatchable capability list for injection into the CMO system prompt."""
    entries = build_dispatchable_manifest()
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
