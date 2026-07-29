import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
API_PATH = ROOT / "api"
if str(API_PATH) not in sys.path:
    sys.path.insert(0, str(API_PATH))
CORE_PATH = ROOT / "plugins" / "storyboard" / "lib" / "json_image_storyboard.py"
MODULE_PATH = ROOT / "plugins" / "storyboard" / "capabilities" / "storyboard" / "json" / "create" / "module.py"
RENDER_MODULE_PATH = ROOT / "plugins" / "storyboard" / "capabilities" / "storyboard" / "json" / "render" / "module.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_storyboard_prompt_labels_official_logo_reference():
    core = _load(CORE_PATH, "storyboard_core_brand_ref_prompt_test")
    spec = core.spec_from_brief({
        "title": "Logo storyboard",
        "artifact_kind": "storyboard",
        "storyboard_text": """Objective: test logo use. Audience: partner. CTA: partner.

Panel 1: Visual/action: the official logo appears on a closing card. Camera/composition: static centered frame. Caption: Partner today. Emotion: confidence. Assets/constraints: use official logo only.""",
    })

    prompt = core.build_prompt(
        spec,
        has_brand_refs=True,
        ref_count=1,
        brand_ref_labels=["OFFICIAL BRAND LOGO — use only where storyboard explicitly requests logo/branded materials"],
    )

    assert "IMAGE 1: OFFICIAL BRAND LOGO" in prompt
    assert "unless the SOURCE STORYBOARD TEXT or JSON spec explicitly requests" in prompt
    assert "rough grayscale storyboard previsualization" in prompt


def test_video_blueprint_prompt_defaults_to_bw_previs_reference():
    core = _load(CORE_PATH, "storyboard_core_color_video_prompt_test")
    spec = core.spec_from_brief({
        "title": "Color Video Blueprint",
        "artifact_kind": "video_production_blueprint",
        "duration": "15s",
        "storyboard_text": """## Objective\nShow a founder moving from confusion to clarity.\n\n## Audience\nOperators under pressure.\n\n## Offer\nKlaroha demand-capture infrastructure.\n\n## Shots\n### Shot 1\n- **Visual Action:** Founder scanning incoming leads in a dim office.\n- **Camera Composition:** Tight push-in.\n- **Script:** Too many signals, no clear next step.\n- **Emotion:** Pressure.\n\n### Shot 2\n- **Visual Action:** Klaroha dashboard highlights buyer intent and next action.\n- **Camera Composition:** Clean over-shoulder reveal.\n- **Script:** Klaroha turns demand into action.\n- **Emotion:** Clarity.\n\n### Shot 3\n- **Visual Action:** Confident CTA frame.\n- **Camera Composition:** Static finish.\n- **Script:** Book a demo.\n- **Emotion:** Confidence.\n""",
    })

    prompt = core.build_prompt(spec)

    assert "black-and-white hand-drawn / animatic storyboard previsualization" in prompt
    assert "Seedance owns final video realism" in prompt
    assert "Use no color except black/white/grayscale by default" in prompt


def test_storyboard_prompt_uses_reference_sheet_for_logo_revision():
    core = _load(CORE_PATH, "storyboard_core_reference_sheet_prompt_test")
    spec = core.spec_from_brief({
        "title": "Logo revision",
        "artifact_kind": "storyboard",
        "storyboard_text": """Objective: revise logo. Audience: partner. CTA: partner.

Panel 1: Visual/action: closing card with a logo. Camera/composition: static centered frame. Caption: Partner today. Emotion: confidence. Assets/constraints: use official logo.""",
    })

    prompt = core.build_prompt(
        spec,
        has_source=True,
        has_brand_refs=True,
        ref_count=1,
        revision_prompt="update logo",
        brand_ref_labels=["OFFICIAL BRAND LOGO — use in final CTA panel"],
    )

    assert "IMAGE 1 is the source storyboard" in prompt
    assert "IMAGE 2" in prompt
    assert "OFFICIAL BRAND LOGO" in prompt


