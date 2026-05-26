import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


class CreativeJob(Base):
    """Async lifecycle for a creative-factory production run.

    BOS does not generate or render. This row tracks a commission-and-return job:
    the operator requests a creative pack, the job is queued, a plugin-local worker
    builds requests for third-party providers, captures results, and surfaces a
    Creative Bundle when complete. See CREATIVE_SUPPLY_CHAIN.md.
    """

    __tablename__ = "creative_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    brand_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="SET NULL"), nullable=True
    )
    campaign_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True
    )
    # The approved creative_concept run that triggered this job (not an FK — runs are
    # broadly referenced by id across the system).
    concept_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    job_type: Mapped[str] = mapped_column(String(64), nullable=False, default="creative_pack")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    # Parsed from the Creative Brief — primitive counts, specs, template recommendations.
    primitive_requirements: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # Per-stage progress for Stream surfacing without leaking provider detail.
    progress_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # The resulting creative_bundle artifact run, set on completion.
    bundle_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
