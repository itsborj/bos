from __future__ import annotations

from datetime import date, timedelta
from urllib.parse import quote

from klaroha_sdk import ChannelModule


class SearchConsoleOpportunitiesPlanModule(ChannelModule):
    id = "marketing.channel.search_console.opportunities.plan"
    name = "Search Console SEO Opportunity Plan"
    vertical = "marketing"
    capability = "marketing.optimize"
    platform_hint = "search console seo opportunities"
    policy_default = "read_only"
    template = "marketing/channel/search_console/opportunities/plan/template.j2"

    def _latency_ms(self, start):
        try:
            import time
            return round((time.perf_counter() - start) * 1000)
        except Exception:
            return 0

    def _attempt(self, start, status, error=None):
        return {"provider": "google_search_console", "model_id": "google_search_console_api_native", "mode": "tool", "status": status, "tokens_input": 0, "tokens_output": 0, "provider_cost": 0.0, "latency_ms": self._latency_ms(start), "error": error}

    def _failure(self, start, reason_code, message, details=None):
        return self._attempt(start, "failed", reason_code), {"content": "Failed to create Search Console opportunity plan: " + message + "\n\nRead-only note: no Search Console settings, sitemaps, indexing requests, or website content were changed.", "sell_price": None, "block": {"type": "search_console_opportunity_plan", "status": "failed", "reason_code": reason_code, "message": message, "details": details or {}, "read_only": True, "changed_resources": []}}

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

    def _post_json(self, url, headers, payload):
        import json
        from urllib.request import Request, urlopen
        request = Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        with urlopen(request, timeout=45) as response:
            return json.loads(response.read().decode("utf-8") or "{}")

    def _query_rows(self, data, key_name):
        rows = []
        for item in data.get("rows", []) if isinstance(data, dict) else []:
            keys = item.get("keys") or []
            key = str(keys[0]) if keys else ""
            rows.append({key_name: key, "clicks": int(float(item.get("clicks") or 0)), "impressions": int(float(item.get("impressions") or 0)), "ctr": round(float(item.get("ctr") or 0) * 100, 2), "position": round(float(item.get("position") or 0), 2)})
        return rows

    def _opportunities(self, queries, pages):
        opps = []
        idx = 1
        for row in queries:
            if row["impressions"] >= 1000 and row["ctr"] < 1.0 and row["position"] <= 15:
                opps.append({"opportunity_id": f"seo_{idx:03d}", "severity": "high", "type": "low_ctr_high_impression_query", "evidence": "Query '" + row["query"] + "' has " + f"{row['impressions']:,}" + " impressions, position " + str(row["position"]) + ", but only " + f"{row['ctr']:.2f}% CTR.", "recommended_action": "Draft title/meta updates or page copy improvements aligned to this query's intent.", "proposed_artifact": "seo_title_meta_update_draft", "requires_site_change": True, "auto_apply": False})
                idx += 1
            elif row["impressions"] >= 500 and 10 < row["position"] <= 20:
                opps.append({"opportunity_id": f"seo_{idx:03d}", "severity": "medium", "type": "page_two_keyword", "evidence": "Query '" + row["query"] + "' averages position " + str(row["position"]) + " with " + f"{row['impressions']:,}" + " impressions.", "recommended_action": "Draft a content optimization brief and internal-link recommendations.", "proposed_artifact": "content_optimization_brief", "requires_site_change": True, "auto_apply": False})
                idx += 1
            if len(opps) >= 5:
                break
        if not opps and pages:
            page = pages[0]
            opps.append({"opportunity_id": "seo_001", "severity": "low", "type": "monitor_core_visibility_page", "evidence": "Top page '" + page["page"] + "' has " + f"{page['impressions']:,}" + " impressions and " + str(page["position"]) + " average position.", "recommended_action": "Monitor this page and compare against branded/non-branded query groups.", "proposed_artifact": "seo_monitoring_note", "requires_site_change": False, "auto_apply": False})
        return opps

    def _content(self, site_url, opps):
        lines = ["# Search Console SEO Opportunity Plan", "", "Property: " + site_url, "Opportunities found: " + str(len(opps)), ""]
        for opp in opps:
            lines.append("- " + opp["opportunity_id"] + " — " + opp["type"] + ": " + opp["evidence"])
        lines.extend(["", "Read-only note: no Search Console settings, sitemaps, indexing requests, or website content were changed."])
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
            site_url = str(brief.get("site_url") or brief.get("search_console_site_url") or self._cred(creds, "google_search_console_default_site_url", "")).strip()
            missing = [name for name, val in [("GOOGLE_SEARCH_CONSOLE_CLIENT_ID", client_id), ("GOOGLE_SEARCH_CONSOLE_CLIENT_SECRET", client_secret), ("GOOGLE_SEARCH_CONSOLE_REFRESH_TOKEN", refresh_token), ("GOOGLE_SEARCH_CONSOLE_DEFAULT_SITE_URL", site_url)] if not val]
            if missing:
                return self._failure(start, "missing_credentials", "missing required plugin environment variables: " + ", ".join(missing), {"missing": missing})
            end = date.today()
            start_date = (end - timedelta(days=28)).isoformat()
            end_date = end.isoformat()
            token = self._refresh_access_token(client_id, client_secret, refresh_token)
            base = "https://www.googleapis.com/webmasters/v3/sites/" + quote(site_url, safe="") + "/searchAnalytics/query"
            headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json", "Accept": "application/json"}
            query_payload = {"startDate": start_date, "endDate": end_date, "dimensions": ["query"], "rowLimit": 1000, "searchType": "web", "dataState": "final"}
            page_payload = dict(query_payload, dimensions=["page"])
            queries = self._query_rows(self._post_json(base, headers, query_payload), "query")
            pages = self._query_rows(self._post_json(base, headers, page_payload), "page")
            opps = self._opportunities(queries, pages)
            return self._attempt(start, "succeeded"), {"content": self._content(site_url, opps), "sell_price": None, "block": {"type": "search_console_opportunity_plan", "status": "pending_review", "risk_level": "review_only", "site_url": site_url, "date_range": {"start_date": start_date, "end_date": end_date}, "read_only": True, "changed_resources": [], "summary": "Found " + str(len(opps)) + " organic search opportunities from Search Console data.", "opportunities": opps, "allowed_actions": ["draft_content_brief", "draft_title_meta_updates", "inspect_selected_urls", "dismiss"], "forbidden_actions": ["auto_edit_website", "claim_rankings_will_improve", "submit_sitemap_without_approval", "request_indexing_without_approval"]}}
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
        if "search console seo opportunity plan" not in lowered:
            failures.append("missing_opportunity_plan_heading")
        if "read-only note" not in lowered:
            failures.append("missing_read_only_note")
        for term in ["submitted sitemap", "requested indexing", "changed site"]:
            if term in lowered:
                failures.append("mutation_claim_found:" + term)
        return ("fail" if failures else "pass"), failures
