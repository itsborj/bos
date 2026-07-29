"""Brand kit style injection — attach approved Campaign Brand Kit / Brand Guidelines.

Extracted from routers/runs.py _inject_campaign_brand_kit_style, _extract_visual_constraints,
_inject_brand_asset_spec, and _brand_spec_from_asset_metadata.
"""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.document import WorkspaceDocument
from models.workspace import Brand, Workspace

logger = logging.getLogger("bos.services.brand_kit")


def _brand_spec_from_asset_metadata(meta: dict | None) -> dict:
    """Map onboarding/Drive asset metadata into Postcraft/Storyboard brand_spec."""
    if not isinstance(meta, dict):
        return {}
    spec: dict[str, Any] = {}
    imprint_folder = meta.get("imprint_asset_folder") if isinstance(meta.get("imprint_asset_folder"), dict) else {}
    folders = meta.get("imprint_asset_folders") if isinstance(meta.get("imprint_asset_folders"), dict) else {}
    brand_assets_folder = folders.get("brand_assets") if isinstance(folders.get("brand_assets"), dict) else {}
    root_id = meta.get("drive_root_folder_id") or imprint_folder.get("id") or brand_assets_folder.get("id")
    root_name = meta.get("drive_root_name") or imprint_folder.get("name") or brand_assets_folder.get("name")
    if root_id:
        spec["drive_root_folder_id"] = str(root_id)
    if root_name:
        spec["drive_root_name"] = str(root_name)

    validation = meta.get("imprint_asset_validation") if isinstance(meta.get("imprint_asset_validation"), dict) else {}
    logo_files = validation.get("logo_files") if isinstance(validation.get("logo_files"), list) else []
    first_logo = next((f for f in logo_files if isinstance(f, dict) and f.get("id")), None)
    logo_id = meta.get("brand_mark_file_id") or (first_logo or {}).get("id")
    logo_name = meta.get("brand_mark_file_name") or (first_logo or {}).get("name")
    logo_mime = meta.get("brand_mark_mime_type") or (first_logo or {}).get("mimeType")
    if logo_id:
        spec["logo_drive_file_id"] = str(logo_id)
    if logo_name:
        spec["logo_file_name"] = str(logo_name)
    if logo_mime:
        spec["logo_mime_type"] = str(logo_mime)

    # Supply a small, curated evidence set to creative generators. These are
    # identity/product/style references—not mandatory layouts. Prefer named
    # character/product assets, then creative references, then other visuals.
    reference_groups = (
        ("mascot_files", "brand_character"),
        ("brand_character_files", "brand_character"),
        ("product_files", "immutable_or_product_reference"),
        ("hero_imagery_files", "hero_reference"),
        ("creative_reference_files", "aesthetic_reference"),
        ("visual_asset_files", "supporting_visual"),
    )
    visual_assets: list[dict[str, Any]] = []
    seen_ids = {str(logo_id or "")}
    for key, role in reference_groups:
        files = validation.get(key) if isinstance(validation.get(key), list) else []
        for item in files:
            if not isinstance(item, dict):
                continue
            file_id = str(item.get("id") or "").strip()
            if not file_id or file_id in seen_ids:
                continue
            seen_ids.add(file_id)
            visual_assets.append({
                "drive_file_id": file_id,
                "title": str(item.get("name") or role.replace("_", " ")),
                "mime_type": str(item.get("mimeType") or "image/png"),
                "placement_role": role,
                "panel_label": f"BRAND REFERENCE — {role.replace('_', ' ')}; preserve factual identity when relevant, otherwise use as aesthetic guidance",
            })
            if len(visual_assets) >= 5:
                break
        if len(visual_assets) >= 5:
            break
    if visual_assets:
        spec["brand_visual_assets"] = visual_assets
    return spec


