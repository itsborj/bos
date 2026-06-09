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


class DriveAssetGetModule(ChannelModule):
    id = "drive.asset.get"
    name = "Drive Asset Get"
    vertical = "drive"
    capability = "marketing.execute"
    platform_hint = "google drive get"
    policy_default = "generate_only"
    template = ""

    def execute_tool_result(self, brief: dict) -> tuple[dict, dict]:
        start = time.perf_counter()
        dc = _dc()
        token = dc.token_from_brief(brief)

        def fail(reason, msg):
            a = dc.attempt("failed", reason)
            a["latency_ms"] = round((time.perf_counter() - start) * 1000)
            return a, {"content": f"Drive get failed: {msg}", "block": {"type": "drive_asset", "status": "failed", "reason_code": reason, "message": msg, "allowed_actions": ["retry", "dismiss"]}}

        if not token:
            return fail("missing_credentials", "Google Drive not connected for this brand")
        file_id = str(brief.get("file_id") or "").strip()
        if not file_id:
            return fail("missing_input", "file_id is required")
        include_bytes = bool(brief.get("include_bytes"))

        try:
            with dc.DriveClient(token) as client:
                meta = client.get_file_meta(file_id)
                content_b64 = base64.b64encode(client.download_file(file_id)).decode("utf-8") if include_bytes else None
        except Exception as exc:
            return fail("drive_api_error", str(exc))

        a = dc.attempt("succeeded")
        a["latency_ms"] = round((time.perf_counter() - start) * 1000)
        return a, {
            "content": f"Retrieved {meta.get('name')} from Drive.",
            "block": {
                "type": "drive_asset",
                "status": "succeeded",
                "drive_file_id": meta.get("id"),
                "name": meta.get("name"),
                "mime_type": meta.get("mimeType"),
                "web_view_link": meta.get("webViewLink"),
                "content_b64": content_b64,
                "allowed_actions": ["use", "dismiss"],
            },
        }
