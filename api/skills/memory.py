from __future__ import annotations

from uuid import UUID
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.document import WorkspaceDocument
from models.run import Run, RunResult
from models.workspace import Audience, Brand, Product


def _limit_text(value: str, limit: int = 1800) -> str:
    value = value or ""
    return value if len(value) <= limit else value[:limit].rstrip() + "…"


async def hydrate_memory_slots(
    db: AsyncSession,
    ws,
    slots: list[str] | tuple[str, ...] | set[str],
    *,
    current_run_id: UUID | None = None,
    brand: Brand | None = None,
) -> dict[str, object]:
    """Hydrate declared skill memory slots from existing BOS resources.

    This is the first implementation of BOS memory: no new memory table yet.
    Skills declare slots; this function maps those slots to durable workspace
    resources already present in PostgreSQL.

    When an active Brand is supplied, memory is strictly scoped to that Brand.
    Do not fall back to workspace-level rows inside an active-brand chat turn;
    otherwise one Brand's products/docs can bleed into another Brand's CMO reply.
    """
    if not ws:
        return {}

    requested = set(slots)
    memory: dict[str, object] = {}
    active_brand_id = brand.id if brand else None

    def scoped_doc_query(doc_type: str):
        query = select(WorkspaceDocument).where(
            WorkspaceDocument.workspace_id == ws.id,
            WorkspaceDocument.doc_type == doc_type,
        )
        if active_brand_id:
            query = query.where(WorkspaceDocument.brand_id == active_brand_id)
        return query

    def scoped_run_query(*criteria: Any):
        query = select(Run, RunResult).join(RunResult, RunResult.run_id == Run.id, isouter=True).where(
            Run.workspace_id == ws.id,
            *criteria,
        )
        if active_brand_id:
            query = query.where(Run.brand_id == active_brand_id)
        return query

    if "brand_roster" in requested:
        brands = (await db.execute(select(Brand).where(Brand.workspace_id == ws.id).order_by(Brand.name.asc()))).scalars().all()
        memory["brand_roster"] = [
            {
                "id": str(b.id),
                "name": b.name,
            }
            for b in brands
        ]

    if "brand_profile" in requested:
        memory["brand_profile"] = {
            "name": brand.name if brand else ws.name,
            "brand": (brand.brand_json if brand else ws.brand_json) or {},
        }

    if "product_catalog" in requested:
        product_query = select(Product).where(Product.workspace_id == ws.id).order_by(Product.created_at.asc())
        if active_brand_id:
            product_query = select(Product).where(Product.brand_id == active_brand_id).order_by(Product.created_at.asc())
        products = (await db.execute(product_query)).scalars().all()
        memory["product_catalog"] = [
            {
                "name": p.name,
                "tagline": p.tagline,
                "benefits": p.benefits_json or {},
            }
            for p in products
        ]

    if "audience_profiles" in requested:
        audience_query = select(Audience).where(Audience.workspace_id == ws.id).order_by(Audience.created_at.asc())
        if active_brand_id:
            audience_query = select(Audience).where(Audience.brand_id == active_brand_id).order_by(Audience.created_at.asc())
        audiences = (await db.execute(audience_query)).scalars().all()
        memory["audience_profiles"] = [
            {
                "name": a.name,
                "segment": a.segment_json or {},
            }
            for a in audiences
        ]

    if "campaign_brand_kit" in requested:
        kit = (
            await db.execute(
                scoped_doc_query("campaign_brand_kit")
                .order_by(WorkspaceDocument.status.desc(), WorkspaceDocument.updated_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        memory["campaign_brand_kit"] = None if not kit else {
            "id": str(kit.id),
            "title": kit.title,
            "status": kit.status,
            "content_markdown": _limit_text(kit.content_markdown),
            "approved_at": kit.approved_at.isoformat() if kit.approved_at else None,
        }

    if "recent_approved_runs" in requested:
        rows = (
            await db.execute(
                scoped_run_query(Run.approval_status == "approved")
                .order_by(Run.updated_at.desc())
                .limit(5)
            )
        ).all()
        memory["recent_approved_runs"] = [
            {
                "run_id": str(run.id),
                "module_id": run.module_id,
                "content": _limit_text(result.content, 900) if result else "",
            }
            for run, result in rows
        ]

    if "recent_rejected_runs" in requested:
        rows = (
            await db.execute(
                scoped_run_query(Run.approval_status.in_(["rejected", "dismissed", "revised", "changes_requested"]))
                .order_by(Run.updated_at.desc())
                .limit(5)
            )
        ).all()
        memory["recent_rejected_runs"] = [
            {
                "run_id": str(run.id),
                "module_id": run.module_id,
                "feedback": run.feedback,
                "content": _limit_text(result.content, 900) if result else "",
            }
            for run, result in rows
        ]

    if "brand_guidelines" in requested:
        doc = (
            await db.execute(
                scoped_doc_query("brand_guideline")
                .order_by(WorkspaceDocument.updated_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        memory["brand_guidelines"] = None if not doc else {
            "id": str(doc.id),
            "title": doc.title,
            "status": doc.status,
            "content_markdown": _limit_text(doc.content_markdown, 3000),
        }

    if "marketing_reports" in requested:
        docs = (
            await db.execute(
                scoped_doc_query("marketing_report")
                .order_by(WorkspaceDocument.updated_at.desc())
                .limit(3)
            )
        ).scalars().all()
        memory["marketing_reports"] = [
            {"id": str(d.id), "title": d.title, "content_markdown": _limit_text(d.content_markdown, 1200)}
            for d in docs
        ] or None

    if "campaign_reports" in requested:
        docs = (
            await db.execute(
                scoped_doc_query("campaign_report")
                .order_by(WorkspaceDocument.updated_at.desc())
                .limit(3)
            )
        ).scalars().all()
        memory["campaign_reports"] = [
            {"id": str(d.id), "title": d.title, "content_markdown": _limit_text(d.content_markdown, 1200)}
            for d in docs
        ] or None

    if "competitor_profiles" in requested:
        docs = (
            await db.execute(
                scoped_doc_query("competitor_profile")
                .order_by(WorkspaceDocument.updated_at.desc())
                .limit(10)
            )
        ).scalars().all()
        memory["competitor_profiles"] = [
            {"id": str(d.id), "title": d.title, "content_markdown": _limit_text(d.content_markdown, 1000)}
            for d in docs
        ] or None

    if "industry_data" in requested:
        docs = (
            await db.execute(
                scoped_doc_query("industry_report")
                .order_by(WorkspaceDocument.updated_at.desc())
                .limit(2)
            )
        ).scalars().all()
        memory["industry_data"] = [
            {"id": str(d.id), "title": d.title, "content_markdown": _limit_text(d.content_markdown, 2000)}
            for d in docs
        ] or None

    if "current_run_result" in requested and current_run_id:
        row = (
            await db.execute(
                scoped_run_query(Run.id == current_run_id)
            )
        ).one_or_none()
        memory["current_run_result"] = None if not row else {
            "run_id": str(row[0].id),
            "module_id": row[0].module_id,
            "approval_status": row[0].approval_status,
            "feedback": row[0].feedback,
            "content": _limit_text(row[1].content, 1800) if row[1] else "",
        }

    return memory


def compile_memory_context(memory: dict[str, object]) -> str:
    """Render hydrated memory into compact prompt-ready context."""
    if not memory:
        return "No hydrated workspace memory."

    sections: list[str] = []
    for key, value in memory.items():
        sections.append(f"## {key}\n{value}")
    return "\n\n".join(sections)
