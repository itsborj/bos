"""Brand context resolution — merge workspace context into brief.

Extracted from routers/runs.py _resolve_brief and related helpers.
"""

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.workspace import Audience, Brand, Product, Workspace


def brand_handle_from_json(brand_json: dict | None) -> str | None:
    """Extract the primary social handle from brand JSON metadata."""
    social_handles = (brand_json or {}).get("social_handles") or {}
    return (
        social_handles.get("facebook")
        or social_handles.get("instagram")
        or social_handles.get("x")
        or social_handles.get("twitter")
    )


def brand_fields_from_row(brand: Brand | None) -> tuple[str | None, str | None]:
    """Return (name, handle) from a Brand row."""
    if not brand:
        return None, None
    return brand.name, brand_handle_from_json(brand.brand_json)


async def resolve_brief(db: AsyncSession, ws: Workspace, brief: dict) -> dict:
    """Merge workspace context into brief. Explicit brief fields always win."""
    resolved = dict(brief)

    # Brand context
    if not resolved.get("brand_name") and ws.name:
        resolved["brand_name"] = ws.name

    if ws.brand_json:
        for field in ("tone", "voice", "values", "domain", "website_url", "social_handles"):
            if not resolved.get(field) and ws.brand_json.get(field):
                resolved[field] = ws.brand_json[field]
        social_handles = ws.brand_json.get("social_handles") or {}
        if not resolved.get("brand_handle"):
            resolved["brand_handle"] = (
                social_handles.get("x")
                or social_handles.get("twitter")
                or social_handles.get("instagram")
            )
        if not resolved.get("display_url"):
            resolved["display_url"] = ws.brand_json.get("domain") or ws.brand_json.get("website_url")

    # Product context
    if not resolved.get("product_name"):
        prod_row = await db.execute(
            select(Product).where(Product.workspace_id == ws.id).limit(1)
        )
        prod = prod_row.scalar_one_or_none()
        if prod:
            resolved["product_name"] = prod.name
            if not resolved.get("tagline") and prod.tagline:
                resolved["tagline"] = prod.tagline
            if prod.benefits_json:
                benefits = prod.benefits_json.get("benefits", [])
                if benefits:
                    if not resolved.get("key_benefit"):
                        resolved["key_benefit"] = benefits[0]
                    resolved["benefits"] = benefits

    # Audience context
    if not resolved.get("audience"):
        aud_row = await db.execute(
            select(Audience).where(Audience.workspace_id == ws.id).limit(1)
        )
        aud = aud_row.scalar_one_or_none()
        if aud:
            resolved["audience"] = aud.name
            if aud.segment_json:
                if not resolved.get("demographics") and aud.segment_json.get("demographics"):
                    resolved["demographics"] = aud.segment_json["demographics"]
                if not resolved.get("pain_points") and aud.segment_json.get("pain_points"):
                    resolved["pain_points"] = aud.segment_json["pain_points"]

    return resolved


def scope_artifact_block(
    block: dict | None,
    *,
    brand_id: Any = None,
    brand_name: str | None = None,
    brand_handle: str | None = None,
) -> dict | None:
    """Attach owning Brand display metadata to artifact blocks without changing native fields."""
    if not isinstance(block, dict):
        return block
    scoped = dict(block)
    if brand_id:
        scoped.setdefault("brand_id", str(brand_id))
    if brand_name:
        scoped.setdefault("brand_name", brand_name)
    if brand_handle:
        scoped.setdefault("brand_handle", brand_handle)

    # Postcraft stores the full image bytes and a separate JPEG thumbnail. Older
    # artifacts copied the thumbnail MIME onto the full PNG payload, causing
    # browser previews (especially revised images) to fail despite successful
    # generation. Normalize the response metadata so existing artifacts recover
    # without another paid render.
    inline_image = str(scoped.get("image_data_b64") or "")
    if inline_image.startswith("iVBORw0KGgo"):
        scoped["mime_type"] = "image/png"
    elif inline_image.startswith("/9j/"):
        scoped["mime_type"] = "image/jpeg"
    return scoped
