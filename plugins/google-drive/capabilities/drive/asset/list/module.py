from __future__ import annotations

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


class DriveAssetListModule(ChannelModule):
    id = "drive.asset.list"
    name = "Drive Asset List"
    vertical = "drive"
    capability = "marketing.execute"
    platform_hint = "google drive list"
    policy_default = "generate_only"
    template = ""

    def execute_tool_result(self, brief: dict) -> tuple[dict, dict]:
        start = time.perf_counter()
        dc = _dc()
        token = dc.token_from_brief(brief)

        def fail(reason, msg):
            a = dc.attempt("failed", reason)
            a["latency_ms"] = round((time.perf_counter() - start) * 1000)
            return a, {"content": f"Drive list failed: {msg}", "block": {"type": "drive_listing", "status": "failed", "reason_code": reason, "message": msg, "allowed_actions": ["retry", "dismiss"]}}

        if not token:
            return fail("missing_credentials", "Google Drive not connected for this brand")
        parent = str(brief.get("parent_folder_id") or "").strip()
        if not parent:
            return fail("missing_input", "parent_folder_id is required")
        mime = brief.get("mime_type") or None

        try:
            with dc.DriveClient(token) as client:
                files = client.list_children(parent, mime)
        except Exception as exc:
            return fail("drive_api_error", str(exc))

        a = dc.attempt("succeeded")
        a["latency_ms"] = round((time.perf_counter() - start) * 1000)
        return a, {
            "content": f"Found {len(files)} item(s) in folder.",
            "block": {
                "type": "drive_listing",
                "status": "succeeded",
                "parent_folder_id": parent,
                "files": files,
                "count": len(files),
                "allowed_actions": ["use", "dismiss"],
            },
        }
