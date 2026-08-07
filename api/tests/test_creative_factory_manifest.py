import pytest

from capability_manifest import build_dispatchable_manifest


@pytest.mark.skip(reason="media.video.generate module was never implemented/committed (no module.py under api/plugins/media-video/)")
def test_media_video_is_dispatchable():
    module_ids = {entry.module_id for entry in build_dispatchable_manifest()}
    assert "media.video.generate" in module_ids


def test_postcraft_is_dispatchable():
    module_ids = {entry.module_id for entry in build_dispatchable_manifest()}
    assert "postcraft.create" in module_ids
