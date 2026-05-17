from __future__ import annotations

from klaroha_sdk import ChannelModule


class MetaPostsDraftModule(ChannelModule):
    id = "marketing.channel.meta.posts.draft"
    name = "Facebook Post Draft"
    vertical = "marketing"
    capability = "marketing.execute"
    platform_hint = "facebook post draft"
    policy_default = "balanced"
    template = "marketing/channel/meta/posts/draft/template.j2"

    max_chars = 2000
    must_mention = []
    banned_phrases = ["guaranteed", "100% free", "act now", "click here"]

    def build_prompt(self, brief: dict) -> str:
        from module_base import _get_env
        return _get_env().get_template(self.template).render(**brief)

    def _build_block(self, content: str) -> dict:
        return {
            "type": "fb_page_post_draft",
            "platform": "facebook",
            "message": content.strip(),
            "link": None,
            "status": "draft",
            "allowed_actions": ["revise", "dismiss", "approve", "publish"],
            "risk_policy": "draft_only_until_approved",
            "changed_resources": [],
        }

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        failures = []
        if len(content.strip()) < 10:
            failures.append("content_too_short")
        if len(content) > self.max_chars:
            failures.append(f"exceeds_max_chars:{len(content)}>{self.max_chars}")
        for phrase in self.banned_phrases:
            if phrase.lower() in content.lower():
                failures.append(f"banned_phrase:{phrase}")
        return ("fail" if failures else "pass"), failures
