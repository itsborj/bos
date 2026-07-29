from services.brand_context import scope_artifact_block


def test_existing_png_artifacts_are_not_advertised_as_jpeg():
    block = scope_artifact_block({
        "type": "image_asset",
        "mime_type": "image/jpeg",
        "image_data_b64": "iVBORw0KGgoAAAANSUhEUg==",
    })
    assert block["mime_type"] == "image/png"
