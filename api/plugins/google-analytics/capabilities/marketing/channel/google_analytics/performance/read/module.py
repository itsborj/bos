from __future__ import annotations

from klaroha_sdk import ChannelModule


class GoogleAnalyticsReadOnlyDataPullModule(ChannelModule):
    id = "marketing.channel.google_analytics.performance.read"
    name = "Google Analytics Read-Only Data Pull"
    vertical = "marketing"
    capability = "marketing.optimize"
    platform_hint = "google analytics"
    policy_default = "read_only"
    template = "marketing/channel/google_analytics/performance/read/template.j2"

    max_chars = 0
    must_mention = []
    banned_phrases = []

    def _latency_ms(self, start):
        try:
            import time
            return round((time.perf_counter() - start) * 1000)
        except Exception:
            return 0

    def _attempt(self, start, status, error=None):
        return {
            "provider": "google_analytics",
            "model_id": "ga4_data_api_rest",
            "mode": "tool",
            "status": status,
            "tokens_input": 0,
            "tokens_output": 0,
            "provider_cost": 0.0,
            "latency_ms": self._latency_ms(start),
            "error": error,
        }

    def _failure(self, start, reason_code, message, details=None):
        details = details or {}
        return self._attempt(start, "failed", reason_code), {
            "content": "Failed to pull Google Analytics data: " + message + "\n\nRead-only note: no Google Analytics properties, audiences, conversions, tags, campaigns, bids, or budgets were changed.",
            "sell_price": None,
            "block": {
                "type": "google_analytics_data_pull",
                "status": "failed",
                "reason_code": reason_code,
                "message": message,
                "details": details,
                "read_only": True,
                "changed_resources": [],
            },
        }

    def _creds(self, brief):
        raw = brief.get("_channel_credentials", {}) if isinstance(brief, dict) else {}
        return raw if isinstance(raw, dict) else {}

    def _cred(self, creds, name, default=None):
        value = creds.get(name.lower()) or creds.get(name.upper()) or creds.get(name)
        if value is None:
            return default
        value = str(value).strip()
        return value or default

    def _property_id(self, value):
        value = str(value or "").strip()
        if value.startswith("properties/"):
            value = value.split("/", 1)[1]
        return value.replace(" ", "")

    def _date_range(self, brief):
        explicit = str(
            brief.get("google_analytics_date_range")
            or brief.get("ga4_date_range")
            or brief.get("date_range")
            or brief.get("dateRange")
            or ""
        ).strip().upper()

        context = str(brief.get("conversation_context") or "").lower()
        if not explicit:
            if "last 7" in context or "past 7" in context:
                explicit = "LAST_7_DAYS"
            elif "last 14" in context or "past 14" in context:
                explicit = "LAST_14_DAYS"
            elif "last 90" in context or "past 90" in context:
                explicit = "LAST_90_DAYS"
            elif "last month" in context:
                explicit = "LAST_MONTH"
            elif "this month" in context:
                explicit = "THIS_MONTH"
            elif "yesterday" in context:
                explicit = "YESTERDAY"
            elif "today" in context:
                explicit = "TODAY"
            else:
                explicit = "LAST_30_DAYS"

        ranges = {
            "TODAY": ("today", "today"),
            "YESTERDAY": ("yesterday", "yesterday"),
            "LAST_7_DAYS": ("7daysAgo", "yesterday"),
            "LAST_14_DAYS": ("14daysAgo", "yesterday"),
            "LAST_30_DAYS": ("30daysAgo", "yesterday"),
            "LAST_90_DAYS": ("90daysAgo", "yesterday"),
            "THIS_MONTH": ("firstDayOfMonth", "today"),
            "LAST_MONTH": ("firstDayOfLastMonth", "lastDayOfLastMonth"),
        }
        if explicit not in ranges:
            explicit = "LAST_30_DAYS"
        start_date, end_date = ranges[explicit]
        return explicit, start_date, end_date

    def _to_int(self, value):
        try:
            return int(float(value or 0))
        except Exception:
            return 0

    def _to_float(self, value):
        try:
            return float(value or 0)
        except Exception:
            return 0.0

    def _fmt_int(self, value):
        return f"{self._to_int(value):,}"

    def _fmt_rate(self, value):
        try:
            return f"{float(value) * 100:.2f}%"
        except Exception:
            return "0.00%"

    def _refresh_access_token(self, client_id, client_secret, refresh_token):
        import json
        from urllib.parse import urlencode
        from urllib.request import Request, urlopen

        payload = urlencode({
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }).encode("utf-8")
        request = Request(
            "https://oauth2.googleapis.com/token",
            data=payload,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            method="POST",
        )
        with urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
            data = json.loads(body) if body else {}
        token = str(data.get("access_token") or "").strip()
        if not token:
            raise RuntimeError("Google OAuth token refresh did not return an access_token")
        return token

    def _post_json(self, url, headers, payload):
        import json
        from urllib.request import Request, urlopen

        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urlopen(request, timeout=45) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}

    def _run_report(self, access_token, property_id, start_date, end_date, dimensions, metrics, limit=10, order_metric="sessions"):
        url = "https://analyticsdata.googleapis.com/v1beta/properties/" + property_id + ":runReport"
        headers = {
            "Authorization": "Bearer " + access_token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {
            "dateRanges": [{"startDate": start_date, "endDate": end_date}],
            "metrics": [{"name": name} for name in metrics],
            "limit": str(limit),
        }
        if dimensions:
            payload["dimensions"] = [{"name": name} for name in dimensions]
        if order_metric:
            payload["orderBys"] = [{"metric": {"metricName": order_metric}, "desc": True}]
        return self._post_json(url, headers, payload)

    def _parse_rows(self, response):
        dimension_headers = [str(item.get("name") or "") for item in response.get("dimensionHeaders", []) if isinstance(item, dict)]
        metric_headers = [str(item.get("name") or "") for item in response.get("metricHeaders", []) if isinstance(item, dict)]
        rows = []
        for item in response.get("rows", []) or []:
            if not isinstance(item, dict):
                continue
            row = {}
            dimension_values = item.get("dimensionValues", []) or []
            metric_values = item.get("metricValues", []) or []
            for idx, header in enumerate(dimension_headers):
                value = ""
                if idx < len(dimension_values) and isinstance(dimension_values[idx], dict):
                    value = dimension_values[idx].get("value") or ""
                row[header] = value
            for idx, header in enumerate(metric_headers):
                value = "0"
                if idx < len(metric_values) and isinstance(metric_values[idx], dict):
                    value = metric_values[idx].get("value") or "0"
                row[header] = value
            rows.append(row)
        return rows

    def _summary(self, response):
        rows = self._parse_rows(response)
        row = rows[0] if rows else {}
        return {
            "sessions": self._to_int(row.get("sessions")),
            "users": self._to_int(row.get("totalUsers")),
            "engaged_sessions": self._to_int(row.get("engagedSessions")),
            "conversions": self._to_float(row.get("conversions")),
            "session_conversion_rate": self._to_float(row.get("sessionConversionRate")),
            "engagement_rate": self._to_float(row.get("engagementRate")),
        }

    def _traffic_sources(self, response):
        rows = []
        for row in self._parse_rows(response):
            rows.append({
                "source_medium": str(row.get("sessionSourceMedium") or "(not set)"),
                "sessions": self._to_int(row.get("sessions")),
                "users": self._to_int(row.get("totalUsers")),
                "engaged_sessions": self._to_int(row.get("engagedSessions")),
                "conversions": self._to_float(row.get("conversions")),
            })
        return rows

    def _landing_pages(self, response):
        rows = []
        for row in self._parse_rows(response):
            rows.append({
                "path": str(row.get("landingPagePlusQueryString") or "(not set)"),
                "sessions": self._to_int(row.get("sessions")),
                "users": self._to_int(row.get("totalUsers")),
                "conversions": self._to_float(row.get("conversions")),
                "engagement_rate": self._to_float(row.get("engagementRate")),
            })
        return rows

    def _content(self, property_id, date_range, summary, traffic_sources, landing_pages):
        lines = [
            "# Google Analytics Data Pull",
            "",
            "Property: " + property_id,
            "Date range: " + date_range,
            "",
            "## Summary",
            "- Sessions: " + self._fmt_int(summary.get("sessions")),
            "- Users: " + self._fmt_int(summary.get("users")),
            "- Engaged sessions: " + self._fmt_int(summary.get("engaged_sessions")),
            "- Conversions: " + f"{float(summary.get('conversions') or 0):,.2f}",
            "- Session conversion rate: " + self._fmt_rate(summary.get("session_conversion_rate")),
            "- Engagement rate: " + self._fmt_rate(summary.get("engagement_rate")),
            "",
            "## Top traffic sources",
            "| Source / Medium | Sessions | Users | Engaged Sessions | Conversions |",
            "|---|---:|---:|---:|---:|",
        ]
        if traffic_sources:
            for row in traffic_sources:
                lines.append(
                    "| "
                    + row["source_medium"]
                    + " | "
                    + self._fmt_int(row["sessions"])
                    + " | "
                    + self._fmt_int(row["users"])
                    + " | "
                    + self._fmt_int(row["engaged_sessions"])
                    + " | "
                    + f"{float(row['conversions'] or 0):,.2f}"
                    + " |"
                )
        else:
            lines.append("| No traffic source rows returned | 0 | 0 | 0 | 0.00 |")

        lines.extend([
            "",
            "## Top landing pages",
            "| Landing Page | Sessions | Users | Conversions | Engagement Rate |",
            "|---|---:|---:|---:|---:|",
        ])
        if landing_pages:
            for row in landing_pages:
                lines.append(
                    "| "
                    + row["path"].replace("|", "\\|")
                    + " | "
                    + self._fmt_int(row["sessions"])
                    + " | "
                    + self._fmt_int(row["users"])
                    + " | "
                    + f"{float(row['conversions'] or 0):,.2f}"
                    + " | "
                    + self._fmt_rate(row["engagement_rate"])
                    + " |"
                )
        else:
            lines.append("| No landing page rows returned | 0 | 0 | 0.00 | 0.00% |")

        lines.extend([
            "",
            "Read-only note: no Google Analytics properties, audiences, conversions, tags, campaigns, bids, or budgets were changed.",
        ])
        return "\n".join(lines)

    def execute_tool_result(self, brief: dict) -> tuple[dict, dict]:
        import time

        start = time.perf_counter()
        try:
            if not isinstance(brief, dict):
                return self._failure(start, "invalid_brief", "brief must be a dictionary")

            creds = self._creds(brief)
            client_id = self._cred(creds, "google_analytics_client_id")
            client_secret = self._cred(creds, "google_analytics_client_secret")
            refresh_token = self._cred(creds, "google_analytics_refresh_token")
            property_id = self._property_id(
                brief.get("google_analytics_property_id")
                or brief.get("ga4_property_id")
                or brief.get("property_id")
                or self._cred(creds, "google_analytics_property_id")
            )
            date_range, start_date, end_date = self._date_range(brief)

            missing = []
            if not client_id:
                missing.append("GOOGLE_ANALYTICS_CLIENT_ID")
            if not client_secret:
                missing.append("GOOGLE_ANALYTICS_CLIENT_SECRET")
            if not refresh_token:
                missing.append("GOOGLE_ANALYTICS_REFRESH_TOKEN")
            if not property_id:
                missing.append("GOOGLE_ANALYTICS_PROPERTY_ID")
            if missing:
                return self._failure(
                    start,
                    "missing_credentials",
                    "missing required plugin environment variables: " + ", ".join(missing),
                    {"missing": missing},
                )

            access_token = self._refresh_access_token(client_id, client_secret, refresh_token)
            summary_response = self._run_report(
                access_token,
                property_id,
                start_date,
                end_date,
                [],
                ["sessions", "totalUsers", "engagedSessions", "conversions", "sessionConversionRate", "engagementRate"],
                limit=1,
                order_metric=None,
            )
            source_response = self._run_report(
                access_token,
                property_id,
                start_date,
                end_date,
                ["sessionSourceMedium"],
                ["sessions", "totalUsers", "engagedSessions", "conversions"],
                limit=10,
                order_metric="sessions",
            )
            landing_response = self._run_report(
                access_token,
                property_id,
                start_date,
                end_date,
                ["landingPagePlusQueryString"],
                ["sessions", "totalUsers", "conversions", "engagementRate"],
                limit=10,
                order_metric="sessions",
            )

            summary = self._summary(summary_response)
            traffic_sources = self._traffic_sources(source_response)
            landing_pages = self._landing_pages(landing_response)
            content = self._content(property_id, date_range, summary, traffic_sources, landing_pages)

            return self._attempt(start, "succeeded"), {
                "content": content,
                "sell_price": None,
                "block": {
                    "type": "google_analytics_data_pull",
                    "status": "succeeded",
                    "property_id": property_id,
                    "date_range": date_range,
                    "summary": summary,
                    "traffic_sources": traffic_sources,
                    "landing_pages": landing_pages,
                    "read_only": True,
                    "changed_resources": [],
                    "allowed_actions": ["revise", "dismiss", "save_learning"],
                    "risk_policy": "read_only_no_mutation",
                },
            }

        except Exception as exc:
            from urllib.error import HTTPError, URLError

            if isinstance(exc, HTTPError):
                try:
                    error_body = exc.read().decode("utf-8")
                except Exception:
                    error_body = ""
                return self._failure(
                    start,
                    "api_call_failed",
                    "Google Analytics Data API returned HTTP " + str(getattr(exc, "code", "error")),
                    {"http_status": getattr(exc, "code", None), "response": error_body},
                )
            if isinstance(exc, URLError):
                return self._failure(start, "api_call_failed", "network error calling Google Analytics Data API", {"error": str(exc)})
            return self._failure(start, "api_call_failed", "unexpected error calling Google Analytics Data API", {"error": str(exc)})

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        failures = []
        try:
            if not isinstance(content, str) or not content.strip():
                failures.append("empty_content")
            lowered = content.lower() if isinstance(content, str) else ""
            if lowered.startswith("failed to pull google analytics data"):
                failures.append("google_analytics_pull_failed")
            if "read-only note" not in lowered:
                failures.append("missing_read_only_note")
            required_phrases = [
                "Google Analytics Data Pull",
                "Summary",
                "Top traffic sources",
                "Top landing pages",
            ]
            for phrase in required_phrases:
                if isinstance(content, str) and phrase not in content:
                    failures.append("missing_section_" + phrase.lower().replace(" ", "_"))
            banned_write_terms = [
                "created audience",
                "edited property",
                "changed conversion",
                "configured tag",
                "created campaign",
                "changed budget",
                "paused campaign",
                "enabled campaign",
                "published ad",
            ]
            for term in banned_write_terms:
                if term in lowered:
                    failures.append("mutation_claim_found_" + term.replace(" ", "_"))
        except Exception as exc:
            failures.append("self_check_exception_" + str(exc).replace(" ", "_")[:80])
        return ("fail" if failures else "pass"), failures
