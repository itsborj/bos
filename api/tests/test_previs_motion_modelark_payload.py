import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SDK_PATH = ROOT / "packages" / "klaroha_sdk"
if str(SDK_PATH) not in sys.path:
    sys.path.insert(0, str(SDK_PATH))


def _load_previs_module():
    path = ROOT / "plugins" / "previs-motion" / "capabilities" / "storyboard" / "motion" / "render" / "module.py"
    spec = importlib.util.spec_from_file_location("previs_motion_render_module_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _load_previs_edit_module():
    path = ROOT / "plugins" / "previs-motion" / "capabilities" / "storyboard" / "motion" / "edit" / "module.py"
    spec = importlib.util.spec_from_file_location("previs_motion_edit_module_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_previs_edit_alias_forces_video_to_video(monkeypatch):
    module = _load_previs_edit_module()
    seen = {}

    def fake_execute(self, brief):
        seen.update(brief)
        return {"status": "succeeded"}, {"block": {"mode": brief.get("mode")}}

    monkeypatch.setattr(module._render.PrevisMotionRenderModule, "execute_tool_result", fake_execute)

    attempt, result = module.PrevisMotionEditModule().execute_tool_result({
        "mode": "image_to_video",
        "reference_video_url": "https://example.invalid/previous.mp4",
    })

    assert attempt["status"] == "succeeded"
    assert seen["mode"] == "video_to_video"
    assert result["block"]["mode"] == "video_to_video"


def test_modelark_payload_defaults_audio_on():
    module = _load_previs_module()
    target = module._compile_target_json(
        {"watermark": "false"},
        {"project": {"title": "Audio default"}},
        "text_to_video",
        None,
        None,
    )

    payload = module._build_modelark_body(target, "render with audio by default")

    assert payload["generate_audio"] is True
    assert "generateAudio" not in payload


def test_t2v_direct_prompt_preserves_large_markdown_without_filtering():
    module = _load_previs_module()
    direct_prompt = "\n".join([
        "# THE WIDOWER — 15-SECOND AI VIDEO PROMPT",
        "Create a 15-second ad for Golden Gate Memorial Garden.",
        "No dialogue. No voiceover. No subtitles.",
        "Sound: soft acoustic guitar and faint outdoor ambience.",
        "Allowed visible text only: BELOVED WIFE, You are missed., Some Rituals Never End.",
        "Detailed shot notes " + ("x" * 12000),
    ])
    target = module._compile_target_json(
        {"mode": "text_to_video", "prompt": direct_prompt},
        {},
        "text_to_video",
        None,
        None,
    )

    prompt = module._prompt_from_target(target, "text_to_video")
    payload = module._build_modelark_body(target, prompt)

    assert prompt == direct_prompt
    assert "Golden Gate Memorial Garden" in prompt
    assert "Sound: soft acoustic guitar" in prompt
    assert payload["content"] == [{"type": "text", "text": direct_prompt}]
    assert payload["model"] == "dreamina-seedance-2-0-260128"


def test_modelark_payload_disables_audio_with_snake_case_key():
    module = _load_previs_module()
    target = module._compile_target_json(
        {"generate_audio": "false", "watermark": "false"},
        {"project": {"title": "Audio moderation regression"}},
        "text_to_video",
        None,
        None,
    )

    payload = module._build_modelark_body(target, "render silently")

    assert payload["generate_audio"] is False
    assert "generateAudio" not in payload
    assert payload["watermark"] is False


def test_bool_coercion_handles_string_false_values():
    module = _load_previs_module()

    for value in ("false", "False", "0", "no", "off", "", None):
        assert module._coerce_bool(value, False) is False

    for value in ("true", "True", "1", "yes", "on", True, 1):
        assert module._coerce_bool(value, False) is True


def test_previs_refuses_non_seedance2_models_by_default():
    module = _load_previs_module()

    try:
        module._compile_target_json({"model": "video-pilot-test-model"}, {}, "text_to_video", None, None)
    except ValueError as exc:
        assert "pinned to Seedance 2.0" in str(exc)
    else:
        raise AssertionError("expected non-Seedance-2 model to be rejected")


def test_previs_prefers_video_backend_model_over_stale_image_model():
    module = _load_previs_module()

    target = module._compile_target_json(
        {
            "model": "gpt-image-2",
            "backend_model_id": "dreamina-seedance-2-0-fast-260128",
            "backend_provider": "byteplus_modelark",
        },
        {},
        "text_to_video",
        None,
        None,
    )

    assert target["provider"]["model"] == "dreamina-seedance-2-0-fast-260128"


def test_previs_accepts_gemini_veo_backend_override():
    module = _load_previs_module()

    target = module._compile_target_json(
        {
            "backend_provider": "gemini",
            "backend_model_id": "veo-3.1-fast-generate-preview",
            "duration": 15,
            "ratio": "16:9",
        },
        {},
        "text_to_video",
        None,
        None,
    )
    payload = module._build_gemini_veo_body(target, "make a polished 8s video")

    assert target["provider"]["name"] == "gemini"
    assert target["provider"]["model"] == "veo-3.1-fast-generate-preview"
    assert target["provider"]["duration_seconds"] == 8
    assert payload["parameters"]["aspectRatio"] == "16:9"
    assert payload["parameters"]["durationSeconds"] == 8
    assert payload["instances"] == [{"prompt": "make a polished 8s video"}]


def test_previs_gemini_payload_can_include_storyboard_image_b64():
    module = _load_previs_module()

    target = module._compile_target_json(
        {"backend_provider": "gemini", "backend_model_id": "veo-3.1-generate-preview"},
        {},
        "image_to_video",
        None,
        None,
        "abc123",
    )
    payload = module._build_gemini_veo_body(target, "animate this", image_b64="abc123")

    assert payload["instances"][0]["image"] == {"bytesBase64Encoded": "abc123", "mimeType": "image/png"}


def test_previs_falls_back_when_storyboard_action_inherits_image_model():
    module = _load_previs_module()

    target = module._compile_target_json(
        {
            "model": "gpt-image-2",
            "artifact_action": "generate_video",
            "source_module_id": "storyboard.render",
            "approved_artifact_type": "image_asset",
        },
        {},
        "image_to_video",
        None,
        None,
    )

    assert target["provider"]["model"] == "dreamina-seedance-2-0-260128"


def test_previs_poll_window_allows_long_seedance_tasks():
    module = _load_previs_module()

    assert module._POLL_INTERVAL * module._MAX_POLLS >= 900


def test_previs_accepts_approval_notes_as_edit_instruction():
    module = _load_previs_module()

    target = module._compile_target_json(
        {"approval_notes": "Produce a colored version and avoid text overlays."},
        {},
        "image_to_video",
        None,
        None,
    )
    prompt = module._prompt_from_target(target, "image_to_video")

    assert target["edit_instruction"] == "Produce a colored version and avoid text overlays."
    assert "Operator revision notes: Produce a colored version and avoid text overlays." in prompt


def test_previs_uses_top_level_storyboard_output_path_for_i2v(tmp_path):
    module = _load_previs_module()
    image_path = tmp_path / "approved-storyboard.png"
    image_path.write_bytes(b"fake-image")

    resolved_path, resolved_b64 = module._resolve_image_reference({
        "type": "image_asset",
        "legacy_type": "storyboard_image",
        "output_path": str(image_path),
    })

    assert resolved_path == str(image_path)
    assert resolved_b64 is None


def test_previs_uses_top_level_storyboard_image_b64_when_path_is_stale():
    module = _load_previs_module()

    resolved_path, resolved_b64 = module._resolve_image_reference({
        "type": "image_asset",
        "legacy_type": "storyboard_image",
        "output_path": "/tmp/does-not-exist-storyboard.png",
        "image_data_b64": "abc123",
    })

    assert resolved_path is None
    assert resolved_b64 == "abc123"


def test_previs_swapped_drive_image_prefers_core_hydrated_b64_over_stale_path(tmp_path):
    module = _load_previs_module()
    original_path = tmp_path / "original-storyboard.png"
    original_path.write_bytes(b"original image")

    resolved_path, resolved_b64 = module._resolve_image_reference({
        "type": "image_asset",
        "legacy_type": "storyboard_image",
        "output_path": str(original_path),
        "_image_swapped": True,
        "_image_data_b64": "swapped-drive-b64",
    })

    assert resolved_path is None
    assert resolved_b64 == "swapped-drive-b64"


def test_previs_seedance_image_reference_uses_core_hydrated_drive_mime():
    module = _load_previs_module()

    item = module._image_reference_content({"_image_mime": "image/webp"}, None, "abc123")

    assert item["image_url"]["url"].startswith("data:image/webp;base64,")


def test_previs_builds_seedance_image_reference_from_b64():
    module = _load_previs_module()

    item = module._image_reference_content({"image_mime_type": "image/png"}, None, "abc123")

    assert item["type"] == "image_url"
    assert item["role"] == "reference_image"
    assert item["image_url"]["url"] == "data:image/png;base64,abc123"


def test_previs_allows_first_frame_image_role():
    module = _load_previs_module()

    item = module._image_reference_content({"image_role": "first_frame"}, None, "abc123")

    assert item["role"] == "first_frame"


def test_previs_preserves_image_b64_fallback_even_when_path_exists(tmp_path):
    module = _load_previs_module()
    image_path = tmp_path / "approved-storyboard.png"
    image_path.write_bytes(b"fake-image")

    brief = {"output_path": str(image_path), "image_data_b64": "durable-b64"}

    resolved_path, resolved_b64 = module._resolve_image_reference(brief)
    assert resolved_path == str(image_path)
    assert resolved_b64 is None
    assert module._resolve_image_b64_fallback(brief) == "durable-b64"


def test_resolve_ref_task_id_reads_top_level():
    module = _load_previs_module()
    assert module._resolve_ref_task_id({"task_id": "cgt-abc123"}) == "cgt-abc123"


def test_resolve_ref_task_id_reads_nested_artifact():
    module = _load_previs_module()
    brief = {"artifact": {"task_id": "cgt-nested-xyz"}}
    assert module._resolve_ref_task_id(brief) == "cgt-nested-xyz"


def test_resolve_ref_task_id_returns_none_when_absent():
    module = _load_previs_module()
    assert module._resolve_ref_task_id({}) is None


def test_refresh_video_url_returns_url_on_success(monkeypatch):
    module = _load_previs_module()

    def fake_ark(method, path, api_key, body=None, timeout=60):
        return {"status": "succeeded", "content": {"video_url": "https://example.tos/fresh.mp4"}}

    monkeypatch.setattr(module, "_ark_request", fake_ark)

    url = module._refresh_video_url("cgt-test", "fake-key")
    assert url == "https://example.tos/fresh.mp4"


def test_refresh_video_url_returns_none_when_task_not_succeeded(monkeypatch):
    module = _load_previs_module()

    def fake_ark(method, path, api_key, body=None, timeout=60):
        return {"status": "expired"}

    monkeypatch.setattr(module, "_ark_request", fake_ark)

    url = module._refresh_video_url("cgt-expired", "fake-key")
    assert url is None
