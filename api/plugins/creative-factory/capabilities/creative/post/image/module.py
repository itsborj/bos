from __future__ import annotations

import base64
import importlib.util
import time
from pathlib import Path

from klaroha_sdk import ChannelModule

# drive_client lives in the sibling google-drive plugin. Modules are loaded by path
# (not on sys.path), so load it by its known in-container absolute path.
_DRIVE_CLIENT_PATH = "/app/plugins/google-drive/drive_client.py"


def _load_drive():
    spec = importlib.util.spec_from_file_location("google_drive_client_cf", _DRIVE_CLIENT_PATH)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


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
        if not token:
            return self._fail(start, "drive_not_connected", "Google Drive not connected for this brand")
        if not root:
            return self._fail(start, "no_root_folder", "no Drive root folder selected — pick one in Admin → Brands")

        dc = _load_drive()
        name = f"meta_post_{int(time.time())}.png"
        try:
            with dc.DriveClient(token) as client:
                folder = client.ensure_path(["Creative Assets", "Meta Posts"], root)
                meta = client.upload_file(name, base64.b64decode(img_b64), "image/png", folder)
        except Exception as exc:
            return self._fail(start, "drive_upload_failed", str(exc))

        return self._attempt(start, "succeeded"), {
            "content": f"Meta post creative generated and saved to Drive ({meta.get('name')}).",
            "block": {
                "type": "creative_post_asset",
                "status": "succeeded",
                "channel": "meta",
                "image_data_b64": img_b64,
                "mime_type": "image/png",
                "drive_file_mime": "image/png",
                "caption": caption or None,
                "message": caption or None,
                "drive_file_id": meta.get("id"),
                "drive_web_view_link": meta.get("webViewLink"),
                "drive_folder": "Creative Assets/Meta Posts",
                "reusable": True,
                "allowed_actions": ["publish", "regenerate", "dismiss"],
                "action_modules": {"publish": "marketing.channel.meta.posts.publish"},
            },
        }

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        # A failed run (e.g. Drive not connected) must NOT surface as an approvable draft.
        # Fail the check so the run is marked partial and rendered as a problem, not "ready".
        if not isinstance(content, str):
            return "fail", ["content_not_string"]
        if content.lower().startswith("meta post creative failed"):
            return "fail", ["generation_or_storage_failed"]
        return "pass", []