def test_storyboard_render_injects_logo_reference_from_brand_spec(monkeypatch):
    mod = _load(RENDER_MODULE_PATH, "storyboard_render_logo_inject_test")

    class FakeClient:
        def __init__(self, token):
            self.token = token
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def get_file_meta(self, file_id):
            return {"name": "logo.png", "mimeType": "image/png"}
        def download_file(self, file_id):
            return b"fake-logo-bytes"

    class FakeDrive:
        DriveClient = FakeClient

    monkeypatch.setattr(mod, "_load_drive", lambda: FakeDrive)
    refs = mod._inject_logo_reference(
        {"_channel_credentials": {"google_drive_page_token": "tok"}, "reference_images": [{"drive_file_id": "other"}]},
        {"logo_drive_file_id": "logo123"},
    )

    assert refs[0]["placement_role"] == "logo"
    assert refs[0]["drive_file_id"] == "logo123"
    assert refs[0]["vision_b64"]
    assert refs[1]["drive_file_id"] == "other"


def test_storyboard_render_normalizes_ratio_size_alias_before_openai_call(monkeypatch):
    mod = _load(RENDER_MODULE_PATH, "storyboard_render_size_alias_test")
    seen: dict = {}

    class FakeCore:
        RUNS_ROOT = "/tmp/bos-storyboard-runs"

        @staticmethod
        def _get_image_creds(_brief):
            return "openai", "gpt-image-2", "fake-key"

        @staticmethod
        def _normalize_requested_size(value):
            seen["requested"] = value
            return "1024x1536"

        @staticmethod
        def _openai_base_url_from_brief(_brief):
            return "https://api.openai.com/v1"

        @staticmethod
        def _call_openai_generate(spec, image_prompt, brief, api_key, model, size, base_url=None):
            seen["size"] = spec["job"]["size"]
            seen["brief_size"] = brief.get("size")
            seen["call_size"] = size
            seen["base_url"] = base_url
            return {"data": [{"b64_json": "ZmFrZQ=="}]}

        @staticmethod
        def _image_response_to_bytes(_response):
            return b"fake-image", {}

    monkeypatch.setattr(mod, "_load_core", lambda: FakeCore)
    monkeypatch.setattr(mod, "_inject_logo_reference", lambda brief, brand_spec: [])
    monkeypatch.setattr(mod, "_store_in_drive", lambda brief, image_bytes, output_path: {"drive_file_id": "drive123"})

    attempt, result = mod.StoryboardRenderModule().execute_tool_result({
        "storyboard_text": "A fully approved storyboard script that is definitely long enough to render.",
        "size": "3:4",
        "_channel_credentials": {
            "provider_api_key": "fake-key",
            "provider_api_key_auth_mode": "api_key",
            "google_drive_page_token": "drive-token",
            "drive_root_folder_id": "root-folder",
        },
    })

    assert attempt["status"] == "succeeded"
    assert seen["requested"] == "3:4"
    assert seen["size"] == "1024x1536"
    assert seen["brief_size"] == "1024x1536"
    assert seen["call_size"] == "1024x1536"
    assert seen["base_url"] == "https://api.openai.com/v1"
    assert result["block"]["status"] == "succeeded"


def test_video_blueprint_quality_gate_flags_generic_template_placeholders():
    core = _load(CORE_PATH, "storyboard_core_generic_template_quality_test")
    spec = core.spec_from_brief({
        "title": "Golden Gate Memorial Storyboard for Family Protectors",
        "artifact_kind": "video_production_blueprint",
        "message": "Golden Gate Memorial Storyboard for Family Protectors",
        "audience": "Filipino Family Protector",
        "offer": "Memorial Garden and Columbarium",
        "existing_tension": "Quiet fear of leaving loved ones unprepared",
        "resolution_mechanism": "A dignified pre-planned resting place",
        "cta_goal": "Book a quiet site visit",
        "duration": "15s",
    })
    _ok, errors, warnings = core.validate_spec(spec)

    assert not errors
    assert any("generic storyboard template placeholders" in w for w in warnings)
    assert any(core.is_blocking_quality_warning(w) for w in warnings)


