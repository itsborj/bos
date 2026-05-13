from __future__ import annotations

from klaroha_sdk import ChannelModule


class GoogleAnalyticsRealtimeReadOnlyModule(ChannelModule):
    id = "marketing.channel.google_analytics.realtime.read"
    name = "Google Analytics Realtime Read-Only Tracking Check"
    vertical = "marketing"
    capability = "marketing.optimize"
    platform_hint = "google analytics"
    policy_default = "read_only"
    template = "marketing/channel/google_analytics/realtime/read/template.j2"

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
            "model_id": "ga4_realtime_data_api_rest",
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
            "content": "Failed to check Google Analytics realtime tracking: " + message + "\n\nRead-only note: no Google Analytics properties, data streams, audiences, conversions, tags, campaigns, bids, or budgets were changed.",
            "sell_price": None,
            "block": {
                "type": "google_analytics_realtime_check",
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

    def _to_int(self, value):
        try:
            return int(float(value or 0))
        except Exception:
            return 0

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
            headers={**headers, "Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=45) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}

    def _run_realtime_report(self, access_token, property_id, dimensions, metrics, limit=10, order_metric=None):
        url = "https://analyticsdata.googleapis.com/v1beta/properties/" + property_id + ":runRealtimeReport"
        headers = {
            "Authorization": "Bearer " + access_token,
            "Accept": "application/json",
        }
        payload = {
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
        first = rows[0] if rows else {}
        return {
            "active_users": self._to_int(first.get("activeUsers")),
            "event_count": self._to_int(first.get("eventCount")),
        }

    def _events(self, response):
        items = []
        for row in self._parse_rows(response):
            items.append({
                "event_name": str(row.get("eventName") or "(not set)"),
                "event_count": self._to_int(row.get("eventCount")),
                "active_users": self._to_int(row.get("activeUsers")),
            })
        return items

    def _pages(self, response):
        items = []
        for row in self._parse_rows(response):
            items.append({
                "page_or_screen": str(row.get("unifiedScreenName") or "(not set)"),
                "active_users": self._to_int(row.get("activeUsers")),
                "event_count": self._to_int(row.get("eventCount")),
            })
        return items

    def _readiness(self, summary, events, pages):
        active_users = self._to_int(summary.get("active_users"))
        event_count = self._to_int(summary.get("event_count"))
        has_event_rows = any(self._to_int(item.get("event_count")) > 0 for item in events)
        has_page_rows = any(self._to_int(item.get("active_users")) > 0 or self._to_int(item.get("event_count")) > 0 for item in pages)
        if active_users > 0 or event_count > 0 or has_event_rows or has_page_rows:
            return {
                "status": "tracking_live",
                "message": "Realtime activity was detected. GA4 tracking appears to be firing.",
            }
        return {
            "status": "no_realtime_activity",
            "message": "No active users or realtime events were detected. Open the website in another tab and retry.",
        }

    def _content(self, property_id, summary, events, pages, readiness):
        lines = [
            "# Google Analytics Realtime Check",
            "",
            "Property: " + property_id,
            "Status: " + str(readiness.get("status") or "no_realtime_activity"),
            "",
            "## Summary",
            "- Active users: " + str(self._to_int(summary.get("active_users"))),
            "- Realtime event count: " + str(self._to_int(summary.get("event_count"))),
            "- Tracking note: " + str(readiness.get("message") or "No realtime status message returned."),
            "",
            "## Realtime events",
            "| Event | Event Count | Active Users |",
            "|---|---:|---:|",
        ]
        if events:
            for item in events:
                lines.append(
                    "| "
                    + str(item.get("event_name") or "(not set)").replace("|", "\\|")
                    + " | "
                    + str(self._to_int(item.get("event_count")))
                    + " | "
                    + str(self._to_int(item.get("active_users")))
                    + " |"
                )
        else:
            lines.append("| No realtime event rows returned | 0 | 0 |")

        lines.extend([
            "",
            "## Realtime pages/screens",
            "| Page / Screen | Active Users | Event Count |",
            "|---|---:|---:|",
        ])
        if pages:
            for item in pages:
                lines.append(
                    "| "
                    + str(item.get("page_or_screen") or "(not set)").replace("|", "\\|")
                    + " | "
                    + str(self._to_int(item.get("active_users")))
                    + " | "
                    + str(self._to_int(item.get("event_count")))
                    + " |"
                )
        else:
            lines.append("| No realtime page/screen rows returned | 0 | 0 |")

        lines.extend([
            "",
            "Read-only note: no Google Analytics properties, data streams, audiences, conversions, tags, campaigns, bids, or budgets were changed.",
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
            summary = self._summary(
                self._run_realtime_report(
                    access_token,
                    property_id,
                    dimensions=[],
                    metrics=["activeUsers", "eventCount"],
                    limit=1,
                )
            )
            events = self._events(
                self._run_realtime_report(
                    access_token,
                    property_id,
                    dimensions=["eventName"],
                    metrics=["eventCount", "activeUsers"],
                    limit=10,
                    order_metric="eventCount",
                )
            )
            pages = self._pages(
                self._run_realtime_report(
                    access_token,
                    property_id,
                    dimensions=["unifiedScreenName"],
                    metrics=["activeUsers", "eventCount"],
                    limit=10,
                    order_metric="activeUsers",
                )
            )
            readiness = self._readiness(summary, events, pages)
            content = self._content(property_id, summary, events, pages, readiness)

            return self._attempt(start, "succeeded"), {
                "content": content,
                "sell_price": None,
                "block": {
                    "type": "google_analytics_realtime_check",
                    "status": "succeeded",
                    "property_id": property_id,
                    "active_users": self._to_int(summary.get("active_users")),
                    "event_count": self._to_int(summary.get("event_count")),
                    "events": events,
                    "pages": pages,
                    "readiness": readiness,
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
                    "Google Analytics Realtime Data API returned HTTP " + str(getattr(exc, "code", "error")),
                    {"http_status": getattr(exc, "code", None), "response": error_body},
                )
            if isinstance(exc, URLError):
                return self._failure(start, "api_call_failed", "network error calling Google Analytics Realtime Data API", {"error": str(exc)})
            return self._failure(start, "api_call_failed", "unexpected error calling Google Analytics Realtime Data API", {"error": str(exc)})

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        failures = []
        try:
            if not isinstance(content, str) or not content.strip():
                failures.append("empty_content")
            lowered = content.lower() if isinstance(content, str) else ""
            if lowered.startswith("failed to check google analytics realtime tracking"):
                failures.append("google_analytics_realtime_check_failed")
            if "read-only note" not in lowered:
                failures.append("missing_read_only_note")
            required_phrases = [
                "Google Analytics Realtime Check",
                "Summary",
                "Realtime events",
                "Realtime pages/screens",
            ]
            for phrase in required_phrases:
                if isinstance(content, str) and phrase not in content:
                    failures.append("missing_section_" + phrase.lower().replace(" ", "_"))
            banned_write_terms = [
                "created audience",
                "created data stream",
                "edited property",
                "changed conversion",
                "configured tag",
                "installed tag",
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
