from __future__ import annotations

from pathlib import Path

from capability_manifest import build_dispatchable_manifest
from skills.loader import list_skill_manifests


def test_campaign_strategy_retired_not_in_active_manifests() -> None:
    # campaign_strategy retired in favour of marketing.planning.strategy_workflow.
    # Must be absent from both the skill loader and the dispatchable manifest.
    manifest_ids = {e.module_id for e in build_dispatchable_manifest()}
    skill_ids = {s.id for s in list_skill_manifests()}
    assert "marketing.plan.campaign_strategy" not in manifest_ids
    assert "marketing.plan.campaign_strategy" not in skill_ids


def test_cmo_prompt_keeps_plans_out_of_inline_chat() -> None:
    prompt = (Path(__file__).resolve().parents[1] / "capabilities/workspace/cmo_context/SYSTEM_PROMPT.md").read_text()

    assert "Artifact surface boundary" in prompt
    assert "do not write full platform-native artifacts inline" in prompt
    assert "Never promise that you will create" in prompt
    assert "another one" in prompt