def test_storyboard_revision_note_is_preserved_in_revised_section():
    core = _load(CORE_PATH, "storyboard_core_revision_note_test")
    prior = """# Blueprint

## Screenplay / Text Storyboard
| Shot | Time | Script / audio | On-screen text | Visual / action | Camera / motion | Assets / constraints |
|---|---:|---|---|---|---|---|
| 1 | 0-5s | Hook | Hook | Concrete scene. | Tight frame. | Use official logo. |
| 2 | 5-10s | Proof | Proof | Concrete solution. | Wide frame. | Use memorial garden. |
| 3 | 10-15s | CTA | CTA | Concrete CTA. | Static close. | Official logo only. |

## Approval checklist
- Ready

## Revised
- No revisions requested yet.
"""

    spec = core.spec_from_brief({
        "title": "Revision",
        "artifact_kind": "video_production_blueprint",
        "storyboard_text": prior,
        "revision_feedback": "show the official logo and ginto",
    })
    text = core.storyboard_text_from_spec(spec)

    assert "show the official logo and ginto" in text
    assert "No revisions requested yet" not in text


def test_storyboard_quality_gate_flags_thin_summary():
    core = _load(CORE_PATH, "storyboard_core_quality_test")
    thin = (
        "A storyboard for the Trusted Connector audience. "
        "Scene 1: A community leader listens to worries. "
        "Scene 2: The leader discovers the brand online. "
        "Scene 3: They present the plan. "
        "Scene 4: The community feels relieved."
    )

    spec = core.spec_from_brief({"title": "Thin", "message": thin})
    ok, errors, warnings = core.validate_spec(spec)

    assert ok
    assert not errors
    assert any(core.is_blocking_quality_warning(w) for w in warnings)


def test_storyboard_quality_gate_counts_bold_panel_headings():
    core = _load(CORE_PATH, "storyboard_core_quality_heading_test")
    detailed = """# Storyboard: The Community Pillar

**Objective:** Show Trusted Connectors how partnering creates dignified community service.
**Audience:** Trusted Connector.
**Offer/CTA:** Partner with Golden Gate Memorial.

### **Panel 1**
* **Visual/Action:** A community leader notices a worried family after a meeting.
* **On-Screen Text:** You see needs people do not say out loud.
* **Camera/Composition:** Medium shot with the leader foregrounded and the family soft in back.
* **Emotion:** Concern and responsibility.
* **Assets/Constraints:** Community hall, no readable logos, consistent wardrobe.

### **Panel 2**
* **Visual/Action:** The leader reviews Golden Gate Memorial materials at her desk.
* **On-Screen Text:** Find a plan that protects dignity.
* **Camera/Composition:** Close-up on her face and brochure, gentle push-in.
* **Emotion:** Discovery and hope.
* **Assets/Constraints:** Subtle brand material, grayscale storyboard style.

### **Panel 3**
* **Visual/Action:** She calmly presents the planning option to the family.
* **On-Screen Text:** Preparedness can be an act of care.
* **Camera/Composition:** Inclusive group shot around a table.
* **Emotion:** Trust and relief.
* **Assets/Constraints:** Private comfortable setting, no exaggerated grief.

### **Panel 4**
* **Visual/Action:** The family leaves reassured while the leader looks fulfilled.
* **On-Screen Text:** Partner in preparedness.
* **Camera/Composition:** Wide closing frame mirroring the opener.
* **Emotion:** Fulfillment and peace.
* **Assets/Constraints:** Same location continuity, CTA handled in post.
"""

    spec = core.spec_from_brief({"title": "Headings", "artifact_kind": "storyboard", "storyboard_text": detailed})
    _ok, errors, warnings = core.validate_spec(spec)

    assert core._count_storyboard_beats(detailed) == 4
    assert len(spec["acts"][0]["shots"]) == 4
    assert not errors
    assert not any(core.is_blocking_quality_warning(w) for w in warnings)


