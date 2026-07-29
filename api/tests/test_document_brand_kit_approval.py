from pathlib import Path
import asyncio
import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[2]
API_PATH = ROOT / "api"
if str(API_PATH) not in sys.path:
    sys.path.insert(0, str(API_PATH))

from routers import documents
from schemas.documents import WorkspaceDocumentUpdate


def valid_meta():
    return {
        "drive_root_folder_id": "folder",
        "imprint_asset_validation": {"logo_files": [{"id": "logo-file", "name": "brand_logo.png"}]},
    }


class FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.is_success = 200 <= status_code < 300

    def json(self):
        return self._payload


class FakeDriveHttpClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def get(self, url, params=None):
        self.calls.append((url, params or {}))
        return self.responses.pop(0)


def test_brand_kit_approval_requires_drive_root_and_indexed_logo():
    assert documents._brand_kit_drive_approval_problem(None)[0] == "DRIVE_ROOT_REQUIRED"
    assert documents._brand_kit_drive_approval_problem({"drive_root_folder_id": "folder"})[0] == "DRIVE_ROOT_MISSING_LOGO"
    assert documents._brand_kit_drive_approval_problem({
        "drive_root_folder_id": "folder",
        "imprint_asset_validation": {"logo_files": []},
    })[0] == "DRIVE_ROOT_MISSING_LOGO"


def test_cached_valid_but_live_missing_logo_blocks_approval():
    client = FakeDriveHttpClient([
        FakeResponse(200, {"id": "folder", "mimeType": "application/vnd.google-apps.folder", "trashed": False}),
        FakeResponse(404),
    ])

    problem = asyncio.run(documents._live_brand_kit_drive_problem(valid_meta(), "token", client=client))

    assert problem[0] == "DRIVE_INDEX_STALE"
    assert problem[2] == 422


def test_live_valid_folder_and_logo_pass_approval_check():
    client = FakeDriveHttpClient([
        FakeResponse(200, {"id": "folder", "mimeType": "application/vnd.google-apps.folder", "trashed": False}),
        FakeResponse(200, {"id": "logo-file", "mimeType": "image/png", "trashed": False}),
    ])

    assert asyncio.run(documents._live_brand_kit_drive_problem(valid_meta(), "token", client=client)) is None
    assert all(call[1]["supportsAllDrives"] == "true" for call in client.calls)


def test_live_401_and_403_remain_distinct():
    auth = FakeDriveHttpClient([FakeResponse(401)])
    permission = FakeDriveHttpClient([FakeResponse(403)])

    assert asyncio.run(documents._live_brand_kit_drive_problem(valid_meta(), "token", client=auth))[2] == 401
    assert asyncio.run(documents._live_brand_kit_drive_problem(valid_meta(), "token", client=permission))[2] == 403


def test_workspace_brand_kit_remains_exempt_from_drive_guard():
    doc = SimpleNamespace(doc_type="campaign_brand_kit", brand_id=None)
    asyncio.run(documents._require_brand_kit_drive_ready(object(), doc))


def test_patch_approval_status_invokes_shared_guard(monkeypatch):
    doc = SimpleNamespace(
        id=uuid4(), workspace_id=uuid4(), brand_id=uuid4(), doc_type="campaign_brand_kit",
        title="Kit", content_markdown="content", status="draft", tags_json=[], metadata_json={},
        source_run_id=None, approved_at=None, created_at=None, updated_at=None,
    )

    class Result:
        def scalar_one_or_none(self):
            return doc

    class Db:
        async def execute(self, _stmt):
            return Result()

    async def fake_workspace(_db):
        return SimpleNamespace(id=doc.workspace_id)

    called = []

    async def fake_guard(_db, guarded_doc):
        called.append(guarded_doc)
        raise HTTPException(status_code=422, detail="blocked")

    monkeypatch.setattr(documents, "get_singleton", fake_workspace)
    monkeypatch.setattr(documents, "_require_brand_kit_drive_ready", fake_guard)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(documents.update_document(doc.id, WorkspaceDocumentUpdate(status="approved"), Db(), "key"))
    assert exc.value.status_code == 422
    assert called == [doc]


def test_post_approve_delegates_to_patch_status_path(monkeypatch):
    seen = {}

    async def fake_update(document_id, body, db, key):
        seen.update(document_id=document_id, status=body.status, db=db, key=key)
        return "updated"

    monkeypatch.setattr(documents, "update_document", fake_update)
    document_id = uuid4()
    db = object()

    result = asyncio.run(documents.approve_document(document_id, db, "key"))

    assert result == "updated"
    assert seen == {"document_id": document_id, "status": "approved", "db": db, "key": "key"}
