from types import SimpleNamespace

import pytest

from routers import chat_v2
import plugin_loader


@pytest.mark.asyncio
async def test_cmo_loop_can_continue_same_turn_after_failed_tool(monkeypatch):
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
                "tool_calls": [
                    {"id": "tc_1", "name": "storyboard_render", "args": {"storyboard_text": "A" * 80, "size": "1152x1536"}},
                    {"id": "tc_2", "name": "storyboard_render", "args": {"storyboard_text": "A" * 80, "size": "1024x1536"}},
                ],
                "provider": "openai",
                "model": "gpt-test",
            }
        tool_messages = [m for m in state if m.get("role") == "tool"]
        assert len(tool_messages) == 2
        assert "invalid size" in tool_messages[0]["content"]
        return {"type": "text", "text": "The first render failed, so I retried with the supported size and the image is ready for review.", "provider": "openai", "model": "gpt-test"}

    monkeypatch.setattr(chat_v2, "call_cmo", fake_call_cmo)

    executed: list[dict] = []

    async def fake_execute_all(tool_calls, db, settings, tools, brand_id=None, workspace_id=None, campaign_id=None, extra_brief=None):
        tc = tool_calls[0]
        executed.append(tc)
        if tc["args"]["size"] == "1152x1536":
            return [{
                "tool": tc["name"],
                "status": "failed",
                "artifact_type": "storyboard_image",
                "error": "invalid size",
            }]
        return [{
            "tool": tc["name"],
            "status": "succeeded",
            "artifact_type": "image_asset",
            "summary": "Storyboard image ready for review.",
            "run_id": "run_2",
        }]

    monkeypatch.setattr(chat_v2, "execute_all", fake_execute_all)

    result = await chat_v2._cmo_loop(
        message="storyboard it",
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

    assert [tc["args"]["size"] for tc in executed] == ["1152x1536", "1024x1536"]
    assert result.reply == "The first render failed, so I retried with the supported size and the image is ready for review."
    assert result.tool_calls[-1]["status"] == "succeeded"
