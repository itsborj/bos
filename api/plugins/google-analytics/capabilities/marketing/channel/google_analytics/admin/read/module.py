from __future__ import annotations

from klaroha_sdk import ChannelModule


class GoogleAnalyticsAdminReadOnlySetupModule(ChannelModule):
    id = "marketing.channel.google_analytics.admin.read"
    name = "Google Analytics Admin Read-Only Setup Check"
    vertical = "marketing"
    capability = "marketing.optimize"
    platform_hint = "google analytics"
    policy_default = "read_only"
    template = "marketing/channel/google_analytics/admin/read/template.j2"

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
            "model_id": "analytics_admin_api_rest",
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
            "content": "Failed to inspect Google Analytics setup: " + message + "\n\nRead-only note: no Google Analytics properties, data streams, audiences, conversions, tags, campaigns, bids, or budgets were changed.",
            "sell_price": None,
            "block": {
                "type": "google_analytics_admin_readiness",
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

    def _get_json(self, url, headers):
        import json
        from urllib.request import Request, urlopen

        request = Request(url, headers=headers, method="GET")
        with urlopen(request, timeout=45) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}

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

    def _property_summary(self, raw):
        return {
            "name": str(raw.get("name") or ""),
            "property_id": str(raw.get("name") or "").replace("properties/", ""),
            "display_name": str(raw.get("displayName") or ""),
            "time_zone": str(raw.get("timeZone") or ""),
            "currency_code": str(raw.get("currencyCode") or ""),
            "industry_category": str(raw.get("industryCategory") or ""),
            "service_level": str(raw.get("serviceLevel") or ""),
            "create_time": str(raw.get("createTime") or ""),
            "update_time": str(raw.get("updateTime") or ""),
            "parent": str(raw.get("parent") or ""),
        }

    def _data_streams(self, raw):
        streams = []
        for item in raw.get("dataStreams", []) or []:
            if not isinstance(item, dict):
                continue
            web = item.get("webStreamData", {}) or {}
            app = item.get("androidAppStreamData", {}) or item.get("iosAppStreamData", {}) or {}
            streams.append({
                "name": str(item.get("name") or ""),
                "stream_id": str(item.get("name") or "").rsplit("/", 1)[-1],
                "display_name": str(item.get("displayName") or ""),
                "type": str(item.get("type") or ""),
                "create_time": str(item.get("createTime") or ""),
                "update_time": str(item.get("updateTime") or ""),
                "default_uri": str(web.get("defaultUri") or ""),
                "measurement_id": str(web.get("measurementId") or ""),
                "firebase_app_id": str(app.get("firebaseAppId") or ""),
            })
        return streams

    def _recent_sessions(self, access_token, property_id):
        try:
            url = "https://analyticsdata.googleapis.com/v1beta/properties/" + property_id + ":runReport"
            headers = {
                "Authorization": "Bearer " + access_token,
                "Accept": "application/json",
            }
            payload = {
                "dateRanges": [{"startDate": "30daysAgo", "endDate": "yesterday"}],
                "metrics": [{"name": "sessions"}, {"name": "totalUsers"}],
                "limit": "1",
            }
            data = self._post_json(url, headers, payload)
            rows = data.get("rows", []) or []
            if not rows:
                return {"available": True, "sessions": 0, "users": 0, "error": None}
            values = rows[0].get("metricValues", []) or []
            sessions = values[0].get("value") if len(values) > 0 and isinstance(values[0], dict) else 0
            users = values[1].get("value") if len(values) > 1 and isinstance(values[1], dict) else 0
            return {"available": True, "sessions": self._to_int(sessions), "users": self._to_int(users), "error": None}
        except Exception as exc:
            return {"available": False, "sessions": None, "users": None, "error": str(exc)}

    def _readiness(self, prop, streams, recent):
        checks = []
        checks.append({
            "name": "property_accessible",
            "status": "pass" if prop.get("property_id") else "fail",
            "message": "GA4 property is accessible through the Admin API." if prop.get("property_id") else "GA4 property metadata was not returned.",
        })

        web_streams = [s for s in streams if s.get("type") == "WEB_DATA_STREAM"]
        checks.append({
            "name": "web_stream_present",
            "status": "pass" if web_streams else "fail",
            "message": "At least one web data stream exists." if web_streams else "No web data stream was returned for this property.",
        })

        measurement_ids = [s for s in web_streams if s.get("measurement_id")]
        checks.append({
            "name": "measurement_id_present",
            "status": "pass" if measurement_ids else "fail",
            "message": "A web Measurement ID is available." if measurement_ids else "No web Measurement ID was returned.",
        })

        if recent.get("available"):
            sessions = self._to_int(recent.get("sessions"))
            checks.append({
                "name": "recent_traffic_present",
                "status": "pass" if sessions > 0 else "fail",
                "message": "Recent sessions were detected in the Data API check." if sessions > 0 else "No sessions were detected in the recent Data API check.",
            })
        else:
            checks.append({
                "name": "recent_traffic_present",
                "status": "unknown",
                "message": "Recent traffic check could not run through the Data API: " + str(recent.get("error") or "unknown error")[:240],
            })

        fail_count = len([c for c in checks if c.get("status") == "fail"])
        unknown_count = len([c for c in checks if c.get("status") == "unknown"])
        if fail_count:
            status = "needs_setup"
        elif unknown_count:
            status = "needs_review"
        else:
            status = "ready"
        return {"status": status, "checks": checks}

    def _content(self, property_id, prop, streams, recent, readiness):
        lines = [
            "# Google Analytics Admin Setup Check",
            "",
            "Property: " + property_id,
            "Readiness: " + str(readiness.get("status") or "needs_review"),
            "",
            "## Property",
            "- Display name: " + (prop.get("display_name") or "Not returned"),
            "- Time zone: " + (prop.get("time_zone") or "Not returned"),
            "- Currency: " + (prop.get("currency_code") or "Not returned"),
            "- Industry: " + (prop.get("industry_category") or "Not returned"),
            "",
            "## Data streams",
            "| Stream | Type | Default URI | Measurement ID |",
            "|---|---|---|---|",
        ]
        if streams:
            for stream in streams:
                lines.append(
                    "| "
                    + (stream.get("display_name") or stream.get("stream_id") or "Unnamed stream").replace("|", "\\|")
                    + " | "
                    + (stream.get("type") or "-")
                    + " | "
                    + (stream.get("default_uri") or "-").replace("|", "\\|")
                    + " | "
                    + (stream.get("measurement_id") or "-")
                    + " |"
                )
        else:
            lines.append("| No data streams returned | - | - | - |")

        lines.extend([
            "",
            "## Recent traffic signal",
        ])
        if recent.get("available"):
            lines.append("- Sessions in recent Data API check: " + str(self._to_int(recent.get("sessions"))))
            lines.append("- Users in recent Data API check: " + str(self._to_int(recent.get("users"))))
        else:
            lines.append("- Recent traffic check unavailable: " + str(recent.get("error") or "unknown error")[:240])

        lines.extend([
            "",
            "## Readiness checks",
            "| Check | Status | Message |",
            "|---|---|---|",
        ])
        for check in readiness.get("checks", []) or []:
            lines.append(
                "| "
                + str(check.get("name") or "check")
                + " | "
                + str(check.get("status") or "unknown")
                + " | "
                + str(check.get("message") or "").replace("|", "\\|")
                + " |"
            )

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
            headers = {
                "Authorization": "Bearer " + access_token,
                "Accept": "application/json",
            }
            admin_base = "https://analyticsadmin.googleapis.com/v1beta/properties/" + property_id
            prop_raw = self._get_json(admin_base, headers)
            streams_raw = self._get_json(admin_base + "/dataStreams", headers)
            prop = self._property_summary(prop_raw)
            streams = self._data_streams(streams_raw)
            recent = self._recent_sessions(access_token, property_id)
            readiness = self._readiness(prop, streams, recent)
            content = self._content(property_id, prop, streams, recent, readiness)

            return self._attempt(start, "succeeded"), {
                "content": content,
                "sell_price": None,
                "block": {
                    "type": "google_analytics_admin_readiness",
                    "status": "succeeded",
                    "property_id": property_id,
                    "property": prop,
                    "data_streams": streams,
                    "recent_traffic": recent,
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
                    "Google Analytics Admin API returned HTTP " + str(getattr(exc, "code", "error")),
                    {"http_status": getattr(exc, "code", None), "response": error_body},
                )
            if isinstance(exc, URLError):
                return self._failure(start, "api_call_failed", "network error calling Google Analytics Admin API", {"error": str(exc)})
            return self._failure(start, "api_call_failed", "unexpected error calling Google Analytics Admin API", {"error": str(exc)})

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        failures = []
        try:
            if not isinstance(content, str) or not content.strip():
                failures.append("empty_content")
            lowered = content.lower() if isinstance(content, str) else ""
            if lowered.startswith("failed to inspect google analytics setup"):
                failures.append("google_analytics_admin_check_failed")
            if "read-only note" not in lowered:
                failures.append("missing_read_only_note")
            required_phrases = [
                "Google Analytics Admin Setup Check",
                "Property",
                "Data streams",
                "Readiness checks",
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
