from types import SimpleNamespace
from uuid import uuid4

import pytest

from routers import chat_v2
import plugin_loader


@pytest.mark.asyncio
async def test_cmo_selected_campaign_read_binds_later_render(monkeypatch):
    selected_id = uuid4()
    calls = 0
    executed = []

    async def fake_get_active_plugin_ids(_db, _brand_id):
        return set()

    async def fake_call_cmo(state, provider_config, tools, on_text=None):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {
                "type": "tool_calls",
                "tool_calls": [{
                    "id": "campaign-read",
                    "name": "campaign_read",
                    "args": {"campaign_id": str(selected_id)},
                }],
                "provider": "openai",
                "model": "gpt-test",
            }
        if calls == 2:
            return {
                "type": "tool_calls",
                "tool_calls": [{
                    "id": "postcraft-render",
                    "name": "postcraft_render",
                    "args": {"render_approved": True, "approved_draft": True, "postcraft_text": "approved"},
                }],
                "provider": "openai",
                "model": "gpt-test",
            }
        return {"type": "text", "text": "Rendering started.", "provider": "openai", "model": "gpt-test"}

    async def fake_execute_all(tool_calls, db, settings, tools, **kwargs):
        executed.append((tool_calls[0]["name"], kwargs.get("campaign_id")))
        if tool_calls[0]["name"] == "campaign_read":
            return [{"tool": "campaign_read", "status": "succeeded", "rows": []}]
        return [{"tool": "postcraft_render", "status": "succeeded", "run_id": "run-1"}]

    monkeypatch.setattr(plugin_loader, "get_active_plugin_ids", fake_get_active_plugin_ids)
    monkeypatch.setattr(chat_v2, "build_tools", lambda _db, active_plugin_ids=None: {
        "campaign_read": {"module_id": "__campaign__"},
        "postcraft_render": {"module_id": "postcraft.render"},
    })
    monkeypatch.setattr(chat_v2, "call_cmo", fake_call_cmo)
    monkeypatch.setattr(chat_v2, "execute_all", fake_execute_all)

    result = await chat_v2._cmo_loop(
        message="Proceed with the approved social post.",
        history=[],
        brand_name="Golden Gate Memorial",
        brand_uuid=uuid4(),
        campaign_goal="",
        system_prompt="",
        references=[],
        db=SimpleNamespace(),
        settings=SimpleNamespace(),
        provider_config={"provider": "openai", "model": "gpt-test"},
        workspace_id=uuid4(),
    )

    assert result.reply == "Rendering started."
    assert result.campaign_id == str(selected_id)
    assert executed == [
        ("campaign_read", None),
        ("postcraft_render", selected_id),
    ]
