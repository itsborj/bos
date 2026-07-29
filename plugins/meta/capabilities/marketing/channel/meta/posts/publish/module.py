from __future__ import annotations

import io
import json
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from klaroha_sdk import ChannelModule

_GRAPH = "https://graph.facebook.com/v21.0"


def _sanitize_marketing_copy(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    blocked_prefixes = (
        "template:", "format:", "headline:", "subheadline:", "body copy:", "body:",
        "cta:", "visual direction:", "asset/brand notes:", "campaign:",
        "json_revision_spec:", "source_render_spec:", "revision source panel:",
    )
    blocked_fragments = (
        "json_revision_spec", "source_render_spec", "revision source panel",
        "you are editing an existing approved social ad", "apply the json revision spec exactly",
    )
    kept: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if kept and kept[-1] != "":
                kept.append("")
            continue
        lowered = line.lower()
        if lowered.startswith(blocked_prefixes):
            continue
        if any(fragment in lowered for fragment in blocked_fragments):
            continue
        kept.append(line)
    while kept and kept[-1] == "":
        kept.pop()
    cleaned = "\n".join(kept).strip()
    return cleaned if cleaned not in {"-", "—", "_"} else ""


class MetaGraphError(Exception):
    def __init__(self, status: int, body: str):
        super().__init__(f"Graph API returned HTTP {status}")
        self.status = status
        self.body = body


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

    def _with_retry(self, call):
        """Retry transient Meta 5xx errors without hiding the final Graph body."""
        last_status = 0
        last_body = ""
        for attempt in range(3):
            try:
                return call()
            except HTTPError as exc:
                try:
                    body = exc.read().decode("utf-8")[:800]
                except Exception:
                    body = ""
                last_status = exc.code
                last_body = body
                if exc.code in {500, 502, 503, 504} and attempt < 2:
                    time.sleep(1.0 + attempt)
                    continue
                raise MetaGraphError(exc.code, body) from exc
        raise MetaGraphError(last_status or 500, last_body)

    def _normalize_photo_for_meta(self, image_data: bytes, mime: str) -> tuple[bytes, str]:
        """Normalize swapped/generated Drive images before Facebook upload.

        Meta can return opaque code=1/subcode=99 errors for large or unsupported
        image encodings. Keep small JPEG/PNG/GIF images as-is; otherwise convert
        to a web-safe JPEG with bounded dimensions for faster, more reliable
        publishing.
        """
        normalized_mime = (mime or "image/jpeg").split(";")[0].strip().lower()
        if normalized_mime in {"image/jpeg", "image/jpg", "image/png", "image/gif"} and len(image_data) <= 7_500_000:
            return image_data, "image/jpeg" if normalized_mime == "image/jpg" else normalized_mime
        try:
            from PIL import Image
            with Image.open(io.BytesIO(image_data)) as img:
                img.thumbnail((4096, 4096))
                if img.mode in ("RGBA", "LA"):
                    bg = Image.new("RGB", img.size, (255, 255, 255))
                    bg.paste(img, mask=img.getchannel("A"))
                    img = bg
                elif img.mode != "RGB":
                    img = img.convert("RGB")
                out = io.BytesIO()
                img.save(out, format="JPEG", quality=88, optimize=True, progressive=True)
                return out.getvalue(), "image/jpeg"
        except Exception:
            return image_data, normalized_mime or "image/jpeg"

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

    def _scheduled_timestamp(self, brief: dict) -> tuple[int | None, str | None]:
        """Return a Meta scheduled_publish_time epoch when the brief asks to schedule.

        Accepts operator/API overrides such as scheduled_at/publish_at in ISO-8601
        form or scheduled_publish_time as epoch seconds. Meta requires scheduled
        posts to be at least 10 minutes and no more than 75 days in the future.
        """
        raw = None
        for key in ("scheduled_publish_time", "scheduled_at", "publish_at", "schedule_at"):
            value = brief.get(key)
            if value not in (None, ""):
                raw = value
                break
        if raw in (None, ""):
            return None, None

        try:
            if isinstance(raw, (int, float)) or (isinstance(raw, str) and raw.strip().isdigit()):
                scheduled = datetime.fromtimestamp(int(raw), tz=timezone.utc)
            else:
                text = str(raw).strip()
                scheduled = datetime.fromisoformat(text.replace("Z", "+00:00"))
                if scheduled.tzinfo is None:
                    scheduled = scheduled.replace(tzinfo=timezone.utc)
                scheduled = scheduled.astimezone(timezone.utc)
        except Exception:
            return None, "scheduled_at must be an ISO-8601 datetime or Unix epoch seconds"

        now = datetime.now(timezone.utc)
        if scheduled < now + timedelta(minutes=10):
            return None, "scheduled_at must be at least 10 minutes in the future"
        if scheduled > now + timedelta(days=75):
            return None, "scheduled_at must be within 75 days"
        return int(scheduled.timestamp()), None

    def _message_from_brief(self, brief: dict) -> str:
        # Generic approved creative handoff: generators like Postcraft produce
        # assets and copy, but Meta owns posting. Accept their final artifact
        # fields directly instead of requiring the generator or chat router to
        # know Facebook publish details.
        creative_parts: list[str] = []
        for key in ("headline", "subheadline", "body_copy", "body"):
            value = _sanitize_marketing_copy(str(brief.get(key, "")))
            if value and value not in creative_parts:
                creative_parts.append(value)
        cta = _sanitize_marketing_copy(str(brief.get("cta_text") or brief.get("cta") or ""))
        if cta and cta not in creative_parts:
            creative_parts.append(cta)
        creative_message = "\n\n".join(creative_parts)
        generation_prompt = str(brief.get("prompt") or "").strip()

        for key in ("message", "caption", "post_text", "text", "approved_post_text"):
            value = str(brief.get(key, "")).strip()
            if not value:
                continue
            # Some generic image approval UIs use the image generation prompt as
            # a caption fallback. If the approved artifact also carries copy
            # fields, publish the human-facing copy instead of leaking the prompt.
            if creative_message and generation_prompt and value == generation_prompt:
                continue
            cleaned = _sanitize_marketing_copy(value)
            if cleaned:
                return cleaned

        if creative_message:
            return creative_message

        directive = str(brief.get("cmo_directive_text", "")).strip()
        if directive:
            quoted = re.search(r'["“”](.+?)["“”]', directive, flags=re.DOTALL)
            if quoted and quoted.group(1).strip():
                cleaned = _sanitize_marketing_copy(quoted.group(1).strip())
                if cleaned:
                    return cleaned

        task_name = str(brief.get("task_name", "")).strip()
        if task_name and not task_name.lower().startswith(("publish", "post to", "post on")):
            cleaned = _sanitize_marketing_copy(task_name)
            if cleaned:
                return cleaned

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
                    cleaned = _sanitize_marketing_copy(m.group(1).strip())
                    if cleaned:
                        return cleaned

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

            scheduled_ts, schedule_error = self._scheduled_timestamp(brief)
            if schedule_error:
                return self._failure(start, "invalid_schedule", schedule_error)
            requested_action = str(brief.get("artifact_action") or brief.get("action") or "").strip().lower()
            if requested_action.startswith("schedule") and scheduled_ts is None:
                return self._failure(
                    start,
                    "missing_schedule_time",
                    "schedule_facebook requires scheduled_at, publish_at, schedule_at, or scheduled_publish_time",
                )
            is_scheduled = scheduled_ts is not None
            scheduled_iso = datetime.fromtimestamp(scheduled_ts, tz=timezone.utc).isoformat() if scheduled_ts else None

            # _image_data_b64 is pre-resolved by the orchestrator (from Drive attachment,
            # direct generation, or any other source). image_data_b64 is accepted for
            # legacy/generator artifacts that cross the action boundary without Drive.
            image_data_b64 = brief.get("_image_data_b64") or brief.get("image_data_b64") or ""
            image_mime = str(brief.get("_image_mime") or brief.get("mime_type") or "image/png").strip()
            image_url = str(brief.get("image_url") or "").strip()
            link = brief.get("link") or None

            media_fbid = ""
            if image_url:
                # Keep public image URLs on the Page stream by creating a /feed
                # link post that points at the image URL. Live testing showed
                # /feed source can be accepted but not render the image preview;
                # /feed link=<image_url> returns an image_share attachment and
                # full_picture without touching /photos.
                feed_payload = {"message": message, "link": image_url, "access_token": token}
                if scheduled_ts:
                    feed_payload["published"] = "false"
                    feed_payload["scheduled_publish_time"] = str(scheduled_ts)
                result = self._with_retry(lambda: self._post_json(f"{_GRAPH}/{page_id}/feed", feed_payload))
                post_id = result.get("id", "")
            elif image_data_b64:
                import base64
                image_data = base64.b64decode(image_data_b64)
                image_data, image_mime = self._normalize_photo_for_meta(image_data, image_mime)
                # Binary/Drive images do not have a public fetchable URL for
                # /feed source (Meta rejects multipart /feed source with
                # "source should represent a valid URL"). Upload unpublished,
                # then attach to /feed as the fallback for private media bytes.
                fields = {"access_token": token, "published": "false"}
                media_result = self._with_retry(lambda: self._post_photo_binary(f"{_GRAPH}/{page_id}/photos", image_data, image_mime, fields))
                media_fbid = str(media_result.get("id") or "")
                feed_payload = {"message": message, "access_token": token, "attached_media[0]": json.dumps({"media_fbid": media_fbid})}
                if scheduled_ts:
                    feed_payload["published"] = "false"
                    feed_payload["scheduled_publish_time"] = str(scheduled_ts)
                result = self._with_retry(lambda: self._post_json(f"{_GRAPH}/{page_id}/feed", feed_payload))
                post_id = result.get("id", "")
            else:
                payload = {"message": message, "access_token": token}
                if link:
                    payload["link"] = link
                if scheduled_ts:
                    payload["published"] = "false"
                    payload["scheduled_publish_time"] = str(scheduled_ts)
                result = self._with_retry(lambda: self._post_json(f"{_GRAPH}/{page_id}/feed", payload))
                post_id = result.get("id", "")

            permalink = None if is_scheduled else (f"https://www.facebook.com/{post_id.replace('_', '/posts/')}" if post_id else None)

            content = (
                f"# Facebook Post {'Scheduled' if is_scheduled else 'Published'}\n\n"
                f"{message[:200]}{'…' if len(message) > 200 else ''}\n\n"
                + (f"Scheduled for: {scheduled_iso}\n" if scheduled_iso else "")
                + f"Post ID: {post_id}"
            )

            status = "scheduled" if is_scheduled else "succeeded"
            block = {
                "type": "fb_page_post_result",
                "platform": "facebook",
                "status": status,
                "post_id": post_id,
                "page_id": page_id,
                "message_preview": message[:280],
                "permalink": permalink,
                "changed_resources": [post_id] if post_id else [],
                "allowed_actions": ["dismiss"] if is_scheduled else ["view_on_facebook", "dismiss"],
            }
            if media_fbid:
                block["media_fbid"] = media_fbid
            if scheduled_ts:
                block["scheduled_publish_time"] = scheduled_ts
                block["scheduled_at"] = scheduled_iso

            return self._attempt(start, "succeeded"), {
                "content": content,
                "sell_price": None,
                "block": block,
            }

        except MetaGraphError as exc:
            return self._failure(start, "api_call_failed", f"Graph API returned HTTP {exc.status}", {"http_status": exc.status, "response": exc.body})
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
