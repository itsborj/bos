from __future__ import annotations

import os
from abc import ABC
from typing import ClassVar, Dict, List, Optional, Tuple

from jinja2 import Environment, FileSystemLoader

_templates_env: Optional[Environment] = None
_extra_template_roots: list[str] = []


def register_template_root(root: str) -> None:
    """Register an additional Jinja2 template search root (called by plugin_loader)."""
    global _templates_env
    if root not in _extra_template_roots:
        _extra_template_roots.append(root)
        _templates_env = None  # force rebuild on next _get_env() call


def _get_env() -> Environment:
    global _templates_env
    if _templates_env is None:
        roots = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "capabilities")]
        roots.extend(_extra_template_roots)
        _templates_env = Environment(loader=FileSystemLoader(roots), autoescape=False)
    return _templates_env


class ModuleBase(ABC):
    id: ClassVar[str]
    legacy_ids: ClassVar[List[str]] = []
    vertical: ClassVar[str]
    capability: ClassVar[str]
    platform_hint: ClassVar[str]
    policy_default: ClassVar[str] = "balanced"
    template: ClassVar[str]
    name: ClassVar[Optional[str]] = None
    internal: ClassVar[bool] = False
    copywriting_skills: ClassVar[List[str]] = []

    # Declared actions — one tool per module, typed parameters.
    # None = fall back to opaque brief:string (backward compatible).
    # Dict = {action_name: {description, parameters, required, produces, consumes}}
    # build_tools() reads this to build typed tool schemas.
    # execute_tool_result receives the merged dict — module dispatches internally.
    actions: ClassVar[dict | None] = None

    max_chars: ClassVar[int] = 0
    must_mention: ClassVar[List[str]] = []
    banned_phrases: ClassVar[List[str]] = []

    def build_prompt(self, brief: dict) -> str:
        context = dict(brief)
        context["copywriting_guidance"] = self._copywriting_guidance()
        context["copywriting_skill_ids"] = list(self.copywriting_skills)
        return _get_env().get_template(self.template).render(**context)

    def _copywriting_guidance(self) -> str:
        """Return prompt guidance from reusable copywriting skill modules."""
        sections: List[str] = []
        for skill_id in self.copywriting_skills:
            try:
                from registry import get_module

                skill_cls = get_module(skill_id)
                if not skill_cls:
                    sections.append(f"### {skill_id}\n[Skill module not found]")
                    continue
                skill = skill_cls()
                as_prompt_section = getattr(skill, "as_prompt_section", None)
                if callable(as_prompt_section):
                    sections.append(as_prompt_section())
                elif hasattr(skill, "prompt_guidance"):
                    sections.append(str(getattr(skill, "prompt_guidance")))
            except Exception as exc:
                sections.append(f"### {skill_id}\n[Skill guidance unavailable: {exc}]")
        return "\n\n".join(s for s in sections if s.strip())

    def self_check(self, content: str, brief: dict) -> Tuple[str, List[str]]:
        failures: List[str] = []
        if self.max_chars and len(content) > self.max_chars:
            failures.append(f"exceeds_max_chars:{len(content)}>{self.max_chars}")
        for field in self.must_mention:
            val = str(brief.get(field, field))
            if val and val.lower() not in content.lower():
                failures.append(f"must_mention_missing:{val}")
        for phrase in self.banned_phrases:
            if phrase.lower() in content.lower():
                failures.append(f"banned_phrase_found:{phrase}")
        return ("fail" if failures else "pass"), failures

    def module_info(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name or self.id.rsplit(".", 1)[-1],
            "vertical": self.vertical,
            "capability": self.capability,
            "platform_hint": self.platform_hint,
            "policy_default": self.policy_default,
            "internal": self.internal,
            "copywriting_skills": list(self.copywriting_skills),
            # Host-routed LLM modules use build_prompt() + provider routing in runs.py.
            # Deterministic/API tool modules implement execute_tool_result() and should
            # not appear in exact LLM/model assignment controls.
            "uses_llm": not callable(getattr(self, "execute_tool_result", None)),
            "constraints": {
                "max_chars": self.max_chars,
                "must_mention": self.must_mention,
                "banned_phrases": self.banned_phrases,
            },
        }
