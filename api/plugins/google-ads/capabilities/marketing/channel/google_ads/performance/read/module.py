from __future__ import annotations

from klaroha_sdk import ChannelModule


class GoogleAdsReadOnlyDataPullModule(ChannelModule):
    id = "marketing.channel.google_ads.performance.read"
    name = "Google Ads Read-Only Data Pull"
    vertical = "marketing"
    capability = "marketing.optimize"
    platform_hint = "google ads"
    policy_default = "read_only"
    template = "marketing/channel/google_ads/performance/read/template.j2"

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
            "provider": "google_ads",
            "model_id": "google_ads_api_rest",
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
            "content": "Failed to pull Google Ads data: " + message + "\n\nRead-only note: no campaigns, ads, keywords, bids, or budgets were changed.",
            "sell_price": None,
            "block": {
                "type": "google_ads_data_pull",
                "status": "failed",
                "reason_code": reason_code,
                "message": message,
                "details": details,
                "read_only": True,
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

    def _customer_id(self, value):
        raw = str(value or "").strip().replace('"', "").replace("'", "")
        digits = "".join(char for char in raw if char.isdigit())
        if not digits:
            return ""
        return digits.zfill(10)

    def _api_version(self, value):
        value = str(value or "v21").strip()
        if not value.startswith("v"):
            value = "v" + value
        return value

    def _date_range(self, brief):
        allowed = {
            "TODAY",
            "YESTERDAY",
            "LAST_7_DAYS",
            "LAST_14_DAYS",
            "LAST_30_DAYS",
            "LAST_90_DAYS",
            "THIS_MONTH",
            "LAST_MONTH",
        }
        explicit = str(brief.get("date_range") or brief.get("dateRange") or "").strip().upper()
        if explicit in allowed:
            return explicit

        context = str(brief.get("conversation_context") or "").lower()
        if "last 7" in context or "past 7" in context:
            return "LAST_7_DAYS"
        if "last 14" in context or "past 14" in context:
            return "LAST_14_DAYS"
        if "last 90" in context or "past 90" in context:
            return "LAST_90_DAYS"
        if "last month" in context:
            return "LAST_MONTH"
        if "this month" in context:
            return "THIS_MONTH"
        return "LAST_30_DAYS"

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

    def _money(self, micros):
        return round(self._to_int(micros) / 1000000.0, 2)

    def _fmt_int(self, value):
        return f"{self._to_int(value):,}"

    def _fmt_money(self, value):
        return "$" + f"{float(value):,.2f}"

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
            return json.loads(body) if body else []

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

    def _campaign_rows(self, response):
        rows = []
        batches = response if isinstance(response, list) else [response]
        for batch in batches:
            if not isinstance(batch, dict):
                continue
            for item in batch.get("results", []) or []:
                campaign = item.get("campaign", {}) or {}
                metrics = item.get("metrics", {}) or {}
                rows.append({
                    "campaign_id": str(campaign.get("id", "")),
                    "campaign_name": str(campaign.get("name", "")),
                    "status": str(campaign.get("status", "")),
                    "impressions": self._to_int(metrics.get("impressions")),
                    "clicks": self._to_int(metrics.get("clicks")),
                    "cost": self._money(metrics.get("costMicros")),
                    "conversions": self._to_float(metrics.get("conversions")),
                    "ctr": self._to_float(metrics.get("ctr")),
                    "average_cpc": self._money(metrics.get("averageCpc")),
                })
        return rows

    def _content(self, customer_id, date_range, rows):
        total_impressions = sum(row["impressions"] for row in rows)
        total_clicks = sum(row["clicks"] for row in rows)
        total_cost = sum(row["cost"] for row in rows)
        total_conversions = sum(row["conversions"] for row in rows)

        lines = [
            "# Google Ads Data Pull",
            "",
            "Customer: " + customer_id,
            "Date range: " + date_range,
            "Campaigns returned: " + str(len(rows)),
            "",
            "| Campaign | Status | Impressions | Clicks | Cost | Conversions |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        if rows:
            for row in rows:
                lines.append(
                    "| "
                    + (row["campaign_name"] or row["campaign_id"] or "Unnamed campaign")
                    + " | "
                    + row["status"]
                    + " | "
                    + self._fmt_int(row["impressions"])
                    + " | "
                    + self._fmt_int(row["clicks"])
                    + " | "
                    + self._fmt_money(row["cost"])
                    + " | "
                    + f"{row['conversions']:,.2f}"
                    + " |"
                )
        else:
            lines.append("| No campaigns returned | - | 0 | 0 | $0.00 | 0.00 |")

        lines.extend([
            "",
            "Totals:",
            "- Impressions: " + self._fmt_int(total_impressions),
            "- Clicks: " + self._fmt_int(total_clicks),
            "- Cost: " + self._fmt_money(total_cost),
            "- Conversions: " + f"{total_conversions:,.2f}",
            "",
            "Read-only note: no campaigns, ads, keywords, bids, or budgets were changed.",
        ])
        return "\n".join(lines)

    def execute_tool_result(self, brief: dict) -> tuple[dict, dict]:
        import time

        start = time.perf_counter()
        try:
            if not isinstance(brief, dict):
                return self._failure(start, "invalid_brief", "brief must be a dictionary")

            creds = self._creds(brief)
            developer_token = self._cred(creds, "google_ads_developer_token")
            client_id = self._cred(creds, "google_ads_client_id")
            client_secret = self._cred(creds, "google_ads_client_secret")
            refresh_token = self._cred(creds, "google_ads_refresh_token")
            customer_id = self._customer_id(
                brief.get("google_ads_customer_id")
                or brief.get("customer_id")
                or self._cred(creds, "google_ads_default_customer_id")
            )
            login_customer_id = self._customer_id(
                brief.get("google_ads_login_customer_id")
                or brief.get("login_customer_id")
                or self._cred(creds, "google_ads_login_customer_id", "")
            )
            api_version = self._api_version(
                brief.get("google_ads_api_version")
                or brief.get("api_version")
                or self._cred(creds, "google_ads_api_version", "v21")
            )
            date_range = self._date_range(brief)

            missing = []
            if not developer_token:
                missing.append("GOOGLE_ADS_DEVELOPER_TOKEN")
            if not client_id:
                missing.append("GOOGLE_ADS_CLIENT_ID")
            if not client_secret:
                missing.append("GOOGLE_ADS_CLIENT_SECRET")
            if not refresh_token:
                missing.append("GOOGLE_ADS_REFRESH_TOKEN")
            if not customer_id:
                missing.append("GOOGLE_ADS_DEFAULT_CUSTOMER_ID")
            if missing:
                return self._failure(
                    start,
                    "missing_credentials",
                    "missing required plugin environment variables: " + ", ".join(missing),
                    {"missing": missing},
                )

            access_token = self._refresh_access_token(client_id, client_secret, refresh_token)

            query = (
                "SELECT campaign.id, campaign.name, campaign.status, "
                "metrics.impressions, metrics.clicks, metrics.cost_micros, "
                "metrics.conversions, metrics.ctr, metrics.average_cpc "
                "FROM campaign "
                "WHERE segments.date DURING " + date_range + " "
                "ORDER BY metrics.cost_micros DESC "
                "LIMIT 50"
            )
            url = (
                "https://googleads.googleapis.com/"
                + api_version
                + "/customers/"
                + customer_id
                + "/googleAds:searchStream"
            )
            headers = {
                "Authorization": "Bearer " + access_token,
                "developer-token": developer_token,
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            if login_customer_id:
                headers["login-customer-id"] = login_customer_id

            from urllib.error import HTTPError
            try:
                response = self._post_json(url, headers, {"query": query})
            except HTTPError as exc:
                # Some directly accessible accounts fail when a manager login header
                # is present but not actually linked to that customer. Retry once
                # without the manager header before returning a permission failure.
                if getattr(exc, "code", None) == 403 and headers.get("login-customer-id"):
                    retry_headers = dict(headers)
                    retry_headers.pop("login-customer-id", None)
                    response = self._post_json(url, retry_headers, {"query": query})
                else:
                    raise
            rows = self._campaign_rows(response)
            content = self._content(customer_id, date_range, rows)

            return self._attempt(start, "succeeded"), {
                "content": content,
                "sell_price": None,
                "block": {
                    "type": "google_ads_data_pull",
                    "status": "succeeded",
                    "customer_id": customer_id,
                    "date_range": date_range,
                    "campaigns": rows,
                    "campaign_count": len(rows),
                    "read_only": True,
                    "changed_resources": [],
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
                    "Google Ads API returned HTTP " + str(getattr(exc, "code", "error")),
                    {"http_status": getattr(exc, "code", None), "response": error_body},
                )
            if isinstance(exc, URLError):
                return self._failure(start, "api_call_failed", "network error calling Google Ads API", {"error": str(exc)})
            return self._failure(start, "api_call_failed", "unexpected error calling Google Ads API", {"error": str(exc)})

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        failures = []
        if not isinstance(content, str) or not content.strip():
            failures.append("empty_content")
        if isinstance(content, str) and content.startswith("Failed to pull Google Ads data"):
            failures.append("google_ads_pull_failed")
        if isinstance(content, str) and "Read-only note" not in content:
            failures.append("missing_read_only_note")
        banned_write_terms = [
            "changed budget",
            "paused campaign",
            "enabled campaign",
            "created campaign",
            "published ad",
        ]
        lowered = content.lower() if isinstance(content, str) else ""
        for term in banned_write_terms:
            if term in lowered:
                failures.append("mutation_claim_found:" + term)
        return ("fail" if failures else "pass"), failures
