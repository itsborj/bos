import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


class CreativeBlueprint(Base):
    """The assembled source creative, expressed as a CompositionSpec JSON.

    The JSON is the edit — layer-by-layer stitch instruction referencing approved
    primitives by asset_id and brand values by slot. Render providers consume it.
    See CREATIVE_SUPPLY_CHAIN.md → JSON Composition Layer.
    """

    __tablename__ = "creative_blueprints"

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
    job_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    # References the originating creative_concept (run id) and the chosen concept key.
    concept_ref: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    spec_version: Mapped[str] = mapped_column(String(16), nullable=False, default="1.0")
    # The full CompositionSpec document — tracks, clips, asset_ids, brand slots, targets.
    composition_spec: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    drive_file_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # pending | passed | blocked  (brand compliance gate result)
    validation_status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    validation_report: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
