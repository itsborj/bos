from __future__ import annotations

import re
from typing import Any

from module_base import ModuleBase


class BuyerIntelligenceModule(ModuleBase):
    id = "reasoning.buyer_intelligence"
    name = "Buyer Intelligence Map"
    vertical = "reasoning"
    capability = "marketing.copywriting"
    platform_hint = "strategy"
    policy_default = "balanced"
    template = "reasoning/buyer_intelligence/template.j2"

    max_chars = 18000
    banned_phrases = ["guaranteed results", "set it and forget it"]

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        failures: list[str] = []
        lower = content.lower()
        required = [
            "buyer map",
            "real outcome",
            "customer roles",
            "jobs",
            "awareness",
            "buyer type",
            "adoption stage",
            "comparison set",
            "value equation",
            "trust signals",
            "switching forces",
            "dominant blocking force",
            "buyer language",
            "critical assumptions",
            "priority calibration",
        ]
        for section in required:
            if section not in lower:
                failures.append(f"missing_section:{section}")
        for lens in range(1, 11):
            if f"lens {lens}" not in lower:
                failures.append(f"missing_lens:{lens}")
        if len(content) > self.max_chars:
            failures.append(f"exceeds_max_chars:{len(content)}>{self.max_chars}")
        for phrase in self.banned_phrases:
            if phrase in lower:
                failures.append(f"banned_phrase_found:{phrase}")
        if re.search(r"\b\d+(?:\.\d+)?\s*%", content):
            failures.append("unsupported_numeric_claim")
        if "confidence:" not in lower:
            failures.append("missing_confidence_flags")
        return ("fail" if failures else "pass"), failures

    def _build_block(self, content: str) -> dict[str, Any]:
        return {
            "type": "buyer_map",
            "artifact_type": "intelligence_artifact",
            "output_contract": "buyer_map.v1",
            "contract": "buyer_map.v1",
            "title": self._heading(content, 1) or "Buyer Intelligence Map",
            "status": "supporting",
            "summary": self._section_text(content, "Executive buyer read")[:800] or "Buyer intelligence substrate generated for downstream strategy.",
            "dominant_blocking_force": self._field_after_label(content, "Dominant blocking force"),
            "awareness_level": self._field_after_label(content, "Awareness level"),
            "buyer_type": self._field_after_label(content, "Buyer type"),
            "critical_assumptions": self._dash_items(self._section_text(content, "Critical assumptions")),
            "priority_calibration": self._dash_items(self._section_text(content, "Priority calibration")),
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
