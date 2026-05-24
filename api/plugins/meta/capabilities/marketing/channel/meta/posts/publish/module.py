from __future__ import annotations

import json
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from klaroha_sdk import ChannelModule

_GRAPH = "https://graph.facebook.com/v21.0"


class MetaPostsPublishModule(ChannelModule):
    id = "marketing.channel.meta.posts.publish"
    name = "Facebook Post Publish"
    vertical = "marketing"
    capability = "marketing.execute"
    platform_hint = "facebook post publish"
    policy_default = "approval_gated"
    template = ""

    max_chars = 0
    must_mention = []
    banned_phrases = []

    def _latency_ms(self, start: float) -> int:
        return round((time.perf_counter() - start) * 1000)

    def _attempt(self, start: float, status: str, error: str | None = None) -> dict:
        return {
            "provider": "meta",
            "model_id": "meta_graph_api_v21",
            "mode": "tool",
            "status": status,
            "tokens_input": 0,
            "tokens_output": 0,
            "provider_cost": 0.0,
            "latency_ms": self._latency_ms(start),
            "error": error,
        }

    def _failure(self, start: float, reason_code: str, message: str, details: dict | None = None) -> tuple[dict, dict]:
        return self._attempt(start, "failed", reason_code), {
            "content": f"Failed to publish Facebook post: {message}",
            "sell_price": None,
            "block": {
                "type": "fb_page_post_result",
                "platform": "facebook",
                "status": "failed",
                "reason_code": reason_code,
                "message": message,
                "details": details or {},
                "changed_resources": [],
            },
        }

    def _creds(self, brief: dict) -> dict:
        raw = brief.get("_channel_credentials", {}) if isinstance(brief, dict) else {}
        return raw if isinstance(raw, dict) else {}

    def _post_json(self, url: str, payload: dict) -> dict:
        data = urlencode(payload).encode("utf-8")
        req = Request(url, data=data, method="POST")
        with urlopen(req, timeout=35) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _post_photo_binary(self, url: str, image_data: bytes, mime: str, fields: dict) -> dict:
        """Multipart/form-data POST for binary image uploads to Facebook Photos API."""
        boundary = b"klaroha_fb_boundary_9a2f1e"
        body = b""
        for key, val in fields.items():
            body += b"--" + boundary + b"\r\n"
            body += f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode()
            body += str(val).encode() + b"\r\n"
        body += b"--" + boundary + b"\r\n"
        body += b'Content-Disposition: form-data; name="source"; filename="image"\r\n'
        body += f"Content-Type: {mime}\r\n\r\n".encode()
        body += image_data + b"\r\n"
        body += b"--" + boundary + b"--\r\n"
        req = Request(url, data=body, method="POST")
        req.add_header("Content-Type", f"multipart/form-data; boundary={boundary.decode()}")
        with urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _message_from_brief(self, brief: dict) -> str:
        for key in ("message", "caption", "post_text", "text", "approved_post_text"):
            value = str(brief.get(key, "")).strip()
            if value:
                return value

        directive = str(brief.get("cmo_directive_text", "")).strip()
        if directive:
            quoted = re.search(r'["“”](.+?)["“”]', directive, flags=re.DOTALL)
            if quoted and quoted.group(1).strip():
                return quoted.group(1).strip()

        task_name = str(brief.get("task_name", "")).strip()
        if task_name and not task_name.lower().startswith(("publish", "post to", "post on")):
            return task_name

        # Fallback: extract from the last USER message in conversation context.
        # Handles "post this to facebook: <text>" when the LLM omits message: param.
        conv = str(brief.get("conversation_context", "")).strip()
        if conv:
            last_user = ""
            for line in reversed(conv.splitlines()):
                if line.strip().upper().startswith("USER:"):
                    last_user = line.strip()[5:].strip()
                    break
            if last_user:
                m = re.search(
                    r"(?:post|publish|send)\b.{0,40}?(?:to|on|in)\b.{0,25}?"
                    r"(?:facebook|fb)\b[^:]*:\s*(.+)",
                    last_user,
                    flags=re.IGNORECASE | re.DOTALL,
                )
                if m and m.group(1).strip():
                    return m.group(1).strip()

        return ""

    def execute_tool_result(self, brief: dict) -> tuple[dict, dict]:
        start = time.perf_counter()
        try:
            if not isinstance(brief, dict):
                return self._failure(start, "invalid_brief", "brief must be a dictionary")

            creds = self._creds(brief)
            token = creds.get("facebook_page_token") or creds.get("page_token") or creds.get("access_token")
            page_id = creds.get("facebook_page_id") or creds.get("page_id")

            if not token:
                return self._failure(start, "missing_credentials", "Facebook page token not connected")
            if not page_id:
                return self._failure(start, "missing_credentials", "Facebook page ID not found")

            message = self._message_from_brief(brief)
            if not message:
                return self._failure(start, "missing_message", "brief must include message (the approved post text)")

            # _image_data_b64 is pre-resolved by the orchestrator (from Drive attachment,
            # direct generation, or any other source) — module never downloads from Drive.
            image_data_b64 = brief.get("_image_data_b64") or ""
            image_mime = str(brief.get("_image_mime") or "image/png").strip()
            image_url = str(brief.get("image_url") or "").strip()
            link = brief.get("link") or None

            if image_data_b64:
                import base64
                image_data = base64.b64decode(image_data_b64)
                fields = {"message": message, "access_token": token, "published": "true"}
                result = self._post_photo_binary(f"{_GRAPH}/{page_id}/photos", image_data, image_mime, fields)
                post_id = result.get("post_id") or result.get("id", "")
            elif image_url:
                payload: dict = {"url": image_url, "message": message, "access_token": token, "published": "true"}
                result = self._post_json(f"{_GRAPH}/{page_id}/photos", payload)
                post_id = result.get("post_id") or result.get("id", "")
            else:
                payload = {"message": message, "access_token": token}
                if link:
                    payload["link"] = link
                result = self._post_json(f"{_GRAPH}/{page_id}/feed", payload)
                post_id = result.get("id", "")

            permalink = f"https://www.facebook.com/{post_id.replace('_', '/posts/')}" if post_id else None

            content = (
                f"# Facebook Post Published\n\n"
                f"{message[:200]}{'…' if len(message) > 200 else ''}\n\n"
                f"Post ID: {post_id}"
            )

            return self._attempt(start, "succeeded"), {
                "content": content,
                "sell_price": None,
                "block": {
                    "type": "fb_page_post_result",
                    "platform": "facebook",
                    "status": "succeeded",
                    "post_id": post_id,
                    "page_id": page_id,
                    "message_preview": message[:280],
                    "permalink": permalink,
                    "changed_resources": [post_id],
                    "allowed_actions": ["view_on_facebook", "dismiss"],
                },
            }

        except HTTPError as exc:
            try:
                body = exc.read().decode("utf-8")[:400]
            except Exception:
                body = ""
            return self._failure(start, "api_call_failed", f"Graph API returned HTTP {exc.code}", {"http_status": exc.code, "response": body})
        except URLError as exc:
            return self._failure(start, "api_call_failed", "Network error calling Meta Graph API", {"error": str(exc)})
        except Exception as exc:
            return self._failure(start, "api_call_failed", "Unexpected error publishing post", {"error": str(exc)})

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        failures = []
        lowered = content.lower() if isinstance(content, str) else ""
        if "published" not in lowered and "post id" not in lowered:
            failures.append("missing_publish_confirmation")
        return ("fail" if failures else "pass"), failures
