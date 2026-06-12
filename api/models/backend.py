import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


class ExecutionBackendOverride(Base):
    __tablename__ = "execution_backend_overrides"
    __table_args__ = (UniqueConstraint("workspace_id", "target", name="uq_backend_override_workspace_target"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    target: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    tool_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    modality: Mapped[str] = mapped_column(String(50), nullable=False, default="text")
    strict: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    fallbacks_json: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)
    routing_hints_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
