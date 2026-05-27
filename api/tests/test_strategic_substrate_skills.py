from __future__ import annotations

from skills.loader import format_activated_skill, get_skill, list_skill_manifests


def test_buyer_intelligence_reasoning_skill_is_non_chat_substrate() -> None:
    skill = next(s for s in list_skill_manifests() if s.id == "reasoning.buyer_intelligence")

    assert skill.name == "buyer-intelligence"
    assert skill.scope == "reasoning"
    assert skill.allowed_from_chat is False
    assert skill.module_id == "reasoning.buyer_intelligence"
    assert skill.load_policy == "explicit_inheritance_only"
    assert skill.outputs == ["buyer_map.v1"]
    assert skill.metadata["output_contract"] == "buyer_map"
    assert "no_downstream_strategy_without_buyer_map" in skill.quality_gates


def test_messaging_architecture_skill_depends_on_buyer_map() -> None:
    skill = next(s for s in list_skill_manifests() if s.id == "marketing.messaging.architecture")

    assert skill.name == "messaging"
    assert skill.scope == "strategy"
    assert skill.allowed_from_chat is False
    assert skill.module_id == "marketing.messaging.architecture"
    assert skill.depends_on == ["reasoning.buyer_intelligence", "brand_brief"]
    assert skill.required_upstream == ["buyer_map.v1"]
    assert skill.outputs == ["message_architecture.v1"]
    assert skill.metadata["output_contract"] == "message_architecture"


def test_activated_skill_context_includes_dependency_metadata() -> None:
    skill = get_skill("marketing.planning.gtm_plan")
    assert skill is not None

    wrapped = format_activated_skill(skill)

    assert "<skill_dependencies>" in wrapped
    assert "reasoning.buyer_intelligence" in wrapped
    assert "marketing.messaging.architecture" in wrapped
    assert "buyer_map.v1" in wrapped
    assert "message_architecture.v1" in wrapped
