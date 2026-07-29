from types import SimpleNamespace
from uuid import uuid4

import pytest

from routers import chat_v2
import plugin_loader


@pytest.mark.asyncio
async def test_cmo_loop_feeds_review_artifact_back_to_llm(monkeypatch):
    async def fake_get_active_plugin_ids(_db, _brand_id):
        return set()

    monkeypatch.setattr(plugin_loader, "get_active_plugin_ids", fake_get_active_plugin_ids)
    monkeypatch.setattr(chat_v2, "build_tools", lambda _db, active_plugin_ids=None: {
        "storyboard_render": {"label": "Storyboard Render"},
        "storyboard_validate": {"label": "Storyboard Validate"},
    })

    calls = 0

    async def fake_call_cmo(state, provider_config, tools, on_text=None):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {
                "type": "tool_calls",
                "tool_calls": [
                    {"id": "tc_1", "name": "storyboard_render", "args": {"storyboard_text": "A" * 80}},
                    {"id": "tc_2", "name": "storyboard_validate", "args": {"storyboard_text": "B" * 80}},
                    {"id": "tc_3", "name": "storyboard_render", "args": {"storyboard_text": "C" * 80}},
                ],
                "provider": "openai",
                "model": "gpt-test",
            }
        assert any(m.get("role") == "tool" for m in state)
        return {"type": "text", "text": "I rendered the storyboard and added it for review.", "provider": "openai", "model": "gpt-test"}

    monkeypatch.setattr(chat_v2, "call_cmo", fake_call_cmo)

    executed: list[str] = []

    async def fake_execute_all(tool_calls, db, settings, tools, brand_id=None, workspace_id=None, campaign_id=None, extra_brief=None):
        assert len(tool_calls) == 1
        tc = tool_calls[0]
        executed.append(tc["name"])
        return [{
            "tool": tc["name"],
            "status": "succeeded",
            "artifact_type": "image_asset",
            "summary": f"{tc['name']} ready.",
            "run_id": f"run_{len(executed)}",
        }]

    monkeypatch.setattr(chat_v2, "execute_all", fake_execute_all)

    result = await chat_v2._cmo_loop(
        message="Need a new storyboard image.",
        history=[],
        brand_name="Golden Gate",
        brand_uuid=None,
        campaign_goal="",
        system_prompt="",
        references=[],
        db=SimpleNamespace(),
        settings=SimpleNamespace(),
        provider_config={"provider": "openai", "model": "gpt-test"},
    )

    assert executed == ["storyboard_render", "storyboard_validate", "storyboard_render"]
    assert result.reply == "I rendered the storyboard and added it for review."
    assert len(result.tool_calls) == 3


@pytest.mark.asyncio
async def test_stale_storyboard_draft_is_not_rendered_after_intervening_user_turn(monkeypatch):
    async def fake_get_active_plugin_ids(_db, _brand_id):
        return set()

    monkeypatch.setattr(plugin_loader, "get_active_plugin_ids", fake_get_active_plugin_ids)
    monkeypatch.setattr(chat_v2, "build_tools", lambda _db, active_plugin_ids=None: {
        "storyboard_render": {"label": "Storyboard Render"},
    })

    called_llm = False

    async def fake_call_cmo(state, provider_config, tools, on_text=None):
        nonlocal called_llm
        called_llm = True
        return {"type": "text", "text": "What would you like to approve?", "provider": "openai", "model": "gpt-test"}

    monkeypatch.setattr(chat_v2, "call_cmo", fake_call_cmo)

    async def fake_execute_all(*args, **kwargs):
        raise AssertionError("stale storyboard draft must not be rendered")

    monkeypatch.setattr(chat_v2, "execute_all", fake_execute_all)

    history = [
        {"role": "assistant", "content": "15-second storyboard\n\nShot 1\nVoiceover: A family gathers...\nText overlay: Plan ahead."},
        {"role": "user", "content": "Thanks, hold that for later."},
    ]

    result = await chat_v2._cmo_loop(
        message="yes proceed",
        history=history,
        brand_name="Golden Gate",
        brand_uuid=uuid4(),
        campaign_goal="",
        system_prompt="",
        references=[],
        db=SimpleNamespace(),
        settings=SimpleNamespace(),
        provider_config={"provider": "openai", "model": "gpt-test"},
    )

    assert called_llm is True
    assert result.reply == "What would you like to approve?"
    assert result.tool_calls == []


@pytest.mark.asyncio
async def test_compound_approval_goes_through_llm_tool_choice(monkeypatch):
    async def fake_get_active_plugin_ids(_db, _brand_id):
        return set()

    monkeypatch.setattr(plugin_loader, "get_active_plugin_ids", fake_get_active_plugin_ids)
    monkeypatch.setattr(chat_v2, "build_tools", lambda _db, active_plugin_ids=None: {
        "storyboard_render": {"label": "Storyboard Render"},
    })

    calls = 0

    async def fake_call_cmo(state, provider_config, tools, on_text=None):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {
                "type": "tool_calls",
                "tool_calls": [{"id": "tc_1", "name": "storyboard_render", "args": {"storyboard_text": "from model " * 20, "size": "1024x1536"}}],
                "provider": "openai",
                "model": "gpt-test",
            }
        return {"type": "text", "text": "Storyboard image ready for review.", "provider": "openai", "model": "gpt-test"}

    monkeypatch.setattr(chat_v2, "call_cmo", fake_call_cmo)

    executed: list[dict] = []

    async def fake_execute_all(tool_calls, db, settings, tools, brand_id=None, workspace_id=None, campaign_id=None, extra_brief=None):
        tc = tool_calls[0]
        executed.append(tc)
        return [{
            "tool": tc["name"],
            "status": "succeeded",
            "artifact_type": "image_asset",
            "summary": "Storyboard image ready for review.",
            "run_id": "run_model_1",
        }]

    monkeypatch.setattr(chat_v2, "execute_all", fake_execute_all)

    history = [{
        "role": "assistant",
        "content": "15-second storyboard\n\nShot 1\nVoiceover: A family gathers...\nText overlay: Plan ahead.",
    }]

    result = await chat_v2._cmo_loop(
        message="good proceed",
        history=history,
        brand_name="Golden Gate",
        brand_uuid=uuid4(),
        campaign_goal="",
        system_prompt="",
        references=[],
        db=SimpleNamespace(),
        settings=SimpleNamespace(),
        provider_config={"provider": "openai", "model": "gpt-test"},
    )

    assert calls == 2
    assert len(executed) == 1
    assert executed[0]["name"] == "storyboard_render"
    assert result.reply == "Storyboard image ready for review."
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0]["tool"] == "storyboard_render"
