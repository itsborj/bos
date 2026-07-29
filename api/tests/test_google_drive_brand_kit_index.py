from pathlib import Path
import asyncio
import importlib.util
import inspect
import sys

import httpx
import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[2]
API_PATH = ROOT / "api"
if str(API_PATH) not in sys.path:
    sys.path.insert(0, str(API_PATH))

PLUGIN_API_PATH = ROOT / "plugins" / "google-drive" / "api.py"
spec = importlib.util.spec_from_file_location("google_drive_plugin_api", PLUGIN_API_PATH)
google_drive_api = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(google_drive_api)


def test_set_drive_root_indexes_brand_kit_images_recursively_like_picker_listing():
    source = inspect.getsource(google_drive_api.set_drive_root)

    assert "search_files(_BRAND_KIT_IMAGE_MIMES, parent_id=body.folder_id)" in source
    assert "children = drive.list_children" not in source


def test_set_drive_root_rejects_my_drive_and_returns_resolved_path():
    source = inspect.getsource(google_drive_api.set_drive_root)

    assert 'body.folder_id == "root"' in source
    assert '_resolve_drive_root_path(meta, body.folder_id, body.folder_path)' in source
    assert '"drive_root_path": meta.get("drive_root_path")' in source


def test_drive_root_path_preserves_only_same_folder_reindex():
    meta = {"drive_root_folder_id": "old", "drive_root_path": "Clients / Old"}

    assert google_drive_api._resolve_drive_root_path(meta, "old", None) == "Clients / Old"
    assert google_drive_api._resolve_drive_root_path(meta, "new", None) is None
    assert google_drive_api._resolve_drive_root_path(meta, "new", "Clients / New") == "Clients / New"


def test_brand_kit_asset_validation_keeps_template_masters_classifiable():
    validation = google_drive_api._brand_kit_asset_validation("root-folder", "Brand Kit", [
        {"id": "logo-1", "name": "brand_logo.png", "mimeType": "image/png"},
        {"id": "tpl-1", "name": "Templates/square_master_reference.png", "mimeType": "image/png"},
        {"id": "asset-1", "name": "Brand Assets/Products/product_photo.webp", "mimeType": "image/webp"},
    ])

    assert validation["status"] == "ok"
    assert [f["id"] for f in validation["logo_files"]] == ["logo-1"]
    assert [f["id"] for f in validation["creative_reference_files"]] == ["tpl-1"]
    assert {f["id"] for f in validation["visual_asset_files"]} == {"tpl-1", "asset-1"}


def _drive_status_error(status: int, payload: dict) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://www.googleapis.com/drive/v3/files/file")
    response = httpx.Response(status, request=request, json=payload)
    return httpx.HTTPStatusError("Drive request failed", request=request, response=response)


def test_drive_403_permission_error_does_not_mark_reauth(monkeypatch):
    marked = []

    async def fake_mark(_db, brand_id):
        marked.append(brand_id)

    monkeypatch.setattr(google_drive_api, "_mark_drive_reauth_required", fake_mark)
    exc = _drive_status_error(403, {"error": {"status": "PERMISSION_DENIED", "errors": [{"reason": "insufficientPermissions"}]}})

    with pytest.raises(HTTPException) as raised:
        asyncio.run(google_drive_api._raise_drive_http_error(exc, object(), "brand"))

    assert raised.value.status_code == 403
    assert marked == []


def test_verified_auth_invalid_403_marks_reauth(monkeypatch):
    marked = []

    async def fake_mark(_db, brand_id):
        marked.append(brand_id)

    monkeypatch.setattr(google_drive_api, "_mark_drive_reauth_required", fake_mark)
    exc = _drive_status_error(403, {"error": {"errors": [{"reason": "authError"}]}})

    with pytest.raises(HTTPException) as raised:
        asyncio.run(google_drive_api._raise_drive_http_error(exc, object(), "brand"))

    assert raised.value.status_code == 401
    assert marked == ["brand"]


def test_thumbnail_rejects_non_images_oversize_and_undecodable_bytes():
    with pytest.raises(HTTPException) as not_image:
        google_drive_api._validate_thumbnail_source("application/pdf", 100)
    assert not_image.value.status_code == 415

    with pytest.raises(HTTPException) as too_large:
        google_drive_api._validate_thumbnail_source("image/png", google_drive_api._MAX_THUMBNAIL_SOURCE_BYTES + 1)
    assert too_large.value.status_code == 413

    with pytest.raises(HTTPException) as undecodable:
        google_drive_api._thumbnail_bytes(b"not-an-image", "image/png")
    assert undecodable.value.status_code == 415
