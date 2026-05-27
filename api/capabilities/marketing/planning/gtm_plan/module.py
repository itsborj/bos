from __future__ import annotations

import re
from typing import Any

from module_base import ModuleBase


class MarketingGtmStrategyPlanModule(ModuleBase):
    id = "marketing.planning.gtm_plan"
    name = "GTM Strategy Plan"
    vertical = "marketing"
    capability = "marketing.copywriting"
    platform_hint = "planning"
    policy_default = "balanced"
    template = "marketing/planning/gtm_plan/template.j2"

    max_chars = 20000
    banned_phrases = ["guaranteed results", "set it and forget it", "blast everyone"]

    def normalize_content(self, content: str, brief: dict) -> str:
        """Apply deterministic safety cleanup before self-check/persistence.

        Provider repair sometimes leaves numeric gate targets or puts late-stage
        channels in Do now. Normalize those to the approved GTM contract rather
        than surfacing a failed artifact for an otherwise usable strategy.
        """
        content = self._normalize_headings(content)
        content = self._replace_section(content, "Measurement frame", self._scrub_numeric_targets(self._section_text(content, "Measurement frame")))
        content = self._move_unsupported_do_now_to_hold(content, brief)
        return content

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        failures: list[str] = []
        lower = content.lower()
        required = [
            "best current motion",
            "why this motion",
            "primary audience",
            "positioning angle",
            "core promise",
            "launch sequence",
            "channel stack",
            "do now",
            "hold",
            "avoid for now",
            "conversion path",
            "first proof assets needed",
            "measurement frame",
            "assumptions i made",
            "critical gaps",
            "useful later",
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

        best_motion = self._section_text(content, "Best current motion").lower()
        allowed_motions = {
            "founder-led",
            "product-led",
            "sales-led",
            "content-led",
            "partner-led",
            "community-led",
        }
        if best_motion and not any(motion in best_motion for motion in allowed_motions):
            failures.append("invalid_motion_taxonomy")

        context_text = self._brief_context_text(brief)
        context_lower = context_text.lower()
        unsupported_metric_patterns = [
            r"\b\d+(?:\.\d+)?\s*%",
            r"\$\s?\d[\d,]*(?:\.\d+)?\s*(?:k|m|b)?\b",
            r"\b\d+[\d,]*\s+(?:leads|sales|customers|signups|demos|calls|conversions)\b",
        ]
        for pattern in unsupported_metric_patterns:
            if re.search(pattern, content, re.IGNORECASE) and not re.search(pattern, context_text, re.IGNORECASE):
                failures.append("invented_numeric_target_or_proof")
                break

        do_now_text_raw = self._section_text(content, "Do now")
        do_now_text = do_now_text_raw.lower()
        do_now_channels = self._do_now_channel_items(do_now_text_raw)
        if len(do_now_channels) > 3:
            failures.append("too_many_do_now_channels")
        do_now_channel_names = "\n".join(str(row.get("channel") or row.get("name") or "") for row in do_now_channels).lower()
        broad_or_late_channels = {
            "affiliate": "unsupported_do_now_channel_without_context:affiliate",
            "referral": "unsupported_do_now_channel_without_context:referral",
            "community": "unsupported_do_now_channel_without_context:community",
            "influencer": "unsupported_do_now_channel_without_context:influencer",
            "paid social": "unsupported_do_now_channel_without_context:paid_social",
            "paid media": "unsupported_do_now_channel_without_context:paid_media",
            "tiktok": "unsupported_do_now_channel_without_context:tiktok",
        }
        for needle, failure in broad_or_late_channels.items():
            if needle in do_now_channel_names and needle not in context_lower:
                failures.append(failure)

        owned_email_signals = (
            "email list",
            "subscriber",
            "subscribers",
            "newsletter",
            "crm",
            "owned list",
            "opt-in",
            "opt in",
            "lead database",
            "customer list",
        )
        list_email_requested = any(
            needle in do_now_channel_names
            for needle in ("email marketing", "newsletter", "email nurture", "nurture email", "email campaign")
        )
        if list_email_requested and not any(signal in context_lower for signal in owned_email_signals):
            failures.append("unsupported_do_now_channel_without_context:email_list")

        block = self._build_block(content)
        if not block.get("best_current_motion"):
            failures.append("missing_best_current_motion")
        if len(block.get("launch_sequence", [])) < 3:
            failures.append("insufficient_launch_sequence")
        channel_stack = block.get("channel_stack") or {}
        if not channel_stack.get("do_now"):
            failures.append("missing_do_now_channels")
        if not block.get("assumptions"):
            failures.append("missing_assumptions")
        if not block.get("critical_gaps"):
            failures.append("missing_critical_gaps")
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
        title = self._heading(content, 1) or "GTM Launch Strategy"
        return {
            "type": "gtm_strategy",
            "artifact_type": "plan_artifact",
            "title": title,
            "status": "pending_review",
            "best_current_motion": self._section_text(content, "Best current motion"),
            "why_this_motion": self._section_text(content, "Why this motion"),
            "primary_audience": self._section_text(content, "Primary audience"),
            "positioning_angle": self._section_text(content, "Positioning angle"),
            "core_promise": self._section_text(content, "Core promise"),
            "launch_sequence": self._launch_sequence_items(content),
            "channel_stack": {
                "do_now": self._do_now_channel_items(self._section_text(content, "Do now")),
                "hold": self._reason_items(self._section_text(content, "Hold")),
                "avoid_for_now": self._reason_items(self._section_text(content, "Avoid for now")),
            },
            "conversion_path": self._path_items(self._section_text(content, "Conversion path")),
            "first_proof_assets_needed": self._dash_items(self._section_text(content, "First proof assets needed")),
            "measurement_frame": self._dash_items(self._section_text(content, "Measurement frame")),
            "assumptions": self._dash_items(self._section_text(content, "Assumptions I made")),
            "critical_gaps": self._gap_items(self._section_text(content, "Critical gaps")),
            "useful_later": self._dash_items(self._section_text(content, "Useful later")),
            "next_artifacts": self._reason_items(self._section_text(content, "Next artifacts")),
            "approval_note": self._section_text(content, "Approval note"),
            "allowed_actions": ["approve", "revise", "dismiss"],
            "changed_resources": [],
            "risk_level": "draft_only",
        }

    @staticmethod
    def _normalize_headings(content: str) -> str:
        """Normalize common LLM markdown variants before parsing.

        Some providers return requested sections as bold labels instead of `##`
        headings. Keep stage labels nested so launch-sequence parsing still works.
        """
        known_sections = {
            "best current motion", "why this motion", "primary audience", "positioning angle",
            "core promise", "launch sequence", "channel stack", "do now", "hold",
            "avoid for now", "conversion path", "first proof assets needed", "measurement frame",
            "assumptions i made", "critical gaps", "useful later", "next artifacts", "approval note",
        }
        normalized: list[str] = []
        for line in content.splitlines():
            m = re.match(r"^\s*\*\*(.+?)\*\*\s*:??\s*$", line)
            if m:
                label = m.group(1).strip()
                if re.match(r"Stage\s+\d+\s+[—-]", label, re.IGNORECASE):
                    normalized.append(f"### {label}")
                elif label.lower() in known_sections:
                    normalized.append(f"## {label}")
                else:
                    normalized.append(line)
            else:
                normalized.append(line)
        return "\n".join(normalized)

    @classmethod
    def _heading(cls, content: str, level: int) -> str | None:
        content = cls._normalize_headings(content)
        prefix = "#" * level
        m = re.search(rf"^\s*{re.escape(prefix)}\s+(.+?)\s*$", content, re.MULTILINE)
        return m.group(1).strip() if m else None

    @classmethod
    def _section_text(cls, content: str, heading: str) -> str:
        content = cls._normalize_headings(content)
        pattern = rf"^#+\s+{re.escape(heading)}\s*$([\s\S]*?)(?=^#+\s+|\Z)"
        m = re.search(pattern, content, re.MULTILINE | re.IGNORECASE)
        if not m:
            return ""
        return m.group(1).strip()

    @classmethod
    def _top_section_text(cls, content: str, heading: str) -> str:
        """Return a section including its nested subsections.

        LLMs often demote the requested Markdown hierarchy (for example, using
        `### Launch sequence` with `#### Stage 0` children). Capture the heading
        at any level and stop only when the next heading is at the same or a
        higher level.
        """
        content = cls._normalize_headings(content)
        pattern = rf"^(#+)\s+{re.escape(heading)}\s*$"
        m = re.search(pattern, content, re.MULTILINE | re.IGNORECASE)
        if not m:
            return ""
        level = len(m.group(1))
        start = m.end()
        next_same_or_parent = re.search(rf"^#{{1,{level}}}\s+", content[start:], re.MULTILINE)
        end = start + next_same_or_parent.start() if next_same_or_parent else len(content)
        return content[start:end].strip()

    @staticmethod
    def _clean_item(line: str) -> str:
        return re.sub(r"^(?:[-*•]|\d+[.)])\s*", "", line.strip()).strip()

    @classmethod
    def _dash_items(cls, text: str) -> list[str]:
        items: list[str] = []
        placeholder_prefixes = {
            "channel — hold reason",
            "channel — avoid reason",
            "trust gap — proof format",
            "stage — leading indicators",
            "touchpoint — message job",
            "**touchpoint** — message job",
        }
        for line in text.splitlines():
            item = cls._clean_item(line)
            normalized = item.strip().lower()
            if item and not any(normalized.startswith(prefix) for prefix in placeholder_prefixes):
                items.append(item)
        return items

    @classmethod
    def _split_reason(cls, item: str) -> tuple[str, str]:
        parts = [p.strip() for p in re.split(r"\s+[—-]\s+", item, maxsplit=1)]
        if len(parts) == 2:
            return parts[0], parts[1]
        return item, ""

    @classmethod
    def _reason_items(cls, text: str) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for item in cls._dash_items(text):
            name, reason = cls._split_reason(item)
            rows.append({"name": name, "reason": reason})
        return rows

    @classmethod
    def _gap_items(cls, text: str) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for item in cls._dash_items(text):
            gap, unlocks = cls._split_reason(item)
            rows.append({"gap": gap, "unlocks": unlocks})
        return rows

    @classmethod
    def _step_items(cls, text: str) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for item in cls._dash_items(text):
            step, purpose = cls._split_reason(item)
            rows.append({"step": step, "purpose": purpose})
        return rows

    @classmethod
    def _channel_items(cls, text: str) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for item in cls._dash_items(text):
            parts = [p.strip() for p in re.split(r"\s+[—-]\s+", item)]
            if len(parts) >= 3:
                rows.append({"channel": parts[0], "role": parts[1], "reason": " — ".join(parts[2:])})
            elif len(parts) == 2:
                rows.append({"channel": parts[0], "role": "", "reason": parts[1]})
            else:
                rows.append({"channel": item, "role": "", "reason": ""})
        return rows

    @classmethod
    def _launch_sequence_items(cls, content: str) -> list[dict[str, str]]:
        text = cls._top_section_text(content, "Launch sequence")
        if not text:
            return []
        if not re.search(r"^#{3,}\s+Stage\s+\d+", text, re.MULTILINE | re.IGNORECASE):
            return cls._step_items(text)

        rows: list[dict[str, str]] = []
        blocks = re.split(r"(?=^#{3,}\s+Stage\s+\d+)", text, flags=re.MULTILINE | re.IGNORECASE)
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            heading = re.search(r"^#{3,}\s+Stage\s+(\d+)\s+[—-]\s+(.+?)\s*$", block, re.MULTILINE | re.IGNORECASE)
            if not heading:
                continue
            stage = heading.group(1).strip()
            label = heading.group(2).strip()
            body = re.sub(r"^#{3,}\s+Stage\s+\d+\s+[—-]\s+.+?\s*$", "", block, count=1, flags=re.MULTILINE | re.IGNORECASE).strip()
            pending_match = re.search(r"Pending gate:\s*(.+)", body, re.IGNORECASE)
            rows.append(
                {
                    "step": f"Stage {stage}: {label}",
                    "stage": stage,
                    "label": label,
                    "purpose": body,
                    "completion_signal": pending_match.group(1).strip() if pending_match else "",
                    "pending_gate": pending_match.group(1).strip() if pending_match else "",
                }
            )
        return rows

    @classmethod
    def _do_now_channel_items(cls, text: str) -> list[dict[str, str]]:
        """Parse either legacy bullet channel rows or the richer template format.

        The current GTM template asks for:

            **Channel name**
            Decision: role — buyer-map signal — proof required
            Rationale: prose

        Self-check should count channel blocks, not every Decision/Rationale line.
        """
        if not re.search(r"^\s*(?:[-*•]\s*)?\*\*.+?\*\*", text, re.MULTILINE):
            return cls._channel_items(text)

        rows: list[dict[str, str]] = []
        blocks = re.split(r"(?=^\s*(?:[-*•]\s*)?\*\*.+?\*\*)", text, flags=re.MULTILINE)
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            heading = re.search(r"^\s*(?:[-*•]\s*)?\*\*(.+?)\*\*", block, re.MULTILINE)
            if not heading:
                continue
            channel = heading.group(1).strip()
            decision_match = re.search(r"^\s*Decision:\s*(.+?)\s*$", block, re.MULTILINE | re.IGNORECASE)
            if not decision_match:
                decision_match = re.search(r"\*\*\s*Decision:\s*([\s\S]*?)(?=\s+Rationale:|\Z)", block, re.IGNORECASE)
            rationale_match = re.search(r"^\s*Rationale:\s*([\s\S]+?)\s*$", block, re.MULTILINE | re.IGNORECASE)
            if not rationale_match:
                rationale_match = re.search(r"\sRationale:\s*([\s\S]+?)\s*$", block, re.IGNORECASE)
            decision = decision_match.group(1).strip() if decision_match else ""
            decision_parts = [p.strip() for p in re.split(r"\s+[—-]\s+", decision)] if decision else []
            role = decision_parts[0] if len(decision_parts) >= 1 else ""
            buyer_map_signal = decision_parts[1] if len(decision_parts) >= 2 else ""
            proof_required = " — ".join(decision_parts[2:]) if len(decision_parts) >= 3 else ""
            rationale = rationale_match.group(1).strip() if rationale_match else ""
            rows.append(
                {
                    "channel": channel,
                    "role": role,
                    "buyer_map_signal": buyer_map_signal,
                    "proof_required": proof_required,
                    "reason": rationale,
                    "rationale": rationale,
                }
            )
        return rows

    @classmethod
    def _path_items(cls, text: str) -> list[str]:
        if "→" in text:
            return [part.strip(" .") for part in text.split("→") if part.strip(" .")]
        return cls._dash_items(text)

    @classmethod
    def _replace_section(cls, content: str, heading: str, replacement: str) -> str:
        if not replacement:
            return content
        normalized = cls._normalize_headings(content)
        pattern = rf"^(#+\s+{re.escape(heading)}\s*$)([\s\S]*?)(?=^#+\s+|\Z)"
        return re.sub(pattern, lambda m: f"{m.group(1)}\n{replacement.strip()}\n\n", normalized, count=1, flags=re.MULTILINE | re.IGNORECASE)

    @staticmethod
    def _scrub_numeric_targets(text: str) -> str:
        if not text:
            return text
        scrubbed = re.sub(r"\$\s?\d[\d,]*(?:\.\d+)?\s*(?:k|m|b)?\b", "requires baseline", text, flags=re.IGNORECASE)
        scrubbed = re.sub(r"\b\d+(?:\.\d+)?\s*%", "requires baseline", scrubbed, flags=re.IGNORECASE)
        scrubbed = re.sub(
            r"\b\d+[\d,]*\s+(?:leads|sales|customers|signups|demos|calls|conversions)\b(?:\s+per\s+\w+)?",
            "baseline required",
            scrubbed,
            flags=re.IGNORECASE,
        )
        return scrubbed

    def _move_unsupported_do_now_to_hold(self, content: str, brief: dict) -> str:
        do_now = self._section_text(content, "Do now")
        hold = self._section_text(content, "Hold")
        if not do_now:
            return content
        context_lower = self._brief_context_text(brief).lower()
        unsupported = {
            "affiliate": "confirmed affiliate partners or successful customers exist",
            "referral": "happy customers, partners, or a referral source are confirmed",
            "community": "an owned community already exists",
            "influencer": "creator partners and proof assets are confirmed",
            "paid social": "proof assets and a budget signal are confirmed",
            "paid media": "proof assets and a budget signal are confirmed",
            "tiktok": "buyer-map evidence makes TikTok an immediate discovery/proof surface",
            "email marketing": "an owned list, CRM, subscribers, opt-ins, or lead database is confirmed",
            "newsletter": "an owned list, CRM, subscribers, opt-ins, or lead database is confirmed",
        }
        kept_lines: list[str] = []
        moved: list[str] = []
        for raw in do_now.splitlines():
            line = raw.rstrip()
            channel_match = re.search(r"\*\*(.+?)\*\*", line)
            channel_name = (channel_match.group(1) if channel_match else line).lower()
            hit = next((needle for needle in unsupported if needle in channel_name), None)
            if hit and hit not in context_lower:
                display = channel_match.group(1).strip() if channel_match else self._clean_item(line).split("—", 1)[0].strip()
                moved.append(f"- {display} — hold reason: prerequisite not loaded — unlock condition: {unsupported[hit]}.")
                continue
            kept_lines.append(line)
        if not moved:
            return content
        updated = self._replace_section(content, "Do now", "\n".join(kept_lines).strip())
        updated_hold = (hold.strip() + "\n" if hold.strip() else "") + "\n".join(moved)
        return self._replace_section(updated, "Hold", updated_hold)
