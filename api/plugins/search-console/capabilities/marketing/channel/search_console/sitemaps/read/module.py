from __future__ import annotations

from urllib.parse import quote

from klaroha_sdk import ChannelModule


class SearchConsoleSitemapsReadModule(ChannelModule):
    id = "marketing.channel.search_console.sitemaps.read"
    name = "Search Console Sitemap Report"
    vertical = "marketing"
    capability = "marketing.optimize"
    platform_hint = "search console sitemaps"
    policy_default = "read_only"
    template = "marketing/channel/search_console/sitemaps/read/template.j2"

    def _latency_ms(self, start):
        try:
            import time
            return round((time.perf_counter() - start) * 1000)
        except Exception:
            return 0

    def _attempt(self, start, status, error=None):
        return {"provider": "google_search_console", "model_id": "google_search_console_api_native", "mode": "tool", "status": status, "tokens_input": 0, "tokens_output": 0, "provider_cost": 0.0, "latency_ms": self._latency_ms(start), "error": error}

    def _failure(self, start, reason_code, message, details=None):
        return self._attempt(start, "failed", reason_code), {"content": "Failed to read Search Console sitemaps: " + message + "\n\nRead-only note: no sitemaps were submitted or deleted, and no website content was changed.", "sell_price": None, "block": {"type": "search_console_sitemap_report", "status": "failed", "reason_code": reason_code, "message": message, "details": details or {}, "read_only": True, "changed_resources": []}}

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

    def _sitemaps(self, data):
        rows = []
        for item in data.get("sitemap", []) if isinstance(data, dict) else []:
            contents = item.get("contents", []) or []
            submitted = sum(int(c.get("submitted") or 0) for c in contents if isinstance(c, dict))
            indexed = sum(int(c.get("indexed") or 0) for c in contents if isinstance(c, dict))
            errors = int(item.get("errors") or 0)
            warnings = int(item.get("warnings") or 0)
            signal = "healthy" if errors == 0 and warnings == 0 else "needs_review"
            rows.append({"feedpath": str(item.get("path") or ""), "type": str(item.get("type") or ""), "is_pending": bool(item.get("isPending")), "is_sitemaps_index": bool(item.get("isSitemapsIndex")), "last_submitted": item.get("lastSubmitted"), "last_downloaded": item.get("lastDownloaded"), "warnings": warnings, "errors": errors, "contents": contents, "submitted": submitted, "indexed": indexed, "signal": signal})
        return rows

    def _content(self, site_url, sitemaps):
        lines = ["# Search Console Sitemap Report", "", "Property: " + site_url, "Sitemaps returned: " + str(len(sitemaps)), "", "| Sitemap | Submitted | Indexed | Errors | Warnings | Signal |", "|---|---:|---:|---:|---:|---|"]
        for row in sitemaps:
            lines.append("| " + row["feedpath"] + " | " + str(row["submitted"]) + " | " + str(row["indexed"]) + " | " + str(row["errors"]) + " | " + str(row["warnings"]) + " | " + row["signal"] + " |")
        if not sitemaps:
            lines.append("| No submitted sitemaps returned | 0 | 0 | 0 | 0 | - |")
        lines.extend(["", "Read-only note: no sitemaps were submitted or deleted, and no website content was changed."])
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
            missing = [name for name, val in [("GOOGLE_SEARCH_CONSOLE_CLIENT_ID", client_id), ("GOOGLE_SEARCH_CONSOLE_CLIENT_SECRET", client_secret), ("GOOGLE_SEARCH_CONSOLE_REFRESH_TOKEN", refresh_token), ("GOOGLE_SEARCH_CONSOLE_DEFAULT_SITE_URL", site_url)] if not val]
            if missing:
                return self._failure(start, "missing_credentials", "missing required plugin environment variables: " + ", ".join(missing), {"missing": missing})
            token = self._refresh_access_token(client_id, client_secret, refresh_token)
            url = "https://www.googleapis.com/webmasters/v3/sites/" + quote(site_url, safe="") + "/sitemaps"
            data = self._get_json(url, {"Authorization": "Bearer " + token, "Accept": "application/json"})
            sitemaps = self._sitemaps(data)
            return self._attempt(start, "succeeded"), {"content": self._content(site_url, sitemaps), "sell_price": None, "block": {"type": "search_console_sitemap_report", "status": "succeeded", "site_url": site_url, "read_only": True, "changed_resources": [], "sitemaps": sitemaps, "sitemap_count": len(sitemaps), "allowed_next_steps": ["inspect_problem_urls", "draft_sitemap_fix_notes", "dismiss"]}}
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
        if "search console sitemap report" not in lowered:
            failures.append("missing_sitemap_report_heading")
        if "read-only note" not in lowered:
            failures.append("missing_read_only_note")
        for term in ["submitted sitemap", "deleted sitemap", "requested indexing"]:
            if term in lowered and "no sitemaps were submitted" not in lowered:
                failures.append("mutation_claim_found:" + term)
        return ("fail" if failures else "pass"), failures
