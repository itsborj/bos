import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


class ChatReference(Base):
    """Durable creative reference attached to CMO chat.

    Stores original upload/Drive/inline extraction metadata. In-turn patched working
    copies may be supplied by the frontend on later /chat calls without overwriting
    the original extracted row.
    """

    __tablename__ = "chat_references"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    brand_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="SET NULL"), nullable=True
    )
    conversation_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    campaign_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True
    )

    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    drive_file_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    drive_file_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    drive_web_view_link: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    thumbnail_link: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    storage_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sha256: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    text_excerpt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extraction_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    extraction_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extracted_chars: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    extraction_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    variables_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
