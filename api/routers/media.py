from __future__ import annotations

import os
import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/media", tags=["media"])

_ALLOWED_VIDEO = re.compile(r"^(bos_shortform_[a-f0-9]{12}|bos_video_[a-z0-9]+|bos_video_edit_[a-f0-9]{12})\.mp4$")


_VIDEO_ROOTS = [
    os.environ.get("PREVIS_MOTION_RUNS_DIR") or "/var/bos/previs-motion-runs",
    "/tmp",
]


@router.get("/video/{filename}", responses={404: {"description": "Video not found or invalid filename"}})
async def serve_video(filename: str) -> FileResponse:
    """Serve a rendered video by unguessable filename. No auth — UUID name is the access control."""
    if not _ALLOWED_VIDEO.match(filename):
        raise HTTPException(status_code=404, detail="Not found")
    for root in _VIDEO_ROOTS:
        path = os.path.join(root, filename)
        if os.path.exists(path):
            return FileResponse(path, media_type="video/mp4", filename=filename)
    raise HTTPException(status_code=404, detail="Video not found — it may have been cleaned up. Re-render the artifact.")
