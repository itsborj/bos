from __future__ import annotations

import re
from urllib.parse import quote

from klaroha_sdk import ChannelModule


class SearchConsoleUrlInspectModule(ChannelModule):
    id = "marketing.channel.search_console.url.inspect"
    name = "Search Console URL Inspection"
    vertical = "marketing"
    capability = "marketing.optimize"
    platform_hint = "search console url inspection"
    policy_default = "read_only"
    template = "marketing/channel/search_console/url/inspect/template.j2"

    def _latency_ms(self, start):
        try:
            import time
            return round((time.perf_counter() - start) * 1000)
        except Exception:
            return 0

    def _attempt(self, start, status, error=None):
        return {"provider": "google_search_console", "model_id": "google_search_console_api_native", "mode": "tool", "status": status, "tokens_input": 0, "tokens_output": 0, "provider_cost": 0.0, "latency_ms": self._latency_ms(start), "error": error}

    def _failure(self, start, reason_code, message, details=None):
        return self._attempt(start, "failed", reason_code), {"content": "Failed to inspect Search Console URL: " + message + "\n\nRead-only note: no indexing request, sitemap change, Search Console setting, or website content was changed.", "sell_price": None, "block": {"type": "search_console_url_inspection", "status": "failed", "reason_code": reason_code, "message": message, "details": details or {}, "read_only": True, "changed_resources": []}}

    def _creds(self, brief):
        raw = brief.get("_channel_credentials", {}) if isinstance(brief, dict) else {}
        return raw if isinstance(raw, dict) else {}

    def _cred(self, creds, name, default=None):
        value = creds.get(name.lower()) or creds.get(name.upper()) or creds.get(name)
        if value is None:
            return default
        value = str(value).strip()
        return value or default

    def _site_url(self, brief, creds):
        return str((brief or {}).get("site_url") or (brief or {}).get("search_console_site_url") or self._cred(creds, "google_search_console_default_site_url", "")).strip()

    def _inspection_url(self, brief):
        if isinstance(brief, dict):
            direct = brief.get("inspection_url") or brief.get("url") or brief.get("page_url")
            if direct:
                return str(direct).strip()
            ctx = str(brief.get("conversation_context") or "")
            match = re.search(r"https?://[^\s)\]>\"']+", ctx)
            if match:
                return match.group(0).rstrip(".,")
        return ""

    def _refresh_access_token(self, client_id, client_secret, refresh_token):
        import json
        from urllib.parse import urlencode
        from urllib.request import Request, urlopen
        payload = urlencode({"client_id": client_id, "client_secret": client_secret, "refresh_token": refresh_token, "grant_type": "refresh_token"}).encode("utf-8")
        request = Request("https://oauth2.googleapis.com/token", data=payload, headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}, method="POST")
        with urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8") or "{}")
        token = str(data.get("access_token") or "").strip()
        if not token:
            raise RuntimeError("Google OAuth token refresh did not return an access_token")
        return token

    def _post_json(self, url, headers, payload):
        import json
        from urllib.request import Request, urlopen
        request = Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        with urlopen(request, timeout=45) as response:
            return json.loads(response.read().decode("utf-8") or "{}")

    def _inspection(self, data):
        result = data.get("inspectionResult", {}) if isinstance(data, dict) else {}
        index = result.get("indexStatusResult", {}) or {}
        rich = result.get("richResultsResult", {}) or {}
        return {
            "verdict": index.get("verdict"),
            "coverage_state": index.get("coverageState"),
            "robots_txt_state": index.get("robotsTxtState"),
            "indexing_state": index.get("indexingState"),
            "last_crawl_time": index.get("lastCrawlTime"),
            "google_canonical": index.get("googleCanonical"),
            "user_canonical": index.get("userCanonical"),
            "rich_results": {"detected": bool(rich), "verdict": rich.get("verdict"), "items": [item.get("richResultType") for item in rich.get("detectedItems", []) if isinstance(item, dict) and item.get("richResultType")]},
        }

    def _content(self, site_url, inspection_url, inspection):
        lines = ["# Search Console URL Inspection", "", "Property: " + site_url, "URL: " + inspection_url, "", "Indexing:", "- Verdict: " + str(inspection.get("verdict") or "unknown"), "- Coverage: " + str(inspection.get("coverage_state") or "unknown"), "- Robots.txt: " + str(inspection.get("robots_txt_state") or "unknown"), "- Indexing: " + str(inspection.get("indexing_state") or "unknown"), "- Last crawl: " + str(inspection.get("last_crawl_time") or "unknown"), "", "Read-only note: no indexing request, sitemap change, Search Console setting, or website content was changed."]
        return "\n".join(lines)

    def execute_tool_result(self, brief: dict) -> tuple[dict, dict]:
        import time
        start = time.perf_counter()
        try:
            brief = brief if isinstance(brief, dict) else {}
            creds = self._creds(brief)
            client_id = self._cred(creds, "google_search_console_client_id")
            client_secret = self._cred(creds, "google_search_console_client_secret")
            refresh_token = self._cred(creds, "google_search_console_refresh_token")
            site_url = self._site_url(brief, creds)
            inspection_url = self._inspection_url(brief)
            missing = [name for name, val in [("GOOGLE_SEARCH_CONSOLE_CLIENT_ID", client_id), ("GOOGLE_SEARCH_CONSOLE_CLIENT_SECRET", client_secret), ("GOOGLE_SEARCH_CONSOLE_REFRESH_TOKEN", refresh_token), ("GOOGLE_SEARCH_CONSOLE_DEFAULT_SITE_URL", site_url)] if not val]
            if not inspection_url:
                missing.append("inspection_url")
            if missing:
                return self._failure(start, "missing_required_input", "missing required values: " + ", ".join(missing), {"missing": missing})
            token = self._refresh_access_token(client_id, client_secret, refresh_token)
            data = self._post_json("https://searchconsole.googleapis.com/v1/urlInspection/index:inspect", {"Authorization": "Bearer " + token, "Content-Type": "application/json", "Accept": "application/json"}, {"inspectionUrl": inspection_url, "siteUrl": site_url, "languageCode": str(brief.get("language_code") or "en-US")})
            inspection = self._inspection(data)
            return self._attempt(start, "succeeded"), {"content": self._content(site_url, inspection_url, inspection), "sell_price": None, "block": {"type": "search_console_url_inspection", "status": "succeeded", "site_url": site_url, "inspection_url": inspection_url, "read_only": True, "changed_resources": [], "indexing": {k: inspection.get(k) for k in ["verdict", "coverage_state", "robots_txt_state", "indexing_state", "last_crawl_time", "google_canonical", "user_canonical"]}, "rich_results": inspection.get("rich_results"), "warnings": ["Inspection URL must belong under the selected Search Console property."]}}
        except Exception as exc:
            from urllib.error import HTTPError, URLError
            if isinstance(exc, HTTPError):
                try:
                    body = exc.read().decode("utf-8")
                except Exception:
                    body = ""
                return self._failure(start, "api_call_failed", "Google Search Console API returned HTTP " + str(getattr(exc, "code", "error")), {"http_status": getattr(exc, "code", None), "response": body})
            if isinstance(exc, URLError):
                return self._failure(start, "api_call_failed", "network error calling Google Search Console API", {"error": str(exc)})
            return self._failure(start, "api_call_failed", "unexpected error calling Google Search Console API", {"error": str(exc)})

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        failures = []
        lowered = content.lower() if isinstance(content, str) else ""
        if "search console url inspection" not in lowered:
            failures.append("missing_url_inspection_heading")
        if "read-only note" not in lowered:
            failures.append("missing_read_only_note")
        for term in ["requested indexing", "submitted sitemap", "changed site"]:
            if term in lowered:
                failures.append("mutation_claim_found:" + term)
        return ("fail" if failures else "pass"), failures
