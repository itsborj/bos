from __future__ import annotations

import base64
import importlib.util
import time
from pathlib import Path

from klaroha_sdk import ChannelModule


def _dc():
    p = Path(__file__).resolve().parents[4] / "drive_client.py"
    spec = importlib.util.spec_from_file_location("google_drive_client", str(p))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class DriveAssetUploadModule(ChannelModule):
    id = "drive.asset.upload"
    name = "Drive Asset Upload"
    vertical = "drive"
    capability = "marketing.execute"
    platform_hint = "google drive upload"
    policy_default = "generate_only"
    template = ""

    def execute_tool_result(self, brief: dict) -> tuple[dict, dict]:
        start = time.perf_counter()
        dc = _dc()
        token = dc.token_from_brief(brief)

        def fail(reason, msg):
            a = dc.attempt("failed", reason)
            a["latency_ms"] = round((time.perf_counter() - start) * 1000)
            return a, {"content": f"Drive upload failed: {msg}", "block": {"type": "drive_asset", "status": "failed", "reason_code": reason, "message": msg, "allowed_actions": ["retry", "dismiss"]}}

        if not token:
            return fail("missing_credentials", "Google Drive not connected for this brand")
        parent = str(brief.get("parent_folder_id") or "").strip()
        name = str(brief.get("filename") or "").strip()
        content_b64 = brief.get("content_b64") or brief.get("_image_data_b64")
        mime = str(brief.get("mime_type") or "image/png")
        if not parent or not name or not content_b64:
            return fail("missing_input", "parent_folder_id, filename, and content_b64 are required")

        try:
            with dc.DriveClient(token) as client:
                meta = client.upload_file(name, base64.b64decode(content_b64), mime, parent)
        except Exception as exc:
            return fail("drive_api_error", str(exc))

        a = dc.attempt("succeeded")
        a["latency_ms"] = round((time.perf_counter() - start) * 1000)
        return a, {
            "content": f"Uploaded {meta.get('name')} to Drive.",
            "block": {
                "type": "drive_asset",
                "status": "succeeded",
                "drive_file_id": meta.get("id"),
                "name": meta.get("name"),
                "mime_type": meta.get("mimeType"),
                "web_view_link": meta.get("webViewLink"),
                "parent_folder_id": parent,
                "allowed_actions": ["use", "dismiss"],
            },
        }
