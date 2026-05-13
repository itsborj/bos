from __future__ import annotations

import re
from module_base import ModuleBase


class MarketingCampaignStrategyPlanModule(ModuleBase):
    id = "marketing.plan.campaign_strategy"
    name = "Marketing Campaign Strategy Plan"
    vertical = "marketing"
    capability = "marketing.copywriting"
    platform_hint = "planning"
    policy_default = "balanced"
    template = "marketing/plan/campaign_strategy/template.j2"

    max_chars = 6000
    banned_phrases = ["guaranteed results", "set it and forget it", "blast everyone"]

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        failures: list[str] = []
        lower = content.lower()
        required = [
            "campaign theme",
            "mission",
            "focus",
            "recommended channels",
            "not recommended yet",
            "missing inputs",
            "next artifacts",
            "approval note",
        ]
        for section in required:
            if section not in lower:
                failures.append(f"missing_section:{section}")
        if len(content) > self.max_chars:
            failures.append(f"exceeds_max_chars:{len(content)}>{self.max_chars}")
        for phrase in self.banned_phrases:
            if phrase in lower:
                failures.append(f"banned_phrase_found:{phrase}")
        if "run:" in lower or "module_id" in lower:
            failures.append("visible_internal_control_marker")
        if "approval" not in lower:
            failures.append("missing_approval_boundary")

        context_text = self._brief_context_text(brief)
        if re.search(r"\b\d+(?:\.\d+)?\s*%", content) and not re.search(r"\b\d+(?:\.\d+)?\s*%", context_text):
            failures.append("invented_percentage_target")
        recommended_lower = self._section_text(content, "Recommended channels").lower()
        for unsupported in ("influencer", "linkedin", "x/twitter", "twitter"):
            if unsupported in recommended_lower and unsupported not in context_text.lower():
                failures.append(f"unsupported_recommended_channel_without_context:{unsupported}")
        if (
            (brief.get("brand_guidelines_excerpt") or brief.get("campaign_brand_kit_excerpt"))
            and "brand guidelines" in lower
            and "missing inputs" in lower
        ):
            missing = self._section_text(content, "Missing inputs").lower()
            if "brand guidelines" in missing:
                failures.append("incorrectly_marks_brand_guidelines_missing")

        block = self._build_block(content)
        if len(block.get("focus", [])) < 2:
            failures.append("insufficient_focus_items")
        if not block.get("recommended_channels"):
            failures.append("missing_recommended_channel_items")
        return ("fail" if failures else "pass"), failures

    @staticmethod
    def _brief_context_text(brief: dict) -> str:
        parts: list[str] = []
        for value in brief.values():
            if isinstance(value, str):
                parts.append(value)
            elif isinstance(value, list):
                parts.extend(str(v) for v in value)
            elif isinstance(value, dict):
                parts.extend(str(v) for v in value.values())
        return "\n".join(parts)

    def _build_block(self, content: str) -> dict:
        title = self._heading(content, 1) or "Marketing Plan"
        return {
            "type": "marketing_plan",
            "artifact_type": "plan_artifact",
            "title": title,
            "status": "pending_review",
            "campaign_theme": self._section_text(content, "Campaign theme"),
            "mission": self._section_text(content, "Mission"),
            "focus": self._numbered_items(self._section_text(content, "Focus")),
            "recommended_channels": self._channel_items(self._section_text(content, "Recommended channels")),
            "not_recommended_yet": self._reason_items(self._section_text(content, "Not recommended yet")),
            "missing_inputs": self._dash_items(self._section_text(content, "Missing inputs")),
            "next_artifacts": self._reason_items(self._section_text(content, "Next artifacts")),
            "approval_note": self._section_text(content, "Approval note"),
            "allowed_actions": ["approve", "revise", "dismiss"],
            "changed_resources": [],
            "risk_level": "draft_only",
        }

    @staticmethod
    def _heading(content: str, level: int) -> str | None:
        prefix = "#" * level
        m = re.search(rf"^\s*{re.escape(prefix)}\s+(.+?)\s*$", content, re.MULTILINE)
        return m.group(1).strip() if m else None

    @staticmethod
    def _section_text(content: str, heading: str) -> str:
        pattern = rf"^##\s+{re.escape(heading)}\s*$([\s\S]*?)(?=^##\s+|\Z)"
        m = re.search(pattern, content, re.MULTILINE | re.IGNORECASE)
        if not m:
            return ""
        return m.group(1).strip()

    @staticmethod
    def _dash_items(text: str) -> list[str]:
        items: list[str] = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            line = re.sub(r"^(?:[-*•]|\d+[.)])\s*", "", line).strip()
            if line:
                items.append(line)
        return items

    @classmethod
    def _numbered_items(cls, text: str) -> list[str]:
        return cls._dash_items(text)

    @classmethod
    def _reason_items(cls, text: str) -> list[dict]:
        rows: list[dict] = []
        for item in cls._dash_items(text):
            parts = [p.strip() for p in re.split(r"\s+[—-]\s+", item, maxsplit=1)]
            if len(parts) == 2:
                rows.append({"name": parts[0], "reason": parts[1]})
            else:
                rows.append({"name": item, "reason": ""})
        return rows

    @classmethod
    def _channel_items(cls, text: str) -> list[dict]:
        rows: list[dict] = []
        for item in cls._dash_items(text):
            parts = [p.strip() for p in re.split(r"\s+[—-]\s+", item)]
            if len(parts) >= 4:
                rows.append({
                    "channel": parts[0],
                    "status": parts[1].lower(),
                    "role": parts[2],
                    "reason": " — ".join(parts[3:]),
                })
            elif len(parts) >= 2:
                rows.append({
                    "channel": parts[0],
                    "status": "active",
                    "role": parts[1],
                    "reason": " — ".join(parts[2:]) if len(parts) > 2 else "",
                })
            else:
                rows.append({"channel": item, "status": "active", "role": "", "reason": ""})
        return rows
