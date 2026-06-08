from types import SimpleNamespace

from artifacts import artifact_ref_from_run, artifact_status, artifact_type


def test_failed_image_asset_is_not_pending_draft_artifact() -> None:
    run = SimpleNamespace(
        run_id="run_failed_image",
        module_id="media.image.generate",
        vertical="media",
        status="partial",
        approval_status="failed",
        result=SimpleNamespace(
            content="Image generation failed: Provider returned HTTP 401",
            self_check="fail",
            platform="image_generation",
            block={
                "type": "image_asset",
                "status": "failed",
                "reason_code": "api_call_failed",
                "allowed_actions": ["retry", "dismiss"],
            },
        ),
    )

    ref = artifact_ref_from_run(run)

    assert artifact_type(run) == "setup_blocker"
    assert artifact_status(run) == "failed"
    assert ref.status == "failed"
    assert ref.type == "setup_blocker"
    assert ref.title == "Image Generation Failed"
