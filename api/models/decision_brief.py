import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


class DecisionBrief(Base):
    """Analyst recommendation artifact for objective-aware operator judgment."""

    __tablename__ = "decision_briefs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    brand_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="SET NULL"), nullable=True
    )
    objective_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("objectives.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    objective_affected: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    hypothesis_ranking: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    confidence: Mapped[str] = mapped_column(String(64), nullable=False, default="directional")
    recommended_next: Mapped[str] = mapped_column(Text, nullable=False)
    do_not_list: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    allowed_actions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    source_refs: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    full_record: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