def test_video_blueprint_accepts_ordered_bullet_panels_without_table():
    core = _load(CORE_PATH, "storyboard_core_quality_bullet_blueprint_test")
    detailed = """# Storyboard: Peace of Mind from Afar

**Objective:** Connect with the audience's distance guilt and position planning as care.
**Audience:** OFW/Seafarer.
**Offer/CTA:** Golden Gate Memorial. Plan today.

### Shot List (9:16 Vertical Video)

**Panel 1**
- **Visual:** Close-up on an OFW in a modest room abroad, worried while looking at a phone.
- **Caption:** Far from home, but always connected.
- **Camera/Composition:** Tight close-up with phone glow lighting her face.
- **Emotion:** Worry and love.
- **Assets/Constraints:** Modest room, no readable app UI, grayscale storyboard style.

**Panel 2**
- **Visual:** Phone video call with an aging parent in the Philippines.
- **Caption:** Some things cannot be fixed over the phone.
- **Camera/Composition:** POV insert of phone, then reaction close-up.
- **Emotion:** Distance guilt and responsibility.
- **Assets/Constraints:** Simulated call UI, no real app logos.

**Panel 3**
- **Visual:** Serene Golden Gate Memorial Garden shot introduces the planning solution.
- **Caption:** A place of peace. A promise of preparedness.
- **Camera/Composition:** Wide slow pan across garden paths.
- **Emotion:** Calm and security.
- **Assets/Constraints:** Use garden reference, no exaggerated grief.

**Panel 4**
- **Visual:** Final logo/CTA over peaceful garden image.
- **Caption:** Plan today. Secure their tomorrow.
- **Camera/Composition:** Static wide end frame with text added in post.
- **Emotion:** Hope and confidence.
- **Assets/Constraints:** Logo handled as overlay, preserve dignified tone.
"""

    spec = core.spec_from_brief({"title": "Bullet Blueprint", "artifact_kind": "video_production_blueprint", "storyboard_text": detailed})
    text = core.storyboard_text_from_spec(spec)
    _ok, errors, warnings = core.validate_spec(spec)

    assert "## Tension Statement" in text
    assert len(spec["acts"][0]["shots"]) == 3
    assert not errors
    assert not any(core.is_blocking_quality_warning(w) for w in warnings)


def test_video_blueprint_creator_normalizes_loose_notes_into_15s_contract():
    core = _load(CORE_PATH, "storyboard_core_creator_owned_blueprint_test")
    raw = """## Objective
Encourage families to plan ahead for a dignified resting place.

## Audience
Filipino Family Protectors and OFWs.

## Offer
Memorial Garden and Columbarium.

## Shots
### Shot 1
- **Visual Action:** A serene view of the memorial garden at sunrise.
- **Camera Composition:** Wide shot, panning across the garden.
- **Script:** A final resting place where peace meets preparation.
- **Emotion:** Calm and inviting.

### Shot 2
- **Visual Action:** A family visits a loved one's columbarium niche and places flowers.
- **Camera Composition:** Medium close-up on emotional faces.
- **Script:** Give your family the confidence to grieve with dignity.
- **Emotion:** Respectful and heartfelt.

### Shot 3
- **Visual Action:** A warm family discussion about pre-need plans.
- **Camera Composition:** Over-the-shoulder shot showing engagement.
- **Script:** Plan today for peace tomorrow.
- **Emotion:** Inviting and proactive.

### Shot 4
- **Visual Action:** Golden Gate Memorial logo closes the piece.
- **Camera Composition:** Simple fade-in.
- **Script:** Golden Gate Memorial—where dignity meets preparation.
- **Emotion:** Trustworthy and comforting.

## Call to Action
Visit Golden Gate Memorial to start planning today.
"""

    spec = core.spec_from_brief({
        "title": "Golden Gate 15s",
        "artifact_kind": "video_production_blueprint",
        "platform": "Facebook",
        "aspect_ratio": "16:9",
        "storyboard_text": raw,
    })
    text = core.storyboard_text_from_spec(spec)
    _ok, errors, warnings = core.validate_spec(spec)

    assert "## Tension Statement" in text
    assert "### Beat 1 — Hook (0–4s)" in text
    assert "### Beat 2 — Shift (4–11s)" in text
    assert "### Beat 3 — CTA (11–15s)" in text
    assert "## What Was Cut And Why" in text
    assert "## Sound-On / Sound-Off Audit" in text
    assert len(spec["acts"][0]["shots"]) == 3
    assert not errors
    assert not any(core.is_blocking_quality_warning(w) for w in warnings)


