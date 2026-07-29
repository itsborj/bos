from pathlib import Path
import asyncio
import importlib.util
import sys
from types import SimpleNamespace
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
API_PATH = ROOT / "api"
if str(API_PATH) not in sys.path:
    sys.path.insert(0, str(API_PATH))

from routers import chat_v2
from services import brand_kit_templates
from services.brand_kit import extract_visual_constraints
from services.brand_kit_templates import (
    TemplateSelectionError,
    available_approved_postcraft_templates,
    default_template_manifest,
    ensure_template_manifest,
    select_template_from_manifest,
)

POSTCRAFT_HOOKS_PATH = ROOT / "plugins" / "postcraft" / "hooks.py"
hooks_spec = importlib.util.spec_from_file_location("postcraft_template_hooks_test", POSTCRAFT_HOOKS_PATH)
postcraft_hooks = importlib.util.module_from_spec(hooks_spec)
assert hooks_spec and hooks_spec.loader
hooks_spec.loader.exec_module(postcraft_hooks)

POSTCRAFT_RENDER_PATH = ROOT / "plugins" / "postcraft" / "capabilities" / "postcraft" / "render" / "module.py"
render_spec = importlib.util.spec_from_file_location("postcraft_template_render_test", POSTCRAFT_RENDER_PATH)
postcraft_render = importlib.util.module_from_spec(render_spec)
assert render_spec and render_spec.loader
render_spec.loader.exec_module(postcraft_render)


def test_legacy_generated_component_and_cross_brand_rules_are_not_media_constraints():
    markdown = """
# Golden Gate Memorial — Campaign Brand Kit
## 2. Color Palette
| color-primary | #342f2c | primary |
## 3. Tone of Voice
Warm, calm, respectful, and emotionally intelligent.
CTA language rules: Book a Memorial demo; Start a pilot.
## 7. Accessibility & Consistency
Visual system rules: use Obsidian and Racing Green surfaces.
"""

    constraints = extract_visual_constraints(markdown)

    assert "#342f2c" in constraints
    assert "Warm, calm" in constraints
    assert "Book a Memorial demo" not in constraints
    assert "Racing Green" not in constraints
    assert "Obsidian" not in constraints


def test_drive_filename_matches_are_not_promoted_to_templates():
    source = (Path(__file__).resolve().parents[1] / "routers" / "cmo_tools.py").read_text(encoding="utf-8")

    assert "creative_reference_files" in source
    assert "_postcraft_templates_from_validation" not in source
    assert "Brand Kit template manifest has not been implemented" not in source


def test_brand_kit_resources_use_cached_drive_index_during_reauth():
    source = (Path(__file__).resolve().parents[1] / "services" / "brand_kit_templates.py").read_text(encoding="utf-8")

    assert 'SocialConnection.status.in_(["connected", "needs_reauth"])' in source


def test_brand_kit_metadata_manifest_is_canonical_template_source():
    metadata = ensure_template_manifest({"version": "v1.0-draft"})

    manifest = metadata["template_manifest"]
    assert manifest["version"] == "brand_kit_templates.v1"
    assert manifest["templates"] == []
    assert manifest["selection_policy"]["default_renderer"] == "postcraft"
    assert manifest["selection_policy"]["confidence_threshold"] == 0.75


def test_chat_template_label_becomes_creative_direction_not_template_identity():
    text = """Template: Premium urgency\nFormat: square\nHeadline: Move now\nCTA: Book today\nVisual direction: Deep blue product hero"""

    args = chat_v2._postcraft_args_from_draft(text)

    assert args["creative_direction"] == "Premium urgency"
    assert args["template_type"] == "promo"
    assert "auto_select_template" not in args
    assert "template_id" not in args


def test_template_free_prompt_uses_original_composition_language():
    prompt = postcraft_render._build_prompt(
        {},
        {"brand_name": "Agency Client", "visual_language": ["warm editorial", "natural light"]},
        {"color_palette": {"primary": "#123456"}},
        {"headline": "A fresh campaign", "subheadline": "", "body": "", "cta": "", "location": ""},
        "square",
        [],
    )

    assert "original, channel-appropriate" in prompt
    assert "agency-level creative judgment rather than a fixed layout" in prompt
    assert "Template:" not in prompt


