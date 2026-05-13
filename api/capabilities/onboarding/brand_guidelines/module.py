from __future__ import annotations

from module_base import ModuleBase


_REQUIRED_SECTIONS = [
    "Campaign Brand Kit Overview",
    "Color Palette",
    "Tone of Voice",
    "Typography Basics",
    "Campaign Components",
    "Multi-Platform Rules",
    "Accessibility & Consistency",
    "Governance",
]


class BrandGuidelinesModule(ModuleBase):
    id = "onboarding.brand_guidelines"
    vertical = "onboarding"
    capability = "onboarding.brand_profiling"
    platform_hint = "campaign brand kit"
    policy_default = "balanced"
    template = "onboarding/brand_guidelines/template.j2"

    max_chars = 0
    must_mention = ["brand_name"]
    banned_phrases = []

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        failures: list[str] = []
        stripped = content.strip()

        if not stripped:
            return "fail", ["empty_output"]

        if not stripped.startswith("#"):
            failures.append("missing_markdown_title")

        for section in _REQUIRED_SECTIONS:
            if section not in content:
                failures.append(f"missing_section:{section}")

        brand_name = str(brief.get("brand_name", "")).strip()
        if brand_name and brand_name.lower() not in content.lower():
            failures.append("brand_name_not_used")

        unresolved_markers = ["[BRAND NAME]", "[PLACEHOLDER]", "[e.g.", "[#XXXXXX]", "[YYYY-MM-DD]"]
        for marker in unresolved_markers:
            if marker.lower() in content.lower():
                failures.append(f"unresolved_placeholder:{marker}")

        required_tokens = [
            "color-primary",
            "color-accent",
            "color-neutral-900",
            "bg-base",
            "font-heading",
            "component-primary-cta",
            "component-ad-headline",
            "email",
        ]
        for token in required_tokens:
            if token not in content.lower():
                failures.append(f"missing_campaign_kit_item:{token}")

        if "WCAG" not in content or "AA" not in content:
            failures.append("accessibility_standard_missing")

        return ("fail" if failures else "pass"), failures
