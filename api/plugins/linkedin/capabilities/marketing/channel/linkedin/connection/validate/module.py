from __future__ import annotations

from klaroha_sdk import ChannelModule


class LinkedInConnectionValidateModule(ChannelModule):
    id = "marketing.channel.linkedin.connection.validate"
    name = "LinkedIn Connection Validate"
    vertical = "marketing"
    capability = "marketing.optimize"
    platform_hint = "linkedin connection"
    policy_default = "read_only"
    template = "marketing/channel/linkedin/connection/validate/template.j2"

    max_chars = 0
    must_mention = []
    banned_phrases = []

    def _creds(self, brief: dict) -> dict:
        raw = brief.get("_channel_credentials", {}) if isinstance(brief, dict) else {}
        return raw if isinstance(raw, dict) else {}

    def _token(self, creds: dict) -> str:
        return str(
            creds.get("linkedin_page_token")
            or creds.get("linkedin_access_token")
            or creds.get("page_token")
            or creds.get("access_token")
            or ""
        ).strip()

    def _org_id(self, creds: dict) -> str:
        return str(
            creds.get("linkedin_page_id")
            or creds.get("linkedin_organization_id")
            or creds.get("organization_id")
            or creds.get("page_id")
            or ""
        ).strip()

    def _attempt(self, status: str, error: str | None = None) -> dict:
        return {
            "provider": "linkedin",
            "model_id": "linkedin_connection_validate_v1",
            "mode": "tool",
            "status": status,
            "tokens_input": 0,
            "tokens_output": 0,
            "provider_cost": 0.0,
            "latency_ms": 0,
            "error": error,
        }

    def _failure(self, reason_code: str, message: str, details: dict | None = None) -> tuple[dict, dict]:
        content = (
            "Failed to validate LinkedIn connection.\n\n"
            f"Reason: {message}\n"
            "Mutation: none — read-only validation only."
        )
        return self._attempt("failed", reason_code), {
            "content": content,
            "sell_price": None,
            "block": {
                "type": "linkedin_connection_check",
                "platform": "linkedin",
                "status": "failed",
                "reason_code": reason_code,
                "message": message,
                "details": details or {},
                "read_only": True,
                "changed_resources": [],
                "allowed_actions": ["connect_linkedin", "retry", "dismiss"],
                "risk_policy": "connection_validate_is_read_only",
            },
        }

    def execute_tool_result(self, brief: dict) -> tuple[dict, dict]:
        try:
            if not isinstance(brief, dict):
                return self._failure("invalid_brief", "brief must be a dictionary")

            creds = self._creds(brief)
            token = self._token(creds)
            org_id = self._org_id(creds)
            if not token:
                return self._failure("missing_credentials", "LinkedIn OAuth access token is not connected for this brand")

            profile: dict = {}
            api_status = "not_called"
            api_error = None
            try:
                from urllib.error import HTTPError, URLError
                from urllib.request import Request, urlopen
                import json

                request = Request(
                    "https://api.linkedin.com/v2/userinfo",
                    headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                    method="GET",
                )
                with urlopen(request, timeout=20) as response:
                    body = response.read().decode("utf-8")
                    profile = json.loads(body) if body else {}
                    api_status = "succeeded"
            except HTTPError as exc:
                api_status = "failed"
                api_error = f"LinkedIn API returned HTTP {exc.code}"
                return self._failure("api_permission_or_token_error", api_error, {"http_status": exc.code, "organization_id": org_id})
            except URLError as exc:
                api_status = "failed"
                api_error = "Network error calling LinkedIn API"
                return self._failure("api_call_failed", api_error, {"error": str(exc), "organization_id": org_id})

            name = str(profile.get("name") or profile.get("localizedFirstName") or "connected LinkedIn account")
            content = (
                "LinkedIn connection validated.\n\n"
                f"Account: {name}\n"
                f"Organization ID: {org_id or 'not provided'}\n"
                "API: LinkedIn OpenID userinfo\n"
                "Mutation: none — read-only validation only."
            )
            return self._attempt("succeeded"), {
                "content": content,
                "sell_price": None,
                "block": {
                    "type": "linkedin_connection_check",
                    "platform": "linkedin",
                    "status": "succeeded",
                    "read_only": True,
                    "account": {
                        "name": name,
                        "email_present": bool(profile.get("email")),
                        "subject_present": bool(profile.get("sub")),
                    },
                    "organization_id": org_id or None,
                    "api_status": api_status,
                    "api_error": api_error,
                    "changed_resources": [],
                    "allowed_actions": ["draft_post", "dismiss"],
                    "risk_policy": "connection_validate_is_read_only",
                },
            }
        except Exception as exc:
            return self._failure("validation_exception", "Unexpected error validating LinkedIn connection", {"error": str(exc)})

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        failures: list[str] = []
        try:
            lowered = (content or "").lower()
            if "linkedin connection validated" not in lowered and "failed to validate linkedin connection" not in lowered:
                failures.append("missing_connection_validation_summary")
            if "mutation: none" not in lowered:
                failures.append("missing_read_only_boundary")
        except Exception:
            failures.append("self_check_exception")
        return ("fail" if failures else "pass", failures)
