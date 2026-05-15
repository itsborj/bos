from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from routers import chat as chat_router
from routers.chat import ChatRequest
from skills.memory import hydrate_memory_slots


class _ScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _ExecuteResult:
    def __init__(self, rows=None, one=None):
        self._rows = rows or []
        self._one = one

    def scalars(self):
        return _ScalarResult(self._rows)

    def scalar_one_or_none(self):
        return self._one

    def all(self):
        return self._rows

    def one_or_none(self):
        return self._one


class _QueueDb:
    def __init__(self, results, *, require_brand_filter: bool = False):
        self._results = list(results)
        self.statements: list[str] = []
        self.require_brand_filter = require_brand_filter

    async def execute(self, statement):
        text = str(statement)
        self.statements.append(text)
        if self.require_brand_filter:
            assert "brand_id" in text
        assert self._results, f"unexpected query: {text}"
        return self._results.pop(0)


@pytest.mark.asyncio
async def test_brand_scoped_brief_never_uses_workspace_fallback(monkeypatch) -> None:
    """Bad trace: _resolve_brief can inject Brand A product before Brand B rows load."""
    ws = SimpleNamespace(id=uuid4(), name="Org", brand_json={"voice": "workspace voice"})
    brand = SimpleNamespace(id=uuid4(), name="Brand B", brand_json={"voice": "brand b voice"})
    db = _QueueDb([
        _ExecuteResult(rows=[]),  # Brand B products
        _ExecuteResult(rows=[]),  # Brand B audiences
        _ExecuteResult(rows=[]),  # Brand B docs
    ])

    async def forbidden_workspace_resolver(*_args, **_kwargs):
        raise AssertionError("workspace resolver must not run for active-brand briefs")

    monkeypatch.setattr(chat_router, "_resolve_brief", forbidden_workspace_resolver)

    brief = await chat_router._brand_scoped_brief(db, ws, brand, {"conversation_context": "USER: draft this"})

    assert brief["brand_name"] == "Brand B"
    assert brief["voice"] == "brand b voice"
    assert brief["conversation_context"] == "USER: draft this"
    assert "product_name" not in brief
    assert "audience" not in brief
    assert all("brand_id" in stmt for stmt in db.statements)


@pytest.mark.asyncio
async def test_hydrated_memory_is_brand_scoped_when_active_brand() -> None:
    """Fixed sample: Brand B memory contains Brand B rows and no Brand A workspace facts."""
    ws = SimpleNamespace(id=uuid4(), name="Org", brand_json={"voice": "brand a workspace voice"})
    brand = SimpleNamespace(id=uuid4(), name="Brand B", brand_json={"voice": "brand b voice"})
    product = SimpleNamespace(name="Brand B Offer", tagline="B tagline", benefits_json={"benefits": ["B benefit"]})
    audience = SimpleNamespace(name="Brand B Buyers", segment_json={"demographics": "B segment"})
    kit = SimpleNamespace(
        id=uuid4(), title="Brand B Kit", status="approved",
        content_markdown="Brand B kit only", approved_at=None,
    )
    guideline = SimpleNamespace(
        id=uuid4(), title="Brand B Guidelines", status="approved",
        content_markdown="Brand B guidelines only",
    )
    db = _QueueDb([
        _ExecuteResult(rows=[product]),
        _ExecuteResult(rows=[audience]),
        _ExecuteResult(one=kit),
        _ExecuteResult(one=guideline),
    ], require_brand_filter=True)

    memory = await hydrate_memory_slots(
        db,
        ws,
        ["brand_profile", "product_catalog", "audience_profiles", "campaign_brand_kit", "brand_guidelines"],
        brand=brand,
    )

    rendered = str(memory)
    assert memory["brand_profile"]["name"] == "Brand B"
    assert memory["brand_profile"]["brand"]["voice"] == "brand b voice"
    assert memory["product_catalog"][0]["name"] == "Brand B Offer"
    assert memory["audience_profiles"][0]["name"] == "Brand B Buyers"
    assert memory["campaign_brand_kit"]["content_markdown"] == "Brand B kit only"
    assert memory["brand_guidelines"]["content_markdown"] == "Brand B guidelines only"
    assert "brand a workspace voice" not in rendered


