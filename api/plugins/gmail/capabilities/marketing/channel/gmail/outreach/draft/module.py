from __future__ import annotations

from klaroha_sdk import ChannelModule


class GmailOutreachDraftModule(ChannelModule):
    id = "marketing.channel.gmail.outreach.draft"
    name = "Gmail Outreach Draft"
    vertical = "marketing"
    capability = "marketing.copywriting"
    platform_hint = "gmail"
    policy_default = "balanced"
    template = "marketing/channel/gmail/outreach/draft/template.j2"

    max_chars = 4000
    must_mention = ["product_name"]
    banned_phrases = ["guaranteed", "100% free", "act now"]

    def build_prompt(self, brief: dict) -> str:
        creds = brief.get("_channel_credentials", {})
        context = dict(brief)
        context["sender_email"] = creds.get("gmail_user", "")
        context["copywriting_guidance"] = self._copywriting_guidance()
        context["copywriting_skill_ids"] = list(self.copywriting_skills)
        from module_base import _get_env
        return _get_env().get_template(self.template).render(**context)

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        failures: list[str] = []

        if len(content) > self.max_chars:
            failures.append(f"exceeds_max_chars:{len(content)}>{self.max_chars}")

        for field in self.must_mention:
            val = str(brief.get(field, field))
            if val and val.lower() not in content.lower():
                failures.append(f"must_mention_missing:{val}")

        for phrase in self.banned_phrases:
            if phrase.lower() in content.lower():
                failures.append(f"banned_phrase_found:{phrase}")

        if "Subject:" not in content:
            failures.append("missing_subject_line")

        return ("fail" if failures else "pass"), failures
