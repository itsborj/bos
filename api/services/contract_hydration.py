"""Contract hydration — resolve SKILL.md-declared upstream contracts.

Extracted from routers/runs.py _hydrate_module_upstream_context and related helpers.
"""

import logging
import re
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from errors import BosError
from models.document import WorkspaceDocument
from models.run import Run, RunResult, RunTrace
from models.workspace import Workspace
from skills.loader import get_skill, list_skill_manifests

logger = logging.getLogger("bos.services.contract_hydration")


def contract_brief_key(contract: str) -> str:
    """Map contract ids like buyer_map.v1 to brief keys like buyer_map."""
    raw = (contract or "").strip()
    if not raw:
        return ""
    return re.sub(r"\.v\d+$", "", raw).replace(".", "_").replace("-", "_")


def has_contract_value(brief: dict, contract: str) -> bool:
    key = contract_brief_key(contract)
    candidates = {contract, contract.replace(".", "_"), key}
    return any(bool(brief.get(candidate)) for candidate in candidates if candidate)


def module_skill(module_id: str):
    return next((skill for skill in list_skill_manifests() if skill.module_id == module_id), None)


def producer_module_for_contract(contract: str) -> str | None:
    """Find the module whose SKILL.md declares it produces this contract."""
    for skill in list_skill_manifests():
        if skill.module_id and contract in skill.outputs:
            return skill.module_id
    return None


def dependency_contract_text(skill_id: str, *, limit: int = 12000) -> str:
    skill = get_skill(skill_id)
    if not skill:
        return ""
    body = skill.body.strip()
    if len(body) > limit:
        body = body[:limit].rstrip() + "…"
    outputs = ", ".join(skill.outputs) or "none"
    required = ", ".join(skill.required_upstream) or "none"
    return (
        f"## {skill.id} — {skill.name}\n"
        f"Outputs: {outputs}\n"
        f"Required upstream: {required}\n\n"
        f"{body}"
    )


async def find_upstream_contract_content(
    db: AsyncSession,
    ws: Workspace,
    contract: str,
    brand_id: UUID | None,
) -> str | None:
    """Load a previously persisted upstream artifact by contract/doc/block type."""
    key = contract_brief_key(contract)
    if not key:
        return None
    aliases = {contract, contract.replace(".", "_"), key}

    doc_query = select(WorkspaceDocument).where(
        WorkspaceDocument.workspace_id == ws.id,
        WorkspaceDocument.doc_type.in_(aliases),
    )
    if brand_id:
        doc_query = doc_query.where(WorkspaceDocument.brand_id == brand_id)
    else:
        doc_query = doc_query.where(WorkspaceDocument.brand_id.is_(None))
    doc = (
        await db.execute(doc_query.order_by(WorkspaceDocument.updated_at.desc()).limit(1))
    ).scalar_one_or_none()
    if doc and doc.content_markdown:
        return doc.content_markdown[:12000]

    run_query = (
        select(Run, RunResult, RunTrace)
        .join(RunResult, RunResult.run_id == Run.id, isouter=True)
        .join(RunTrace, RunTrace.run_id == Run.id, isouter=True)
        .where(Run.workspace_id == ws.id)
        .where(Run.status.in_(["success", "partial"]))
        .order_by(Run.updated_at.desc())
        .limit(40)
    )
    if brand_id:
        run_query = run_query.where(Run.brand_id == brand_id)
    else:
        run_query = run_query.where(Run.brand_id.is_(None))

    rows = (await db.execute(run_query)).all()
    for run, result, trace in rows:
        block = ((trace.lineage_json or {}).get("block") if trace and trace.lineage_json else None) or {}
        block_markers = {
            str(block.get("type") or ""),
            str(block.get("artifact_type") or ""),
            str(block.get("output_contract") or ""),
            str(block.get("contract") or ""),
        }
        if aliases.intersection(marker for marker in block_markers if marker):
            content = result.content if result else ""
            return content[:12000] if content else str(block)[:12000]
    return None


async def hydrate_module_upstream_context(
    db: AsyncSession,
    ws: Workspace,
    module_id: str,
    brief: dict,
    brand_id: UUID | None,
    settings=None,
    policy: str | None = None,
    campaign_id: UUID | None = None,
    upstream_stack: tuple[str, ...] | None = None,
    _execute_module_fn=None,
) -> dict:
    """Inject SKILL.md-declared upstream contracts into a module brief.

    `required_upstream` is an execution contract, not prompt decoration. The host
    first loads an existing contract artifact. If none exists and a producer
    module is installed, it runs that producer as a supporting substrate before
    the requested module runs.
    """
    skill = module_skill(module_id)
    if not skill or not skill.required_upstream:
        return brief

    enriched = dict(brief)
    missing: list[str] = []
    loaded: list[str] = []
    generated: list[str] = []
    stack = tuple(upstream_stack or ()) + (module_id,)
    for contract in skill.required_upstream:
        if has_contract_value(enriched, contract):
            loaded.append(contract)
            continue
        content = await find_upstream_contract_content(db, ws, contract, brand_id)
        if content:
            enriched[contract_brief_key(contract)] = content
            loaded.append(contract)
            continue

        producer_module_id = producer_module_for_contract(contract)
        if producer_module_id and settings is not None and producer_module_id not in stack:
            logger.info(
                "Hydrating upstream contract %s via %s for %s",
                contract, producer_module_id, module_id,
            )
            if _execute_module_fn is None:
                raise RuntimeError("_execute_module_fn required for recursive contract hydration")
            upstream_result = await _execute_module_fn(
                db,
                ws,
                producer_module_id,
                enriched,
                settings,
                policy=policy,
                campaign_id=campaign_id,
                brand_id=brand_id,
                _upstream_stack=stack,
                _supporting=True,
            )
            if upstream_result.status != "success" or not upstream_result.result:
                raise BosError(
                    424,
                    "UPSTREAM_CONTRACT_FAILED",
                    f"Required upstream contract '{contract}' could not be generated by {producer_module_id}",
                    {"contract": contract, "producer_module_id": producer_module_id, "status": upstream_result.status},
                )
            enriched[contract_brief_key(contract)] = upstream_result.result.content
            loaded.append(contract)
            generated.append(contract)
            continue

        missing.append(contract)

    dependency_ids = [dep for dep in skill.depends_on if dep and dep != "brand_brief"]
    dependency_text = "\n\n---\n\n".join(
        text for dep in dependency_ids if (text := dependency_contract_text(dep))
    )
    if dependency_text:
        enriched.setdefault("upstream_dependency_instructions", dependency_text)

    enriched["required_upstream_contracts"] = list(skill.required_upstream)
    enriched["loaded_upstream_contracts"] = loaded
    enriched["generated_upstream_contracts"] = generated
    enriched["missing_upstream_contracts"] = missing
    if missing:
        raise BosError(
            424,
            "UPSTREAM_CONTRACT_MISSING",
            f"Required upstream contracts are missing for {module_id}: {', '.join(missing)}",
            {"module_id": module_id, "missing": missing},
        )
    enriched.setdefault(
        "upstream_contract_status",
        "Required upstream contracts loaded before module execution.",
    )
    return enriched
