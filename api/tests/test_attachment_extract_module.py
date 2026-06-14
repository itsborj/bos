import json

from capabilities.workspace.attachment_extract.module import WorkspaceAttachmentExtractModule


def test_attachment_extract_module_outputs_context_json():
    module = WorkspaceAttachmentExtractModule()
    attempt, result = module.execute_tool_result({
        "references": [
            {
                "kind": "document",
                "source": "inline",
                "title": "Brief",
                "text": '{"creative":{"audience":"widower","tone":"calm"}}',
                "extraction_status": "read",
            }
        ]
    })

    payload = json.loads(result["content"])

    assert attempt["status"] == "succeeded"
    assert payload["schema"] == "bos.operator_reference_context.v1"
    assert payload["items"][0]["content_json"]["creative"]["audience"] == "widower"
    assert any(v["path"].endswith(".creative.audience") for v in payload["variables"])
    assert result["block"]["context"] == payload
    assert module.self_check(result["content"], {}) == ("pass", [])
