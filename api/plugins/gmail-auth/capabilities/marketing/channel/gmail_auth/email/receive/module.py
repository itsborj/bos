from __future__ import annotations

from klaroha_sdk import ChannelModule


class GmailReceiveEmailModule(ChannelModule):
    id = "marketing.channel.gmail_auth.email.receive"
    name = "Gmail Receive Email"
    vertical = "marketing"
    capability = "marketing.analytics"
    platform_hint = "gmail inbox"
    template = "marketing/channel/gmail_auth/email/receive/template.j2"

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
            "provider": "gmail",
            "model_id": "gmail_v1",
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
            "content": "Failed to receive Gmail emails: " + message,
            "sell_price": None,
            "block": {
                "type": "gmail_receive_result",
                "status": "failed",
                "reason_code": reason_code,
                "message": message,
                "details": details,
            },
        }

    def _token(self, creds):
        if not isinstance(creds, dict):
            return None
        return creds.get("access_token") or creds.get("gmail_access_token") or creds.get("page_token")

    def _as_list(self, value):
        if value is None:
            return []
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        if isinstance(value, tuple):
            return [str(v).strip() for v in value if str(v).strip()]
        value = str(value).strip()
        if not value:
            return []
        return [part.strip() for part in value.split(",") if part.strip()]

    def _bool(self, value):
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        return str(value).strip().lower() in ["1", "true", "yes", "y", "on"]

    def _max_results(self, value):
        try:
            parsed = int(value if value is not None else 10)
        except Exception:
            parsed = 10
        if parsed < 1:
            return 1
        if parsed > 100:
            return 100
        return parsed

    def _api_get_json(self, url, access_token):
        import json
        from urllib.request import Request, urlopen

        request = Request(
            url,
            headers={
                "Authorization": "Bearer " + access_token,
                "Accept": "application/json",
            },
            method="GET",
        )
        with urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}

    def _header_map(self, message):
        headers = message.get("payload", {}).get("headers", [])
        result = {}
        for header in headers:
            name = str(header.get("name", "")).lower()
            if name:
                result[name] = header.get("value", "")
        return result

    def _decode_gmail_body(self, data):
        try:
            import base64
            if not data:
                return ""
            padding = "=" * (-len(data) % 4)
            return base64.urlsafe_b64decode((data + padding).encode("utf-8")).decode("utf-8", errors="replace")
        except Exception:
            return ""

    def _extract_text_body(self, payload):
        try:
            mime_type = payload.get("mimeType", "")
            body_data = payload.get("body", {}).get("data")
            if mime_type == "text/plain" and body_data:
                return self._decode_gmail_body(body_data)
            if mime_type == "text/html" and body_data:
                return self._decode_gmail_body(body_data)
            for part in payload.get("parts", []) or []:
                found = self._extract_text_body(part)
                if found:
                    return found
        except Exception:
            return ""
        return ""

    def execute_tool_result(self, brief: dict) -> tuple[dict, dict]:
        import time

        start = time.perf_counter()
        try:
            if not isinstance(brief, dict):
                return self._failure(start, "invalid_brief", "brief must be a dictionary")

            creds = brief.get("_channel_credentials", {})
            access_token = self._token(creds)
            if not access_token:
                return self._failure(
                    start,
                    "no_social_connection",
                    "missing Gmail OAuth access token in _channel_credentials",
                )

            from urllib.error import HTTPError, URLError
            from urllib.parse import urlencode

            query = brief.get("query") or brief.get("q")
            label_ids = self._as_list(brief.get("label_ids") or brief.get("labelIds") or brief.get("labels"))
            max_results = self._max_results(brief.get("max_results") or brief.get("maxResults"))
            include_spam_trash = self._bool(brief.get("include_spam_trash") or brief.get("includeSpamTrash"))
            include_body = self._bool(brief.get("include_body") or brief.get("includeBody"))
            page_token = brief.get("page_token") or brief.get("pageToken")

            list_params = {"maxResults": max_results}
            if query:
                list_params["q"] = str(query)
            if label_ids:
                list_params["labelIds"] = label_ids
            if include_spam_trash:
                list_params["includeSpamTrash"] = "true"
            if page_token:
                list_params["pageToken"] = str(page_token)

            list_url = "https://gmail.googleapis.com/gmail/v1/users/me/messages?" + urlencode(list_params, doseq=True)
            list_result = self._api_get_json(list_url, access_token)
            message_refs = list_result.get("messages", []) or []

            emails = []
            for message_ref in message_refs:
                message_id = message_ref.get("id")
                if not message_id:
                    continue

                get_params = {
                    "format": "full" if include_body else "metadata",
                    "metadataHeaders": ["From", "To", "Cc", "Subject", "Date", "Message-ID"],
                }
                get_url = (
                    "https://gmail.googleapis.com/gmail/v1/users/me/messages/"
                    + str(message_id)
                    + "?"
                    + urlencode(get_params, doseq=True)
                )
                message = self._api_get_json(get_url, access_token)
                header_map = self._header_map(message)

                email_block = {
                    "id": message.get("id"),
                    "thread_id": message.get("threadId"),
                    "label_ids": message.get("labelIds", []),
                    "snippet": message.get("snippet", ""),
                    "history_id": message.get("historyId"),
                    "internal_date": message.get("internalDate"),
                    "from": header_map.get("from", ""),
                    "to": header_map.get("to", ""),
                    "cc": header_map.get("cc", ""),
                    "subject": header_map.get("subject", ""),
                    "date": header_map.get("date", ""),
                    "message_id_header": header_map.get("message-id", ""),
                }
                if include_body:
                    email_block["body"] = self._extract_text_body(message.get("payload", {}))
                emails.append(email_block)

            count = len(emails)
            result_data = {
                "content": "Received " + str(count) + " Gmail email" + ("" if count == 1 else "s"),
                "sell_price": None,
                "block": {
                    "type": "gmail_receive_result",
                    "status": "succeeded",
                    "query": str(query) if query else None,
                    "label_ids": label_ids,
                    "max_results": max_results,
                    "result_size_estimate": list_result.get("resultSizeEstimate"),
                    "next_page_token": list_result.get("nextPageToken"),
                    "emails": emails,
                },
            }
            return self._attempt(start, "succeeded"), result_data

        except HTTPError as exc:
            try:
                error_body = exc.read().decode("utf-8")
            except Exception:
                error_body = ""
            return self._failure(
                start,
                "api_call_failed",
                "Gmail API returned HTTP " + str(getattr(exc, "code", "error")),
                {"http_status": getattr(exc, "code", None), "response": error_body},
            )
        except URLError as exc:
            return self._failure(start, "api_call_failed", "network error calling Gmail API", {"error": str(exc)})
        except Exception as exc:
            return self._failure(start, "api_call_failed", "unexpected error calling Gmail API", {"error": str(exc)})

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        failures = []
        try:
            if not isinstance(brief, dict):
                failures.append("invalid_brief")
                return "fail", failures

            creds = brief.get("_channel_credentials", {})
            if not self._token(creds):
                failures.append("no_social_connection")
            try:
                requested = int(brief.get("max_results") or brief.get("maxResults") or 10)
                if requested < 1 or requested > 100:
                    failures.append("max_results_clamped")
            except Exception:
                failures.append("invalid_max_results")
            if isinstance(content, str) and content.startswith("Failed to receive Gmail emails"):
                failures.append("api_call_failed")
        except Exception:
            failures.append("self_check_error")
        return ("fail" if failures else "pass"), failures
