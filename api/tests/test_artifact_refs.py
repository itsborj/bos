from types import SimpleNamespace

from artifacts import artifact_ref_from_run


def test_artifact_ref_excludes_native_content():
    run = SimpleNamespace(
        run_id="run_123",
        module_id="marketing.channel.gmail.outreach.draft",
        vertical="marketing",
        status="success",
        approval_status="pending",
        result=SimpleNamespace(
            content="Native email body should remain in Workspace artifact detail.",
            self_check="pass",
            platform="email",
        ),
    )

    ref = artifact_ref_from_run(run)

    assert ref.artifact_id == "run_123"
    assert ref.title == "Email Draft"
    assert ref.type == "draft_artifact"
    assert ref.status == "pending_review"
    assert ref.renderer == "email_preview"
    assert ref.workspace_url == "/workspace/artifacts/run_123"
    assert "Native email body" not in ref.model_dump_json()
