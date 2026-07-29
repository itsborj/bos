from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import uuid4
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
API_PATH = ROOT / "api"
# Use the real FastAPI package from site-packages, not the repo-local stub at
# /home/ubu/bos/fastapi/, then import BOS modules from /api.
sys.path = [p for p in sys.path if p not in {"", str(ROOT)}]
sys.path.insert(0, str(API_PATH))

import httpx
import pytest
from fastapi import FastAPI

import plugin_loader
from auth import require_api_key
from db import get_db
from routers import chat_v2

app = FastAPI()
app.include_router(chat_v2.router)


class _DummyDB:
    pass


@asynccontextmanager
async def _dummy_session_ctx():
    yield _DummyDB()


class _DummySessionFactory:
    def __call__(self):
        return _dummy_session_ctx()


async def _override_db():
    yield _DummyDB()


async def _override_api_key():
    return "test-api-key"


@pytest.mark.asyncio
async def test_cmo_v2_chat_endpoint_continues_after_failed_storyboard_render(monkeypatch):
    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[require_api_key] = _override_api_key

    async def fake_get_singleton(_db):
        return SimpleNamespace(id=uuid4())

    async def fake_resolve_provider(_db, _ws, _settings):
        return {"provider": "openai", "model": "gpt-test"}

    async def fake_prepare_context(_db, _ws, _body, _settings):
        return ("Golden Gate", None, "", None, "", [], [], [])

    async def fake_get_active_plugin_ids(_db, _brand_id):
        return set()

    calls = {"count": 0}

    async def fake_call_cmo(state, provider_config, tools, on_text=None):
        calls["count"] += 1
        if calls["count"] == 1:
            return {
                "type": "tool_calls",
                "tool_calls": [
                    {"id": "tc_1", "name": "storyboard_render", "args": {"storyboard_text": "A" * 80, "size": "3:4"}},
                    {"id": "tc_2", "name": "storyboard_render", "args": {"storyboard_text": "A" * 80, "size": "1024x1536"}},
                ],
                "provider": "openai",
                "model": "gpt-test",
            }
        return {
            "type": "text",
            "text": "Storyboard image ready for review.",
            "provider": "openai",
            "model": "gpt-test",
        }

    executed: list[dict] = []

    async def fake_execute_all(tool_calls, db, settings, tools, brand_id=None, workspace_id=None, campaign_id=None, extra_brief=None):
        tc = tool_calls[0]
        executed.append(tc)
        if tc["args"]["size"] == "3:4":
            return [{
                "tool": tc["name"],
                "status": "failed",
                "artifact_type": "storyboard_image",
                "error": "Invalid size '3:4'. Expected WIDTHxHEIGHT.",
            }]
        return [{
            "tool": tc["name"],
            "status": "succeeded",
            "artifact_type": "image_asset",
            "summary": "Storyboard image ready for review.",
            "run_id": "run_2",
        }]

    monkeypatch.setattr(chat_v2, "get_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(chat_v2, "get_singleton", fake_get_singleton)
    monkeypatch.setattr(chat_v2, "resolve_provider", fake_resolve_provider)
    monkeypatch.setattr(chat_v2, "_prepare_context", fake_prepare_context)
    monkeypatch.setattr(chat_v2, "build_tools", lambda _db, active_plugin_ids=None: {
        "storyboard_render": {"label": "Storyboard Render"},
    })
    monkeypatch.setattr(chat_v2, "call_cmo", fake_call_cmo)
    monkeypatch.setattr(chat_v2, "execute_all", fake_execute_all)
    monkeypatch.setattr(plugin_loader, "get_active_plugin_ids", fake_get_active_plugin_ids)

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/cmo_v2/chat",
                headers={"X-API-Key": "test-api-key"},
                json={"message": "storyboard it", "history": []},
            )

        assert response.status_code == 200
        data = response.json()
        assert [tc["args"]["size"] for tc in executed] == ["3:4", "1024x1536"]
        assert data["reply"] == "Storyboard image ready for review."
        assert data["tool_calls"][-1]["status"] == "succeeded"
        assert data["tool_calls"][-1]["artifact_type"] == "image_asset"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_cmo_v2_chat_stream_endpoint_emits_storyboard_progress_and_done(monkeypatch):
    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[require_api_key] = _override_api_key

    async def fake_get_singleton(_db):
        return SimpleNamespace(id=uuid4())

    async def fake_resolve_provider(_db, _ws, _settings):
        return {"provider": "openai", "model": "gpt-test"}

    async def fake_prepare_context(_db, _ws, _body, _settings):
        return ("Golden Gate", None, "", None, "", [], [], [])

    async def fake_get_active_plugin_ids(_db, _brand_id):
        return set()

    calls = {"count": 0}

    async def fake_call_cmo(state, provider_config, tools, on_text=None):
        calls["count"] += 1
        if calls["count"] == 1:
            return {
                "type": "tool_calls",
                "tool_calls": [
                    {"id": "tc_1", "name": "storyboard_render", "args": {"storyboard_text": "A" * 80, "size": "1024x1536"}},
                ],
                "provider": "openai",
                "model": "gpt-test",
            }
        return {
            "type": "text",
            "text": "Storyboard image ready for review.",
            "provider": "openai",
            "model": "gpt-test",
        }

    async def fake_execute_all(tool_calls, db, settings, tools, brand_id=None, workspace_id=None, campaign_id=None, extra_brief=None):
        tc = tool_calls[0]
        return [{
            "tool": tc["name"],
            "status": "succeeded",
            "artifact_type": "image_asset",
            "summary": "Storyboard image ready for review.",
            "artifact_title": "Video Ad Storyboard",
            "run_id": "run_stream_1",
        }]

    monkeypatch.setattr(chat_v2, "get_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(chat_v2, "get_singleton", fake_get_singleton)
    monkeypatch.setattr(chat_v2, "resolve_provider", fake_resolve_provider)
    monkeypatch.setattr(chat_v2, "_prepare_context", fake_prepare_context)
    monkeypatch.setattr(chat_v2, "get_session_factory", lambda: _DummySessionFactory())
    monkeypatch.setattr(chat_v2, "build_tools", lambda _db, active_plugin_ids=None: {
        "storyboard_render": {"label": "Storyboard Render"},
    })
    monkeypatch.setattr(chat_v2, "call_cmo", fake_call_cmo)
    monkeypatch.setattr(chat_v2, "execute_all", fake_execute_all)
    monkeypatch.setattr(plugin_loader, "get_active_plugin_ids", fake_get_active_plugin_ids)

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            async with client.stream(
                "POST",
                "/cmo_v2/chat/stream",
                headers={"X-API-Key": "test-api-key"},
                json={"message": "storyboard it", "history": []},
            ) as response:
                body = (await response.aread()).decode()

        assert response.status_code == 200
        assert 'Storyboard image generation in progress' in body
        assert 'data: {"type": "module_result", "artifact_ref": {"artifact_id": "run_stream_1"' in body
        assert 'data: {"type": "reply", "text": "Storyboard image ready for review."' in body
        assert 'data: {"type": "done", "provider": "openai", "model": "gpt-test"' in body
        assert 'data: [DONE]' in body
    finally:
        app.dependency_overrides.clear()
