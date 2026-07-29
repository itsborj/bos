from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
API_PATH = ROOT / "api"
# Prefer site-packages FastAPI/SQLAlchemy over repo-local stubs, then add /api.
sys.path = [p for p in sys.path if p not in {"", str(ROOT)}]
sys.path.insert(0, str(API_PATH))

from routers import runs
from schemas.runs import RunResponse, RunResultOut


class _ExecResult:
    def __init__(self, *, row=None, scalar=None):
        self._row = row
        self._scalar = scalar

    def one_or_none(self):
        return self._row

    def scalar_one(self):
        return self._scalar

    def scalar_one_or_none(self):
        return self._scalar


class _Db:
    def __init__(self, responses):
        self._responses = list(responses)
        self.commits = 0

    async def execute(self, _stmt):
        if not self._responses:
            raise AssertionError("Unexpected DB execute call")
        return self._responses.pop(0)

    async def commit(self):
        self.commits += 1


def _run_response(run_id: str, module_id: str, *, block: dict, approval_status: str = "pending") -> RunResponse:
    return RunResponse(
        run_id=run_id,
        module_id=module_id,
        vertical="test",
        status="success",
        approval_status=approval_status,
        result=RunResultOut(content="ok", self_check="pass", block=block),
        created_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_chat_revise_run_storyboard_preserves_source_image_inputs(monkeypatch):
    source_run_id = uuid4()
    revised_run_id = uuid4()
    source_run = SimpleNamespace(
        id=source_run_id,
        module_id="storyboard.render",
        brand_id=uuid4(),
        campaign_id=None,
        approval_status="pending",
        parent_run_id=None,
    )
    source_result = SimpleNamespace(content="Storyboard image ready")
    source_trace = SimpleNamespace(lineage_json={
        "block": {
            "type": "image_asset",
            "legacy_type": "storyboard_image",
            "image_data_b64": "abc123",
            "output_path": "/tmp/storyboard-source.png",
            "allowed_actions": ["revise"],
            "action_modules": {"revise": "storyboard.render"},
        }
    })
    revised_row = SimpleNamespace(id=revised_run_id, parent_run_id=None)
    db = _Db([
        _ExecResult(row=(source_run, source_result, source_trace)),
        _ExecResult(scalar=revised_row),
    ])

    captured: dict = {}

    async def fake_execute_module(db, ws, module_id, brief, settings, campaign_id=None, brand_id=None):
        captured["module_id"] = module_id
        captured["brief"] = brief
        return _run_response(str(revised_run_id), module_id, block={"status": "succeeded", "type": "image_asset", "approval_status": "pending"})

    async def fake_get_singleton(_db):
        return SimpleNamespace(id=uuid4())

    monkeypatch.setattr(runs, "get_singleton", fake_get_singleton)
    monkeypatch.setattr(runs, "get_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(runs, "_execute_module", fake_execute_module)

    response = await runs.chat_revise_run(
        source_run_id,
        runs.ChatReviseRequest(feedback="Tighten panel 2 and keep the rest unchanged."),
        db,
        _="test-api-key",
    )

    assert response.module_id == "storyboard.render"
    assert "image revision" in response.reply.lower()
    assert captured["module_id"] == "storyboard.render"
    assert captured["brief"]["source_run_id"] == str(source_run_id)
    assert captured["brief"]["source_image_data_b64"] == "abc123"
    assert captured["brief"]["source_image_path"] == "/tmp/storyboard-source.png"
    assert captured["brief"]["revision_prompt"] == "Tighten panel 2 and keep the rest unchanged."
    assert revised_row.parent_run_id == source_run_id


@pytest.mark.asyncio
async def test_chat_revise_run_previs_uses_motion_edit_module_and_keeps_video_lineage(monkeypatch):
    source_run_id = uuid4()
    revised_run_id = uuid4()
    source_run = SimpleNamespace(
        id=source_run_id,
        module_id="storyboard.motion.render",
        brand_id=uuid4(),
        campaign_id=None,
        approval_status="pending",
        parent_run_id=None,
    )
    source_result = SimpleNamespace(content="Previs Motion final-cut candidate ready")
    source_trace = SimpleNamespace(lineage_json={
        "block": {
            "type": "video_asset",
            "legacy_type": "previs_motion_video",
            "video_url_path": "/tmp/previs-video-url.txt",
            "task_id": "cgt-task-123",
            "allowed_actions": ["revise"],
            "action_modules": {"revise": "storyboard.motion.edit"},
        }
    })
    revised_row = SimpleNamespace(id=revised_run_id, parent_run_id=None)
    db = _Db([
        _ExecResult(row=(source_run, source_result, source_trace)),
        _ExecResult(scalar=revised_row),
    ])

    captured: dict = {}

    async def fake_execute_module(db, ws, module_id, brief, settings, campaign_id=None, brand_id=None):
        captured["module_id"] = module_id
        captured["brief"] = brief
        return _run_response(str(revised_run_id), module_id, block={"status": "succeeded", "type": "video_asset", "approval_status": "pending"})

    async def fake_get_singleton(_db):
        return SimpleNamespace(id=uuid4())

    monkeypatch.setattr(runs, "get_singleton", fake_get_singleton)
    monkeypatch.setattr(runs, "get_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(runs, "_execute_module", fake_execute_module)

    response = await runs.chat_revise_run(
        source_run_id,
        runs.ChatReviseRequest(feedback="Keep timing, but smooth the motion and warm the end card."),
        db,
        _="test-api-key",
    )

    assert response.module_id == "storyboard.motion.edit"
    assert "video edit" in response.reply.lower()
    assert captured["module_id"] == "storyboard.motion.edit"
    assert captured["brief"]["source_run_id"] == str(source_run_id)
    assert captured["brief"]["video_url_path"] == "/tmp/previs-video-url.txt"
    assert captured["brief"]["task_id"] == "cgt-task-123"
    assert captured["brief"]["revision_prompt"] == "Keep timing, but smooth the motion and warm the end card."
    assert revised_row.parent_run_id == source_run_id


@pytest.mark.asyncio
async def test_execute_declared_run_action_passes_schedule_overrides_to_meta_publish(monkeypatch):
    source_run_id = uuid4()
    action_run_id = uuid4()
    brand_id = uuid4()
    workspace_id = uuid4()
    source_run = SimpleNamespace(
        id=source_run_id,
        module_id="postcraft.render",
        brand_id=brand_id,
        campaign_id=None,
        workspace_id=workspace_id,
        approval_status="pending",
        feedback=None,
    )
    source_result = SimpleNamespace(content="Approved post image")
    source_trace = SimpleNamespace(lineage_json={
        "block": {
            "type": "post_image",
            "message": "Approved copy for Facebook.",
            "allowed_actions": ["schedule_facebook"],
            "action_modules": {"schedule_facebook": "marketing.channel.meta.posts.publish"},
        }
    })
    action_row = SimpleNamespace(id=action_run_id, approval_status=None)
    db = _Db([
        _ExecResult(row=(source_run, source_result, source_trace)),
        _ExecResult(scalar=1),
        _ExecResult(scalar=SimpleNamespace(id=brand_id)),
        _ExecResult(scalar=action_row),
    ])

    captured: dict = {}

    async def fake_get_singleton(_db):
        return SimpleNamespace(id=workspace_id)

    async def fake_execute_module(db, ws, module_id, brief, settings, campaign_id=None, brand_id=None):
        captured["module_id"] = module_id
        captured["brief"] = brief
        return _run_response(
            str(action_run_id),
            module_id,
            block={"status": "scheduled", "type": "fb_page_post_result", "scheduled_at": "2026-07-13T09:00:00+00:00"},
            approval_status="approved",
        )

    async def noop(*args, **kwargs):
        return None

    monkeypatch.setattr(runs, "get_module", lambda module_id: object() if module_id == "marketing.channel.meta.posts.publish" else None)
    monkeypatch.setattr(runs, "get_singleton", fake_get_singleton)
    monkeypatch.setattr(runs, "_execute_module", fake_execute_module)
    monkeypatch.setattr(runs, "write_memory_event", noop)
    monkeypatch.setattr(runs, "update_pm_task_status", noop)

    response = await runs.execute_declared_run_action(
        db,
        str(source_run_id),
        "schedule_facebook",
        settings=SimpleNamespace(),
        overrides={"scheduled_at": "2026-07-13T09:00:00Z"},
    )

    assert response.action == "schedule_facebook"
    assert response.source_approval_status == "approved"
    assert captured["module_id"] == "marketing.channel.meta.posts.publish"
    assert captured["brief"]["action"] == "schedule_facebook"
    assert captured["brief"]["artifact_action"] == "schedule_facebook"
    assert captured["brief"]["message"] == "Approved copy for Facebook."
    assert captured["brief"]["scheduled_at"] == "2026-07-13T09:00:00Z"
    assert captured["brief"]["source_run_id"] == str(source_run_id)
    assert source_run.approval_status == "approved"
    assert action_row.approval_status == "approved"


@pytest.mark.asyncio
async def test_execute_declared_run_action_enriches_operator_revision_references(monkeypatch):
    source_run_id = uuid4()
    action_run_id = uuid4()
    brand_id = uuid4()
    workspace_id = uuid4()
    source_run = SimpleNamespace(
        id=source_run_id,
        module_id="postcraft.render",
        brand_id=brand_id,
        campaign_id=None,
        workspace_id=workspace_id,
        approval_status="pending",
        feedback=None,
    )
    source_result = SimpleNamespace(content="Approved post image")
    source_trace = SimpleNamespace(lineage_json={
        "block": {
            "type": "image_asset",
            "image_data_b64": "base-image-b64",
            "allowed_actions": ["revise"],
            "action_modules": {"revise": "postcraft.render"},
        }
    })
    action_row = SimpleNamespace(id=action_run_id, approval_status=None)
    db = _Db([
        _ExecResult(row=(source_run, source_result, source_trace)),
        _ExecResult(scalar=1),
        _ExecResult(scalar=SimpleNamespace(id=brand_id)),
        _ExecResult(scalar=action_row),
    ])

    captured: dict = {}

    async def fake_get_singleton(_db):
        return SimpleNamespace(id=workspace_id)

    async def fake_execute_module(db, ws, module_id, brief, settings, campaign_id=None, brand_id=None):
        captured["module_id"] = module_id
        captured["brief"] = brief
        return _run_response(
            str(action_run_id),
            module_id,
            block={"status": "succeeded", "type": "image_asset"},
            approval_status="pending",
        )

    async def noop(*args, **kwargs):
        return None

    async def fake_enrich_drive_references(refs, brand_id_str, db, settings):
        assert brand_id_str == str(brand_id)
        refs[0].setdefault("kind", "image")
        refs[0].setdefault("mime_type", "image/png")

    def fake_attachment_brief_fields(refs, *, brand_id=None, conversation_id=None, objective=None):
        assert objective == "Use the attached product photo instead of the current hero."
        return {
            "reference_images": [{
                "id": "ref_1",
                "title": "product-photo.png",
                "drive_file_id": "drive-ref-1",
                "mime_type": "image/png",
                "vision_b64": "ref-b64",
            }],
            "creative_context_json": '{"ok":true}',
        }

    monkeypatch.setattr(runs, "get_module", lambda module_id: object() if module_id == "postcraft.render" else None)
    monkeypatch.setattr(runs, "get_singleton", fake_get_singleton)
    monkeypatch.setattr(runs, "_execute_module", fake_execute_module)
    monkeypatch.setattr(runs, "write_memory_event", noop)
    monkeypatch.setattr(runs, "update_pm_task_status", noop)
    monkeypatch.setattr(runs, "ensure_reference_identity", lambda ref: ref.setdefault("id", "raw-ref-1"))
    monkeypatch.setattr(runs, "enrich_drive_references", fake_enrich_drive_references)
    monkeypatch.setattr(runs, "persist_chat_references", noop)
    monkeypatch.setattr(runs, "attachment_brief_fields", fake_attachment_brief_fields)

    response = await runs.execute_declared_run_action(
        db,
        str(source_run_id),
        "revise",
        settings=SimpleNamespace(),
        overrides={
            "revision_prompt": "Use the attached product photo instead of the current hero.",
            "operator_references": [{"drive_file_id": "drive-ref-1", "title": "product-photo.png"}],
        },
    )

    assert response.action == "revise"
    assert captured["module_id"] == "postcraft.render"
    assert captured["brief"]["source_run_id"] == str(source_run_id)
    assert captured["brief"]["source_image_data_b64"] == "base-image-b64"
    assert captured["brief"]["operator_revision_reference_count"] == 1
    assert "operator_references" not in captured["brief"]
    ref = captured["brief"]["reference_images"][0]
    assert ref["drive_file_id"] == "drive-ref-1"
    assert ref["vision_b64"] == "ref-b64"
    assert ref["revision_reference"] is True
    assert ref["priority"] == "operator_revision"
    assert ref["source"] == "operator_attachment"
