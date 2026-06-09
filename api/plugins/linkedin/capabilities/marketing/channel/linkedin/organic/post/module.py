from __future__ import annotations

from klaroha_sdk import ChannelModule


class LinkedInOrganicPostModule(ChannelModule):
    id = "marketing.channel.linkedin.organic.post"
    name = "LinkedIn Organic Post Draft"
    vertical = "marketing"
    capability = "marketing.copywriting"
    platform_hint = "linkedin"
    policy_default = "balanced"
    template = "marketing/channel/linkedin/organic/post/template.j2"

    max_chars = 3000
    must_mention = []
    banned_phrases = [
        "guaranteed",
        "100% free",
        "act now",
        "click here",
        "limited time only",
    ]

    def _safe_text(self, value: object, fallback: str = "") -> str:
        if value is None:
            return fallback
        text = str(value).strip()
        return text or fallback

    def _split_hashtags(self, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            raw_items = value
        else:
            raw_items = str(value).replace("#", " #").replace(",", " ").split()
        tags: list[str] = []
        for item in raw_items:
            tag = str(item).strip().lstrip("#")
            if not tag:
                continue
            safe = "".join(ch for ch in tag if ch.isalnum() or ch == "_")
            if safe and safe.lower() not in [existing.lower() for existing in tags]:
                tags.append(safe[:40])
        return tags[:5]

    def _creds(self, brief: dict) -> dict:
        raw = brief.get("_channel_credentials", {}) if isinstance(brief, dict) else {}
        return raw if isinstance(raw, dict) else {}

    def _has_linkedin_connection(self, brief: dict) -> bool:
        creds = self._creds(brief)
        token = str(
            creds.get("linkedin_page_token")
            or creds.get("linkedin_access_token")
            or creds.get("page_token")
            or creds.get("access_token")
            or ""
        ).strip()
        return bool(token)

    def _connection_required_result(self) -> tuple[dict, dict]:
        content = (
            "LinkedIn connection required before drafting.\n\n"
            "Connect LinkedIn for this brand, then run the LinkedIn connection check.\n"
            "Mutation: none — no draft, publish, schedule, or platform action was performed."
        )
        return {
            "provider": "linkedin",
            "model_id": "connection_gate_v1",
            "mode": "tool",
            "status": "failed",
            "tokens_input": 0,
            "tokens_output": 0,
            "provider_cost": 0.0,
            "latency_ms": 0,
            "error": "missing_credentials",
        }, {
            "content": content,
            "sell_price": None,
            "block": {
                "type": "linkedin_connection_check",
                "artifact_type": "action_result",
                "platform": "linkedin",
                "status": "failed",
                "reason_code": "missing_credentials",
                "message": "LinkedIn OAuth access token is not connected for this brand",
                "read_only": True,
                "changed_resources": [],
                "allowed_actions": ["connect_linkedin", "retry", "dismiss"],
                "risk_policy": "connection_validate_is_read_only",
            },
        }

    def _draft_post(self, brief: dict) -> tuple[str, list[str]]:
        brand = self._safe_text(brief.get("brand_name"), "the brand")
        audience = self._safe_text(brief.get("audience") or brief.get("target_audience"), "business operators")
        objective = self._safe_text(brief.get("objective") or brief.get("goal"), "start a useful conversation")
        topic = self._safe_text(brief.get("topic") or brief.get("subject") or brief.get("campaign_name"), objective)
        offer = self._safe_text(brief.get("offer") or brief.get("product_name") or brief.get("service_name"), "")
        tone = self._safe_text(brief.get("tone"), "clear, practical, and professional")
        cta = self._safe_text(brief.get("cta") or brief.get("call_to_action"), "What would you add?")
        raw_hashtags = brief.get("hashtags") or brief.get("keywords") or ["B2B", "Marketing", "Growth"]
        hashtags = self._split_hashtags(raw_hashtags)
        if not hashtags:
            hashtags = ["B2B", "Marketing", "Growth"]

        offer_line = f"\n\nFor {brand}, this connects directly to {offer}." if offer else ""
        post = (
            f"Most {audience} do not need more noise around {topic}.\n\n"
            f"They need a clearer way to decide what matters, what to do next, and what to ignore."
            f"{offer_line}\n\n"
            f"A simple operating question helps:\n"
            f"If this work succeeds, what signal will prove it?\n\n"
            f"That keeps the conversation grounded in outcomes instead of activity.\n\n"
            f"Tone for this draft: {tone}.\n\n"
            f"{cta}\n\n"
            + " ".join(f"#{tag}" for tag in hashtags)
        ).strip()
        return post, hashtags

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        failures: list[str] = []
        try:
            text = (content or "").strip()
            connection_gate = "linkedin connection required before drafting" in text.lower()
            if connection_gate:
                if "mutation: none" not in text.lower():
                    failures.append("missing_read_only_boundary")
                return ("fail" if failures else "pass", failures)
            if len(text) < 40:
                failures.append("content_too_short")
            if len(text) > self.max_chars:
                failures.append("exceeds_max_chars")
            for phrase in self.banned_phrases:
                if phrase.lower() in text.lower():
                    failures.append("banned_phrase")
            if "#" not in text:
                failures.append("missing_hashtag")
        except Exception:
            failures.append("self_check_exception")
        return ("fail" if failures else "pass", failures)

    def execute_tool_result(self, brief: dict) -> tuple[dict, dict]:
        safe_brief = dict(brief or {})
        if not self._has_linkedin_connection(safe_brief):
            return self._connection_required_result()

        content, hashtags = self._draft_post(safe_brief)

        attempt_data = {
            "provider": "linkedin",
            "model_id": "deterministic_draft_v1",
            "mode": "tool",
            "status": "succeeded",
            "tokens_input": 0,
            "tokens_output": 0,
            "provider_cost": 0.0,
            "latency_ms": 0,
            "error": None,
        }

        result_data = {
            "content": content,
            "sell_price": None,
            "block": {
                "type": "linkedin_post_draft",
                "artifact_type": "draft_artifact",
                "platform": "linkedin",
                "status": "draft",
                "message": content,
                "hashtags": hashtags,
                "character_count": len(content),
                "recommended_surface": "linkedin_feed",
                "read_only": True,
                "changed_resources": [],
                "allowed_actions": ["revise", "dismiss", "approve"],
                "risk_policy": "draft_only_no_external_action",
            },
        }
        return attempt_data, result_data
