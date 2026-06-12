from __future__ import annotations

import importlib.util
import time
from pathlib import Path

from klaroha_sdk import ChannelModule

# BOS's working subfolders, created UNDER the operator-picked root. The root itself
# is chosen by the operator via the Google Picker — BOS never creates the root.
_DEFAULT_SUBTREE = [
    ["Brand Assets", "Logos"],
    ["Brand Assets", "Products"],
    ["Brand Assets", "Footage"],
    ["Templates"],
    ["Archive"],
]


def _dc():
    p = Path(__file__).resolve().parents[4] / "drive_client.py"
    spec = importlib.util.spec_from_file_location("google_drive_client", str(p))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class DriveFolderSetupModule(ChannelModule):
    id = "drive.folder.setup"
    name = "Drive Folder Setup"
    vertical = "drive"
    capability = "marketing.execute"
    platform_hint = "google drive folder setup"
    policy_default = "generate_only"
    template = ""

    def execute_tool_result(self, brief: dict) -> tuple[dict, dict]:
        start = time.perf_counter()
        dc = _dc()
        token = dc.token_from_brief(brief)

        def fail(reason, msg):
            a = dc.attempt("failed", reason)
            a["latency_ms"] = round((time.perf_counter() - start) * 1000)
            return a, {"content": f"Drive folder setup failed: {msg}", "block": {"type": "drive_setup", "status": "failed", "reason_code": reason, "message": msg, "allowed_actions": ["retry", "dismiss"]}}

        if not token:
            return fail("missing_credentials", "Google Drive not connected for this brand")
        # Root resolved from brief override or credential slot (set by operator via Picker).
        creds = brief.get("_channel_credentials") or {}
        root = str(brief.get("root_folder_id") or creds.get("drive_root_folder_id") or "").strip()
        if not root:
            return fail("missing_root", "root_folder_id required — operator must pick a Drive root folder first")
        campaign = str(brief.get("campaign") or "").strip()

        subtree = [list(parts) for parts in _DEFAULT_SUBTREE]
        if campaign:
            for leaf in ("Creative Concepts", "Primitives/Image Plates", "Primitives/Video Plates", "Primitives/Motion Cards", "Blueprints", "Export Packages"):
                subtree.append(["Campaigns", campaign, *leaf.split("/")])

        created: dict[str, str] = {}
        try:
            with dc.DriveClient(token) as client:
                for parts in subtree:
                    folder_id = client.ensure_path(parts, root)
                    created["/".join(parts)] = folder_id
        except Exception as exc:
            return fail("drive_api_error", str(exc))

        a = dc.attempt("succeeded")
        a["latency_ms"] = round((time.perf_counter() - start) * 1000)
        return a, {
            "content": f"Ensured {len(created)} folder path(s) under the brand root.",
            "block": {
                "type": "drive_setup",
                "status": "succeeded",
                "root_folder_id": root,
                "folders": created,
                "allowed_actions": ["use", "dismiss"],
            },
        }
