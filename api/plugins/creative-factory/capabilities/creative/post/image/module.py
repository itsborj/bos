from __future__ import annotations

import base64
import importlib.util
import time
from pathlib import Path

from klaroha_sdk import ChannelModule

# drive_client lives in the sibling google-drive plugin. Modules are loaded by path
# (not on sys.path), so resolve it relative to the active plugin root first.
_DRIVE_CLIENT_CANDIDATES = [
    Path(__file__).resolve().parents[5] / "google-drive" / "drive_client.py",
    Path("/external_plugins/google-drive/drive_client.py"),
    Path("/app/plugins/google-drive/drive_client.py"),
]


def _load_drive():
    for path in _DRIVE_CLIENT_CANDIDATES:
        if path.exists():
            spec = importlib.util.spec_from_file_location("google_drive_client_cf", str(path))
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
            return m
    raise FileNotFoundError("google-drive/drive_client.py not found in plugin root")


class CreativePostImageModule(ChannelModule):
    """Generate a Meta post creative (image) and store it in the brand's Drive for reuse.

    Relies on the host image hook: when the brief carries an `image_prompt`, runs.py
    generates the image via media.image.generate and injects `_image_data_b64` before
    this module runs. This module then uploads that image to the brand's Drive root
    (operator-picked) under Creative Assets/Meta Posts/. Generation is third-party;
    BOS routes and stores. Does NOT publish.
    """

    id = "creative.post.image"
    name = "Facebook Post"
    vertical = "creative"
    capability = "marketing.execute"
    # platform_hint drives the artifact title + feed-preview rendering on the client.
    platform_hint = "facebook post"
    policy_default = "generate_only"
    template = ""
    requires_generated_image = True

    def _attempt(self, start: float, status: str, error=None) -> dict:
        return {
            "provider": "creative_factory",
            "model_id": "post_image_v1",
            "mode": "tool",
            "status": status,
            "tokens_input": 0,
            "tokens_output": 0,
            "provider_cost": 0.0,
            "latency_ms": round((time.perf_counter() - start) * 1000),
            "error": error,
        }

    def _fail(self, start, reason, msg) -> tuple[dict, dict]:
        return self._attempt(start, "failed", reason), {
            "content": f"Meta post creative failed: {msg}",
            "block": {"type": "creative_post_asset", "status": "failed", "reason_code": reason, "message": msg, "allowed_actions": ["retry", "dismiss"]},
        }

    def execute_tool_result(self, brief: dict) -> tuple[dict, dict]:
        start = time.perf_counter()
        creds = brief.get("_channel_credentials", {}) if isinstance(brief, dict) else {}
        token = str(creds.get("page_token") or creds.get("google_drive_page_token") or "").strip()
        root = str(creds.get("drive_root_folder_id") or "").strip()
        img_b64 = brief.get("_image_data_b64")
        caption = str(
            brief.get("caption")
            or brief.get("post_text")
            or brief.get("copy")
            or brief.get("message")
            or brief.get("post_copy")
            or ""
        ).strip()

        if not img_b64:
            return self._fail(start, "no_image", "no image generated — include an image_prompt in the brief")

        # Drive upload — non-fatal. Creative is always returned for review even if Drive is unavailable.
        drive_file_id: str | None = None
        drive_web_view_link: str | None = None
        drive_name: str | None = None
        if token and root:
            dc = _load_drive()
            name = f"meta_post_{int(time.time())}.png"
            try:
                with dc.DriveClient(token) as client:
                    folder = client.ensure_path(["Creative Assets", "Meta Posts"], root)
                    meta = client.upload_file(name, base64.b64decode(img_b64), "image/png", folder)
                drive_file_id = meta.get("id")
                drive_web_view_link = meta.get("webViewLink")
                drive_name = meta.get("name")
            except Exception:
                pass  # Drive storage failure does not block the review card or publish

        content = (
            f"Meta post creative generated and saved to Drive ({drive_name})."
            if drive_name
            else "Meta post creative generated."
        )

        return self._attempt(start, "succeeded"), {
            "content": content,
            "block": {
                "type": "creative_post_asset",
                "status": "succeeded",
                "channel": "meta",
                "image_data_b64": img_b64,
                "mime_type": "image/png",
                "drive_file_mime": "image/png",
                "caption": caption or None,
                "message": caption or None,
                "drive_file_id": drive_file_id,
                "drive_web_view_link": drive_web_view_link,
                "drive_folder": "Creative Assets/Meta Posts" if drive_file_id else None,
                "reusable": bool(drive_file_id),
                "allowed_actions": ["publish", "regenerate", "dismiss"],
                "action_modules": {"publish": "marketing.channel.meta.posts.publish"},
            },
        }

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        if not isinstance(content, str):
            return "fail", ["content_not_string"]
        # Only fail when the image itself was not generated
        if content.lower().startswith("meta post creative failed"):
            return "fail", ["image_generation_failed"]
        return "pass", []
