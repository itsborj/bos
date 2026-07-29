from __future__ import annotations

import json
import mimetypes
import os
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from klaroha_sdk import ChannelModule

_TIKTOK_CREATOR_INFO_URL = "https://open.tiktokapis.com/v2/post/publish/creator_info/query/"
_TIKTOK_PUBLISH_INIT_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"
_TIKTOK_STATUS_URL = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"


class TikTokVideoPublishModule(ChannelModule):
    id = "marketing.channel.tiktok.video.publish"
    name = "TikTok Video Publish"
    vertical = "marketing"
    capability = "marketing.execute"
    platform_hint = "tiktok video publish"
    policy_default = "approval_gated"
    template = ""

    def _latency_ms(self, start: float) -> int:
        return round((time.perf_counter() - start) * 1000)

    def _attempt(self, start: float, status: str, error: str | None = None) -> dict:
        return {
            "provider": "tiktok",
            "model_id": "tiktok_content_posting_api",
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
            "content": "TikTok publish failed: " + message,
            "sell_price": None,
            "block": {
                "type": "tiktok_publish_result",
                "platform": "tiktok",
                "status": "failed",
                "reason_code": reason_code,
                "message": message,
                "details": details or {},
                "changed_resources": [],
                "allowed_actions": ["retry", "dismiss"],
            },
        }

    def _creds(self, brief: dict) -> dict:
        raw = brief.get("_channel_credentials", {}) if isinstance(brief, dict) else {}
        return raw if isinstance(raw, dict) else {}

    def _download(self, url: str) -> str:
        suffix = Path(url.split("?", 1)[0]).suffix or ".mp4"
        fd, path = tempfile.mkstemp(prefix="tiktok_upload_", suffix=suffix)
        os.close(fd)
        req = Request(url, headers={"User-Agent": "Klaroha/1.0"}, method="GET")
        with urlopen(req, timeout=120) as response, open(path, "wb") as fh:
            fh.write(response.read())
        return path

    def _field_from_context(self, brief: dict, key: str) -> str:
        import re

        ctx = str(brief.get("conversation_context") or brief.get("request") or "")
        pattern = re.compile(
            rf"\b{re.escape(key)}\s*:\s*(.*?)(?=\s+\b(?:video_url|video_file|video_path|asset_url|title|caption|description|privacy|privacy_level)\s*:|$)",
            re.IGNORECASE | re.DOTALL,
        )
        matches = list(pattern.finditer(ctx))
        return matches[-1].group(1).strip() if matches else ""

    def _brief_value(self, brief: dict, *keys: str) -> str:
        for key in keys:
            value = brief.get(key)
            if value:
                return str(value).strip()
        for key in keys:
            value = self._field_from_context(brief, key)
            if value:
                return value
        return ""

    def _video_path(self, brief: dict) -> tuple[str | None, bool]:
        path = self._brief_value(brief, "video_file", "video_path")
        if path:
            return path, False
        url = self._brief_value(brief, "video_url", "asset_url")
        if url:
            return self._download(url), True
        return None, False

    def _coerce_bool(self, value, default: bool = False) -> bool:
        if value is None or value == "":
            return default
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in {"1", "true", "yes", "y", "on"}:
            return True
        if text in {"0", "false", "no", "n", "off"}:
            return False
        return default

    def _int_or_none(self, value) -> int | None:
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _post_json(self, url: str, headers: dict, payload: dict | None = None) -> dict:
        request = Request(
            url,
            data=json.dumps(payload or {}).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urlopen(request, timeout=45) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}

    def _creator_info(self, token: str) -> dict:
        return self._post_json(
            _TIKTOK_CREATOR_INFO_URL,
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json; charset=UTF-8",
            },
            {},
        )

    def _init_publish(self, token: str, payload: dict) -> dict:
        return self._post_json(
            _TIKTOK_PUBLISH_INIT_URL,
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json; charset=UTF-8",
            },
            payload,
        )

    def _fetch_status(self, token: str, publish_id: str) -> dict:
        return self._post_json(
            _TIKTOK_STATUS_URL,
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json; charset=UTF-8",
            },
            {"publish_id": publish_id},
        )

    def _upload_video(self, upload_url: str, path: str, content_type: str) -> None:
        size = os.path.getsize(path)
        with open(path, "rb") as fh:
            data = fh.read()
        req = Request(
            upload_url,
            data=data,
            headers={
                "Content-Type": content_type,
                "Content-Length": str(size),
                "Content-Range": f"bytes 0-{size - 1}/{size}",
            },
            method="PUT",
        )
        with urlopen(req, timeout=300) as response:
            response.read()

    def _privacy_level(self, brief: dict, options: list[str]) -> str:
        raw = self._brief_value(brief, "privacy_level", "privacy")
        mapping = {
            "public": "PUBLIC_TO_EVERYONE",
            "public_to_everyone": "PUBLIC_TO_EVERYONE",
            "friends": "MUTUAL_FOLLOW_FRIENDS",
            "mutual_follow_friends": "MUTUAL_FOLLOW_FRIENDS",
            "followers": "FOLLOWER_OF_CREATOR",
            "follower_of_creator": "FOLLOWER_OF_CREATOR",
            "private": "SELF_ONLY",
            "self_only": "SELF_ONLY",
            "only_me": "SELF_ONLY",
        }
        chosen = mapping.get(str(raw or "").strip().lower(), str(raw or "").strip().upper()) if raw else "SELF_ONLY"
        if chosen in options:
            return chosen
        if "SELF_ONLY" in options:
            return "SELF_ONLY"
        return options[0] if options else "SELF_ONLY"

    def _caption(self, brief: dict) -> str:
        title = self._brief_value(brief, "caption", "title", "video_title")
        description = self._brief_value(brief, "description", "video_description")
        if title and description and description != title:
            return f"{title}\n\n{description}"[:2200]
        return (title or description or "")[:2200]

    def _api_error(self, payload: dict) -> tuple[str | None, str | None]:
        error = payload.get("error") or {}
        code = str(error.get("code") or "")
        if code and code != "ok":
            return code, str(error.get("message") or code)
        return None, None

    def _public_url(self, creator_username: str, post_ids: list[str]) -> str:
        if not creator_username or not post_ids:
            return ""
        username = creator_username.lstrip("@")
        return f"https://www.tiktok.com/@{username}/video/{post_ids[0]}"

    def execute_tool_result(self, brief: dict) -> tuple[dict, dict]:
        start = time.perf_counter()
        temp_path: str | None = None
        try:
            if not isinstance(brief, dict):
                return self._failure(start, "invalid_brief", "brief must be a dictionary")

            token = self._creds(brief).get("tiktok_page_token") or self._creds(brief).get("page_token") or self._creds(brief).get("access_token")
            if not token:
                return self._failure(start, "missing_credentials", "Connect TikTok for this brand first")

            path, is_temp = self._video_path(brief)
            temp_path = path if is_temp else None
            if not path:
                return self._failure(start, "missing_video", "Send a video_file, video_path, video_url, or asset_url")
            if not os.path.exists(path):
                return self._failure(start, "video_not_found", f"Video file not found: {path}")

            creator_info = self._creator_info(token)
            code, message = self._api_error(creator_info)
            if code:
                details = {"api_error": creator_info}
                if code == "scope_not_authorized":
                    return self._failure(start, code, "TikTok token is connected but missing the video.publish scope", details)
                return self._failure(start, code, message or "TikTok creator info query failed", details)

            creator_data = creator_info.get("data") or {}
            privacy_options = [str(v) for v in (creator_data.get("privacy_level_options") or []) if str(v)]
            privacy_level = self._privacy_level(brief, privacy_options)
            caption = self._caption(brief)
            size = os.path.getsize(path)
            content_type = mimetypes.guess_type(path)[0] or "video/mp4"
            post_info = {
                "privacy_level": privacy_level,
                "disable_duet": self._coerce_bool(brief.get("disable_duet"), False),
                "disable_comment": self._coerce_bool(brief.get("disable_comment"), False),
                "disable_stitch": self._coerce_bool(brief.get("disable_stitch"), False),
                "brand_content_toggle": self._coerce_bool(brief.get("brand_content_toggle"), False),
                "brand_organic_toggle": self._coerce_bool(brief.get("brand_organic_toggle"), False),
                "is_aigc": self._coerce_bool(brief.get("is_aigc"), False),
            }
            if caption:
                post_info["title"] = caption
            cover_ts = self._int_or_none(brief.get("video_cover_timestamp_ms") or self._field_from_context(brief, "video_cover_timestamp_ms"))
            if cover_ts is not None:
                post_info["video_cover_timestamp_ms"] = cover_ts

            init_payload = {
                "post_info": post_info,
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": size,
                    "chunk_size": size,
                    "total_chunk_count": 1,
                },
            }
            init_response = self._init_publish(token, init_payload)
            code, message = self._api_error(init_response)
            if code:
                return self._failure(start, code, message or "TikTok publish init failed", {"api_error": init_response})

            data = init_response.get("data") or {}
            publish_id = str(data.get("publish_id") or "")
            upload_url = str(data.get("upload_url") or "")
            if not publish_id:
                return self._failure(start, "api_call_failed", "TikTok publish init did not return a publish_id", {"response": init_response})
            if not upload_url:
                return self._failure(start, "api_call_failed", "TikTok publish init did not return an upload_url", {"response": init_response})

            self._upload_video(upload_url, path, content_type)

            interval = max(1, int(brief.get("status_poll_interval_sec") or 2))
            attempts = max(1, int(brief.get("status_poll_attempts") or 8))
            status_data: dict = {}
            status_value = "PROCESSING_UPLOAD"
            for attempt_index in range(attempts):
                status_response = self._fetch_status(token, publish_id)
                code, message = self._api_error(status_response)
                if code:
                    return self._failure(start, code, message or "TikTok publish status fetch failed", {"api_error": status_response, "publish_id": publish_id})
                status_data = status_response.get("data") or {}
                status_value = str(status_data.get("status") or "")
                if status_value in {"PUBLISH_COMPLETE", "FAILED", "SEND_TO_USER_INBOX"}:
                    break
                if attempt_index < attempts - 1:
                    time.sleep(interval)

            if status_value == "FAILED":
                return self._failure(
                    start,
                    "publish_failed",
                    str(status_data.get("fail_reason") or "TikTok reported the publish failed"),
                    {"publish_id": publish_id, "status": status_data},
                )

            post_ids = [str(v) for v in (status_data.get("publicaly_available_post_id") or []) if str(v)]
            creator_username = str(creator_data.get("creator_username") or "")
            url = self._public_url(creator_username, post_ids)
            processing = status_value not in {"PUBLISH_COMPLETE", "SEND_TO_USER_INBOX"}
            headline = "TikTok post submitted and is still processing." if processing else "TikTok video published."
            lines = [headline, "", f"Publish ID: {publish_id}"]
            if caption:
                lines.insert(1, f"Caption: {caption}")
            if url:
                lines.append(f"URL: {url}")
            if status_value:
                lines.append(f"Status: {status_value}")
            return self._attempt(start, "succeeded"), {
                "content": "\n".join(lines),
                "sell_price": None,
                "block": {
                    "type": "tiktok_publish_result",
                    "platform": "tiktok",
                    "status": "processing" if processing else "succeeded",
                    "publish_id": publish_id,
                    "post_ids": post_ids,
                    "url": url,
                    "privacy_level": privacy_level,
                    "creator_username": creator_username,
                    "changed_resources": post_ids or [publish_id],
                    "allowed_actions": ["view_on_tiktok" if url else "view_publish_status", "dismiss"],
                },
            }

        except HTTPError as exc:
            try:
                body = exc.read().decode("utf-8")[:800]
            except Exception:
                body = ""
            return self._failure(start, "api_call_failed", f"TikTok API returned HTTP {exc.code}", {"http_status": exc.code, "response": body})
        except (URLError, OSError, RuntimeError, ValueError) as exc:
            return self._failure(start, "api_call_failed", str(exc))
        finally:
            if temp_path:
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        failures: list[str] = []
        lowered = content.lower() if isinstance(content, str) else ""
        if "tiktok video published" not in lowered and "tiktok post submitted" not in lowered and "tiktok publish failed" not in lowered:
            failures.append("missing_tiktok_publish_status")
        return ("fail" if failures else "pass"), failures
