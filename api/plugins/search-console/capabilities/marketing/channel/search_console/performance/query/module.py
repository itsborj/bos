from __future__ import annotations

from datetime import date, timedelta
from urllib.parse import quote

from klaroha_sdk import ChannelModule


class SearchConsolePerformanceQueryModule(ChannelModule):
    id = "marketing.channel.search_console.performance.query"
    name = "Search Console Performance Report"
    vertical = "marketing"
    capability = "marketing.optimize"
    platform_hint = "search console performance"
    policy_default = "read_only"
    template = "marketing/channel/search_console/performance/query/template.j2"

    def _latency_ms(self, start):
        try:
            import time
            return round((time.perf_counter() - start) * 1000)
        except Exception:
            return 0

    def _attempt(self, start, status, error=None):
        return {"provider": "google_search_console", "model_id": "google_search_console_api_native", "mode": "tool", "status": status, "tokens_input": 0, "tokens_output": 0, "provider_cost": 0.0, "latency_ms": self._latency_ms(start), "error": error}

    def _failure(self, start, reason_code, message, details=None):
        return self._attempt(start, "failed", reason_code), {"content": "Failed to query Search Console performance: " + message + "\n\nRead-only note: no Search Console settings, sitemaps, indexing requests, or website content were changed.", "sell_price": None, "block": {"type": "search_console_performance_report", "status": "failed", "reason_code": reason_code, "message": message, "details": details or {}, "read_only": True, "changed_resources": []}}

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

    def _date_range(self, brief):
        end = date.today()
        start = end - timedelta(days=28)
        if isinstance(brief, dict):
            if brief.get("start_date") and brief.get("end_date"):
                return str(brief["start_date"]), str(brief["end_date"])
            ctx = str(brief.get("conversation_context") or "").lower()
            if "last 7" in ctx or "past 7" in ctx:
                start = end - timedelta(days=7)
            elif "last 90" in ctx or "past 90" in ctx:
                start = end - timedelta(days=90)
        return start.isoformat(), end.isoformat()

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

    def _rows(self, data, key_name):
        rows = []
        for item in data.get("rows", []) if isinstance(data, dict) else []:
            keys = item.get("keys") or []
            key = str(keys[0]) if keys else ""
            clicks = int(float(item.get("clicks") or 0))
            impressions = int(float(item.get("impressions") or 0))
            ctr = round(float(item.get("ctr") or 0) * 100, 2)
            position = round(float(item.get("position") or 0), 2)
            signal = "strong"
            if impressions >= 1000 and ctr < 1.0 and position <= 15:
                signal = "ctr_opportunity"
            elif 10 < position <= 20 and impressions >= 500:
                signal = "page_two_opportunity"
            rows.append({key_name: key, "clicks": clicks, "impressions": impressions, "ctr": ctr, "position": position, "signal": signal})
        return rows

    def _totals(self, data, query_rows, page_rows):
        total_rows = data.get("rows", []) if isinstance(data, dict) else []
        if total_rows:
            item = total_rows[0]
            return {"clicks": int(float(item.get("clicks") or 0)), "impressions": int(float(item.get("impressions") or 0)), "ctr": round(float(item.get("ctr") or 0) * 100, 2), "average_position": round(float(item.get("position") or 0), 2)}
        clicks = sum(row["clicks"] for row in query_rows)
        impressions = sum(row["impressions"] for row in query_rows)
        ctr = round((clicks / impressions) * 100, 2) if impressions else 0.0
        avg_position = round(sum(row["position"] for row in query_rows) / len(query_rows), 2) if query_rows else 0.0
        return {"clicks": clicks, "impressions": impressions, "ctr": ctr, "average_position": avg_position}

    def _content(self, site_url, start_date, end_date, totals, queries, pages):
        lines = ["# Search Console Performance Report", "", "Property: " + site_url, "Date range: " + start_date + " to " + end_date, "", "Totals:", "- Clicks: " + f"{totals['clicks']:,}", "- Impressions: " + f"{totals['impressions']:,}", "- CTR: " + f"{totals['ctr']:.2f}%", "- Average position: " + f"{totals['average_position']:.2f}", "", "Top query opportunities:"]
        for row in queries[:5]:
            lines.append("- " + row["query"] + " — " + str(row["clicks"]) + " clicks, " + str(row["impressions"]) + " impressions, " + f"{row['ctr']:.2f}% CTR, pos. " + str(row["position"]) + " (" + row["signal"] + ")")
        lines.extend(["", "Top pages:"])
        for row in pages[:5]:
            lines.append("- " + row["page"] + " — " + str(row["clicks"]) + " clicks, " + str(row["impressions"]) + " impressions, pos. " + str(row["position"]))
        lines.extend(["", "Read-only note: no Search Console settings, sitemaps, indexing requests, or website content were changed."])
        return "\n".join(lines)

    def _query(self, site_url, token, start_date, end_date, dimensions, row_limit=1000):
        url = "https://www.googleapis.com/webmasters/v3/sites/" + quote(site_url, safe="") + "/searchAnalytics/query"
        payload = {"startDate": start_date, "endDate": end_date, "dimensions": dimensions, "rowLimit": row_limit, "startRow": 0, "searchType": "web", "aggregationType": "auto", "dataState": "final"}
        return self._post_json(url, {"Authorization": "Bearer " + token, "Content-Type": "application/json", "Accept": "application/json"}, payload)

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
            start_date, end_date = self._date_range(brief)
            token = self._refresh_access_token(client_id, client_secret, refresh_token)
            totals_data = self._query(site_url, token, start_date, end_date, [], 1)
            query_data = self._query(site_url, token, start_date, end_date, ["query"], 1000)
            page_data = self._query(site_url, token, start_date, end_date, ["page"], 1000)
            queries = self._rows(query_data, "query")
            pages = self._rows(page_data, "page")
            totals = self._totals(totals_data, queries, pages)
            content = self._content(site_url, start_date, end_date, totals, queries, pages)
            return self._attempt(start, "succeeded"), {"content": content, "sell_price": None, "block": {"type": "search_console_performance_report", "status": "succeeded", "site_url": site_url, "date_range": {"start_date": start_date, "end_date": end_date, "data_delay_note": "Search Console data can lag by 2–3 days; fresh data may still change."}, "search_type": "web", "dimensions": ["query", "page"], "read_only": True, "changed_resources": [], "totals": totals, "top_queries": queries, "top_pages": pages, "pagination": {"row_limit": 1000, "start_row": 0, "max_rows_per_request": 25000}}}
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
        if "search console performance report" not in lowered:
            failures.append("missing_performance_report_heading")
        if "read-only note" not in lowered:
            failures.append("missing_read_only_note")
        for term in ["submitted sitemap", "deleted sitemap", "requested indexing", "changed site"]:
            if term in lowered:
                failures.append("mutation_claim_found:" + term)
        return ("fail" if failures else "pass"), failures
