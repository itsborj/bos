from __future__ import annotations

from klaroha_sdk import ChannelModule


class SearchConsolePropertiesListModule(ChannelModule):
    id = "marketing.channel.search_console.properties.list"
    name = "Search Console Property Inventory"
    vertical = "marketing"
    capability = "marketing.optimize"
    platform_hint = "search console properties"
    policy_default = "read_only"
    template = "marketing/channel/search_console/properties/list/template.j2"

    def _latency_ms(self, start):
        try:
            import time
            return round((time.perf_counter() - start) * 1000)
        except Exception:
            return 0

    def _attempt(self, start, status, error=None):
        return {"provider": "google_search_console", "model_id": "google_search_console_api_native", "mode": "tool", "status": status, "tokens_input": 0, "tokens_output": 0, "provider_cost": 0.0, "latency_ms": self._latency_ms(start), "error": error}

    def _failure(self, start, reason_code, message, details=None):
        return self._attempt(start, "failed", reason_code), {"content": "Failed to list Search Console properties: " + message + "\n\nRead-only note: no Search Console settings, sitemaps, indexing requests, or website content were changed.", "sell_price": None, "block": {"type": "search_console_property_inventory", "status": "failed", "reason_code": reason_code, "message": message, "details": details or {}, "read_only": True, "changed_resources": []}}

    def _creds(self, brief):
        raw = brief.get("_channel_credentials", {}) if isinstance(brief, dict) else {}
        return raw if isinstance(raw, dict) else {}

    def _cred(self, creds, name, default=None):
        value = creds.get(name.lower()) or creds.get(name.upper()) or creds.get(name)
        if value is None:
            return default
        value = str(value).strip()
        return value or default

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

    def _get_json(self, url, headers):
        import json
        from urllib.request import Request, urlopen
        request = Request(url, headers=headers, method="GET")
        with urlopen(request, timeout=45) as response:
            return json.loads(response.read().decode("utf-8") or "{}")

    def _properties(self, data):
        rows = []
        for item in data.get("siteEntry", []) if isinstance(data, dict) else []:
            site_url = str(item.get("siteUrl") or "")
            rows.append({
                "site_url": site_url,
                "permission_level": str(item.get("permissionLevel") or ""),
                "property_type": "domain" if site_url.startswith("sc-domain:") else "url_prefix",
            })
        return rows

    def _content(self, properties, recommended):
        lines = ["# Search Console Property Inventory", "", "Properties returned: " + str(len(properties))]
        if recommended:
            lines.append("Recommended property: " + recommended)
        lines.extend(["", "| Property | Permission | Type |", "|---|---|---|"])
        for row in properties:
            lines.append("| " + row["site_url"] + " | " + row["permission_level"] + " | " + row["property_type"] + " |")
        if not properties:
            lines.append("| No properties returned | - | - |")
        lines.extend(["", "Read-only note: no Search Console settings, sitemaps, indexing requests, or website content were changed."])
        return "\n".join(lines)

    def execute_tool_result(self, brief: dict) -> tuple[dict, dict]:
        import time
        start = time.perf_counter()
        try:
            creds = self._creds(brief if isinstance(brief, dict) else {})
            client_id = self._cred(creds, "google_search_console_client_id")
            client_secret = self._cred(creds, "google_search_console_client_secret")
            refresh_token = self._cred(creds, "google_search_console_refresh_token")
            default_site = self._cred(creds, "google_search_console_default_site_url", "")
            missing = [name for name, val in [("GOOGLE_SEARCH_CONSOLE_CLIENT_ID", client_id), ("GOOGLE_SEARCH_CONSOLE_CLIENT_SECRET", client_secret), ("GOOGLE_SEARCH_CONSOLE_REFRESH_TOKEN", refresh_token)] if not val]
            if missing:
                return self._failure(start, "missing_credentials", "missing required plugin environment variables: " + ", ".join(missing), {"missing": missing})
            token = self._refresh_access_token(client_id, client_secret, refresh_token)
            data = self._get_json("https://www.googleapis.com/webmasters/v3/sites", {"Authorization": "Bearer " + token, "Accept": "application/json"})
            properties = self._properties(data)
            recommended = default_site or (properties[0]["site_url"] if properties else "")
            return self._attempt(start, "succeeded"), {"content": self._content(properties, recommended), "sell_price": None, "block": {"type": "search_console_property_inventory", "status": "succeeded", "read_only": True, "changed_resources": [], "connector": {"protocol": "google_search_console_api", "connection_status": "active", "host_injected_credentials": True}, "properties": properties, "property_count": len(properties), "recommended_property": recommended, "warnings": ["URL-prefix properties require exact protocol and trailing slash. Domain properties use sc-domain:example.com."]}}
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
        if "search console property inventory" not in lowered:
            failures.append("missing_property_inventory_heading")
        if "read-only note" not in lowered:
            failures.append("missing_read_only_note")
        for term in ["submitted sitemap", "deleted sitemap", "requested indexing", "changed site"]:
            if term in lowered:
                failures.append("mutation_claim_found:" + term)
        return ("fail" if failures else "pass"), failures
