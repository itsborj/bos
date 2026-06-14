from attachment_context import build_payload, compose_storyboard_spec


class Ref:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def test_variables_are_relative_to_reference_extraction_json():
    ref = Ref(
        kind="document",
        source="inline",
        title="Brief JSON",
        text='{"brand_brief":{"visual_design":{"primary_colors":{"body_gold":{"hex":"#C8A84B"}}}}}',
        extraction_status="read",
    )

    payload = build_payload([ref])

    assert payload["items"][0]["id"] == ref.id
    assert any(v["reference_id"] == ref.id and v["path"] == "$.brand_brief.visual_design.primary_colors.body_gold.hex" for v in payload["variables"])
    assert not any("items[0]" in v["path"] for v in payload["variables"])


def test_storyboard_spec_defaults_four_bw_sheets_to_sixteen_scene_candidates():
    refs = [Ref(kind="document", source="inline", title="Concept", text="A 15-second reel", extraction_status="read")]
    refs.extend(
        Ref(kind="image", source="google_drive", title=f"B&W storyboard sheet {idx}", drive_file_id=f"sheet_{idx}", extraction_status="vision_ready")
        for idx in range(1, 5)
    )
    refs.append(Ref(kind="image", source="google_drive", title="Final color shot", drive_file_id="final", extraction_status="vision_ready"))

    spec = compose_storyboard_spec(refs)

    assert spec is not None
    assert spec["schema"] == "bos.storyboard_spec.v1"
    assert spec["scene_count"] == 16
    assert len({scene["scene_id"] for scene in spec["scenes"]}) == 16
    assert spec["final_shot_reference_ids"]
    assert spec["status"] == "draft_review_required"