def test_postcraft_does_not_require_or_auto_select_a_template():
    brief = {"headline": "Create with brand latitude"}
    ctx = SimpleNamespace(brand_id=uuid4(), module_id="postcraft.render")

    resolved = asyncio.run(postcraft_hooks._resolve_brand_template_contract(brief, ctx))

    assert resolved == brief
    assert "_postcraft_template_blocker" not in resolved
    assert "template_id" not in resolved


def test_template_selector_chooses_highest_scoring_approved_template():
    manifest = default_template_manifest()
    manifest["templates"] = [
        {
            "id": "bk_tpl_low",
            "status": "approved",
            "renderer": "postcraft",
            "format": "square_feed",
            "content_type": "promo",
            "objective_fit": ["awareness"],
            "tone": ["informative"],
            "copy_density": "medium",
            "required_slots": ["headline", "logo"],
            "priority": 1,
        },
        {
            "id": "bk_tpl_best",
            "status": "approved",
            "renderer": "postcraft",
            "format": "square_feed",
            "content_type": "promo",
            "objective_fit": ["lead_gen"],
            "tone": ["urgent"],
            "copy_density": "medium",
            "required_slots": ["headline", "logo", "hero_image"],
            "priority": 5,
        },
    ]

    selection = select_template_from_manifest(manifest, {
        "renderer": "postcraft",
        "format": "square_feed",
        "content_type": "promo",
        "objective": "lead_gen",
        "tone": "urgent",
        "copy_density": "medium",
        "assets_available": ["logo", "hero_image"],
        "copy": {"headline": "Launch offer", "cta": "Book now"},
    })

    assert selection.template_id == "bk_tpl_best"
    assert selection.confidence >= 0.75
    assert "required assets available" in selection.reason


def test_template_selector_ranks_by_confidence_before_raw_score_and_bonuses():
    manifest = default_template_manifest()
    manifest["selection_policy"]["confidence_threshold"] = 0.75
    manifest["templates"] = [
        {
            "id": "high-raw-low-confidence",
            "status": "approved",
            "renderer": "postcraft",
            "format": "square_feed",
            "content_type": "testimonial",
            "objective_fit": ["awareness"],
            "tone": ["formal"],
            "copy_density": "high",
            "required_slots": ["headline", "logo"],
            "priority": 10,
            "performance_score": 1,
        },
        {
            "id": "lower-raw-high-confidence",
            "status": "approved",
            "renderer": "postcraft",
            "format": "square_feed",
        },
    ]

    selection = select_template_from_manifest(manifest, {
        "renderer": "postcraft",
        "format": "square_feed",
        "content_type": "promo",
        "objective": "lead_gen",
        "tone": "urgent",
        "copy_density": "medium",
        "assets_available": ["logo"],
        "copy": {"headline": "Launch"},
    })

    assert selection.template_id == "lower-raw-high-confidence"
    assert selection.confidence == 1.0


def test_priority_and_performance_do_not_inflate_fit_confidence():
    manifest = default_template_manifest()
    manifest["selection_policy"]["confidence_threshold"] = 0.6
    manifest["templates"] = [{
        "id": "bonus-heavy",
        "status": "approved",
        "renderer": "postcraft",
        "format": "square_feed",
        "content_type": "testimonial",
        "priority": 10,
        "performance_score": 1,
    }]

    selection = select_template_from_manifest(manifest, {
        "renderer": "postcraft",
        "format": "square_feed",
        "content_type": "promo",
    })

    assert selection.confidence == 0.67


def test_template_selector_blocks_missing_required_assets():
    manifest = default_template_manifest()
    manifest["templates"] = [{
        "id": "bk_tpl_needs_hero",
        "status": "approved",
        "renderer": "postcraft",
        "format": "square_feed",
        "content_type": "promo",
        "copy_density": "medium",
        "required_slots": ["headline", "logo", "hero_image"],
    }]

    try:
        select_template_from_manifest(manifest, {
            "renderer": "postcraft",
            "format": "square_feed",
            "content_type": "promo",
            "copy_density": "medium",
            "assets_available": ["logo"],
            "copy": {"headline": "Launch offer"},
        })
    except TemplateSelectionError as exc:
        assert exc.code == "no_matching_template"
        assert "missing required" in str(exc.details["invalid_templates"][0]["reasons"])
    else:
        raise AssertionError("expected missing required asset block")


