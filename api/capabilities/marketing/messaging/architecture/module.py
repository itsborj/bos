from __future__ import annotations

import re
from typing import Any

from module_base import ModuleBase


class MessagingArchitectureModule(ModuleBase):
    id = "marketing.messaging.architecture"
    name = "Message Architecture"
    vertical = "marketing"
    capability = "marketing.copywriting"
    platform_hint = "strategy"
    policy_default = "balanced"
    template = "marketing/messaging/architecture/template.j2"

    max_chars = 18000
    banned_phrases = ["guaranteed results", "set it and forget it"]

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        failures: list[str] = []
        lower = content.lower()
        required = [
            "message architecture",
            "awareness level target",
            "dominant blocking force",
            "lead message strategy",
            "core message",
            "positioning frame",
            "proof arc",
            "objection responses",
            "proof points",
            "ctas",
            "message don't list",
            "critical assumptions",
            "priority calibration",
        ]
        for section in required:
            if section not in lower:
                failures.append(f"missing_section:{section}")
        if "buyer map consumed" not in lower and "buyer-map signals consumed" not in lower:
            failures.append("missing_section:buyer map consumed")
        if not (brief.get("buyer_map") or brief.get("buyer_map_v1")):
            failures.append("missing_buyer_map_input")
        if re.search(r"\b\d+(?:\.\d+)?\s*%", content):
            failures.append("unsupported_numeric_claim")
        if len(content) > self.max_chars:
            failures.append(f"exceeds_max_chars:{len(content)}>{self.max_chars}")
        for phrase in self.banned_phrases:
            if phrase in lower:
                failures.append(f"banned_phrase_found:{phrase}")
        return ("fail" if failures else "pass"), failures

    def _build_block(self, content: str) -> dict[str, Any]:
        return {
            "type": "message_architecture",
            "artifact_type": "intelligence_artifact",
            "output_contract": "message_architecture.v1",
            "contract": "message_architecture.v1",
            "title": self._heading(content, 1) or "Message Architecture",
            "status": "supporting",
            "summary": self._section_text(content, "Buyer map consumed")[:800] or "Message architecture substrate generated for downstream strategy.",
            "awareness_level_target": self._field_after_label(content, "Awareness level target"),
            "dominant_blocking_force": self._field_after_label(content, "Dominant blocking force"),
            "lead_message_strategy": self._field_after_label(content, "Lead message strategy"),
            "core_message": self._section_text(content, "Core message"),
            "positioning_frame": self._section_text(content, "Positioning frame"),
            "message_dont_list": self._dash_items(self._section_text(content, "Message don't list")),
            "critical_assumptions": self._dash_items(self._section_text(content, "Critical assumptions")),
            "allowed_actions": ["review", "revise", "dismiss"],
            "changed_resources": [],
            "risk_level": "no_external_action",
        }

    @staticmethod
    def _heading(content: str, level: int) -> str | None:
        m = re.search(rf"^{'#' * level}\s+(.+?)\s*$", content, re.MULTILINE)
        return m.group(1).strip() if m else None

    @staticmethod
    def _section_text(content: str, heading: str) -> str:
        pattern = rf"^#+\s+{re.escape(heading)}\s*$([\s\S]*?)(?=^#+\s+|\Z)"
        m = re.search(pattern, content, re.MULTILINE | re.IGNORECASE)
        return m.group(1).strip() if m else ""

    @staticmethod
    def _field_after_label(content: str, label: str) -> str:
        m = re.search(rf"{re.escape(label)}\s*:\s*(.+)", content, re.IGNORECASE)
        return m.group(1).strip(" -*") if m else ""

    @staticmethod
    def _dash_items(text: str) -> list[str]:
        rows: list[str] = []
        for line in text.splitlines():
            item = re.sub(r"^(?:[-*•]|\d+[.)])\s*", "", line.strip()).strip()
            if item:
                rows.append(item)
        return rows
