import uuid

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


class Capability(Base):
    __tablename__ = "capabilities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    modality: Mapped[str] = mapped_column(String(50), nullable=False)
    budget_ceiling: Mapped[float] = mapped_column(Float, nullable=False)
    latency_target_ms: Mapped[int] = mapped_column(Integer, nullable=False)


class ModelOption(Base):
    __tablename__ = "model_options"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    capability_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("capabilities.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model_id: Mapped[str] = mapped_column(String(255), nullable=False)
    input_cost_per_token: Mapped[float] = mapped_column(Float, nullable=False)
    output_cost_per_token: Mapped[float] = mapped_column(Float, nullable=False)
    quality_tier: Mapped[str] = mapped_column(String(50), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    availability_score: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    supports_json: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="healthy")
