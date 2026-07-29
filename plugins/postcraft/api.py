from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_api_key
from config import get_settings
from db import get_db

router = APIRouter(prefix="/postcraft", tags=["postcraft"])


class PostcraftActionRequest(BaseModel):
    confirm: bool = True
    overrides: dict = Field(default_factory=dict)


class PostcraftRevisionRequest(BaseModel):
    feedback: str = ""
    references: list = Field(default_factory=list)
    overrides: dict = Field(default_factory=dict)


@router.post("/runs/{run_id}/render", dependencies=[Depends(require_api_key)])
async def render_postcraft_run(
    run_id: UUID,
    body: PostcraftActionRequest = PostcraftActionRequest(),
    db: AsyncSession = Depends(get_db),
):
    """Postcraft-owned render transition for a persisted postcraft draft."""
    if not body.confirm:
        raise HTTPException(status_code=400, detail={"error": {"code": "CONFIRM_REQUIRED", "message": "Set confirm=true to render this Postcraft artifact.", "details": None}})
    from routers.runs import execute_declared_run_action

    return await execute_declared_run_action(db, str(run_id), "render", get_settings(), body.overrides)


@router.post("/runs/{run_id}/revise", dependencies=[Depends(require_api_key)])
async def revise_postcraft_run(
    run_id: UUID,
    body: PostcraftRevisionRequest = PostcraftRevisionRequest(),
    db: AsyncSession = Depends(get_db),
):
    """Postcraft-owned revision endpoint for postcraft image/draft artifacts."""
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


@router.get("/campaign-alignment", dependencies=[Depends(require_api_key)])
async def get_postcraft_campaign_alignment(
    brand_id: UUID,
    campaign_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
):
    """Return the Campaign V2 alignment object Postcraft uses for preflight.

    Postcraft owns this adapter because the required shape is its execution
    contract. Campaign remains the source of truth; this endpoint only reads
    campaign_rows and formats the Postcraft view.
    """
    from campaign import db as campaign_db

    if campaign_id:
        rows = await campaign_db.rows_for_campaign(
            db, campaign_id, brand_id=brand_id, limit=20
        )
    else:
        rows = await campaign_db.read_rows(db, brand_id=brand_id, status="active", limit=50)
        grouped: dict[str, list] = {}
        for row in rows:
            grouped.setdefault(str(campaign_db.campaign_key(row)), []).append(row)
        if len(grouped) > 1:
            raise HTTPException(status_code=409, detail={"error": {"code": "POSTCRAFT_CAMPAIGN_AMBIGUOUS", "message": "Select a campaign before rendering with Postcraft.", "details": {"campaign_ids": list(grouped)}}})
        rows = next(iter(grouped.values())) if grouped else []

    if not rows:
        raise HTTPException(status_code=404, detail={"error": {"code": "POSTCRAFT_CAMPAIGN_NOT_FOUND", "message": "No active Campaign V2 row found for this brand.", "details": None}})

    import importlib.util
    from pathlib import Path

    hooks_path = Path(__file__).with_name("hooks.py")
    spec = importlib.util.spec_from_file_location("_bos_postcraft_hooks_for_api", hooks_path)
    if not spec or not spec.loader:
        raise HTTPException(status_code=500, detail="Postcraft alignment formatter is unavailable")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return {"campaign_alignment": mod._alignment_from_rows(campaign_db, rows)}