@pytest.mark.asyncio
async def test_org_level_prompt_with_brands_does_not_load_workspace_brand_facts() -> None:
    ws = SimpleNamespace(id=uuid4(), name="MotorMoto", brand_json={"voice": "helpful motorcycle expert"})
    brands = [
        SimpleNamespace(id=uuid4(), name="Klaroha", brand_json={}),
        SimpleNamespace(id=uuid4(), name="MotorMoto", brand_json={}),
    ]
    db = _QueueDb([_ExecuteResult(rows=brands)])

    prompt = await chat_router._build_system_prompt(db, ws, brand=None)

    assert "Known org context (no active brand)" in prompt
    assert "- Klaroha" in prompt
    assert "- MotorMoto" in prompt
    assert "helpful motorcycle expert" not in prompt
    assert "Products/offers" not in prompt
    assert "No Brand is active" in prompt


@pytest.mark.asyncio
async def test_pre_llm_scope_uses_persisted_brand_not_message_phrase_matching() -> None:
    ws = SimpleNamespace(id=uuid4(), name="Org", brand_json={})
    klaroha = SimpleNamespace(id=uuid4(), workspace_id=ws.id, name="Klaroha", brand_json={})
    db = _QueueDb([_ExecuteResult(one=klaroha)])

    brand, action = await chat_router._resolve_active_brand_for_turn(
        db,
        ws,
        ChatRequest(message="how about for motormoto", history=[], brand_id=str(klaroha.id)),
    )

    assert brand is klaroha
    assert action is None


def test_scope_directive_is_parsed_and_hidden_from_visible_reply() -> None:
    raw = """SCOPE:
conversation_brand: Klaroha
execution_brand: MotorMoto
mode: equivalent_artifact
confidence: high

I’ll make the MotorMoto version.
RUN: marketing.channel.google_ads.search_text.draft"""

    scope, without_scope = chat_router._extract_scope_directive(raw)
    visible = chat_router._strip_control_directives(raw)

    assert scope["conversation_brand"] == "Klaroha"
    assert scope["execution_brand"] == "MotorMoto"
    assert scope["mode"] == "equivalent_artifact"
    assert "SCOPE:" not in without_scope
    assert "SCOPE:" not in visible
    assert "RUN:" not in visible
    assert visible == "I’ll make the MotorMoto version."


def test_inline_scope_directive_is_parsed_and_hidden_from_visible_reply() -> None:
    raw = """SCOPE: conversation_brand: MotorMoto execution_brand: MotorMoto mode: new_artifact confidence: high
I’ll create a Google Ads angle for MotorMoto.
RUN: marketing.channel.google_ads.search_text.draft"""

    scope, without_scope = chat_router._extract_scope_directive(raw)
    visible = chat_router._strip_control_directives(raw)

    assert scope["conversation_brand"] == "MotorMoto"
    assert scope["execution_brand"] == "MotorMoto"
    assert scope["mode"] == "new_artifact"
    assert "SCOPE:" not in without_scope
    assert "SCOPE:" not in visible
    assert visible == "I’ll create a Google Ads angle for MotorMoto."


@pytest.mark.asyncio
async def test_scope_execution_brand_resolves_from_brand_roster() -> None:
    ws = SimpleNamespace(id=uuid4(), name="Org", brand_json={})
    klaroha = SimpleNamespace(id=uuid4(), workspace_id=ws.id, name="Klaroha", brand_json={})
    motormoto = SimpleNamespace(id=uuid4(), workspace_id=ws.id, name="MotorMoto", brand_json={})
    db = _QueueDb([_ExecuteResult(rows=[klaroha, motormoto])])

    brand = await chat_router._resolve_scope_brand(db, ws, "MotorMoto")

    assert brand is motormoto


@pytest.mark.asyncio
async def test_brand_roster_memory_lists_brands_without_loading_workspace_facts() -> None:
    ws = SimpleNamespace(id=uuid4(), name="Org", brand_json={"voice": "workspace voice"})
    brands = [
        SimpleNamespace(id=uuid4(), workspace_id=ws.id, name="Klaroha", brand_json={}),
        SimpleNamespace(id=uuid4(), workspace_id=ws.id, name="MotorMoto", brand_json={}),
    ]
    db = _QueueDb([_ExecuteResult(rows=brands)])

    memory = await hydrate_memory_slots(db, ws, ["brand_roster"], brand=None)

    assert memory["brand_roster"] == [
        {"id": str(brands[0].id), "name": "Klaroha"},
        {"id": str(brands[1].id), "name": "MotorMoto"},
    ]
    assert "workspace voice" not in str(memory)
