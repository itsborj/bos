from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


class CouncilSession(Base):
    __tablename__ = "council_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    brand_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)

    brief: Mapped[str] = mapped_column(Text, nullable=False)
    # status: round_1_active | awaiting_c6 | round_N_active | finalizing | settled
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="round_1_active")
    current_round: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    rounds_completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    safety_ceiling: Mapped[int] = mapped_column(Integer, nullable=False, default=10)

    # rounds[n] = list of {seat_id, display_name, round, content, timestamp}
    rounds: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # [{round_boundary, content, timestamp}]
    c6_injections: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    pending_c6_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)

    settlement: Mapped[str | None] = mapped_column(Text, nullable=True)
    marching_orders: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    parked_decisions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
