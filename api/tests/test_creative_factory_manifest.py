from capability_manifest import build_dispatchable_manifest


def test_creative_factory_media_capabilities_are_dispatchable():
    module_ids = {entry.module_id for entry in build_dispatchable_manifest()}

    assert "media.image.generate" in module_ids
    assert "media.video.generate" in module_ids
    assert "creative.post.image" in module_ids
