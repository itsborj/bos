from __future__ import annotations

from klaroha_sdk import ChannelModule


class SearchConsoleSpecialistOverviewModule(ChannelModule):
    id = "marketing.channel.search_console.specialist.overview"
    name = "Google Search Console Specialist"
    vertical = "marketing"
    capability = "marketing.optimize"
    platform_hint = "google search console"
    policy_default = "read_only"
    template = "marketing/channel/search_console/specialist/overview/template.j2"

    def execute_tool_result(self, brief: dict) -> tuple[dict, dict]:
        content = self._content()
        return {
            "provider": "google_search_console",
            "model_id": "specialist_overview",
            "mode": "deterministic",
            "status": "succeeded",
            "tokens_input": 0,
            "tokens_output": 0,
            "provider_cost": 0.0,
            "latency_ms": 0,
            "error": None,
        }, {
            "content": content,
            "sell_price": None,
            "block": {
                "type": "search_console_capability_card",
                "status": "needs_setup",
                "title": "Google Search Console Specialist",
                "read_only": True,
                "changed_resources": [],
                "jobs_supported": ["marketing.optimize"],
                "current_access_levels": {
                    "discover_properties": True,
                    "read_query_performance": True,
                    "read_page_performance": True,
                    "read_indexing_signals": True,
                    "read_sitemaps": True,
                    "inspect_url": True,
                    "draft_seo_opportunities": True,
                    "submit_sitemap": False,
                    "delete_sitemap": False,
                    "add_or_delete_site": False,
                    "change_site_or_search_console_settings": False,
                },
                "setup_required": [
                    "Verified Google Search Console property",
                    "Google OAuth access for an account with property permission",
                    "GOOGLE_SEARCH_CONSOLE_CLIENT_ID",
                    "GOOGLE_SEARCH_CONSOLE_CLIENT_SECRET",
                    "GOOGLE_SEARCH_CONSOLE_REFRESH_TOKEN",
                    "GOOGLE_SEARCH_CONSOLE_DEFAULT_SITE_URL",
                    "Brand-to-site property mapping",
                ],
            },
        }

    def _content(self) -> str:
        return "\n".join([
            "# Google Search Console Specialist",
            "",
            "Optimizes organic search by reading Search Console signals and turning them into reviewable SEO recommendations.",
            "",
            "What it can do:",
            "- Properties: confirm which Search Console sites are connected.",
            "- Performance: report queries, pages, clicks, impressions, CTR, and average position.",
            "- URL inspection: check indexing, crawl, canonical, robots, and rich-result signals for a URL.",
            "- Sitemaps: review sitemap status, warnings, errors, submitted URLs, and indexed counts.",
            "- SEO opportunities: surface low-CTR queries, page-two terms, visibility drops, and indexing gaps.",
            "",
            "Needed for setup:",
            "- A verified Google Search Console property for the site.",
            "- OAuth access for a Google account with permission to that property.",
            "- GOOGLE_SEARCH_CONSOLE_CLIENT_ID.",
            "- GOOGLE_SEARCH_CONSOLE_CLIENT_SECRET.",
            "- GOOGLE_SEARCH_CONSOLE_REFRESH_TOKEN.",
            "- GOOGLE_SEARCH_CONSOLE_DEFAULT_SITE_URL, such as sc-domain:example.com or https://www.example.com/.",
            "- Brand/site mapping so the property matches the brand being analyzed.",
            "",
            "Read-only note: no website content, Search Console settings, sitemaps, indexing requests, or properties are changed.",
        ])

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        failures: list[str] = []
        lowered = content.lower() if isinstance(content, str) else ""
        if "google search console specialist" not in lowered:
            failures.append("missing_specialist_heading")
        if "needed for setup" not in lowered:
            failures.append("missing_setup_requirements")
        if "read-only note" not in lowered:
            failures.append("missing_read_only_note")
        for term in ["submitted sitemap", "deleted sitemap", "requested indexing", "changed site"]:
            if term in lowered:
                failures.append("mutation_claim_found:" + term)
        return ("fail" if failures else "pass"), failures
