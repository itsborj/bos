from attachment_context import brief_fields, build_payload
from routers.chat import ChatReference


def test_reference_context_payload_preserves_json_and_exposes_variables():
    refs = [
        ChatReference(
            kind="document",
            source="google_drive",
            title="Golden Gate Character Brief.json",
            text='{"brand_brief":{"meta":{"character_name":"Ginto"},"visual_design":{"primary_colors":{"body_gold":{"hex":"#C8A84B"}}}}}',
            drive_file_id="drive_doc_1",
            mime_type="application/json",
            extraction_status="read",
        ),
        ChatReference(
            kind="document",
            source="google_drive",
            title="Unread.pdf",
            drive_file_id="drive_doc_2",
            mime_type="application/pdf",
            extraction_status="failed",
            extraction_error="PDF extraction failed",
        ),
    ]

    payload = build_payload(refs)

    assert payload["schema"] == "bos.operator_reference_context.v1"
    assert payload["summary"] == "1/2 readable, 1 failed"
    assert payload["items"][0]["content_json_status"] == "parsed_json"
    assert payload["items"][0]["content_json"]["brand_brief"]["meta"]["character_name"] == "Ginto"
    assert any(v["path"].endswith(".body_gold.hex") and v["value"] == "#C8A84B" for v in payload["variables"])
    assert payload["items"][1]["extraction_status"] == "failed"
    assert payload["items"][1]["content_json"] is None


def test_reference_context_brief_fields_are_json_serialisable():
    refs = [ChatReference(kind="document", title="Brief", text="Use this context.", extraction_status="read")]

    fields = brief_fields(refs)

    assert fields["operator_reference_context"]["items"][0]["title"] == "Brief"
    assert fields["operator_reference_context"]["items"][0]["content_json_status"] in {"text_wrapped_json", "provided_json"}
    assert '"schema": "bos.operator_reference_context.v1"' in fields["operator_reference_context_json"]
