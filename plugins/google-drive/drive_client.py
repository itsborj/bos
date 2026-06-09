"""Self-contained Google Drive REST v3 client for the google-drive plugin.

Sync (so it can run inside a ChannelModule's execute_tool_result) and dependency-free
beyond httpx. Takes an OAuth access token (resolved by the host via get_page_token and
injected through brief._channel_credentials) — never reads settings or the DB itself.

Failures raise loudly (raise_for_status). No bare except / silent fallback — a credential
or API error must surface, never resolve to the wrong folder.
"""
from __future__ import annotations

import json
from typing import Optional

import httpx

_FILES = "https://www.googleapis.com/drive/v3/files"
_UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"
_DRIVES = "https://www.googleapis.com/drive/v3/drives"
_FOLDER_MIME = "application/vnd.google-apps.folder"


def attempt(status: str, error: Optional[str] = None) -> dict:
    """Standard module execution record for drive.* capabilities."""
    return {
        "provider": "google_drive",
        "model_id": "drive_v3",
        "mode": "tool",
        "status": status,
        "tokens_input": 0,
        "tokens_output": 0,
        "provider_cost": 0.0,
        "latency_ms": 0,
        "error": error,
    }


def token_from_brief(brief: dict) -> str:
    creds = brief.get("_channel_credentials", {}) if isinstance(brief, dict) else {}
    return str(creds.get("page_token") or creds.get("google_drive_page_token") or creds.get("access_token") or "").strip()


class DriveClient:
    def __init__(self, access_token: str, timeout: float = 60.0):
        if not access_token:
            raise ValueError("DriveClient requires an access token")
        self._client = httpx.Client(
            timeout=timeout,
            headers={"Authorization": f"Bearer {access_token}"},
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "DriveClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ── folders ──────────────────────────────────────────────────────────────

    def find_folder(self, name: str, parent_id: Optional[str] = None) -> Optional[dict]:
        safe = name.replace("\\", "\\\\").replace("'", "\\'")
        q = f"name = '{safe}' and mimeType = '{_FOLDER_MIME}' and trashed = false"
        if parent_id:
            q += f" and '{parent_id}' in parents"
        r = self._client.get(_FILES, params={"q": q, "fields": "files(id,name,webViewLink)", "pageSize": 1})
        r.raise_for_status()
        files = r.json().get("files", [])
        return files[0] if files else None

    def ensure_folder(self, name: str, parent_id: Optional[str] = None) -> dict:
        """Find a folder by name under parent, or create it. Returns {id, name, webViewLink}."""
        existing = self.find_folder(name, parent_id)
        if existing:
            return existing
        body = {"name": name, "mimeType": _FOLDER_MIME}
        if parent_id:
            body["parents"] = [parent_id]
        r = self._client.post(_FILES, params={"fields": "id,name,webViewLink"}, json=body)
        r.raise_for_status()
        return r.json()

    def ensure_path(self, path_parts: list[str], root_id: str) -> str:
        """Ensure a nested folder path under root_id exists. Returns the deepest folder id."""
        parent = root_id
        for part in path_parts:
            if not part:
                continue
            folder = self.ensure_folder(part, parent)
            parent = folder["id"]
        return parent

    # ── files ────────────────────────────────────────────────────────────────

    def upload_file(self, name: str, data: bytes, mime: str, parent_id: str) -> dict:
        """Multipart upload of bytes into parent_id. Returns {id,name,webViewLink,...}."""
        metadata = {"name": name, "parents": [parent_id]}
        boundary = "klaroha_drive_boundary_7f3a1c"
        body = (
            f"--{boundary}\r\n"
            "Content-Type: application/json; charset=UTF-8\r\n\r\n"
            f"{json.dumps(metadata)}\r\n"
            f"--{boundary}\r\n"
            f"Content-Type: {mime}\r\n\r\n"
        ).encode("utf-8") + data + f"\r\n--{boundary}--".encode("utf-8")
        r = self._client.post(
            _UPLOAD,
            params={"uploadType": "multipart", "fields": "id,name,mimeType,size,webViewLink,parents"},
            content=body,
            headers={"Content-Type": f"multipart/related; boundary={boundary}"},
        )
        r.raise_for_status()
        return r.json()

    def list_children(self, parent_id: str, mime_type: Optional[str] = None, all_drives: bool = False) -> list[dict]:
        q = f"'{parent_id}' in parents and trashed = false"
        if mime_type:
            q += f" and mimeType = '{mime_type}'"
        params: dict = {"q": q, "fields": "files(id,name,mimeType,size,webViewLink,thumbnailLink)", "pageSize": 200}
        if all_drives:
            params["supportsAllDrives"] = "true"
            params["includeItemsFromAllDrives"] = "true"
        r = self._client.get(_FILES, params=params)
        r.raise_for_status()
        return r.json().get("files", [])

    def search_files(self, mime_types: list[str], parent_id: Optional[str] = None) -> list[dict]:
        """Search the connected Drive for files matching any of the given MIME types.

        If parent_id is supplied, constrain the search to that folder's direct children.
        Without parent_id it searches across Drive, which is useful for global asset
        lookup and backward-compatible picker behavior.
        """
        mime_q = " or ".join(f"mimeType = '{m}'" for m in mime_types)
        q = f"({mime_q}) and trashed = false"
        if parent_id:
            q += f" and '{parent_id}' in parents"
        params: dict = {
            "q": q,
            "fields": "files(id,name,mimeType,size,webViewLink,thumbnailLink)",
            "pageSize": 200,
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
        }
        r = self._client.get(_FILES, params=params)
        r.raise_for_status()
        return r.json().get("files", [])

    def list_shared_with_me_folders(self) -> list[dict]:
        params = {
            "q": f"sharedWithMe = true and mimeType = '{_FOLDER_MIME}' and trashed = false",
            "fields": "files(id,name)",
            "pageSize": 200,
            "includeItemsFromAllDrives": "true",
            "supportsAllDrives": "true",
        }
        r = self._client.get(_FILES, params=params)
        r.raise_for_status()
        return r.json().get("files", [])

    def list_shared_drives(self) -> list[dict]:
        r = self._client.get(_DRIVES, params={"pageSize": 100, "fields": "drives(id,name)"})
        r.raise_for_status()
        return r.json().get("drives", [])

    def get_file_meta(self, file_id: str) -> dict:
        r = self._client.get(f"{_FILES}/{file_id}", params={"fields": "id,name,mimeType,size,webViewLink,parents"})
        r.raise_for_status()
        return r.json()

    def download_file(self, file_id: str) -> bytes:
        r = self._client.get(f"{_FILES}/{file_id}", params={"alt": "media"})
        r.raise_for_status()
        return r.content
