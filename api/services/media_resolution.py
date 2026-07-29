"""Drive attachment and video resolution.

Extracted from routers/runs.py _resolve_drive_attachment and _resolve_drive_video.
"""

import base64
import logging
import os
import tempfile
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("bos.services.media_resolution")


async def resolve_drive_attachment(
    brief: dict,
    brand_id: UUID | None,
    db: AsyncSession,
    settings,
    _is_plugin_platform_active_fn=None,
) -> dict:
    """If brief contains drive_file_id, download the file from Google Drive and
    inject it as _image_data_b64 / _image_mime."""
    drive_file_id = str(brief.get("drive_file_id") or "").strip()
    if not drive_file_id:
        return brief

    image_swapped = bool(brief.get("_image_swapped"))
    if image_swapped:
        # A caller-selected Drive image must not fall back to embedded bytes from
        # the original artifact. If Drive resolution fails, publish should fail
        # or continue without an image — never silently use the old image.
        brief = {**brief}
        brief.pop("_image_data_b64", None)
        brief.pop("image_data_b64", None)
        brief.pop("image_url", None)
    existing_b64 = brief.get("_image_data_b64") or brief.get("image_data_b64")
    if existing_b64 and not image_swapped:
        mime = str(
            brief.get("_image_mime") or brief.get("mime_type") or brief.get("drive_file_mime") or "image/png"
        ).strip()
        return {**brief, "_image_data_b64": existing_b64, "_image_mime": mime}

    try:
        if _is_plugin_platform_active_fn is None:
            return brief
        if not await _is_plugin_platform_active_fn("google_drive", brand_id, db):
            return brief
        from routers.social import get_page_token
        brand_id_str = str(brand_id) if brand_id else None
        if not brand_id_str:
            return brief
        token, _ = await get_page_token(db, brand_id_str, "google_drive", settings)
        if not token:
            logger.warning("Drive attachment present but no google_drive token for brand %s", brand_id_str)
            return brief
        DriveClient = _load_google_drive_client_module("_bos_drive_client").DriveClient
        with DriveClient(token) as drive:
            image_data = drive.download_file(drive_file_id)
        mime = str(brief.get("drive_file_mime") or "image/jpeg").strip()
        return {
            **brief,
            "_image_data_b64": base64.b64encode(image_data).decode(),
            "_image_mime": mime,
        }
    except Exception:
        logger.exception("Drive attachment resolution failed for file %s — continuing without image", drive_file_id)
        return brief


async def resolve_drive_video(
    brief: dict,
    brand_id: UUID | None,
    db: AsyncSession,
    settings,
    _is_plugin_platform_active_fn=None,
) -> dict:
    """If video_path is absent, the file has been cleaned up, or a swap was requested,
    download the video from Google Drive into a fresh temp file."""
    video_path = str(brief.get("video_path") or "").strip()
    drive_file_id = str(brief.get("drive_file_id") or "").strip()
    video_swapped = bool(brief.get("_video_swapped"))

    if not drive_file_id:
        return brief
    if not video_swapped and video_path and os.path.exists(video_path):
        return brief

    try:
        if _is_plugin_platform_active_fn is None:
            return brief
        if not await _is_plugin_platform_active_fn("google_drive", brand_id, db):
            return brief
        from routers.social import get_page_token
        brand_id_str = str(brand_id) if brand_id else None
        if not brand_id_str:
            return brief
        token, _ = await get_page_token(db, brand_id_str, "google_drive", settings)
        if not token:
            return brief

        DriveClient = _load_google_drive_client_module("_bos_drive_client_video").DriveClient
        with DriveClient(token) as drive:
            video_data = drive.download_file(drive_file_id)

        fd, new_path = tempfile.mkstemp(prefix="bos_video_", suffix=".mp4")
        os.close(fd)
        with open(new_path, "wb") as fh:
            fh.write(video_data)
        logger.info("Drive video re-downloaded for file %s → %s", drive_file_id, new_path)
        return {**brief, "video_path": new_path}
    except Exception:
        logger.exception("Drive video re-download failed for file %s — continuing without re-download", drive_file_id)
        return brief


def _load_google_drive_client_module(module_name: str):
    import importlib.util
    import pathlib

    candidates = [pathlib.Path("/external_plugins/google-drive/drive_client.py")]
    try:
        from plugin_loader import get_loaded_plugins
        state = get_loaded_plugins().get("google.drive")
        if state:
            candidates.insert(0, state.root_path / "drive_client.py")
    except Exception:
        pass
    candidates.append(pathlib.Path(__file__).parent.parent / "plugins" / "google-drive" / "drive_client.py")

    for path in candidates:
        if path.exists():
            spec = importlib.util.spec_from_file_location(module_name, path)
            module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
            spec.loader.exec_module(module)  # type: ignore[union-attr]
            return module
    raise FileNotFoundError("google-drive/drive_client.py not found")