def test_template_selector_blocks_when_no_manifest_template_available():
    manifest = default_template_manifest()

    try:
        select_template_from_manifest(manifest, {"renderer": "postcraft", "format": "square_feed"})
    except TemplateSelectionError as exc:
        assert exc.code == "no_approved_templates"
    else:
        raise AssertionError("expected no approved templates block")


def test_available_templates_require_postcraft_approved_status_and_indexed_drive_source():
    manifest = default_template_manifest()
    manifest["templates"] = [
        {"id": "ready", "status": "approved", "renderer": "postcraft", "source": {"drive_file_id": "drive-ready"}},
        {"id": "default-renderer", "status": "approved", "source": {"drive_file_id": "drive-default"}},
        {"id": "stale", "status": "approved", "renderer": "postcraft", "source": {"drive_file_id": "drive-missing"}},
        {"id": "wrong-renderer", "status": "approved", "renderer": "other", "source": {"drive_file_id": "drive-ready"}},
        {"id": "draft", "status": "draft", "renderer": "postcraft", "source": {"drive_file_id": "drive-ready"}},
    ]
    resources = [{"id": "drive-ready"}, {"id": "drive-default"}]

    available = available_approved_postcraft_templates(manifest, resources)

    assert [template["id"] for template in available] == ["ready", "default-renderer"]


def test_live_template_source_validation_uses_injected_drive_credentials(monkeypatch):
    calls = []

    class FakeDriveClient:
        def __init__(self, token):
            calls.append(("token", token))

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def get_file_meta(self, file_id):
            calls.append(("file", file_id))
            return {"id": file_id}

    monkeypatch.setattr(postcraft_hooks, "_load_drive", lambda: SimpleNamespace(DriveClient=FakeDriveClient))
    problem = postcraft_hooks._live_template_source_problem(
        {"_channel_credentials": {"google_drive_page_token": "drive-token"}},
        {"source": {"drive_file_id": "template-file"}},
    )

    assert problem is None
    assert calls == [("token", "drive-token"), ("file", "template-file")]


def test_live_template_source_validation_returns_structured_problem(monkeypatch):
    class MissingDriveClient:
        def __init__(self, _token):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def get_file_meta(self, _file_id):
            raise RuntimeError("Drive file not found")

    monkeypatch.setattr(postcraft_hooks, "_load_drive", lambda: SimpleNamespace(DriveClient=MissingDriveClient))
    problem = postcraft_hooks._live_template_source_problem(
        {"_channel_credentials": {"google_drive_page_token": "drive-token"}},
        {"source": {"drive_file_id": "missing-file"}},
    )

    assert problem["drive_file_id"] == "missing-file"
    assert "not found" in problem["live_validation_error"]


def test_runtime_selection_blocks_when_approved_source_is_not_in_drive_index(monkeypatch):
    manifest = default_template_manifest()
    manifest["templates"] = [{
        "id": "stale",
        "status": "approved",
        "renderer": "postcraft",
        "source": {"drive_file_id": "drive-missing"},
    }]
    doc = SimpleNamespace(metadata_json={"template_manifest": manifest})

    async def fake_latest_document(*_args, **_kwargs):
        return doc

    async def fake_latest_resources(*_args, **_kwargs):
        return [{"id": "some-other-file"}]

    monkeypatch.setattr(brand_kit_templates, "latest_brand_kit_document", fake_latest_document)
    monkeypatch.setattr(brand_kit_templates, "latest_drive_resources", fake_latest_resources)

    async def run():
        try:
            await brand_kit_templates.select_brand_kit_template(
                object(), SimpleNamespace(id=uuid4()), uuid4(), {"renderer": "postcraft", "format": "square_feed"}
            )
        except TemplateSelectionError as exc:
            assert exc.code == "approved_template_source_unavailable"
            assert exc.details["unavailable_templates"][0]["template_id"] == "stale"
        else:
            raise AssertionError("expected stale approved source blocker")

    asyncio.run(run())
