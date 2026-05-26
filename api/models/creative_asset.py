import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


class CreativeAsset(Base):
    """Asset library metadata. The binary lives in Google Drive; this row is the index.

    Covers AI-generated primitives (image/video plates, motion cards), client-uploaded
    brand assets (logos, product images, footage), and inline text blocks. Brand-scoped.
    See CREATIVE_SUPPLY_CHAIN.md → Object Model → Asset Library.
    """

    __tablename__ = "creative_assets"

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
    # The job that produced this primitive (not an FK — assets outlive their job).
    job_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    # Google Drive references. Null until the binary is uploaded (text blocks have none).
    drive_file_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    drive_folder_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # image_plate | video_plate | motion_card | brand_overlay | product_cutout |
    # audio_bed | voiceover | thumbnail_frame | text_block | brand_asset | template | export
    asset_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # ai_generated | client_uploaded | stock | existing_footage
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    # image | video | audio | text | template
    modality: Mapped[str] = mapped_column(String(16), nullable=False)
    # Inline content for text blocks (hooks, CTAs) — Drive is not used for short text.
    value_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # draft | approved | rejected | archived
    approval_status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    # unrestricted | campaign_only | single_use
    usage_rights: Mapped[str] = mapped_column(String(16), nullable=False, default="campaign_only")
    # Which third-party provider produced this asset (audit / regeneration).
    provider: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # The prompt BOS built and sent to the provider (audit / regeneration).
    generation_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
