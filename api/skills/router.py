from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from skills.loader import SkillManifest, list_skill_manifests

_GENERATION_RE = re.compile(r"\b(generate|create|write|draft|make|produce|show me|let me see|get me|give me|build|need|i need|sample|samples|copy)\b", re.IGNORECASE)
_REVISION_RE = re.compile(r"\b(revise|redo|modify|update|change|improve|shorten|lengthen|rewrite|again|more|less)\b", re.IGNORECASE)
_APPROVAL_RE = re.compile(r"\b(approve|approved|reject|rejected)\b", re.IGNORECASE)
_DIAGNOSTIC_RE = re.compile(r"\b(audit|review|diagnose|check|look up|pull|fetch|health check|issue|issues|not ranking|traffic dropped|lost rankings|tracking setup|analytics setup|ga4 setup|performance|report|doing|spend|conversions|cpa|ctr|analytics|summary|campaign related|campaign updates?)\b", re.IGNORECASE)
_DISCUSSION_RE = re.compile(
    r"\b(what is|what are|explain|tell me|what do you know|current project|about|brand|business|audience|offer|positioning)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SkillRoute:
    skill: SkillManifest
    matched_triggers: tuple[str, ...]


@dataclass(frozen=True)
class RoutedSkills:
    intents: tuple[str, ...]
    routes: tuple[SkillRoute, ...]

    @property
    def module_ids(self) -> tuple[str, ...]:
        return tuple(route.skill.module_id for route in self.routes if route.skill.module_id)


def classify_chat_intents(message: str) -> tuple[str, ...]:
    intents: list[str] = []
    if _GENERATION_RE.search(message):
        intents.append("generation")
    if _REVISION_RE.search(message):
        intents.append("revision")
    if _APPROVAL_RE.search(message):
        intents.append("approval")
    if _DIAGNOSTIC_RE.search(message):
        intents.append("diagnostic")
    if _DISCUSSION_RE.search(message) or not intents:
        intents.append("discussion")
    return tuple(dict.fromkeys(intents))


def _trigger_matches(message: str, trigger: str) -> bool:
    trigger = trigger.strip().lower()
    if not trigger:
        return False
    pattern = r"(?<![a-z0-9])" + re.escape(trigger) + r"(?![a-z0-9])"
    return bool(re.search(pattern, message.lower()))


def route_chat_skills(message: str, manifests: Optional[tuple[SkillManifest, ...]] = None) -> RoutedSkills:
    """Route a CMO chat turn to skill contracts using frontmatter only."""
    intents = classify_chat_intents(message)
    available = manifests or list_skill_manifests()
    routes: list[SkillRoute] = []

    for skill in available:
        if not skill.allowed_from_chat:
            continue

        required = set(skill.requires_intent)
        if required and not required.intersection(intents):
            continue

        if any(_trigger_matches(message, excluded) for excluded in skill.excluded_triggers):
            continue

        matches = tuple(t for t in skill.triggers if _trigger_matches(message, t))

        if skill.id == "workspace.cmo_context" and "discussion" in intents and (matches or not routes):
            routes.append(SkillRoute(skill=skill, matched_triggers=matches))
            continue

        if skill.module_id and matches:
            required_intents = set(skill.requires_intent)
            if required_intents:
                if not required_intents.intersection(intents):
                    continue
            else:
                if intents == ("discussion",) and not {"generation", "revision", "diagnostic"}.intersection(intents):
                    if not re.search(r"\b(send|submit|check|read|receive|any replies|did anyone)\b", message, re.IGNORECASE):
                        continue
            routes.append(SkillRoute(skill=skill, matched_triggers=matches))
            continue

        if skill.id == "workspace.approval_review" and matches and ({"approval", "revision"}.intersection(intents)):
            routes.append(SkillRoute(skill=skill, matched_triggers=matches))
            continue

        if not skill.module_id and skill.id not in {"workspace.cmo_context", "workspace.approval_review"} and matches:
            if not required or required.intersection(intents):
                routes.append(SkillRoute(skill=skill, matched_triggers=matches))

    if routes and any(route.skill.id != "workspace.cmo_context" for route in routes):
        context = next((s for s in available if s.id == "workspace.cmo_context" and s.allowed_from_chat), None)
        if context and all(route.skill.id != context.id for route in routes):
            routes.insert(0, SkillRoute(skill=context, matched_triggers=()))

    return RoutedSkills(intents=intents, routes=tuple(routes))
