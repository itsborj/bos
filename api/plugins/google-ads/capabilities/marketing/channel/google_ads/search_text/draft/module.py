from __future__ import annotations

from klaroha_sdk import ChannelModule


class GoogleAdsSearchTextDraftModule(ChannelModule):
    id = "marketing.channel.google_ads.search_text.draft"
    name = "Google Ads Search Text Draft"
    vertical = "marketing"
    capability = "marketing.execute"
    platform_hint = "google search text"
    policy_default = "balanced"
    template = "marketing/channel/google_ads/search_text/draft/template.j2"

    max_headline_chars = 30
    max_description_chars = 90
    banned_phrases = ["guaranteed", "100% free", "#1", "best ever", "risk-free"]

    def _latency_ms(self, start):
        try:
            import time
            return round((time.perf_counter() - start) * 1000)
        except Exception:
            return 0

    def _attempt(self, start, status, error=None):
        return {
            "provider": "google_ads_plugin",
            "model_id": "deterministic_google_search_ad_draft_v1",
            "mode": "tool",
            "status": status,
            "tokens_input": 0,
            "tokens_output": 0,
            "provider_cost": 0.0,
            "latency_ms": self._latency_ms(start),
            "error": error,
        }

    def _value(self, brief, *keys, default=""):
        for key in keys:
            value = brief.get(key) if isinstance(brief, dict) else None
            if value:
                return str(value).strip()
        return default

    def _brand_name(self, brief):
        direct = self._value(brief, "brand_name", "company_name")
        if direct:
            return direct
        brand = brief.get("brand_profile") if isinstance(brief, dict) else None
        if isinstance(brand, dict):
            return str(brand.get("brand_name") or brand.get("name") or "Your Brand").strip()
        return "Your Brand"

    def _product_name(self, brief):
        direct = self._value(brief, "product_name", "product", "offer", "service")
        if direct:
            return direct
        products = brief.get("products") if isinstance(brief, dict) else None
        if isinstance(products, list) and products:
            first = products[0]
            if isinstance(first, dict) and first.get("name"):
                return str(first["name"]).strip()
        return self._brand_name(brief)

    def _audience(self, brief):
        return self._value(brief, "audience", "target_audience", "customer_segment", default="ready buyers")

    def _benefit(self, brief):
        direct = self._value(brief, "key_benefit", "benefit", "value_prop", "objective")
        if direct:
            return direct
        return "clearer choices"

    def _display_url(self, brief):
        url = self._value(brief, "display_url", "website", "domain", default="example.com")
        url = url.replace("https://", "").replace("http://", "").strip("/")
        return url or "example.com"

    def _clip(self, text, limit):
        clean = " ".join(str(text or "").replace("\n", " ").split()).strip(" -|,.;")
        if len(clean) <= limit:
            return clean
        # Truncate at last full word boundary so long product/brand names
        # don't produce mid-word cut headlines like "Motorcycle Sa".
        truncated = clean[:limit]
        last_space = truncated.rfind(" ")
        if last_space > 0:
            return truncated[:last_space].rstrip(" -|,.;")
        return truncated.rstrip(" -|,.;")

    def _dedupe(self, values, limit):
        seen = set()
        result = []
        for value in values:
            clipped = self._clip(value, limit)
            key = clipped.lower()
            if clipped and key not in seen:
                seen.add(key)
                result.append(clipped)
        return result

    def _draft(self, brief):
        brand = self._brand_name(brief)
        product = self._product_name(brief)
        audience = self._audience(brief)
        benefit = self._benefit(brief)
        display_url = self._display_url(brief)

        raw_headlines = [
            f"{brand} Official",
            f"{product} For You",
            f"Find {product}",
            f"Shop {brand}",
            f"Built For {audience}",
            f"Clear {benefit}",
            f"Get {product}",
            f"Compare Options",
            f"Book With {brand}",
            f"See Available Offers",
            f"Trusted Local Help",
            f"Simple Next Steps",
            f"Start With {brand}",
            f"Explore {product}",
            f"Talk To An Expert",
        ]
        raw_descriptions = [
            f"Explore {product} from {brand}. Get clear options and helpful next steps today.",
            f"Built for {audience}. Learn how {brand} helps you move from interest to action.",
            f"Compare choices, ask questions, and choose the path that fits your needs.",
            f"Review this draft before launch. No campaigns, budgets, or ads were changed.",
        ]

        headlines = self._dedupe(raw_headlines, self.max_headline_chars)
        descriptions = self._dedupe(raw_descriptions, self.max_description_chars)
        return {
            "brand": brand,
            "product": product,
            "audience": audience,
            "benefit": benefit,
            "display_url": display_url,
            "headlines": headlines,
            "descriptions": descriptions,
        }

    def _content(self, draft):
        lines = [
            "# Google Ads Search Text Draft",
            "",
            "Status: draft for review — not published",
            "Display URL: " + draft["display_url"],
            "",
            "## Responsive search ad headlines",
        ]
        for idx, headline in enumerate(draft["headlines"], start=1):
            lines.append(f"{idx}. {headline}")
        lines.extend(["", "## Descriptions"])
        for idx, description in enumerate(draft["descriptions"], start=1):
            lines.append(f"{idx}. {description}")
        lines.extend([
            "",
            "Read-only/draft note: this artifact is copy only. No campaigns, ads, keywords, bids, or budgets were changed.",
        ])
        return "\n".join(lines)

    def _block(self, draft):
        return {
            "type": "google_search_ad_draft",
            "status": "draft",
            "platform": "google_ads",
            "channel": "search",
            "format": "responsive_search_ad",
            "display_url": draft["display_url"],
            "headlines": [{"text": text, "pinned": False} for text in draft["headlines"]],
            "descriptions": [{"text": text, "pinned": False} for text in draft["descriptions"]],
            "path1": "",
            "path2": "",
            "read_only": True,
            "changed_resources": [],
            "allowed_actions": ["approve", "request_changes", "dismiss"],
            "risk_level": "requires_approval",
        }

    def execute_tool_result(self, brief: dict) -> tuple[dict, dict]:
        import time

        start = time.perf_counter()
        draft = self._draft(brief if isinstance(brief, dict) else {})
        content = self._content(draft)
        return self._attempt(start, "succeeded"), {
            "content": content,
            "sell_price": None,
            "block": self._block(draft),
        }

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        failures = []
        lowered = content.lower() if isinstance(content, str) else ""
        if "google ads search text draft" not in lowered:
            failures.append("missing_google_ads_draft_heading")
        if "not published" not in lowered:
            failures.append("missing_not_published_boundary")
        if "no campaigns, ads, keywords, bids, or budgets were changed" not in lowered:
            failures.append("missing_no_mutation_note")
        for phrase in self.banned_phrases:
            if phrase.lower() in lowered:
                failures.append("banned_phrase_found:" + phrase)

        draft = self._draft(brief if isinstance(brief, dict) else {})
        if len(draft["headlines"]) < 10:
            failures.append("too_few_headlines")
        if len(draft["descriptions"]) < 4:
            failures.append("too_few_descriptions")
        for headline in draft["headlines"]:
            if len(headline) > self.max_headline_chars:
                failures.append("headline_too_long:" + headline)
        for description in draft["descriptions"]:
            if len(description) > self.max_description_chars:
                failures.append("description_too_long:" + description)
        return ("fail" if failures else "pass"), failures
