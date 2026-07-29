from __future__ import annotations

import re
from typing import Any

from module_base import ModuleBase


class StrategyWorkflowModule(ModuleBase):
    id = "marketing.planning.strategy_workflow"
    name = "Strategy Workflow"
    vertical = "marketing"
    capability = "marketing.copywriting"
    platform_hint = "planning"
    policy_default = "balanced"
    template = "marketing/planning/strategy_workflow/template.j2"

    max_chars = 30000
    banned_phrases = ["guaranteed results", "set it and forget it", "blast everyone"]

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        failures: list[str] = []
        lower = content.lower()

        required_components = [
            "component: archetype",
            "component: buyer_map",
            "component: strategic_thesis",
            "component: offer_architecture",
            "component: channel_stack",
            "component: channel_content_matrix",
            "component: tactical_funnel",
            "component: work_orders",
        ]
        for comp in required_components:
            if comp not in lower:
                failures.append(f"missing_component:{comp}")

        required_fields = [
            "awareness level",
            "buyer type",
            "trust gap",
            "primary motion",
            "wedge",
            "decision",
            "do now",
            "hold",
            "reach",
            "action",
            "approval note",
            "weekly slot total",
        ]
        for field in required_fields:
            if field not in lower:
                failures.append(f"missing_field:{field}")

        if len(content) > self.max_chars:
            failures.append(f"exceeds_max_chars:{len(content)}>{self.max_chars}")

        for phrase in self.banned_phrases:
            if phrase in lower:
                failures.append(f"banned_phrase_found:{phrase}")

        if "run:" in lower or "module_id" in lower:
            failures.append("visible_internal_control_marker")

        if "approval" not in lower:
            failures.append("missing_approval_boundary")

        allowed_motions = {
            "founder-led", "product-led", "sales-led",
            "content-led", "partner-led", "community-led",
        }
        thesis_text = self._component_text(content, "strategic_thesis").lower()
        if thesis_text and not any(m in thesis_text for m in allowed_motions):
            failures.append("invalid_motion_taxonomy")

        do_now_channels = self._do_now_channels(content)
        if len(do_now_channels) > 3:
            failures.append("too_many_do_now_channels")

        unsupported_metric_patterns = [
            r"\b\d+(?:\.\d+)?\s*%",
            r"\$\s?\d[\d,]*(?:\.\d+)?\s*(?:k|m|b)?\b",
            r"\b\d+[\d,]*\s+(?:leads|sales|customers|signups|demos|calls|conversions)\b",
        ]
        context_text = " ".join(str(v) for v in brief.values() if isinstance(v, str))
        for pattern in unsupported_metric_patterns:
            if re.search(pattern, content, re.IGNORECASE) and not re.search(pattern, context_text, re.IGNORECASE):
                failures.append("invented_numeric_target")
                break

        return ("fail" if failures else "pass"), failures

    def _build_block(self, content: str) -> dict[str, Any]:
        archetype_text = self._component_text(content, "archetype")
        archetype = self._field_after_label(archetype_text, "Archetype selected") or "direct_sales"

        buyer = self._component_text(content, "buyer_map")
        thesis = self._component_text(content, "strategic_thesis")
        offer = self._component_text(content, "offer_architecture")
        channel = self._component_text(content, "channel_stack")
        content_matrix = self._component_text(content, "channel_content_matrix")
        funnel = self._component_text(content, "tactical_funnel")
        orders = self._component_text(content, "work_orders")

        return {
            "type": "strategy_workflow",
            "artifact_type": "plan_artifact",
            "title": self._heading(content, 1) or "Strategy Workflow",
            "status": "pending_review",
            "archetype": archetype.strip(),
            "primary_motion": self._field_after_label(thesis, "Primary motion"),
            "wedge": self._field_after_label(thesis, "Wedge"),
            "components": [
                {
                    "type": "buyer_map",
                    "status": "complete",
                    "data": {
                        "awareness_level": self._field_after_label(buyer, "Awareness level"),
                        "buyer_type": self._field_after_label(buyer, "Buyer type"),
                        "blocking_forces": self._field_after_label(buyer, "Blocking forces"),
                        "trust_gap": self._field_after_label(buyer, "Trust gap"),
                        "push_forces": self._dash_items(self._after_label(buyer, "Push forces")),
                        "pull_forces": self._dash_items(self._after_label(buyer, "Pull forces")),
                        "anxiety_sources": self._dash_items(self._after_label(buyer, "Anxiety sources")),
                        "buyer_language": self._dash_items(self._after_label(buyer, "Buyer language")),
                        "decision_roles": self._decision_roles(buyer),
                        "confidence": self._field_after_label(buyer, "Confidence"),
                        "raw": buyer,
                    },
                },
                {
                    "type": "strategic_thesis",
                    "status": "complete",
                    "data": {
                        "primary_motion": self._field_after_label(thesis, "Primary motion"),
                        "secondary_motion": self._field_after_label(thesis, "Secondary motion"),
                        "secondary_unlock": self._field_after_label(thesis, "Secondary unlock"),
                        "wedge": self._field_after_label(thesis, "Wedge"),
                        "decision": self._field_after_label(thesis, "Decision"),
                        "not_doing": self._dash_items(self._after_label(thesis, "Not doing")),
                        "motion_rationale": self._field_after_label(thesis, "Motion rationale"),
                        "raw": thesis,
                    },
                },
                {
                    "type": "offer_architecture",
                    "status": "complete",
                    "data": {
                        "audience_need": self._field_after_label(offer, "Audience need"),
                        "resource": self._field_after_label(offer, "Resource"),
                        "micro_commitment": self._field_after_label(offer, "Micro commitment"),
                        "macro_activation": self._field_after_label(offer, "Macro activation"),
                        "offer_ladder": self._dash_items(self._after_label(offer, "Offer ladder")),
                        "anxiety_treatment": self._field_after_label(offer, "Anxiety treatment"),
                        "proof_required": self._field_after_label(offer, "Proof required"),
                        "raw": offer,
                    },
                },
                {
                    "type": "channel_stack",
                    "status": "complete",
                    "data": {
                        "do_now": self._do_now_channels(content),
                        "hold": self._dash_items(self._after_label_in(channel, "Hold")),
                        "avoid": self._dash_items(self._after_label_in(channel, "Avoid")),
                        "raw": channel,
                    },
                },
                {
                    "type": "channel_content_matrix",
                    "status": "complete",
                    "data": {
                        "pillars": self._parse_pillars(content_matrix),
                        "weekly_slot_total": self._weekly_slot_total(content_matrix),
                        "rationale": self._field_after_label(content_matrix, "Rationale"),
                        "raw": content_matrix,
                    },
                },
                {
                    "type": "tactical_funnel",
                    "status": "complete",
                    "data": {
                        "reach_tactic": self._field_after_label(funnel, "Tactic"),
                        "engage_resource": self._field_after_label(funnel, "Resource"),
                        "action_cta": self._field_after_label(funnel, "CTA"),
                        "proof_capture": self._field_after_label(funnel, "Proof capture"),
                        "raw": funnel,
                    },
                },
                {
                    "type": "work_orders",
                    "status": "complete",
                    "data": {
                        "briefs": self._work_order_items(orders),
                        "raw": orders,
                    },
                },
            ],
            "not_wired_components": [
                "market_context",
                "framework_lenses",
                "measurement_model",
            ],
            "approval_note": "This is a draft strategy for review. Execution artifacts, outreach, publishing, spend, and external platform actions require separate approval.",
            "allowed_actions": ["approve", "revise", "dismiss"],
            "changed_resources": [],
            "risk_level": "draft_only",
        }

    @staticmethod
    def _heading(content: str, level: int) -> str | None:
        m = re.search(rf"^{'#' * level}\s+(.+?)\s*$", content, re.MULTILINE)
        return m.group(1).strip() if m else None

    @classmethod
    def _component_text(cls, content: str, component_type: str) -> str:
        pattern = rf"^##\s+COMPONENT:\s+{re.escape(component_type)}\s*$([\s\S]*?)(?=^##\s+COMPONENT:|\Z)"
        m = re.search(pattern, content, re.MULTILINE | re.IGNORECASE)
        return m.group(1).strip() if m else ""

    @staticmethod
    def _field_after_label(text: str, label: str) -> str:
        m = re.search(rf"^{re.escape(label)}:\s*(.+?)$", text, re.MULTILINE | re.IGNORECASE)
        return m.group(1).strip() if m else ""

    @classmethod
    def _after_label(cls, text: str, label: str) -> str:
        pattern = rf"^{re.escape(label)}:\s*$([\s\S]*?)(?=^\w|\Z)"
        m = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
        if m:
            return m.group(1).strip()
        pattern2 = rf"^{re.escape(label)}:(.+?)(?=^\w|\Z)"
        m2 = re.search(pattern2, text, re.MULTILINE | re.IGNORECASE | re.DOTALL)
        return m2.group(1).strip() if m2 else ""

    @staticmethod
    def _after_label_in(text: str, label: str) -> str:
        # Prefer the label on its own line followed by content on the next lines.
        pattern = rf"^{re.escape(label)}:\s*$([\s\S]*?)(?=^(?:Do now|Hold|Avoid|##)|\Z)"
        m = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
        if m and m.group(1).strip():
            return m.group(1).strip()
        # Fallback: label followed by inline content on the same line.
        pattern2 = rf"^{re.escape(label)}:\s+(.+?)(?=^(?:Do now|Hold|Avoid|##)|\Z)"
        m2 = re.search(pattern2, text, re.MULTILINE | re.IGNORECASE | re.DOTALL)
        return m2.group(1).strip() if m2 else ""

    @staticmethod
    def _dash_items(text: str) -> list[str]:
        items = []
        for line in text.splitlines():
            item = re.sub(r"^[-*•]\s*", "", line.strip()).strip()
            if item and not item.endswith(":"):
                items.append(item)
        return items

    @staticmethod
    def _decision_roles(text: str) -> dict[str, str]:
        roles: dict[str, str] = {}
        for role in ("Champion", "Economic buyer", "Veto"):
            m = re.search(rf"^-\s*{re.escape(role)}:\s*(.+?)$", text, re.MULTILINE | re.IGNORECASE)
            if m:
                roles[role.lower().replace(" ", "_")] = m.group(1).strip()
        return roles

    @classmethod
    def _do_now_channels(cls, content: str) -> list[dict[str, str]]:
        channel_text = cls._component_text(content, "channel_stack")

        # Format 2/3 first: "### Do now: **Channel**\n..." or "Do now: **Channel**\n..."
        # LLMs frequently merge the Do now label and channel name on one line.
        # [^\S\n]* = horizontal whitespace only — ensures **Channel** is on the same line as "Do now:".
        # Check this before _after_label_in so multiple channels aren't collapsed by the fallback.
        inline_pattern = r"(?:#{1,3}\s+)?Do\s+now:[^\S\n]*\*\*(.+?)\*\*"
        matches = list(re.finditer(inline_pattern, channel_text, re.MULTILINE | re.IGNORECASE))
        if matches:
            rows = []
            for i, m in enumerate(matches):
                channel = m.group(1).strip()
                start = m.end()
                end = matches[i + 1].start() if i + 1 < len(matches) else len(channel_text)
                block = channel_text[start:end]
                rows.append({
                    "channel": channel,
                    "role": cls._field_after_label(block, "Role"),
                    "buyer_map_signal": cls._field_after_label(block, "Buyer map signal"),
                    "proof_required": cls._field_after_label(block, "Proof required to scale"),
                    "rationale": cls._field_after_label(block, "Rationale"),
                })
            return rows

        # Format 1 (template-spec): "Do now:\n**Channel**\n..."
        do_now_section = cls._after_label_in(channel_text, "Do now")
        if do_now_section:
            return cls._parse_bold_channel_blocks(do_now_section)

        return []

    @classmethod
    def _parse_bold_channel_blocks(cls, section: str) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        blocks = re.split(r"(?=^\*\*.+?\*\*)", section, flags=re.MULTILINE)
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            heading = re.search(r"^\*\*(.+?)\*\*", block, re.MULTILINE)
            if not heading:
                continue
            rows.append({
                "channel": heading.group(1).strip(),
                "role": cls._field_after_label(block, "Role"),
                "buyer_map_signal": cls._field_after_label(block, "Buyer map signal"),
                "proof_required": cls._field_after_label(block, "Proof required to scale"),
                "rationale": cls._field_after_label(block, "Rationale"),
            })
        return rows

    @classmethod
    def _parse_pillars(cls, text: str) -> list[dict[str, Any]]:
        pillars: list[dict[str, Any]] = []
        blocks = re.split(r"(?=^PILLAR:)", text, flags=re.MULTILINE | re.IGNORECASE)
        for block in blocks:
            block = block.strip()
            if not block or not re.match(r"^PILLAR:", block, re.IGNORECASE):
                continue
            id_match = re.match(r"^PILLAR:\s*(.+?)$", block, re.MULTILINE | re.IGNORECASE)
            if not id_match:
                continue
            pillar_id = id_match.group(1).strip().lower().replace(" ", "_").replace("-", "_")

            fmt_match = re.search(
                r"^Format:\s*$([\s\S]*?)(?=^[A-Z]|\Z)", block, re.MULTILINE | re.IGNORECASE
            )
            format_by_platform: dict[str, str] = {}
            if fmt_match:
                for line in fmt_match.group(1).splitlines():
                    fm = re.match(r"^\s*-\s*(.+?):\s*(.+?)$", line)
                    if fm:
                        format_by_platform[fm.group(1).strip().lower()] = fm.group(2).strip()

            platforms_raw = cls._field_after_label(block, "Platforms")
            platforms = [p.strip().lower() for p in platforms_raw.split(",") if p.strip()]

            freq_raw = cls._field_after_label(block, "Weekly frequency")
            try:
                weekly_freq = int(re.search(r"\d+", freq_raw).group()) if freq_raw else 1
            except (AttributeError, ValueError):
                weekly_freq = 1

            pillars.append({
                "id": pillar_id,
                "label": cls._field_after_label(block, "Label"),
                "angle": cls._field_after_label(block, "Angle"),
                "cta_weight": cls._field_after_label(block, "CTA weight"),
                "weekly_freq": weekly_freq,
                "image_style": cls._field_after_label(block, "Image style"),
                "copy_length": cls._field_after_label(block, "Copy length"),
                "platforms": platforms,
                "format_by_platform": format_by_platform,
            })
        return pillars

    @classmethod
    def _weekly_slot_total(cls, text: str) -> int:
        raw = cls._field_after_label(text, "Weekly slot total")
        try:
            return int(re.search(r"\d+", raw).group()) if raw else 0
        except (AttributeError, ValueError):
            return 0

    @classmethod
    def _work_order_items(cls, text: str) -> list[dict[str, Any]]:
        briefs: list[dict[str, Any]] = []
        blocks = re.split(r"(?=^\d+\.\s+)", text, flags=re.MULTILINE)
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            heading = re.match(r"^\d+\.\s+(.+?)$", block, re.MULTILINE)
            if not heading:
                continue
            title = re.sub(r"\*+", "", heading.group(1)).strip()
            purpose = cls._field_after_label(block, "Purpose")
            gate = cls._field_after_label(block, "Gate")
            contents_section = cls._after_label(block, "Contents")
            contents = cls._dash_items(contents_section)
            briefs.append({
                "title": title,
                "purpose": purpose,
                "contents": contents,
                "gate": gate,
            })
        return briefs