def test_video_blueprint_ignores_panel_count_override_after_creator_normalization():
    core = _load(CORE_PATH, "storyboard_core_panel_override_test")
    raw = """## Objective
Help first-time motorcycle buyers feel confident choosing the right motorcycle.

## Audience
First-time motorcycle buyers who need guidance and confidence.

## Offer
Helpful motorcycle buying guidance plus practical ownership support.

## Shots
### Shot 1
- **Visual Action:** A nervous buyer scans several motorcycles.
- **Camera Composition:** Tight handheld close-up.
- **Script:** Too many choices can feel risky.
- **Emotion:** Uncertainty.

### Shot 2
- **Visual Action:** A MotorMoto advisor points to the right fit and explains why.
- **Camera Composition:** Medium two-shot.
- **Script:** Get clear guidance built around how you actually ride.
- **Emotion:** Relief.

### Shot 3
- **Visual Action:** The buyer rides away confidently.
- **Camera Composition:** Clean follow shot.
- **Script:** Talk to a MotorMoto advisor.
- **Emotion:** Confidence.
"""

    spec = core.spec_from_brief({
        "title": "MotorMoto 15s",
        "artifact_kind": "video_production_blueprint",
        "duration": "15s",
        "panel_count": 5,
        "storyboard_text": raw,
    })
    _ok, errors, warnings = core.validate_spec(spec)

    assert len(spec["acts"][0]["shots"]) == 3
    assert not errors
    assert not any(core.is_blocking_quality_warning(w) for w in warnings)


def test_storyboard_creator_compresses_markdown_table_runtime_to_15s_contract():
    core = _load(CORE_PATH, "storyboard_core_quality_table_duration_test")
    detailed = """### Production Blueprint

Objective: Show a trusted connector why this is a dignified community-service offer.
Audience: community referral partners. Offer/CTA: invite families to request a planning conversation.

## Script / Storyboard

| Shot / Panel | Duration | Script / audio | On-screen text | Visual / action | Camera / motion | Assets / constraints |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1** (0-5s) | 5s | Voiceover frames the responsibility. | Carry their trust. | The connector reviews notes after a community meeting, visibly concerned but composed. | Medium wide establishing frame, slow push toward the connector. | Community room location, no readable logos, consistent wardrobe. |
| **2** (5-12s) | 7s | Voiceover introduces planning as care. | Preparedness is care. | The connector sits with a family and calmly opens a simple planning guide. | Over-the-shoulder composition, guide visible as a prop. | Keep text unreadable, warm grayscale lighting, no exaggerated grief. |
| **3** (12-18s) | 6s | CTA invites a next step. | Start the conversation. | The family leaves reassured while the connector remains fulfilled. | Wide closing frame matching the opener, gentle pullback. | Same room and props, black-and-white storyboard prototype. |

## Approval checklist
- Message and claims approved
- Timing and scene order approved
- Required assets confirmed

## Revised
- No revisions requested yet.
"""

    spec = core.spec_from_brief({"title": "Table", "artifact_kind": "video_production_blueprint", "storyboard_text": detailed})
    text = core.storyboard_text_from_spec(spec)
    _ok, errors, warnings = core.validate_spec(spec)

    assert core._count_storyboard_beats(detailed) == 3
    assert not errors
    assert not any(core.is_blocking_quality_warning(w) for w in warnings)
    assert "### Beat 3 — CTA (11–15s)" in text
    assert "Reduced" in text or "trimmed" in text


def test_storyboard_quality_gate_accepts_15s_markdown_table_runtime():
    core = _load(CORE_PATH, "storyboard_core_quality_table_pass_test")
    detailed = """### Production Blueprint

Objective: Deliver a complete short-form partner story inside the runtime cap.
Audience: community referral partners. Offer/CTA: invite families to request a planning conversation.

## Script / Storyboard

| Shot | Time | Script / audio | On-screen text | Visual / action | Camera / motion | Assets / constraints |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | 0-5s | Voiceover frames the responsibility. | Carry their trust. | The connector reviews notes after a community meeting, visibly concerned but composed. | Medium wide establishing frame, slow push toward the connector. | Community room location, no readable logos, consistent wardrobe. |
| 2 | 5-10s | Voiceover introduces planning as care. | Preparedness is care. | The connector sits with a family and calmly opens a simple planning guide. | Over-the-shoulder composition, guide visible as a prop. | Keep text unreadable, warm grayscale lighting, no exaggerated grief. |
| 3 | 10-15s | CTA invites a next step. | Start the conversation. | The family leaves reassured while the connector remains fulfilled. | Wide closing frame matching the opener, gentle pullback. | Same room and props, black-and-white storyboard prototype. |

## Approval checklist
- Message and claims approved
- Timing and scene order approved
- Required assets confirmed

## Revised
- No revisions requested yet.
"""

    spec = core.spec_from_brief({"title": "Table", "artifact_kind": "video_production_blueprint", "storyboard_text": detailed})
    _ok, errors, warnings = core.validate_spec(spec)

    assert core._count_storyboard_beats(detailed) == 3
    assert not errors
    assert not any(core.is_blocking_quality_warning(w) for w in warnings)


