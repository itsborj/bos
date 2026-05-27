from __future__ import annotations

from types import SimpleNamespace

from artifacts import artifact_ref_from_run, artifact_title, artifact_renderer


def test_gtm_plan_artifact_ref_is_gtm_strategy_not_generic_campaign_plan() -> None:
    run = SimpleNamespace(
        run_id="11111111-1111-1111-1111-111111111111",
        module_id="marketing.planning.gtm_plan",
        status="success",
        approval_status="pending",
        result=SimpleNamespace(platform="planning", self_check="pass"),
    )

    assert artifact_title(run) == "GTM Strategy"
    assert artifact_renderer(run) == "gtm_strategy_preview"
    ref = artifact_ref_from_run(run)
    assert ref.title == "GTM Strategy"
    assert ref.renderer == "gtm_strategy_preview"
