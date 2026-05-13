import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


class IntentContract(Base):
    __tablename__ = "intent_contracts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contract_type: Mapped[str] = mapped_column(String(100), nullable=False, default="campaign")
    version: Mapped[str] = mapped_column(String(50), nullable=False, default="1.0.0")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evaluator: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    criteria_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    scoring_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    on_pass: Mapped[str] = mapped_column(String(50), nullable=False, default="advance")
    on_fail: Mapped[str] = mapped_column(String(50), nullable=False, default="retry")
    on_escalate: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CampaignIntent(Base):
    __tablename__ = "campaign_intents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    intent_contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intent_contracts.id", ondelete="CASCADE"), nullable=False
    )
    overrides_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ModuleCriterion(Base):
    __tablename__ = "module_criteria"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    module_id: Mapped[str] = mapped_column(String(255), nullable=False)
    criterion_id: Mapped[str] = mapped_column(String(100), nullable=False)
    field: Mapped[str] = mapped_column(String(255), nullable=False)
    rule: Mapped[str] = mapped_column(String(100), nullable=False)
    threshold_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False, default="soft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
