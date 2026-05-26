"""Stream builder — orchestrates all generators and persists new blocks.

Idempotent: blocks with the same (workspace_id, source_key) are skipped
if they already exist and haven't been dismissed.
"""

import logging
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.stream import StreamUpdate
from models.workspace import Workspace
from stream.generators import alert, decision_brief, narrative, outcome, performance, recommendation

logger = logging.getLogger("bos.stream.builder")


async def build(
    db: AsyncSession,
    workspace: Workspace,
    openrouter_key: str = "",
) -> int:
    """Run all generators and persist any new blocks. Returns count of new blocks created."""
    # Dedup against ALL source_keys ever seen for this workspace (including dismissed).
    # Dismissed daily blocks should not re-surface the same day; they re-appear the next
    # day because date-keyed source_keys (e.g. "performance:2026-05-04") change daily.
    # Per-run alert keys (e.g. "alert:run:{uuid}") are permanently deduplicated once seen.
    existing_keys_rows = await db.execute(
        select(StreamUpdate.source_key).where(
            StreamUpdate.workspace_id == workspace.id,
            StreamUpdate.source_key.is_not(None),
        )
    )
    existing_keys: set[str] = {row[0] for row in existing_keys_rows.all()}

    # Run all generators
    candidates: list[dict] = []
    candidates.extend(await alert.generate(db, workspace))
    candidates.extend(await performance.generate(db, workspace))
    candidates.extend(await outcome.generate(db, workspace))
    candidates.extend(await decision_brief.generate(db, workspace))
    candidates.extend(await narrative.generate(db, workspace, openrouter_key))
    candidates.extend(await recommendation.generate(db, workspace))

    # Persist new blocks only
    created = 0
    for block in candidates:
        key = block.get("source_key")
        if key and key in existing_keys:
            continue

        campaign_id: Optional[uuid.UUID] = block.get("campaign_id")

        update = StreamUpdate(
            workspace_id=workspace.id,
            campaign_id=campaign_id,
            type=block["type"],
            layout_hint=block["layout_hint"],
            interaction=block["interaction"],
            priority=block["priority"],
            data_json=block["data_json"],
            source_key=key,
        )
        db.add(update)
        created += 1
        if key:
            existing_keys.add(key)

    if created:
        await db.commit()
        logger.info("Stream: created %d new blocks for workspace %s", created, workspace.id)

    return created
