from __future__ import annotations

from skills.loader import list_skill_manifests


def test_gtm_strategy_skill_is_retired_from_dispatchable_manifests() -> None:
    # The module and SKILL.md were retired. CMO chat dispatches
    # marketing.planning.strategy_workflow instead.
    skill_ids = {s.id for s in list_skill_manifests()}
    assert "marketing.planning.gtm_plan" not in skill_ids
