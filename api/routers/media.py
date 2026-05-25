from __future__ import annotations

import os
import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/media", tags=["media"])

_ALLOWED_VIDEO = re.compile(r"^bos_shortform_[a-f0-9]{12}\.mp4$")


@router.get("/video/{filename}")
async def serve_video(filename: str) -> FileResponse:
    """Serve a rendered shortform video from /tmp. No auth — UUID filename is unguessable."""
    if not _ALLOWED_VIDEO.match(filename):
        raise HTTPException(status_code=404, detail="Not found")
    path = f"/tmp/{filename}"
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Video not found — it may have been cleaned up. Re-render the artifact.")
    return FileResponse(path, media_type="video/mp4", filename=filename)