def _merge_brand_row_into_brand_kit(brand_kit: dict, brand: Brand | None) -> dict:
    """Build the lightweight brand_kit scaffold Postcraft/Storyboard expect."""
    merged = dict(brand_kit or {})
    if not brand:
        return merged
    bj = brand.brand_json or {}
    merged.setdefault("brand_id", str(brand.id))
    merged.setdefault("brand_name", brand.name)
    merged.setdefault("name", brand.name)
    if bj.get("tone") or bj.get("brand_tone"):
        merged.setdefault("tone", bj.get("tone") or bj.get("brand_tone"))
    if bj.get("voice"):
        merged.setdefault("voice", bj.get("voice"))
    if bj.get("values"):
        merged.setdefault("values", bj.get("values") or [])
    if bj.get("color_palette") or bj.get("colors"):
        merged.setdefault("color_palette", bj.get("color_palette") or bj.get("colors") or {})
    if bj.get("visual_language") or bj.get("visual_tone") or bj.get("tone"):
        visual = bj.get("visual_language") or bj.get("visual_tone") or bj.get("tone") or []
        merged.setdefault("visual_tone", visual)
        merged.setdefault("visual_language", visual)
    if bj.get("typography"):
        merged.setdefault("typography", bj.get("typography") or {})
    if bj.get("mandatory_treatments"):
        merged.setdefault("mandatory_treatments", bj.get("mandatory_treatments") or [])
    if bj.get("negative_prompts"):
        merged.setdefault("negative_prompts", bj.get("negative_prompts") or [])
    return merged


async def inject_brand_asset_spec(
    brief: dict,
    ws: Workspace,
    brand_id: UUID | None,
    db: AsyncSession,
) -> dict:
    """Inject official logo/root metadata and lightweight brand_kit for creative modules."""
    if not brand_id:
        return brief
    brand_kit = brief.get("brand_kit") if isinstance(brief.get("brand_kit"), dict) else {}
    brand = (await db.execute(
        select(Brand).where(Brand.id == brand_id, Brand.workspace_id == ws.id)
    )).scalar_one_or_none()
    updated_kit = _merge_brand_row_into_brand_kit(brand_kit, brand)

    existing = {}
    if isinstance(updated_kit.get("brand_spec"), dict):
        existing.update(updated_kit.get("brand_spec") or {})
    if isinstance(brief.get("brand_spec"), dict):
        existing.update(brief.get("brand_spec") or {})
    if existing.get("logo_drive_file_id") and existing.get("drive_root_folder_id"):
        updated = dict(brief)
        updated["brand_spec"] = dict(existing)
        updated_kit["brand_spec"] = dict(existing)
        updated["brand_kit"] = updated_kit
        return updated

    brand_spec = dict(existing)
    try:
        from models.social import SocialConnection
        conn = (await db.execute(
            select(SocialConnection).where(
                SocialConnection.brand_id == brand_id,
                SocialConnection.platform == "google_drive",
                SocialConnection.status == "connected",
            ).order_by(SocialConnection.created_at.desc()).limit(1)
        )).scalar_one_or_none()
        if conn:
            for k, v in _brand_spec_from_asset_metadata(conn.token_meta_json or {}).items():
                brand_spec.setdefault(k, v)
    except Exception:
        logger.debug("Could not resolve brand_spec from Drive SocialConnection for brand %s", brand_id, exc_info=True)

    if not brand_spec.get("logo_drive_file_id") or not brand_spec.get("drive_root_folder_id"):
        try:
            kit_doc = (await db.execute(
                select(WorkspaceDocument)
                .where(
                    WorkspaceDocument.workspace_id == ws.id,
                    WorkspaceDocument.brand_id == brand_id,
                    WorkspaceDocument.doc_type == "campaign_brand_kit",
                )
                .order_by(WorkspaceDocument.approved_at.desc().nullslast(), WorkspaceDocument.updated_at.desc())
                .limit(1)
            )).scalar_one_or_none()
            for k, v in _brand_spec_from_asset_metadata(kit_doc.metadata_json if kit_doc else {}).items():
                brand_spec.setdefault(k, v)
        except Exception:
            logger.debug("Could not resolve brand_spec from campaign_brand_kit for brand %s", brand_id, exc_info=True)

    updated = dict(brief)
    if brand_spec:
        updated["brand_spec"] = brand_spec
        nested = dict(updated_kit.get("brand_spec") or {}) if isinstance(updated_kit.get("brand_spec"), dict) else {}
        nested.update({k: v for k, v in brand_spec.items() if v not in (None, "", [], {})})
        updated_kit["brand_spec"] = nested
    if updated_kit:
        updated["brand_kit"] = updated_kit
    return updated