def test_storyboard_quality_gate_accepts_decimal_subsecond_markdown_table_runtime():
    core = _load(CORE_PATH, "storyboard_core_quality_table_decimal_pass_test")
    detailed = """### Production Blueprint

Objective: Deliver a complete short-form product demo inside the runtime cap.
Audience: marketing operators. Offer/CTA: try Klaroha.

## Script / Storyboard

| Shot | Time | Script / audio | On-screen text | Visual / action | Camera / motion | Assets / constraints |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 01 | 0–3.5s | The brief has been ready for three days. | 3 days overdue | Marketing lead glances at an 11am clock beside the finished brief. | Static locked frame. | Natural office lighting. |
| 02 | 3.5–5.2s | | | User selects the full brief text. | Soft follow on cursor. | No readable extra UI. |
| 03 | 5.2–6s | You paste it once. | | Klaroha chat input receives the pasted brief. | Hard clean cut. | Plain native chat interface. |
| 04 | 6–9.2s | | Done. | Three finished ad variants appear inline. | Static frame hold. | No loading spinner. |
| 05 | 9.2–11.8s | Edit anything. Just talk. | | User types one edit and the ad updates instantly. | Instant cut only. | Show exactly one line of chat text. |
| 06 | 11.8–14.7s | Try it free. | Try it free. | Finished ad centered with small wordmark. | Static clean closing frame. | No extra logos. |

## Approval checklist
- Message and claims approved
- Timing and scene order approved
- Required assets confirmed

## Revised
- No revisions requested yet.
"""

    spec = core.spec_from_brief({"title": "Decimal Table", "artifact_kind": "video_production_blueprint", "storyboard_text": detailed})
    _ok, errors, warnings = core.validate_spec(spec)

    assert core._extract_table_runtime_seconds(detailed) == ("screenplay table timeline end", 14.7)
    assert not errors
    assert not any(core.is_blocking_quality_warning(w) for w in warnings)


def test_storyboard_quality_gate_accepts_detailed_markdown():
    core = _load(CORE_PATH, "storyboard_core_quality_pass_test")
    detailed = """# Secondary Audience Storyboard

Objective: Build trust with secondary audience referral partners who need a dignified way to introduce planning.
Audience: Community connectors. Offer/CTA: Invite families to request a gentle planning guide.

## Shot List
1. Panel 1 — Script/audio: quiet room tone; caption says planning can be an act of care. Visual/action: connector reviews notes at a community table with two families nearby. Camera/composition: wide establishing frame with the connector in foreground. Emotion: responsibility. Assets/constraints: no readable logos, modest wardrobe, community hall location.
2. Panel 2 — Script/audio: voiceover names the worry of waiting too long. Visual/action: close shot of a handwritten checklist and phone beside a coffee cup. Camera/composition: overhead close-up, shallow grayscale contrast. Emotion: concern becoming focus. Assets/constraints: no fake UI text, keep props simple.
3. Panel 3 — Script/audio: connector explains a dignified next step. Visual/action: connector speaks with a family at the table, open posture, hands visible. Camera/composition: medium over-the-shoulder framing. Emotion: calm authority. Assets/constraints: preserve same room and character continuity.
"""

    spec = core.spec_from_brief({"title": "Detailed", "artifact_kind": "storyboard", "storyboard_text": detailed})
    _ok, errors, warnings = core.validate_spec(spec)

    assert len(spec["acts"][0]["shots"]) == 3
    assert not errors
    assert not any(core.is_blocking_quality_warning(w) for w in warnings)
