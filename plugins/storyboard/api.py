from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_api_key
from config import get_settings
from db import get_db

router = APIRouter(prefix="/storyboard", tags=["storyboard"])


class StoryboardActionRequest(BaseModel):
    confirm: bool = True
    overrides: dict = Field(default_factory=dict)


class StoryboardRevisionRequest(BaseModel):
    feedback: str = ""
    references: list = Field(default_factory=list)
    overrides: dict = Field(default_factory=dict)


@router.post("/runs/{run_id}/render", dependencies=[Depends(require_api_key)])
async def render_storyboard_run(
    run_id: UUID,
    body: StoryboardActionRequest = StoryboardActionRequest(),
    db: AsyncSession = Depends(get_db),
):
    """Storyboard-owned text/JSON → image storyboard render transition."""
    if not body.confirm:
        raise HTTPException(status_code=400, detail={"error": {"code": "CONFIRM_REQUIRED", "message": "Set confirm=true to render this Storyboard artifact.", "details": None}})
    from routers.runs import execute_declared_run_action

    return await execute_declared_run_action(db, str(run_id), "render", get_settings(), body.overrides)


@router.post("/runs/{run_id}/revise", dependencies=[Depends(require_api_key)])
async def revise_storyboard_run(
    run_id: UUID,
    body: StoryboardRevisionRequest = StoryboardRevisionRequest(),
    db: AsyncSession = Depends(get_db),
):
    """Storyboard-owned revision endpoint for storyboard draft/image artifacts."""
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