def extract_visual_constraints(markdown: str) -> str:
    """Extract compact brand constraints for media prompts.

    Prefer actual color / voice / typography / CTA rules over introductory
    document titles and overview tables.
    """
    keep: list[str] = []
    active_section = ""
    markdown_lower = markdown.lower()
    legacy_campaign_kit = (
        "campaign brand kit overview" in markdown_lower or "— campaign brand kit" in markdown_lower
    ) and "brand creative brief" not in markdown_lower
    section_keywords = (
        "color", "colour", "palette", "visual", "imagery", "photography",
        "style", "tone", "voice", "logo", "typography", "font", "cta",
        "component", "motion", "avoid", "forbidden", "banned", "do / don't",
    )
    line_keywords = section_keywords + ("#", "manrope", "inter", "hex", "contrast")
    skip_phrases = (
        "campaign brand kit overview",
        "brand name",
        "approval owner",
        "primary product/service",
        "target audience",
        "this campaign brand kit",
        "long-lived onboarding artifact",
        "category | description",
    )

    def _clean(raw: str) -> str:
        line = raw.strip()
        if not line:
            return ""
        if not line.replace("|", "").replace(":", "").replace("-", "").strip():
            return ""
        if line.startswith("|") and line.endswith("|"):
            cells = [c.strip(" `") for c in line.strip("|").split("|")]
            cells = [c for c in cells if c and c.replace(":", "").replace("-", "").strip()]
            line = ": ".join(cells)
        line = line.strip(" -#\t")
        return " ".join(line.split())

    for raw in markdown.splitlines():
        stripped = raw.strip()
        if stripped.startswith("#"):
            heading = _clean(stripped).lower()
            active_section = heading if any(k in heading for k in section_keywords) else ""
            continue

        line = _clean(raw)
        if not line:
            continue
        lowered = line.lower()
        if any(skip in lowered for skip in skip_phrases):
            continue
        if legacy_campaign_kit and any(fragment in lowered for fragment in (
            "visual system rules", "component-", "cta language", "primary execution cta",
        )):
            # Legacy deterministic kits contained generic SaaS/component prose
            # and, in some records, cross-brand visual terminology. Keep their
            # supplied palette/voice/typography but do not send those generated
            # prescriptions into media models.
            continue
        if active_section or any(k in lowered for k in line_keywords):
            keep.append(line)
        if len("; ".join(keep)) > 1500:
            break

    constraints = "; ".join(dict.fromkeys(keep))[:1800]
    if constraints:
        constraints += (
            "; Never generate fake text, random UI labels, or baked-in logos inside AI media. "
            "Leave clear safe space for approved captions, CTA, typography, and the official logo."
        )
    return constraints[:2200]


async def inject_campaign_brand_kit_style(
    brief: dict,
    ws: Workspace,
    brand_id: UUID | None,
    db: AsyncSession,
) -> dict:
    """Attach approved Campaign Brand Kit / Brand Guidelines style constraints."""
    if brief.get("brand_visual_constraints"):
        return brief

    existing_sources = [
        str(brief.get("campaign_brand_kit_excerpt") or "").strip(),
        str(brief.get("brand_guidelines_excerpt") or "").strip(),
    ]
    existing_markdown = "\n\n".join(s for s in existing_sources if s)
    if existing_markdown:
        constraints = extract_visual_constraints(existing_markdown)
        if constraints:
            return {**brief, "brand_visual_constraints": constraints}

    filters = [
        WorkspaceDocument.workspace_id == ws.id,
        WorkspaceDocument.doc_type.in_(["campaign_brand_kit", "brand_guideline"]),
        WorkspaceDocument.status == "approved",
    ]
    if brand_id:
        filters.append(WorkspaceDocument.brand_id == brand_id)
    else:
        filters.append(WorkspaceDocument.brand_id.is_(None))

    docs = (
        await db.execute(
            select(WorkspaceDocument)
            .where(*filters)
            .order_by(
                WorkspaceDocument.doc_type.asc(),
                WorkspaceDocument.approved_at.desc().nullslast(),
                WorkspaceDocument.updated_at.desc(),
            )
        )
    ).scalars().all()
    if not docs:
        return brief

    latest_by_type: dict[str, WorkspaceDocument] = {}
    for doc in docs:
        latest_by_type.setdefault(doc.doc_type, doc)

    kit_excerpt = (
        (latest_by_type.get("campaign_brand_kit").content_markdown or "")[:5000]
        if latest_by_type.get("campaign_brand_kit")
        else ""
    )
    guideline_excerpt = (
        (latest_by_type.get("brand_guideline").content_markdown or "")[:5000]
        if latest_by_type.get("brand_guideline")
        else ""
    )
    combined = "\n\n".join(s for s in (kit_excerpt, guideline_excerpt) if s)
    if not combined:
        return brief
    return {
        **brief,
        "campaign_brand_kit_excerpt": brief.get("campaign_brand_kit_excerpt") or kit_excerpt,
        "brand_guidelines_excerpt": brief.get("brand_guidelines_excerpt") or guideline_excerpt,
        "brand_visual_constraints": extract_visual_constraints(combined),
    }
