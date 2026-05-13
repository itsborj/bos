from __future__ import annotations

from klaroha_sdk import ChannelModule


class GmailSendEmailModule(ChannelModule):
    id = "marketing.channel.gmail_auth.email.send"
    name = "Gmail Send Email"
    vertical = "marketing"
    capability = "marketing.copywriting"
    platform_hint = "gmail send"
    template = "marketing/channel/gmail_auth/email/send/template.j2"

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
            "content": "Failed to send Gmail email: " + message,
            "sell_price": None,
            "block": {
                "type": "gmail_send_result",
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

    def _first_value(self, brief, keys):
        for key in keys:
            value = brief.get(key)
            if value is not None and value != "":
                return value
        return None

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

            recipients = self._as_list(self._first_value(brief, ["to", "recipient", "recipients"]))
            cc = self._as_list(brief.get("cc"))
            bcc = self._as_list(brief.get("bcc"))
            subject = self._first_value(brief, ["subject", "subject_line"])
            body = self._first_value(brief, ["body", "message", "email_body", "text_body"])
            html_body = brief.get("html_body")
            reply_to = brief.get("reply_to")
            thread_id = brief.get("thread_id")

            # If fields are missing, try to extract them from conversation_context.
            # CMO passes the full conversation as context; the plugin owns this parsing.
            ctx = brief.get("conversation_context", "")
            if ctx and (not recipients or not subject or not body):
                import re as _re
                if not recipients:
                    m = _re.search(r'\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\b', ctx)
                    if m:
                        recipients = [m.group(1)]
                if not subject or not body:
                    # Collect the most recent AI block — may span multiple lines
                    lines = ctx.splitlines()
                    ai_block_lines: list[str] = []
                    in_ai_block = False
                    for _line in lines:
                        stripped = _line.strip()
                        if stripped.upper().startswith("AI:"):
                            ai_block_lines = [stripped[3:].strip()]
                            in_ai_block = True
                        elif in_ai_block:
                            if stripped.upper().startswith("USER:"):
                                in_ai_block = False
                            else:
                                ai_block_lines.append(stripped)
                    if ai_block_lines:
                        content = "\n".join(ai_block_lines).strip()
                        subj_m = _re.search(r'\bSubject:\s*(.+?)(?:\n|$)', content, _re.IGNORECASE)
                        if subj_m:
                            if not subject:
                                subject = subj_m.group(1).strip()
                            if not body:
                                body = content[subj_m.end():].strip() or None
                        elif content and not body:
                            body = content

            missing = []
            if not recipients:
                missing.append("to")
            if not subject:
                missing.append("subject")
            if not body and not html_body:
                missing.append("body")
            if missing:
                return self._failure(
                    start,
                    "missing_required_fields",
                    "missing required field(s): " + ", ".join(missing),
                    {"missing": missing},
                )

            from email.message import EmailMessage
            import base64
            import json
            from urllib.error import HTTPError, URLError
            from urllib.request import Request, urlopen

            msg = EmailMessage()
            msg["To"] = ", ".join(recipients)
            msg["Subject"] = str(subject)
            if cc:
                msg["Cc"] = ", ".join(cc)
            if bcc:
                msg["Bcc"] = ", ".join(bcc)
            if reply_to:
                msg["Reply-To"] = str(reply_to)

            if body:
                msg.set_content(str(body))
                if html_body:
                    msg.add_alternative(str(html_body), subtype="html")
            else:
                msg.set_content("This message contains an HTML body. Please use an HTML-capable mail client.")
                msg.add_alternative(str(html_body), subtype="html")

            raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
            payload = {"raw": raw_message}
            if thread_id:
                payload["threadId"] = str(thread_id)

            request = Request(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": "Bearer " + access_token,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                method="POST",
            )

            with urlopen(request, timeout=30) as response:
                response_body = response.read().decode("utf-8")
                gmail_result = json.loads(response_body) if response_body else {}

            message_id = gmail_result.get("id")
            result_data = {
                "content": "Sent Gmail email to " + ", ".join(recipients),
                "sell_price": None,
                "block": {
                    "type": "gmail_send_result",
                    "status": "succeeded",
                    "message_id": message_id,
                    "thread_id": gmail_result.get("threadId"),
                    "label_ids": gmail_result.get("labelIds", []),
                    "to": recipients,
                    "cc": cc,
                    "bcc_count": len(bcc),
                    "subject": str(subject),
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

            if not self._as_list(self._first_value(brief, ["to", "recipient", "recipients"])):
                failures.append("missing_to")
            if not self._first_value(brief, ["subject", "subject_line"]):
                failures.append("missing_subject_line")
            if not self._first_value(brief, ["body", "message", "email_body", "text_body"]) and not brief.get("html_body"):
                failures.append("missing_body")
            if isinstance(content, str) and content.startswith("Failed to send Gmail email"):
                failures.append("api_call_failed")
        except Exception:
            failures.append("self_check_error")
        return ("fail" if failures else "pass"), failures
