"""Structure tests for the compact CMO prompt context built around Campaign V2."""
from services.working_context import PAYLOAD_TYPE, working_context_prompt_block

_SECTIONS = {"brand", "campaign", "desk", "references"}


def _sample_doc(**section_overrides):
    sections = {
        "brand": "sample scaffold text",
        "campaign": "Selected Campaign V2 context: sample",
        "desk": {"workflow_state": "sample workflow", "actionable_artifacts": "sample artifacts"},
        "references": "",
    }
    sections.update(section_overrides)
    coverage = {k: ("present" if v else "none") for k, v in sections.items()}
    return {
        "payload_type": PAYLOAD_TYPE,
        "assembled_at": "2026-07-03T09:00:00Z",
        "freshness": {"brand": "cached_5m", "campaign": "live_campaign_v2", "desk": "live", "references": "session"},
        "coverage": coverage,
        "sections": sections,
    }


def test_renders_one_document_with_all_section_markers():
    block = working_context_prompt_block(_sample_doc())
    assert block.count("=== CMO prompt context") == 1
    assert block.count("=== end prompt context ===") == 1
    for marker in ("--- brand ---", "--- campaign ---", "--- desk ---"):
        assert marker in block
    assert "--- today ---" not in block
    assert "Section freshness:" in block
    assert "Coverage:" in block


def test_no_campaign_selected_keeps_campaign_read_guidance():
    block = working_context_prompt_block(_sample_doc(campaign=""))
    assert "No selected Campaign V2 context is loaded in this prompt" in block
    assert "call campaign_read" in block
    assert "all_active=true" in block
    assert "synthesize the portfolio after the read" in block
    assert "Onboarding now creates a live campaign from the brand profile" in block
    assert "creative execution should bind to that live campaign" in block


def test_empty_sections_are_omitted_not_fabricated():
    block = working_context_prompt_block(
        _sample_doc(brand="", desk=None, references="")
    )
    assert "--- brand ---" not in block
    assert "--- desk ---" not in block
    assert "--- references" not in block
    assert "--- today ---" not in block
    assert "--- campaign ---" in block


def test_prompt_context_no_longer_injects_daily_brief_section():
    block = working_context_prompt_block(_sample_doc())
    assert "cmo_daily_brief@v1" not in block
    assert "coverage is 'reported'" not in block


def test_desk_section_preserves_workflow_and_artifact_guidance():
    block = working_context_prompt_block(_sample_doc())
    assert "Package workflow state" in block
    assert "available_actions/current_artifact_id" in block
    assert "Actionable approved/reviewable artifacts" in block


def test_empty_doc_renders_nothing():
    assert working_context_prompt_block({}) == ""
