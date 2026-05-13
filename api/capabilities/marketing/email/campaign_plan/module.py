from __future__ import annotations

from module_base import ModuleBase


class EmailCampaignPlanModule(ModuleBase):
    id = "marketing.email.campaign_plan"
    name = "Email Campaign Plan"
    vertical = "marketing"
    capability = "marketing.copywriting"
    platform_hint = "email plan"
    template = "marketing/email/campaign_plan/template.j2"

    max_chars = 8000
    must_mention = []
    banned_phrases = ["blast everyone", "guaranteed results"]

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        failures: list[str] = []
        required = [
            "Goal",
            "Audience",
            "Offer",
            "Sequence",
            "Success metric",
            "Approval",
        ]
        lower = content.lower()
        for section in required:
            if section.lower() not in lower:
                failures.append(f"missing_section:{section}")
        if "send" in lower and "approval" not in lower:
            failures.append("missing_send_approval_policy")
        if len(content) > self.max_chars:
            failures.append(f"exceeds_max_chars:{len(content)}>{self.max_chars}")
        for phrase in self.banned_phrases:
            if phrase in lower:
                failures.append(f"banned_phrase_found:{phrase}")
        return ("fail" if failures else "pass"), failures
