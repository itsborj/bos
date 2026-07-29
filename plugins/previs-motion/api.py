from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_api_key
from config import get_settings
from db import get_db

router = APIRouter(prefix="/previs-motion", tags=["previs-motion"])


class PrevisActionRequest(BaseModel):
    confirm: bool = True
    overrides: dict = Field(default_factory=dict)


class PrevisRevisionRequest(BaseModel):
    feedback: str = ""
    references: list = Field(default_factory=list)
    overrides: dict = Field(default_factory=dict)


@router.post("/runs/{run_id}/generate-video", dependencies=[Depends(require_api_key)])
async def generate_previs_video_from_storyboard(
    run_id: UUID,
    body: PrevisActionRequest = PrevisActionRequest(),
    db: AsyncSession = Depends(get_db),
):
    """Previs Motion-owned storyboard/image → video transition."""
    if not body.confirm:
        raise HTTPException(status_code=400, detail={"error": {"code": "CONFIRM_REQUIRED", "message": "Set confirm=true to generate video with Previs Motion.", "details": None}})
    from routers.runs import execute_declared_run_action

    return await execute_declared_run_action(db, str(run_id), "generate_video", get_settings(), body.overrides)


@router.post("/runs/{run_id}/regenerate", dependencies=[Depends(require_api_key)])
async def regenerate_previs_video(
    run_id: UUID,
    body: PrevisActionRequest = PrevisActionRequest(),
    db: AsyncSession = Depends(get_db),
):
    """Previs Motion-owned video regeneration endpoint."""
    if not body.confirm:
        raise HTTPException(status_code=400, detail={"error": {"code": "CONFIRM_REQUIRED", "message": "Set confirm=true to regenerate this Previs Motion artifact.", "details": None}})
    from routers.runs import execute_declared_run_action

    return await execute_declared_run_action(db, str(run_id), "regenerate", get_settings(), body.overrides)


@router.post("/runs/{run_id}/revise", dependencies=[Depends(require_api_key)])
async def revise_previs_video(
    run_id: UUID,
    body: PrevisRevisionRequest = PrevisRevisionRequest(),
    db: AsyncSession = Depends(get_db),
):
    """Previs Motion-owned video edit/revision endpoint."""
    from routers.runs import execute_declared_run_action

    overrides = dict(body.overrides or {})
    feedback = (body.feedback or "").strip()
    if feedback:
        overrides.setdefault("edit_instruction", feedback)
        overrides.setdefault("revision_prompt", feedback)
        overrides.setdefault("revision_feedback", feedback)
    if body.references:
        overrides.setdefault("operator_references", body.references)
    return await execute_declared_run_action(db, str(run_id), "revise", get_settings(), overrides)
