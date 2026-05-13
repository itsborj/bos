from __future__ import annotations

import json

from module_base import ModuleBase

_REQUIRED_TOP = {"brand_name", "voice", "tone", "values", "products", "audiences"}
_REQUIRED_PRODUCT = {"name", "tagline", "benefits"}
_REQUIRED_AUDIENCE = {"name", "demographics", "pain_points"}


class BrandSetupModule(ModuleBase):
    id = "onboarding.brand_setup"
    vertical = "onboarding"
    capability = "onboarding.brand_profiling"
    platform_hint = None
    policy_default = "balanced"
    template = "onboarding/brand_setup/template.j2"

    max_chars = 0
    must_mention = []
    banned_phrases = []

    def self_check(self, content: str, _brief: dict) -> tuple[str, list[str]]:
        failures: list[str] = []

        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```", 2)[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
            cleaned = cleaned.strip().rstrip("`").strip()

        try:
            profile = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            return "fail", [f"invalid_json:{exc}"]

        missing_top = _REQUIRED_TOP - set(profile.keys())
        for field in sorted(missing_top):
            failures.append(f"missing_field:{field}")

        for field in ("brand_name", "voice", "tone"):
            val = profile.get(field)
            if isinstance(val, str) and not val.strip():
                failures.append(f"empty_field:{field}")

        products = profile.get("products", [])
        if not isinstance(products, list) or len(products) == 0:
            failures.append("products_empty")
        else:
            for i, p in enumerate(products, 1):
                if not isinstance(p, dict):
                    failures.append(f"product_{i}_not_object")
                    continue
                for key in _REQUIRED_PRODUCT - set(p.keys()):
                    failures.append(f"product_{i}_missing:{key}")

        audiences = profile.get("audiences", [])
        if not isinstance(audiences, list) or len(audiences) == 0:
            failures.append("audiences_empty")
        else:
            for i, a in enumerate(audiences, 1):
                if not isinstance(a, dict):
                    failures.append(f"audience_{i}_not_object")
                    continue
                for key in _REQUIRED_AUDIENCE - set(a.keys()):
                    failures.append(f"audience_{i}_missing:{key}")

        return ("fail" if failures else "pass"), failures
