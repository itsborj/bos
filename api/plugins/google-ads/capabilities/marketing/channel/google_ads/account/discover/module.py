from __future__ import annotations

from klaroha_sdk import ChannelModule


class GoogleAdsAccountDiscoverModule(ChannelModule):
    id = "marketing.channel.google_ads.account.discover"
    name = "Google Ads Account Discovery"
    vertical = "marketing"
    capability = "marketing.optimize"
    platform_hint = "google ads account discovery"
    policy_default = "read_only"
    template = "marketing/channel/google_ads/account/discover/template.j2"

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
            "content": "Failed to discover Google Ads accounts: " + message + "\n\nRead-only note: no campaigns, ads, keywords, bids, budgets, or account settings were changed.",
            "sell_price": None,
            "block": {
                "type": "google_ads_account_inventory",
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
            headers=headers,
            method="POST",
        )
        with urlopen(request, timeout=45) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else []

    def _accessible_accounts(self, response):
        names = response.get("resourceNames", []) if isinstance(response, dict) else []
        accounts = []
        for name in names or []:
            customer_id = self._customer_id(name)
            if customer_id:
                accounts.append({
                    "customer_id": customer_id,
                    "resource_name": "customers/" + customer_id,
                    "descriptive_name": customer_id,
                    "manager": None,
                    "currency_code": None,
                    "time_zone": None,
                    "status": "ACCESSIBLE",
                    "test_account": None,
                })
        return accounts

    def _manager_clients(self, response):
        accounts = []
        batches = response if isinstance(response, list) else [response]
        for batch in batches:
            if not isinstance(batch, dict):
                continue
            for item in batch.get("results", []) or []:
                client = item.get("customerClient", {}) or item.get("customer_client", {}) or {}
                customer_id = self._customer_id(client.get("id"))
                if not customer_id:
                    continue
                accounts.append({
                    "customer_id": customer_id,
                    "resource_name": "customers/" + customer_id,
                    "descriptive_name": str(client.get("descriptiveName") or client.get("descriptive_name") or customer_id),
                    "manager": client.get("manager"),
                    "currency_code": client.get("currencyCode") or client.get("currency_code"),
                    "time_zone": client.get("timeZone") or client.get("time_zone"),
                    "status": str(client.get("status") or "UNKNOWN"),
                    "test_account": client.get("testAccount") if "testAccount" in client else client.get("test_account"),
                })
        return accounts

    def _content(self, accounts, selected_customer_id=""):
        lines = [
            "# Google Ads Account Inventory",
            "",
            "Accounts returned: " + str(len(accounts)),
        ]
        if selected_customer_id:
            lines.append("Configured customer: " + selected_customer_id)
        lines.extend([
            "",
            "| Customer ID | Name | Manager | Currency | Time Zone | Status |",
            "|---|---|---:|---|---|---|",
        ])
        if accounts:
            for account in accounts:
                lines.append(
                    "| "
                    + str(account.get("customer_id") or "")
                    + " | "
                    + str(account.get("descriptive_name") or "")
                    + " | "
                    + str(account.get("manager"))
                    + " | "
                    + str(account.get("currency_code") or "")
                    + " | "
                    + str(account.get("time_zone") or "")
                    + " | "
                    + str(account.get("status") or "")
                    + " |"
                )
        else:
            lines.append("| No accounts returned | - | - | - | - | - |")
        lines.extend([
            "",
            "Read-only note: no campaigns, ads, keywords, bids, budgets, or account settings were changed.",
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
            selected_customer_id = self._customer_id(
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

            missing = []
            if not developer_token:
                missing.append("GOOGLE_ADS_DEVELOPER_TOKEN")
            if not client_id:
                missing.append("GOOGLE_ADS_CLIENT_ID")
            if not client_secret:
                missing.append("GOOGLE_ADS_CLIENT_SECRET")
            if not refresh_token:
                missing.append("GOOGLE_ADS_REFRESH_TOKEN")
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
                "developer-token": developer_token,
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            if login_customer_id:
                headers["login-customer-id"] = login_customer_id

            url = "https://googleads.googleapis.com/" + api_version + "/customers:listAccessibleCustomers"
            response = self._get_json(url, headers)
            accounts = self._accessible_accounts(response)

            # If a manager/default customer is configured, enrich with customer_client rows.
            lookup_customer_id = login_customer_id or selected_customer_id
            if lookup_customer_id:
                query = (
                    "SELECT customer_client.id, customer_client.descriptive_name, "
                    "customer_client.manager, customer_client.status, customer_client.test_account, "
                    "customer_client.currency_code, customer_client.time_zone "
                    "FROM customer_client WHERE customer_client.level <= 1"
                )
                stream_url = (
                    "https://googleads.googleapis.com/"
                    + api_version
                    + "/customers/"
                    + lookup_customer_id
                    + "/googleAds:searchStream"
                )
                try:
                    manager_response = self._post_json(stream_url, headers, {"query": query})
                    manager_accounts = self._manager_clients(manager_response)
                    by_id = {row["customer_id"]: row for row in accounts}
                    for row in manager_accounts:
                        by_id[row["customer_id"]] = row
                    accounts = list(by_id.values())
                except Exception:
                    # Account discovery should still succeed with accessible customer IDs.
                    pass

            content = self._content(accounts, selected_customer_id)
            return self._attempt(start, "succeeded"), {
                "content": content,
                "sell_price": None,
                "block": {
                    "type": "google_ads_account_inventory",
                    "status": "succeeded",
                    "customer_id": selected_customer_id,
                    "accounts": accounts,
                    "account_count": len(accounts),
                    "read_only": True,
                    "changed_resources": [],
                    "allowed_actions": ["select_account", "dismiss"],
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
        lowered = content.lower() if isinstance(content, str) else ""
        if "google ads account inventory" not in lowered:
            failures.append("missing_account_inventory_heading")
        if "read-only note" not in lowered:
            failures.append("missing_read_only_note")
        banned_write_terms = [
            "changed budget",
            "paused campaign",
            "enabled campaign",
            "created campaign",
            "published ad",
            "removed campaign",
        ]
        for term in banned_write_terms:
            if term in lowered:
                failures.append("mutation_claim_found:" + term)
        return ("fail" if failures else "pass"), failures
