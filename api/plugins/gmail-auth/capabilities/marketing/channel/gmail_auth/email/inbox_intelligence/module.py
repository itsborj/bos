from __future__ import annotations

import time

from klaroha_sdk import ChannelModule

_SIGNAL_RULES: list[tuple[str, list[str]]] = [
    ("unsubscribe", [
        "remove me", "unsubscribe", "stop emailing", "stop sending", "take me off",
        "opt out", "opt-out", "please remove",
    ]),
    ("booked", [
        "sent invite", "we're on for", "we are on for", "calendar invite", "booked",
        "confirmed for", "see you then", "see you at",
    ]),
    ("interested", [
        "tell me more", "sounds interesting", "sounds relevant", "i'm interested",
        "im interested", "can we chat", "can we talk", "let's connect", "lets connect",
        "would love to", "keen to learn", "keen to hear", "send me more",
        "how does it work", "schedule a call", "book a call",
    ]),
    ("pricing_concern", [
        "what's the cost", "whats the cost", "how much", "too expensive",
        "out of budget", "pricing", "price", "what does it cost", "cost per",
        "monthly fee", "annual fee",
    ]),
    ("not_now", [
        "reach out in", "try again in", "not right now", "maybe later",
        "on hold", "currently focused", "come back in", "next quarter",
        "next year", "not the right time", "too busy",
    ]),
    ("wrong_person", [
        "not my department", "not the right person", "try", "contact",
        "speak with", "talk to", "reach out to", "forward this to",
        "you want", "better person",
    ]),
    ("objection", [
        "we already use", "we have a solution", "not a priority", "not interested",
        "don't need", "dont need", "doesn't apply", "doesnt apply",
        "not relevant", "not for us", "we're good", "we are good",
    ]),
]

_ACTIONS: dict[str, str] = {
    "interested": "Book a call or move to warm follow-up sequence",
    "objection": "Send an objection-handling reply",
    "pricing_concern": "Share pricing page + ROI framing",
    "not_now": "Archive and set a follow-up reminder",
    "wrong_person": "Re-route to the named contact",
    "unsubscribe": "Remove immediately — do not reply",
    "booked": "Move to CRM and send a confirmation email",
    "unknown": "Review manually",
}

_PRIORITY_ORDER = [
    "unsubscribe", "booked", "interested", "pricing_concern",
    "objection", "not_now", "wrong_person", "unknown",
]


def _classify(subject: str, snippet: str) -> str:
    text = (subject + " " + snippet).lower()
    for category, keywords in _SIGNAL_RULES:
        if any(kw in text for kw in keywords):
            return category
    return "unknown"


class GmailInboxIntelligenceModule(ChannelModule):
    id = "marketing.channel.gmail_auth.email.inbox_intelligence"
    name = "Email Inbox Intelligence"
    vertical = "marketing"
    capability = "marketing.analytics"
    platform_hint = "gmail inbox"
    template = "marketing/channel/gmail_auth/email/inbox_intelligence/template.j2"

    max_chars = 0
    must_mention = []
    banned_phrases = []

    def _latency_ms(self, start: float) -> int:
        return round((time.perf_counter() - start) * 1000)

    def _attempt(self, start: float, status: str, error=None) -> dict:
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

    def _failure(self, start: float, reason_code: str, message: str, details=None) -> tuple[dict, dict]:
        return self._attempt(start, "failed", reason_code), {
            "content": "Inbox Intelligence failed: " + message,
            "sell_price": None,
            "block": {
                "type": "inbox_intelligence_result",
                "status": "failed",
                "reason_code": reason_code,
                "message": message,
                "details": details or {},
            },
        }

    def _token(self, creds: dict) -> str | None:
        if not isinstance(creds, dict):
            return None
        return creds.get("access_token") or creds.get("gmail_access_token") or creds.get("page_token")

    def _api_get_json(self, url: str, access_token: str) -> dict:
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

    def _header_value(self, headers: list[dict], name: str) -> str:
        name_lower = name.lower()
        for h in headers:
            if str(h.get("name", "")).lower() == name_lower:
                return h.get("value", "")
        return ""

    def execute_tool_result(self, brief: dict) -> tuple[dict, dict]:
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
                    "missing Gmail OAuth access token — connect Gmail in Admin → Brands",
                )

            from urllib.error import HTTPError, URLError
            from urllib.parse import urlencode

            max_results = min(int(brief.get("max_results") or 20), 50)
            query = brief.get("query") or "in:inbox"

            list_params = {"maxResults": max_results, "q": query}
            list_url = (
                "https://gmail.googleapis.com/gmail/v1/users/me/messages?"
                + urlencode(list_params)
            )
            list_result = self._api_get_json(list_url, access_token)
            message_refs = list_result.get("messages") or []

            signals: list[dict] = []
            for ref in message_refs:
                message_id = ref.get("id")
                if not message_id:
                    continue
                get_url = (
                    "https://gmail.googleapis.com/gmail/v1/users/me/messages/"
                    + str(message_id)
                    + "?format=metadata&metadataHeaders=From,Subject,Date"
                )
                message = self._api_get_json(get_url, access_token)
                headers = message.get("payload", {}).get("headers", [])
                subject = self._header_value(headers, "Subject")
                sender = self._header_value(headers, "From")
                snippet = message.get("snippet", "")
                category = _classify(subject, snippet)
                signals.append({
                    "message_id": message_id,
                    "from": sender,
                    "subject": subject,
                    "snippet": snippet[:200],
                    "category": category,
                    "recommended_action": _ACTIONS[category],
                })

            summary: dict[str, int] = {}
            for s in signals:
                cat = s["category"]
                summary[cat] = summary.get(cat, 0) + 1

            top_action = "No replies to classify"
            for priority_cat in _PRIORITY_ORDER:
                if priority_cat in summary:
                    top_action = _ACTIONS[priority_cat]
                    break

            count = len(signals)
            content = (
                f"Classified {count} inbox signal{'s' if count != 1 else ''}. "
                + "Top action: " + top_action
            )

            return self._attempt(start, "succeeded"), {
                "content": content,
                "sell_price": None,
                "block": {
                    "type": "inbox_intelligence_result",
                    "status": "succeeded",
                    "query": query,
                    "total_classified": count,
                    "summary": summary,
                    "top_action": top_action,
                    "signals": signals,
                },
            }

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
            return self._failure(start, "network_error", "network error calling Gmail API", {"error": str(exc)})
        except Exception as exc:
            return self._failure(start, "unexpected_error", "unexpected error", {"error": str(exc)})

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        failures: list[str] = []
        creds = brief.get("_channel_credentials", {}) if isinstance(brief, dict) else {}
        if not self._token(creds):
            failures.append("no_social_connection")
        if "Failed" in content or "failed" in content.lower() and "inbox" not in content.lower():
            failures.append("api_call_failed")
        return ("fail" if failures else "pass"), failures
