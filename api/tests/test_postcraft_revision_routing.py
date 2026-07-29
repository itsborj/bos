import pytest

from routers import cmo_tools


@pytest.mark.asyncio
async def test_direct_postcraft_render_revision_routes_through_generic_revise(monkeypatch):
    captured = {}

    async def fake_revise(tool_name, tool_args, db, settings, start, *, extra_brief=None):
        captured["tool_name"] = tool_name
        captured["tool_args"] = tool_args
        captured["extra_brief"] = extra_brief
        return {"tool": tool_name, "status": "succeeded", "summary": "routed"}

    monkeypatch.setattr(cmo_tools, "_execute_revise_artifact_tool", fake_revise)

    result = await cmo_tools.execute_one(
        "postcraft_render",
        {
            "source_run_id": "00000000-0000-0000-0000-000000000001",
            "revision_prompt": "Make the logo bigger and keep everything else the same.",
            "postcraft_text": "Updated approved text",
        },
        brand_id=None,
        db=None,
        settings=None,
        tools={"postcraft_render": {"module_id": "postcraft.render", "label": "Postcraft Render"}},
        extra_brief={"reference_images": []},
    )

    assert result["status"] == "succeeded"
    assert captured["tool_name"] == "postcraft_render"
    assert captured["tool_args"]["revision_prompt"].startswith("Make the logo bigger")
    assert captured["tool_args"]["postcraft_text"] == "Updated approved text"


def test_revise_artifact_accepts_revision_prompt_source():
    # Regression guard for direct module revise actions: they often name the
    # instruction revision_prompt rather than generic feedback.
    source = open("api/routers/cmo_tools.py", encoding="utf-8").read()
    assert 'get("revision_prompt")' in source
