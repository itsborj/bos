import asyncio
import inspect
import json
import logging
import os
import re
import tempfile
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from auth import require_api_key
from capability_router import route
from config import get_settings
from plugin_loader import get_active_plugin_ids, get_plugin_for_module, inject_channel_credentials
from db import get_db
from errors import BosError
from executor import execute_live, execute_mock, get_platform_key
from memory_events import write_memory_event
from model_overrides import effective_strict, get_module_model_override, reorder_candidates_for_model_override
from provider_auth import resolve_stored_provider_credential
from routers.backend_settings import resolve_backend_override
from models.document import WorkspaceDocument
from models.run import Run, RunAttempt, RunResult, RunTrace
from models.workflow import WorkflowComponent, WorkflowRun
from models.workspace import Audience, Brand, Campaign, Product, Workspace
from registry import get_module
from routers.workspace import get_singleton
from skills.loader import get_skill, list_skill_manifests
from schemas.runs import (
    RunExecutionOut,
    RunListItem,
    RunListResponse,
    RunRequest,
    RunResponse,
    RunResultOut,
    RunTraceOut,
)

router = APIRouter(tags=["runs"])
logger = logging.getLogger("bos.runs")


def _contract_brief_key(contract: str) -> str:
    """Map contract ids like buyer_map.v1 to brief keys like buyer_map."""
    raw = (contract or "").strip()
    if not raw:
        return ""
    return re.sub(r"\.v\d+$", "", raw).replace(".", "_").replace("-", "_")


def _has_contract_value(brief: dict, contract: str) -> bool:
    key = _contract_brief_key(contract)
    candidates = {contract, contract.replace(".", "_"), key}
    return any(bool(brief.get(candidate)) for candidate in candidates if candidate)


def _module_skill(module_id: str):
    return next((skill for skill in list_skill_manifests() if skill.module_id == module_id), None)


def _producer_module_for_contract(contract: str) -> str | None:
    """Find the module whose SKILL.md declares it produces this contract."""
    for skill in list_skill_manifests():
        if skill.module_id and contract in skill.outputs:
            return skill.module_id
    return None


def _dependency_contract_text(skill_id: str, *, limit: int = 12000) -> str:
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


async def _find_upstream_contract_content(
    db: AsyncSession,
    ws: "Workspace",
    contract: str,
    brand_id: UUID | None,
) -> str | None:
    """Load a previously persisted upstream artifact by contract/doc/block type.

    This is generic dependency hydration: modules declare required_upstream in
    SKILL.md; the host looks for a matching artifact/document and passes it into
    the brief. It does not dispatch capability-specific logic from chat.
    """
    key = _contract_brief_key(contract)
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


async def _hydrate_module_upstream_context(
    db: AsyncSession,
    ws: "Workspace",
    module_id: str,
    brief: dict,
    brand_id: UUID | None,
    settings=None,
    policy: str | None = None,
    campaign_id: UUID | None = None,
    upstream_stack: tuple[str, ...] | None = None,
) -> dict:
    """Inject SKILL.md-declared upstream contracts into a module brief.

    `required_upstream` is an execution contract, not prompt decoration. The host
    first loads an existing contract artifact. If none exists and a producer
    module is installed, it runs that producer as a supporting substrate before
    the requested module runs. If the contract still cannot be produced, module
    execution is blocked rather than silently inferring from a surface Brand Brief.
    """
    skill = _module_skill(module_id)
    if not skill or not skill.required_upstream:
        return brief

    enriched = dict(brief)
    missing: list[str] = []
    loaded: list[str] = []
    generated: list[str] = []
    stack = tuple(upstream_stack or ()) + (module_id,)
    for contract in skill.required_upstream:
        if _has_contract_value(enriched, contract):
            loaded.append(contract)
            continue
        content = await _find_upstream_contract_content(db, ws, contract, brand_id)
        if content:
            enriched[_contract_brief_key(contract)] = content
            loaded.append(contract)
            continue

        producer_module_id = _producer_module_for_contract(contract)
        if producer_module_id and settings is not None and producer_module_id not in stack:
            logger.info("Hydrating upstream contract %s via %s for %s", contract, producer_module_id, module_id)
            upstream_result = await _execute_module(
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
            enriched[_contract_brief_key(contract)] = upstream_result.result.content
            loaded.append(contract)
            generated.append(contract)
            continue

        missing.append(contract)

    dependency_ids = [dep for dep in skill.depends_on if dep and dep != "brand_brief"]
    dependency_text = "\n\n---\n\n".join(
        text for dep in dependency_ids if (text := _dependency_contract_text(dep))
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


def _brand_handle_from_json(brand_json: dict | None) -> str | None:
    social_handles = (brand_json or {}).get("social_handles") or {}
    return social_handles.get("facebook") or social_handles.get("instagram") or social_handles.get("x") or social_handles.get("twitter")


def _scope_artifact_block(
    block: dict | None,
    *,
    brand_id: Any = None,
    brand_name: str | None = None,
    brand_handle: str | None = None,
) -> dict | None:
    """Attach owning Brand display metadata to artifact blocks without changing native fields.

    This keeps Stream/Workspace previews tied to the run's persisted Brand, not
    the currently selected UI Brand or workspace fallback. It intentionally does
    not invent channel page/account fields.
    """
    if not isinstance(block, dict):
        return block
    scoped = dict(block)
    if brand_id:
        scoped.setdefault("brand_id", str(brand_id))
    if brand_name:
        scoped.setdefault("brand_name", brand_name)
    if brand_handle:
        scoped.setdefault("brand_handle", brand_handle)
    return scoped


def _scope_result_out(
    *,
    content: str,
    self_check: str,
    platform: str | None,
    block: dict | None,
    brand_id: Any = None,
    brand_name: str | None = None,
    brand_handle: str | None = None,
) -> RunResultOut:
    return RunResultOut(
        content=content,
        self_check=self_check,
        platform=platform,
        brand_name=brand_name,
        brand_handle=brand_handle,
        block=_scope_artifact_block(block, brand_id=brand_id, brand_name=brand_name, brand_handle=brand_handle),
    )


def _brand_fields_from_row(brand: Brand | None) -> tuple[str | None, str | None]:
    if not brand:
        return None, None
    return brand.name, _brand_handle_from_json(brand.brand_json)


def _self_check_repair_guidance(failures: list[str]) -> str:
    guidance: list[str] = []
    for failure in failures:
        if failure == "unsupported_do_now_channel_without_context:email_list":
            guidance.append("Move Email marketing/newsletter/email nurture out of Do now and into Hold unless an owned list, CRM, subscribers, opt-ins, or lead database is explicitly loaded.")
        elif failure.startswith("unsupported_do_now_channel_without_context:"):
            channel = failure.rsplit(":", 1)[-1].replace("_", " ")
            guidance.append(f"Remove {channel} from Do now unless the loaded context explicitly proves the prerequisite asset exists; put it in Hold or Avoid with an unlock condition.")
        elif failure == "invalid_motion_taxonomy":
            guidance.append("Use exactly one of these motion names: founder-led, product-led, sales-led, content-led, partner-led, community-led.")
        elif failure == "invented_numeric_target_or_proof":
            guidance.append("Remove fabricated numbers, budgets, percentages, lead counts, revenue targets, and proof thresholds unless supplied in the brief.")
        elif failure == "too_many_do_now_channels":
            guidance.append("Limit Do now to at most three channels.")
    return "\n".join(f"- {item}" for item in guidance)


# ── Brief resolution ───────────────────────────────────────────────────────────

async def _resolve_brief(db: AsyncSession, ws: Workspace, brief: dict) -> dict:
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
            resolved["brand_handle"] = social_handles.get("x") or social_handles.get("twitter") or social_handles.get("instagram")
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
                    resolved["benefits"] = benefits  # full list

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


# ── Image pre-generation (injected into brief before channel module dispatch) ──

async def _inject_campaign_brand_kit_style(
    brief: dict,
    ws: Workspace,
    brand_id,
    db: AsyncSession,
) -> dict:
    """Attach approved Campaign Brand Kit / Brand Guidelines style constraints.

    Chat dispatch already injects raw ``campaign_brand_kit_excerpt`` and
    ``brand_guidelines_excerpt`` into the brief. Do not treat the presence of raw
    excerpts as proof that visual constraints were extracted: image/video
    providers need a compact, brand-locked constraint string, not the top of a
    markdown document or overview table.
    """
    if brief.get("brand_visual_constraints"):
        return brief

    existing_sources = [
        str(brief.get("campaign_brand_kit_excerpt") or "").strip(),
        str(brief.get("brand_guidelines_excerpt") or "").strip(),
    ]
    existing_markdown = "\n\n".join(s for s in existing_sources if s)
    if existing_markdown:
        constraints = _extract_visual_constraints(existing_markdown)
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
            .order_by(WorkspaceDocument.doc_type.asc(), WorkspaceDocument.approved_at.desc().nullslast(), WorkspaceDocument.updated_at.desc())
        )
    ).scalars().all()
    if not docs:
        return brief

    latest_by_type: dict[str, WorkspaceDocument] = {}
    for doc in docs:
        latest_by_type.setdefault(doc.doc_type, doc)

    kit_excerpt = (latest_by_type.get("campaign_brand_kit").content_markdown or "")[:5000] if latest_by_type.get("campaign_brand_kit") else ""
    guideline_excerpt = (latest_by_type.get("brand_guideline").content_markdown or "")[:5000] if latest_by_type.get("brand_guideline") else ""
    combined = "\n\n".join(s for s in (kit_excerpt, guideline_excerpt) if s)
    if not combined:
        return brief
    return {
        **brief,
        "campaign_brand_kit_excerpt": brief.get("campaign_brand_kit_excerpt") or kit_excerpt,
        "brand_guidelines_excerpt": brief.get("brand_guidelines_excerpt") or guideline_excerpt,
        "brand_visual_constraints": _extract_visual_constraints(combined),
    }


def _extract_visual_constraints(markdown: str) -> str:
    """Extract compact brand constraints for media prompts.

    Prefer actual color / voice / typography / CTA rules over introductory
    document titles and overview tables. Provider prompts should receive a
    concise brand contract, not raw markdown.
    """
    keep: list[str] = []
    active_section = ""
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
        if active_section or any(k in lowered for k in line_keywords):
            keep.append(line)
        if len("; ".join(keep)) > 1500:
            break

    constraints = "; ".join(dict.fromkeys(keep))[:1800]
    if constraints:
        constraints += "; Never generate fake text, random UI labels, or baked-in logos inside AI media. Leave safe space for BOS-applied captions, CTA, typography, and logo overlays."
    return constraints[:2200]


async def _is_plugin_module_active(module_id: str, brand_id, db: AsyncSession) -> bool:
    plugin = get_plugin_for_module(module_id)
    if not plugin:
        return True
    return plugin.manifest.plugin_id in await get_active_plugin_ids(db, brand_id)


async def _is_plugin_platform_active(platform: str, brand_id, db: AsyncSession) -> bool:
    from plugin_loader import get_loaded_plugins
    active_ids = await get_active_plugin_ids(db, brand_id)
    for pid, state in get_loaded_plugins().items():
        if pid not in active_ids:
            continue
        if any(s.type == "social_token" and s.platform == platform for s in state.manifest.credential_slots):
            return True
        if any(conn.platform == platform for conn in state.manifest.connections):
            return True
    return False


async def _inject_generated_image(
    brief: dict,
    brand_id,
    db: AsyncSession,
    settings,
) -> dict:
    """
    If the brief contains image_prompt, call media.image.generate before the
    channel module runs and inject _image_data_b64 / _image_mime into the brief.
    Channel modules read these fields from brief — no cross-plugin imports needed.
    """
    try:
        if not await _is_plugin_module_active("media.image.generate", brand_id, db):
            return brief
        from registry import get_module as _get_module
        img_cls = _get_module("media.image.generate")
        if not img_cls:
            return brief
        img_brief = await inject_channel_credentials("media.image.generate", brief, brand_id, db, settings)
        _, result = img_cls().execute_tool_result(img_brief)
        block = result.get("block", {})
        if block.get("status") == "succeeded" and block.get("image_data_b64"):
            return {
                **brief,
                "_image_data_b64": block["image_data_b64"],
                "_image_mime": block.get("mime_type", "image/png"),
                "_image_width": block.get("width", 1024),
                "_image_height": block.get("height", 1024),
            }
    except Exception:
        logger.exception("Image pre-generation failed — continuing without image")
    return brief


async def _resolve_drive_attachment(
    brief: dict,
    brand_id,
    db: AsyncSession,
    settings,
) -> dict:
    """If brief contains drive_file_id, download the file from Google Drive and
    inject it as _image_data_b64 / _image_mime so every channel module receives
    pre-resolved bytes without needing Drive-specific code."""
    drive_file_id = str(brief.get("drive_file_id") or "").strip()
    if not drive_file_id:
        return brief
    # Image bytes may be present under either key:
    #   _image_data_b64 — set by _inject_generated_image (underscore-prefixed pipeline key)
    #   image_data_b64  — copied from the artifact block by _brief_from_action_artifact
    #                     (block fields without underscore prefix are preserved)
    # Normalise to _image_data_b64 so publish modules find the bytes regardless of path.
    existing_b64 = brief.get("_image_data_b64") or brief.get("image_data_b64")
    if existing_b64:
        mime = str(
            brief.get("_image_mime") or brief.get("mime_type") or brief.get("drive_file_mime") or "image/png"
        ).strip()
        return {**brief, "_image_data_b64": existing_b64, "_image_mime": mime}
    try:
        if not await _is_plugin_platform_active("google_drive", brand_id, db):
            return brief
        from routers.social import get_page_token
        brand_id_str = str(brand_id) if brand_id else None
        if not brand_id_str:
            return brief
        token, _ = await get_page_token(db, brand_id_str, "google_drive", settings)
        if not token:
            logger.warning("Drive attachment present but no google_drive token for brand %s", brand_id_str)
            return brief
        import base64
        import importlib.util
        import pathlib
        _drive_dir = str(pathlib.Path(__file__).parent.parent / "plugins" / "google-drive")
        spec = importlib.util.spec_from_file_location(
            "_bos_drive_client", pathlib.Path(_drive_dir) / "drive_client.py"
        )
        _dc_mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(_dc_mod)  # type: ignore[union-attr]
        DriveClient = _dc_mod.DriveClient
        with DriveClient(token) as drive:
            image_data = drive.download_file(drive_file_id)
        mime = str(brief.get("drive_file_mime") or "image/jpeg").strip()
        return {
            **brief,
            "_image_data_b64": base64.b64encode(image_data).decode(),
            "_image_mime": mime,
        }
    except Exception:
        logger.exception("Drive attachment resolution failed for file %s — continuing without image", drive_file_id)
        return brief


async def _resolve_drive_video(
    brief: dict,
    brand_id,
    db: AsyncSession,
    settings,
) -> dict:
    """If video_path is absent, the file has been cleaned up, or a swap was requested,
    download the video from Google Drive into a fresh temp file.

    Swap detection: the frontend sets _video_swapped=True in overrides when the user
    picks a different Drive file. Without this marker the resolver would return early
    when the original local file still exists on disk.
    """
    video_path = str(brief.get("video_path") or "").strip()
    drive_file_id = str(brief.get("drive_file_id") or "").strip()
    video_swapped = bool(brief.get("_video_swapped"))

    if not drive_file_id:
        return brief
    if not video_swapped and video_path and os.path.exists(video_path):
        return brief  # local copy present, no swap requested — use it

    try:
        if not await _is_plugin_platform_active("google_drive", brand_id, db):
            return brief
        from routers.social import get_page_token
        brand_id_str = str(brand_id) if brand_id else None
        if not brand_id_str:
            return brief
        token, _ = await get_page_token(db, brand_id_str, "google_drive", settings)
        if not token:
            return brief

        import pathlib
        import importlib.util as _iutil
        _drive_dir = str(pathlib.Path(__file__).parent.parent / "plugins" / "google-drive")
        spec = _iutil.spec_from_file_location("_bos_drive_client_video", pathlib.Path(_drive_dir) / "drive_client.py")
        _dc_mod = _iutil.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(_dc_mod)  # type: ignore[union-attr]
        DriveClient = _dc_mod.DriveClient
        with DriveClient(token) as drive:
            video_data = drive.download_file(drive_file_id)

        fd, new_path = tempfile.mkstemp(prefix="bos_video_", suffix=".mp4")
        os.close(fd)
        with open(new_path, "wb") as fh:
            fh.write(video_data)
        logger.info("Drive video re-downloaded for file %s → %s", drive_file_id, new_path)
        return {**brief, "video_path": new_path}
    except Exception:
        logger.exception("Drive video re-download failed for file %s — continuing without re-download", drive_file_id)
        return brief


# ── PM plugin run sync helpers ────────────────────────────────────────────────
# These helpers are PM-system agnostic. The active plugin is read from
# brand.brand_json["pm_config"]["plugin"] (e.g. "channel.clickup").
# A different PM plugin just needs tasks.create / tasks.update capabilities
# following the same module ID pattern: marketing.channel.{plugin}.tasks.*

def _pm_cfg(brand: Brand) -> dict:
    bj = brand.brand_json or {}
    return bj.get("pm_config") or {}


async def _sync_run_to_pm(run: Run, brand: Brand, db: AsyncSession, settings) -> str | None:
    """Create a PM task for this run if brand has sync enabled. Returns task_id or None."""
    cfg = _pm_cfg(brand)
    if not cfg.get("sync_enabled") or not cfg.get("list_id") or not cfg.get("plugin"):
        return None
    plugin = cfg["plugin"]
    create_id = f"marketing.channel.{plugin}.tasks.create"
    try:
        if not await _is_plugin_module_active(create_id, run.brand_id, db):
            return None
        cls = get_module(create_id)
        if not cls:
            return None
        pending_status = cfg.get("status_map", {}).get("pending", "review")
        brief: dict = {
            "list_id": cfg["list_id"],
            "tasks": [{"name": f"[BOS] {run.module_id}", "description": f"Run ID: {run.id}", "status": pending_status}],
        }
        brief = await inject_channel_credentials(create_id, brief, run.brand_id, db, settings)
        _, result = cls().execute_tool_result(brief)
        created = result.get("block", {}).get("created", [])
        return created[0].get("id") if created else None
    except Exception:
        logger.exception("PM run sync (create) failed for run %s plugin=%s", run.id, plugin)
        return None


async def _update_pm_task_status(run: Run, new_bos_status: str, brand: Brand, db: AsyncSession, settings) -> None:
    """Update PM task status when run approval_status changes."""
    if not run.pm_task_id:
        return
    cfg = _pm_cfg(brand)
    if not cfg.get("plugin"):
        return
    plugin = cfg["plugin"]
    new_pm_status = cfg.get("status_map", {}).get(new_bos_status, new_bos_status)
    update_id = f"marketing.channel.{plugin}.tasks.update"
    try:
        if not await _is_plugin_module_active(update_id, run.brand_id, db):
            return
        cls = get_module(update_id)
        if not cls:
            return
        brief: dict = {"task_id": run.pm_task_id, "new_status": new_pm_status}
        brief = await inject_channel_credentials(update_id, brief, run.brand_id, db, settings)
        cls().execute_tool_result(brief)
    except Exception:
        logger.exception("PM task status update failed for run %s plugin=%s", run.id, plugin)


# ── Strategy workflow persistence ──────────────────────────────────────────────

# Component types that are generated in the initial full-chain run
_WIRED_COMPONENTS = [
    "buyer_map",
    "strategic_thesis",
    "offer_architecture",
    "channel_stack",
    "tactical_funnel",
    "work_orders",
]

# Component types that are placeholders (not_wired) in the initial run
_NOT_WIRED_COMPONENTS = [
    "market_context",
    "framework_lenses",
    "channel_content_matrix",
    "measurement_model",
]


async def _persist_workflow_record(
    db: AsyncSession,
    ws: "Workspace",
    run: "Run",
    brand_id: "Optional[UUID]",
    brief: dict,
    block: dict,
) -> dict:
    """Create WorkflowRun + WorkflowComponent rows from a strategy_workflow block.

    Returns the block with workflow_id and workflow_url injected.
    """
    try:
        archetype = block.get("archetype") or "direct_sales"
        request = brief.get("request") or brief.get("message") or brief.get("objective") or ""

        wf = WorkflowRun(
            workspace_id=ws.id,
            brand_id=brand_id,
            run_id=run.id,
            archetype=archetype,
            request=str(request)[:2000],
            status="complete",
        )
        db.add(wf)
        await db.flush()  # populate wf.id before creating components

        # Wired components from block data
        component_list = block.get("components") or []
        comp_map = {c.get("type"): c for c in component_list if c.get("type")}

        for ctype in _WIRED_COMPONENTS:
            comp_data = comp_map.get(ctype, {})
            db.add(WorkflowComponent(
                workflow_run_id=wf.id,
                component_type=ctype,
                status="complete",
                version=1,
                data=comp_data.get("data") or {},
                summary=_component_summary(ctype, comp_data.get("data") or {}),
                run_id=run.id,
            ))

        for ctype in _NOT_WIRED_COMPONENTS:
            db.add(WorkflowComponent(
                workflow_run_id=wf.id,
                component_type=ctype,
                status="not_wired",
                version=1,
                data={},
                summary=None,
                run_id=None,
            ))

        block = {**block, "workflow_id": str(wf.id), "workflow_url": f"/strategy-workflows/{wf.id}"}
        logger.info("WorkflowRun created: %s (archetype=%s)", wf.id, archetype)
    except Exception:
        logger.exception("Failed to persist WorkflowRun — block returned without workflow_id")

    return block


def _component_summary(component_type: str, data: dict) -> str | None:
    """One-sentence summary for Stream card / CMO chat from component data."""
    if component_type == "buyer_map":
        al = data.get("awareness_level", "")
        bt = data.get("buyer_type", "")
        tg = data.get("trust_gap", "")
        if al and bt:
            return f"{bt.replace('_', ' ').title()} buyer at {al.replace('_', ' ')} stage — trust gap: {tg}" if tg else f"{bt.replace('_', ' ').title()} buyer at {al.replace('_', ' ')} stage."
    if component_type == "strategic_thesis":
        motion = data.get("primary_motion", "")
        wedge = data.get("wedge", "")
        return f"{motion.replace('-', ' ').title()} motion — {wedge}" if motion and wedge else None
    if component_type == "offer_architecture":
        mc = data.get("micro_commitment", "")
        return f"Entry: {mc}" if mc else None
    if component_type == "channel_stack":
        do_now = data.get("do_now") or []
        if do_now:
            channels = ", ".join(c.get("channel", "") for c in do_now[:3] if c.get("channel"))
            return f"Do now: {channels}." if channels else None
    if component_type == "tactical_funnel":
        cta = data.get("action_cta", "")
        return f"CTA: {cta}" if cta else None
    if component_type == "work_orders":
        briefs = data.get("briefs") or []
        return f"{len(briefs)} work order{'s' if len(briefs) != 1 else ''} generated." if briefs else None
    return None


# ── Core execution (shared by /runs and /chat) ─────────────────────────────────

async def _execute_module(
    db: AsyncSession,
    ws: "Workspace",
    module_id: str,
    brief: dict,
    settings,
    policy: str | None = None,
    campaign_id: UUID | None = None,
    brand_id: UUID | None = None,
    _upstream_stack: tuple[str, ...] | None = None,
    _supporting: bool = False,
) -> RunResponse:
    """Route, execute, persist, and return a RunResponse for any module."""
    module_cls = get_module(module_id)
    if not module_cls:
        raise BosError(404, "MODULE_NOT_FOUND", f"Module '{module_id}' is not registered", None)

    plugin_state = get_plugin_for_module(module_id)
    if plugin_state:
        active_plugin_ids = await get_active_plugin_ids(db, brand_id)
        if plugin_state.manifest.plugin_id not in active_plugin_ids:
            raise BosError(
                403,
                "PLUGIN_INACTIVE",
                f"Plugin '{plugin_state.manifest.plugin_id}' is installed but not active for this Brand",
                {"plugin_id": plugin_state.manifest.plugin_id, "module_id": module_id, "brand_id": str(brand_id) if brand_id else None},
            )

    module = module_cls()

    eff_policy = policy or module.policy_default

    if brand_id:
        brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
        if brand:
            scoped_brief = dict(brief)
            scoped_brief["brand_name"] = brand.name
            bj = brand.brand_json or {}
            for field in ("tone", "voice", "values", "domain", "website_url", "social_handles"):
                if bj.get(field):
                    scoped_brief[field] = bj[field]
            handle = _brand_handle_from_json(bj)
            if handle:
                scoped_brief["brand_handle"] = handle
            if bj.get("domain") or bj.get("website_url"):
                scoped_brief.setdefault("display_url", bj.get("domain") or bj.get("website_url"))
            brief = scoped_brief

    brief = await inject_channel_credentials(module_id, brief, brand_id, db, settings)

    if module_id == "media.image.generate" or brief.get("image_prompt"):
        brief = await _inject_campaign_brand_kit_style(brief, ws, brand_id, db)

    if module_id != "media.image.generate" and (brief.get("image_prompt") or getattr(module, "requires_generated_image", False)):
        brief = await _inject_generated_image(brief, brand_id, db, settings)

    _drive_mime = str(brief.get("drive_file_mime") or "").lower()
    if (module_id != "media.image.generate"
            and brief.get("drive_file_id")
            and not _drive_mime.startswith("video/")):
        brief = await _resolve_drive_attachment(brief, brand_id, db, settings)

    if brief.get("video_path") or brief.get("drive_file_id"):
        brief = await _resolve_drive_video(brief, brand_id, db, settings)

    try:
        brief = await _hydrate_module_upstream_context(
            db,
            ws,
            module_id,
            brief,
            brand_id,
            settings=settings,
            policy=eff_policy,
            campaign_id=campaign_id,
            upstream_stack=_upstream_stack,
        )
    except BosError as upstream_exc:
        # Persist a failed Run so chat can surface an artifact reference instead of silence.
        failed_run = Run(
            workspace_id=ws.id, module_id=module_id, status="failed",
            campaign_id=campaign_id, brand_id=brand_id,
        )
        db.add(failed_run)
        await db.flush()
        db.add(RunTrace(
            run_id=failed_run.id,
            routing_json={"error": upstream_exc.message, "code": upstream_exc.code},
            lineage_json=None,
        ))
        await db.commit()
        raise

    # ── New SDK path: async execute() → klaroha_sdk.RunResult ────────────────
    _sdk_execute = getattr(module, "execute", None)
    if callable(_sdk_execute) and asyncio.iscoroutinefunction(_sdk_execute):
        run = Run(
            workspace_id=ws.id,
            module_id=module_id,
            status="running",
            campaign_id=campaign_id,
            brand_id=brand_id,
            approval_status="supporting" if _supporting else "pending",
        )
        db.add(run)
        await db.flush()

        try:
            sdk_result = await _sdk_execute(brief)
        except Exception as exc:
            logger.exception("SDK execute() raised for run %s", run.id)
            run.status = "failed"
            run.approval_status = "failed"
            await db.commit()
            raise BosError(500, "MODULE_EXECUTE_FAILED", str(exc), None) from exc

        # Convert sdk_result to the legacy attempt_data + result_data + block format
        _plugin_prefix = (module_id or "sdk").split(".")[0]
        _platform = getattr(module, "platform_hint", "") or _plugin_prefix
        _capability = getattr(module, "capability", "marketing.execute") or "marketing.execute"

        attempt_data = {
            "provider": _platform,
            "model_id": module_id,
            "mode": "tool",
            "status": "succeeded" if sdk_result.status != "failed" else "failed",
            "tokens_input": 0,
            "tokens_output": 0,
            "provider_cost": 0.0,
            "latency_ms": sdk_result.metadata.get("latency_ms", 0),
            "error": sdk_result.error,
        }

        # First artifact block becomes the canonical block for Stream rendering
        _sdk_block: dict | None = None
        if sdk_result.artifact_blocks:
            _ab = sdk_result.artifact_blocks[0]
            _sdk_block = {
                "type": _ab.block_type,
                "artifact_type": "action_result",
                "platform": _platform,
                "status": "succeeded" if sdk_result.status == "success" else sdk_result.status,
                "allowed_actions": _ab.allowed_actions,
                "renderer_hint": _ab.renderer_hint,
                **_ab.content,
            }
            _sdk_block = _scope_artifact_block(
                _sdk_block,
                brand_id=brand_id,
                brand_name=brief.get("brand_name"),
                brand_handle=brief.get("brand_handle"),
            )

        _content = sdk_result.metadata.get("content") or (
            json.dumps(_sdk_block) if _sdk_block else ""
        )
        verdict = sdk_result.self_check or "pass"
        failures: list[str] = []

        db.add(RunAttempt(run_id=run.id, **attempt_data))
        run_result_row = RunResult(
            run_id=run.id,
            content=_content,
            self_check_verdict=verdict,
            sell_price=None,
        )
        db.add(run_result_row)

        routing_meta = {
            "capability": _capability,
            "policy": eff_policy,
            "candidates_considered": 1,
            "candidates_filtered": 0,
            "winner": f"{_platform}/{module_id}",
            "routing_reason": "sdk execute() — external plugin",
        }
        db.add(RunTrace(
            run_id=run.id,
            routing_json=routing_meta,
            lineage_json={
                "connector": _platform,
                "self_check": verdict,
                "self_check_failures": failures,
                "block": _sdk_block,
            },
        ))

        _attempt_failed = attempt_data["status"] == "failed"
        run.status = "success" if verdict == "pass" and not _attempt_failed else "partial"
        if _attempt_failed and not _supporting:
            run.approval_status = "failed"
        _allowed_actions = (_sdk_block or {}).get("allowed_actions") or []
        _needs_publish = any(str(a).startswith("publish") for a in _allowed_actions)
        if run.status == "success" and not _needs_publish and not _supporting:
            run.approval_status = "approved"

        await write_memory_event(
            db,
            workspace_id=ws.id,
            brand_id=brand_id,
            event_type="artifact_created",
            topic_tags=[],
            summary=f"Artifact created by {module_id}",
            source_ref=f"run:{run.id}",
            full_record={
                "run_id": str(run.id),
                "module_id": module_id,
                "status": run.status,
                "approval_status": run.approval_status,
            },
        )
        await db.commit()
        await db.refresh(run)

        return RunResponse(
            run_id=str(run.id),
            module_id=run.module_id,
            vertical=getattr(module, "vertical", "marketing"),
            status=run.status,
            approval_status=run.approval_status,
            campaign_id=str(run.campaign_id) if run.campaign_id else None,
            brand_id=str(run.brand_id) if run.brand_id else None,
            brand_name=brief.get("brand_name"),
            result=_scope_result_out(
                content=_content,
                self_check=verdict,
                platform=_platform,
                block=_sdk_block,
                brand_id=brand_id,
                brand_name=brief.get("brand_name"),
                brand_handle=brief.get("brand_handle"),
            ),
            execution=RunExecutionOut(
                provider=_platform,
                model=module_id,
                mode="tool",
                attempts=1,
                latency_ms=attempt_data["latency_ms"],
                tokens_used=0,
                provider_cost=0.0,
                sell_price=None,
            ),
            trace=RunTraceOut(
                capability=_capability,
                policy=eff_policy,
                candidates_considered=1,
                candidates_filtered=0,
                winner=f"{_platform}/{module_id}",
                routing_reason="sdk execute() — external plugin",
            ),
            created_at=run.created_at,
        )
    # ─────────────────────────────────────────────────────────────────────────

    tool_executor = getattr(module, "execute_tool_result", None)
    if callable(tool_executor):
        run = Run(
            workspace_id=ws.id,
            module_id=module_id,
            status="running",
            campaign_id=campaign_id,
            brand_id=brand_id,
            approval_status="supporting" if _supporting else "pending",
        )
        db.add(run)
        await db.flush()

        attempt_data, result_data = tool_executor(brief)
        # Guard: tool modules that fail early may omit provider/model_id, which
        # are NOT NULL in run_attempts. Fill required fields so the row is valid.
        attempt_data.setdefault("provider", module_id.split(".")[0])
        attempt_data.setdefault("model_id", module_id)
        attempt_data.setdefault("mode", "tool")
        attempt_data.setdefault("status", "succeeded")
        attempt_data.setdefault("latency_ms", 0)
        try:
            verdict, failures = module.self_check(result_data["content"], brief)
        except Exception as exc:
            logger.exception("self_check raised for run %s", run.id)
            verdict, failures = "fail", [str(exc)]

        if isinstance(result_data.get("block"), dict):
            result_data["block"] = _scope_artifact_block(
                result_data.get("block"),
                brand_id=brand_id,
                brand_name=brief.get("brand_name"),
                brand_handle=brief.get("brand_handle"),
            )

        db.add(RunAttempt(run_id=run.id, **attempt_data))
        run_result_row = RunResult(
            run_id=run.id,
            content=result_data["content"],
            self_check_verdict=verdict,
            sell_price=result_data.get("sell_price"),
        )
        db.add(run_result_row)

        routing_meta = {
            "capability": module.capability,
            "policy": eff_policy,
            "candidates_considered": 1,
            "candidates_filtered": 0,
            "winner": f"{attempt_data['provider']}/{attempt_data['model_id']}",
            "routing_reason": "deterministic tool connector execution",
        }
        db.add(RunTrace(
            run_id=run.id,
            routing_json=routing_meta,
            lineage_json={
                "connector": attempt_data["provider"],
                "self_check": verdict,
                "self_check_failures": failures,
                "block": result_data.get("block"),
            },
        ))

        block_data = result_data.get("block") or {}
        _attempt_failed = str(attempt_data.get("status") or "").lower() == "failed"
        _block_failed = isinstance(block_data, dict) and str(block_data.get("status") or "").lower() == "failed"
        run.status = "success" if verdict == "pass" and not _attempt_failed and not _block_failed else "partial"
        # Failed provider/setup/tool results are reviewable facts, not approvable drafts.
        # Keep the run visible for audit/history, but remove it from the approval queue.
        if (_attempt_failed or _block_failed) and not _supporting:
            run.approval_status = "failed"
        # Don't auto-approve artifacts that still require a human publish action.
        # These arrive on Stream as 'pending' so the operator can review and publish.
        _allowed_actions = block_data.get("allowed_actions") or []
        _needs_publish = any(str(a).startswith("publish") for a in _allowed_actions)
        if run.status == "success" and block_data.get("status") == "succeeded" and not _needs_publish and not _supporting:
            run.approval_status = "approved"
        await write_memory_event(
            db,
            workspace_id=ws.id,
            brand_id=brand_id,
            event_type="artifact_created",
            topic_tags=[],
            summary=f"Artifact created by {module_id}",
            source_ref=f"run:{run.id}",
            full_record={
                "run_id": str(run.id),
                "module_id": module_id,
                "status": run.status,
                "approval_status": run.approval_status,
                "campaign_id": str(campaign_id) if campaign_id else None,
            },
        )
        await db.commit()

        if brand_id:
            _brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
            if _brand:
                task_id = await _sync_run_to_pm(run, _brand, db, settings)
                if task_id:
                    run.pm_task_id = task_id
                    await db.commit()

        await db.refresh(run)

        return RunResponse(
            run_id=str(run.id),
            module_id=run.module_id,
            vertical=module.vertical,
            status=run.status,
            approval_status=run.approval_status,
            campaign_id=str(run.campaign_id) if run.campaign_id else None,
            brand_id=str(run.brand_id) if run.brand_id else None,
            brand_name=brief.get("brand_name"),
            result=_scope_result_out(
                content=run_result_row.content,
                self_check=verdict,
                platform=module.platform_hint,
                block=result_data.get("block"),
                brand_id=brand_id,
                brand_name=brief.get("brand_name"),
                brand_handle=brief.get("brand_handle"),
            ),
            execution=RunExecutionOut(
                provider=attempt_data["provider"],
                model=attempt_data["model_id"],
                mode=attempt_data["mode"],
                attempts=1,
                latency_ms=attempt_data["latency_ms"],
                tokens_used=attempt_data["tokens_output"],
                provider_cost=attempt_data["provider_cost"],
                sell_price=run_result_row.sell_price,
            ),
            trace=RunTraceOut(
                capability=module.capability,
                policy=eff_policy,
                candidates_considered=routing_meta["candidates_considered"],
                candidates_filtered=routing_meta["candidates_filtered"],
                winner=routing_meta["winner"],
                routing_reason=routing_meta["routing_reason"],
            ),
            created_at=run.created_at,
        )

    candidates, routing_meta = await route(db, module.capability, eff_policy)
    original_candidates = list(candidates)

    model_override = await resolve_backend_override(db, ws.id, module_id) or get_module_model_override(settings, module_id)
    override_is_strict = effective_strict(settings, model_override) if model_override else False
    if model_override and candidates:
        candidates = reorder_candidates_for_model_override(
            candidates,
            model_override,
            strict=override_is_strict,
        )
        override_display_id = f"{model_override.provider}/{model_override.model_id or model_override.tool_id or 'unknown'}"
        routing_meta["backend_override"] = {
            "provider": model_override.provider,
            "model_id": model_override.model_id,
            "tool_id": model_override.tool_id,
            "modality": model_override.modality,
            "strict": override_is_strict,
        }
        routing_meta["routing_reason"] = (
            f"operator-configured backend override for {module_id}: "
            f"{override_display_id} ({model_override.modality})"
        )
        routing_meta["winner"] = (
            f"{candidates[0]['provider']}/{candidates[0]['model_id']}" if candidates else None
        )

    if not candidates:
        failed_run = Run(
            workspace_id=ws.id, module_id=module_id, status="failed",
            campaign_id=campaign_id, brand_id=brand_id,
        )
        db.add(failed_run)
        await db.flush()
        db.add(RunTrace(run_id=failed_run.id, routing_json=routing_meta, lineage_json=None))
        await write_memory_event(
            db,
            workspace_id=ws.id,
            brand_id=brand_id,
            event_type="run_failed",
            topic_tags=[],
            summary=f"Run failed for {module_id}: no eligible candidates",
            source_ref=f"run:{failed_run.id}",
            full_record={"run_id": str(failed_run.id), "module_id": module_id, "routing": routing_meta},
        )
        await db.commit()
        raise BosError(503, "NO_ELIGIBLE_CANDIDATES", "No healthy model options for this capability and policy", routing_meta)

    run = Run(
        workspace_id=ws.id, module_id=module_id, status="running",
        campaign_id=campaign_id, brand_id=brand_id,
        approval_status="supporting" if _supporting else "pending",
    )
    db.add(run)
    await db.flush()

    prompt = module.build_prompt(brief)
    attempt_data: dict | None = None
    result_data: dict | None = None
    failed_attempts: list[dict] = []
    last_error: str | None = None

    attempted_fallback_for_missing_override_credential = False
    while True:
        missing_credential_candidates: list[dict] = []
        for candidate in candidates:
            provider = candidate["provider"]
            api_key, auth_mode = await resolve_stored_provider_credential(db, ws.id, provider, settings, brand_id=brand_id)
            if api_key:
                run_mode = "oauth" if auth_mode == "oauth" else "byok"
            else:
                api_key = get_platform_key(provider, settings)
                auth_mode = None
                run_mode = "platform" if api_key else None

            if not api_key:
                missing_credential_candidates.append(candidate)
                continue

            try:
                attempt_data, result_data = await execute_live(
                    candidate, prompt, api_key, settings.markup_multiplier, byok=(run_mode != "platform"), auth_mode=auth_mode
                )
                break
            except Exception as exc:
                logger.warning("Candidate %s/%s failed: %s", provider, candidate["model_id"], exc)
                failed_attempts.append({
                    "provider": provider, "model": candidate["model_id"],
                    "status": "failed", "error": str(exc),
                })
                db.add(RunAttempt(
                    run_id=run.id, provider=provider, model_id=candidate["model_id"],
                    mode=run_mode, status="failed", error=str(exc),
                ))
                last_error = str(exc)

        if attempt_data is not None:
            break
        if (
            override_is_strict
            and model_override
            and not attempted_fallback_for_missing_override_credential
            and original_candidates
        ):
            fallback_reason = "execution_failed" if last_error else "missing_credentials"
            logger.warning(
                "Strict backend override for %s %s; falling back to normal model routing",
                module_id,
                fallback_reason,
            )
            routing_meta["strict_override_fallback"] = fallback_reason
            candidates = original_candidates
            attempted_fallback_for_missing_override_credential = True
            last_error = None
            continue
        break

    if attempt_data is None:
        if last_error:
            db.add(RunTrace(run_id=run.id, routing_json=routing_meta,
                            lineage_json={"failed_attempts": failed_attempts}))
            run.status = "failed"
            await write_memory_event(
                db,
                workspace_id=ws.id,
                brand_id=brand_id,
                event_type="run_failed",
                topic_tags=[],
                summary=f"Run failed for {module_id}: all provider candidates failed",
                source_ref=f"run:{run.id}",
                full_record={
                    "run_id": str(run.id),
                    "module_id": module_id,
                    "failed_attempts": failed_attempts,
                    "last_error": last_error,
                },
            )
            await db.commit()
            raise BosError(500, "EXECUTION_FAILED", "All provider candidates failed", {"error": last_error})
        else:
            attempt_data, result_data = execute_mock(
                candidates[0], brief, module_id, settings.markup_multiplier
            )
            run_mode = "mock"

    normalizer = getattr(module, "normalize_content", None)
    if callable(normalizer) and result_data and result_data.get("content"):
        result_data["content"] = normalizer(result_data["content"], brief)

    try:
        verdict, failures = module.self_check(result_data["content"], brief)
    except Exception as exc:
        logger.exception("self_check raised for run %s", run.id)
        verdict, failures = "fail", [str(exc)]

    repair_round = 0
    while verdict == "fail" and attempt_data is not None and result_data is not None and api_key and repair_round < 2:
        repair_round += 1
        repair_prompt = "\n\n".join([
            prompt,
            "SELF-CHECK FAILED. Revise the artifact and return the full corrected artifact only.",
            "Failures: " + ", ".join(failures[:12]),
            "Required fixes:\n" + (_self_check_repair_guidance(failures) or "Correct every listed failure explicitly."),
            "Do not include placeholder instruction text. Do not violate any listed self-check failure.",
        ])
        try:
            retry_attempt, retry_result = await execute_live(
                candidate,
                repair_prompt,
                api_key,
                settings.markup_multiplier,
                byok=(run_mode != "platform"),
                auth_mode=auth_mode,
            )
            if callable(normalizer) and retry_result.get("content"):
                retry_result["content"] = normalizer(retry_result["content"], brief)
            retry_verdict, retry_failures = module.self_check(retry_result["content"], brief)
            if retry_verdict == "pass" or len(retry_failures) <= len(failures):
                failed_attempts.append({
                    "provider": attempt_data["provider"],
                    "model": attempt_data["model_id"],
                    "status": "self_check_failed",
                    "failures": failures,
                })
                attempt_data, result_data = retry_attempt, retry_result
                verdict, failures = retry_verdict, retry_failures
            else:
                break
        except Exception as exc:
            logger.warning("Self-check repair attempt failed for %s: %s", module_id, exc)
            break

    db.add(RunAttempt(run_id=run.id, **attempt_data))

    run_result_row = RunResult(
        run_id=run.id,
        content=result_data["content"],
        self_check_verdict=verdict,
        sell_price=result_data["sell_price"],
    )
    db.add(run_result_row)

    # Build and persist structured artifact block for modules that expose native fields.
    block = None
    if hasattr(module, '_build_block') and result_data.get("content"):
        try:
            build_block = module._build_block
            if len(inspect.signature(build_block).parameters) >= 2:
                block = build_block(result_data["content"], brief)
            else:
                block = build_block(result_data["content"])
        except Exception:
            pass
    block = _scope_artifact_block(
        block,
        brand_id=brand_id,
        brand_name=brief.get("brand_name"),
        brand_handle=brief.get("brand_handle"),
    )

    # Persist WorkflowRun + WorkflowComponents for strategy_workflow artifacts
    if block and block.get("type") == "strategy_workflow":
        block = await _persist_workflow_record(db, ws, run, brand_id, brief, block)

    db.add(RunTrace(
        run_id=run.id,
        routing_json=routing_meta,
        lineage_json={
            "attempts": failed_attempts + [{"provider": attempt_data["provider"], "model": attempt_data["model_id"], "status": "succeeded"}],
            "self_check": verdict,
            "self_check_failures": failures,
            "block": block,
        },
    ))

    run.status = "success" if verdict == "pass" else "partial"

    await write_memory_event(
        db,
        workspace_id=ws.id,
        brand_id=brand_id,
        event_type="artifact_created",
        topic_tags=[],
        summary=f"Artifact created by {module_id}",
        source_ref=f"run:{run.id}",
        full_record={
            "run_id": str(run.id),
            "module_id": module_id,
            "status": run.status,
            "approval_status": run.approval_status,
            "campaign_id": str(campaign_id) if campaign_id else None,
            "self_check": verdict,
        },
    )

    await db.commit()

    if brand_id:
        _brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
        if _brand:
            task_id = await _sync_run_to_pm(run, _brand, db, settings)
            if task_id:
                run.pm_task_id = task_id
                await db.commit()

    await db.refresh(run)

    return RunResponse(
        run_id=str(run.id),
        module_id=run.module_id,
        vertical=module.vertical,
        status=run.status,
        approval_status=run.approval_status,
        campaign_id=str(run.campaign_id) if run.campaign_id else None,
        brand_id=str(run.brand_id) if run.brand_id else None,
        brand_name=brief.get("brand_name"),
        result=_scope_result_out(
            content=run_result_row.content,
            self_check=verdict,
            platform=module.platform_hint,
            block=block,
            brand_id=brand_id,
            brand_name=brief.get("brand_name"),
            brand_handle=brief.get("brand_handle"),
        ),
        execution=RunExecutionOut(
            provider=attempt_data["provider"],
            model=attempt_data["model_id"],
            mode=attempt_data["mode"],
            attempts=1,
            latency_ms=attempt_data["latency_ms"],
            tokens_used=attempt_data["tokens_output"],
            provider_cost=attempt_data["provider_cost"],
            sell_price=run_result_row.sell_price,
        ),
        trace=RunTraceOut(
            capability=module.capability,
            policy=eff_policy,
            candidates_considered=routing_meta["candidates_considered"],
            candidates_filtered=routing_meta["candidates_filtered"],
            winner=routing_meta["winner"],
            routing_reason=routing_meta["routing_reason"],
        ),
        created_at=run.created_at,
    )


# ── POST /runs ─────────────────────────────────────────────────────────────────

@router.post("/runs", response_model=RunResponse, status_code=201, summary="Trigger a module run")
async def post_run(
    body: RunRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    settings = get_settings()

    module_cls = get_module(body.module_id)
    if not module_cls:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "MODULE_NOT_FOUND", "message": f"Module '{body.module_id}' is not registered", "details": None}},
        )

    ws = await get_singleton(db)
    if not ws:
        raise HTTPException(
            status_code=412,
            detail={"error": {"code": "WORKSPACE_NOT_INITIALIZED", "message": "Initialize your workspace first: PUT /workspace/brand", "details": None}},
        )

    brief = await _resolve_brief(db, ws, body.payload.brief.model_dump(exclude_none=True))
    return await _execute_module(
        db, ws, body.module_id, brief, settings, body.policy,
        campaign_id=body.campaign_id,
        brand_id=body.brand_id,
    )


# ── GET /runs ──────────────────────────────────────────────────────────────────

@router.get("/runs", response_model=RunListResponse, summary="List run history")
async def list_runs(
    module_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    approval_status: Optional[str] = Query(None),
    brand_id: Optional[UUID] = Query(None),
    created_after: Optional[datetime] = Query(None),
    created_before: Optional[datetime] = Query(None),
    include_preview: bool = Query(False, description="Include compact result/block preview metadata with large inline assets stripped."),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    filters = []
    if module_id:
        filters.append(Run.module_id == module_id)
    if status:
        filters.append(Run.status == status)
    if approval_status:
        filters.append(Run.approval_status == approval_status)
    if brand_id:
        filters.append(Run.brand_id == brand_id)
    if created_after:
        filters.append(Run.created_at >= created_after)
    if created_before:
        filters.append(Run.created_at <= created_before)

    count_stmt = select(func.count()).select_from(Run)
    if filters:
        count_stmt = count_stmt.where(*filters)
    total = (await db.execute(count_stmt)).scalar_one()

    if include_preview:
        stmt = select(Run, RunAttempt, Campaign, Brand, RunResult, RunTrace).join(
            RunAttempt, RunAttempt.run_id == Run.id, isouter=True
        ).join(
            Campaign, Campaign.id == Run.campaign_id, isouter=True
        ).join(
            Brand, Brand.id == Run.brand_id, isouter=True
        ).join(
            RunResult, RunResult.run_id == Run.id, isouter=True
        ).join(
            RunTrace, RunTrace.run_id == Run.id, isouter=True
        ).order_by(Run.created_at.desc()).limit(limit).offset(offset)
    else:
        stmt = select(Run, RunAttempt, Campaign, Brand).join(
            RunAttempt, RunAttempt.run_id == Run.id, isouter=True
        ).join(
            Campaign, Campaign.id == Run.campaign_id, isouter=True
        ).join(
            Brand, Brand.id == Run.brand_id, isouter=True
        ).order_by(Run.created_at.desc()).limit(limit).offset(offset)
    if filters:
        stmt = stmt.where(*filters)
    result = await db.execute(stmt)
    rows_with_attempts = result.all()
    # Outer joins can produce duplicate run rows when a run has multiple attempts/traces.
    # The feed contract is one card per run, so dedupe before serialising.
    seen_run_ids: set[Any] = set()
    unique_rows = []
    for row in rows_with_attempts:
        run_id = row.Run.id
        if run_id in seen_run_ids:
            continue
        seen_run_ids.add(run_id)
        unique_rows.append(row)
    rows_with_attempts = unique_rows

    module_cache: dict[str, Any] = {}

    def _module_cls(mid: str) -> Any:
        if mid not in module_cache:
            module_cache[mid] = get_module(mid)
        return module_cache[mid]

    def _vertical(mid: str) -> str:
        cls = _module_cls(mid)
        return cls.vertical if cls else mid.split(".")[0]

    def _platform(mid: str) -> str | None:
        cls = _module_cls(mid)
        return cls.platform_hint if cls else None

    def _preview(row: Any) -> RunResultOut | None:
        if not include_preview or not getattr(row, "RunResult", None):
            return None
        lineage = row.RunTrace.lineage_json if getattr(row, "RunTrace", None) else {}
        block = (lineage or {}).get("block")
        if block:
            block = _strip_large_block_assets(block)
        brand_name, brand_handle = _brand_fields_from_row(getattr(row, "Brand", None))
        return _scope_result_out(
            content=row.RunResult.content,
            self_check=row.RunResult.self_check_verdict,
            platform=_platform(row.Run.module_id),
            block=block,
            brand_id=row.Run.brand_id,
            brand_name=brand_name,
            brand_handle=brand_handle,
        )

    return RunListResponse(
        runs=[
            RunListItem(
                run_id=str(r.Run.id),
                module_id=r.Run.module_id,
                vertical=_vertical(r.Run.module_id),
                status=r.Run.status,
                approval_status=r.Run.approval_status,
                campaign_id=str(r.Run.campaign_id) if r.Run.campaign_id else None,
                campaign_name=r.Campaign.name if r.Campaign else None,
                brand_id=str(r.Run.brand_id) if r.Run.brand_id else None,
                brand_name=r.Brand.name if getattr(r, "Brand", None) else None,
                created_at=r.Run.created_at,
                provider=r.RunAttempt.provider if r.RunAttempt else None,
                model=r.RunAttempt.model_id if r.RunAttempt else None,
                latency_ms=r.RunAttempt.latency_ms if r.RunAttempt else None,
                tokens=r.RunAttempt.tokens_output if r.RunAttempt else None,
                cost=r.RunAttempt.provider_cost if r.RunAttempt else None,
                result=_preview(r),
            )
            for r in rows_with_attempts
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


# ── GET /runs/{run_id} ─────────────────────────────────────────────────────────

_LARGE_BLOCK_FIELDS = {
    "image_data_b64",
    "_image_data_b64",
    "content_b64",
    "audio_data_b64",
    "video_data_b64",
}


def _strip_large_block_assets(value: Any) -> Any:
    """Return a copy of a result block with large inline asset payloads removed.

    Stream and history surfaces need artifact metadata quickly; they do not need
    multi-MB base64 blobs for every prior image/video run on initial load.
    """
    if isinstance(value, dict):
        stripped = False
        out = {}
        for key, child in value.items():
            if key in _LARGE_BLOCK_FIELDS and isinstance(child, str) and child:
                stripped = True
                continue
            out[key] = _strip_large_block_assets(child)
        if stripped:
            out["asset_omitted"] = True
        return out
    if isinstance(value, list):
        return [_strip_large_block_assets(item) for item in value]
    return value


@router.get("/runs/{run_id}", response_model=RunResponse, summary="Get run detail with full trace")
async def get_run(
    run_id: str,
    include_assets: bool = Query(True, description="Include large inline asset payloads such as image_data_b64."),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
    settings=Depends(get_settings),
):
    detail_row = await db.execute(
        select(Run, RunAttempt, RunResult, RunTrace)
        .join(RunAttempt, RunAttempt.run_id == Run.id, isouter=True)
        .join(RunResult, RunResult.run_id == Run.id, isouter=True)
        .join(RunTrace, RunTrace.run_id == Run.id, isouter=True)
        .where(Run.id == run_id)
        .limit(1)
    )
    row = detail_row.one_or_none()
    if not row:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "RUN_NOT_FOUND", "message": f"Run '{run_id}' not found", "details": None}},
        )

    run, attempt, result, trace = row

    cls = get_module(run.module_id)
    vertical = cls.vertical if cls else run.module_id.split(".")[0]
    platform = cls.platform_hint if cls else None

    routing = trace.routing_json if trace else {}
    lineage = trace.lineage_json if trace else {}

    block = (lineage or {}).get("block")
    if block and include_assets and (block.get("video_path") or block.get("drive_file_id")):
        block = await _resolve_drive_video(block, run.brand_id, db, settings)
    if block and not include_assets:
        block = _strip_large_block_assets(block)

    brand = None
    if run.brand_id:
        brand = (await db.execute(select(Brand).where(Brand.id == run.brand_id))).scalar_one_or_none()
    brand_name, brand_handle = _brand_fields_from_row(brand)

    return RunResponse(
        run_id=str(run.id),
        module_id=run.module_id,
        vertical=vertical,
        status=run.status,
        approval_status=run.approval_status,
        campaign_id=str(run.campaign_id) if run.campaign_id else None,
        brand_id=str(run.brand_id) if run.brand_id else None,
        brand_name=brand_name,
        result=_scope_result_out(
            content=result.content,
            self_check=result.self_check_verdict,
            platform=platform,
            block=block,
            brand_id=run.brand_id,
            brand_name=brand_name,
            brand_handle=brand_handle,
        ) if result else None,
        execution=RunExecutionOut(
            provider=attempt.provider,
            model=attempt.model_id,
            mode=attempt.mode,
            attempts=1,
            latency_ms=attempt.latency_ms or 0,
            tokens_used=attempt.tokens_output,
            provider_cost=attempt.provider_cost,
            sell_price=result.sell_price if result else None,
        ) if attempt else None,
        trace=RunTraceOut(
            capability=routing.get("capability", ""),
            policy=routing.get("policy", ""),
            candidates_considered=routing.get("candidates_considered", 0),
            candidates_filtered=routing.get("candidates_filtered", 0),
            winner=routing.get("winner"),
            routing_reason=routing.get("routing_reason", ""),
        ) if trace else None,
        created_at=run.created_at,
    )

# ── Approval Endpoints ────────────────────────────────────────────────────────

class ApprovalRequest(BaseModel):
    feedback: Optional[str] = None


class RunActionRequest(BaseModel):
    confirm: bool = False
    overrides: dict = Field(default_factory=dict)


class RunActionResponse(BaseModel):
    source_run_id: str
    source_approval_status: str
    action: str
    action_run: RunResponse


def _action_module_from_block(block: dict, action: str) -> str | None:
    """Resolve an approved artifact action to a module using plugin-provided block metadata."""
    allowed = block.get("allowed_actions") if isinstance(block, dict) else []
    action_modules = block.get("action_modules") if isinstance(block, dict) else {}
    if not isinstance(allowed, list) or action not in allowed:
        return None
    if not isinstance(action_modules, dict):
        return None
    module_id = action_modules.get(action)
    return module_id if isinstance(module_id, str) and module_id else None


def _brief_from_action_artifact(run: Run, result: RunResult, block: dict, overrides: dict | None = None) -> dict:
    """Build a minimal action brief from a reviewed artifact block."""
    brief = {
        k: v for k, v in (block or {}).items()
        if k not in {"allowed_actions", "action_modules"} and not k.startswith("_")
    }
    brief.update({
        "source_run_id": str(run.id),
        "source_module_id": run.module_id,
        "approved_artifact_type": (block or {}).get("type"),
    })
    if not brief.get("message"):
        brief["message"] = (block or {}).get("message") or result.content
    if overrides:
        brief.update(overrides)
    return brief


@router.patch("/runs/{run_id}/approve", status_code=200, summary="Approve a run")
async def approve_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """Mark a run as approved."""
    from uuid import UUID
    try:
        run_uuid = UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run ID format")
    
    result = await db.execute(select(Run).where(Run.id == run_uuid))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    run.approval_status = "approved"
    run.feedback = None
    await write_memory_event(
        db,
        workspace_id=run.workspace_id,
        brand_id=run.brand_id,
        event_type="artifact_approved",
        topic_tags=[],
        summary=f"Artifact approved for {run.module_id}",
        source_ref=f"run:{run.id}",
        full_record={"run_id": str(run.id), "module_id": run.module_id, "approval_status": "approved"},
    )
    await db.commit()

    if run.brand_id:
        _brand = (await db.execute(select(Brand).where(Brand.id == run.brand_id))).scalar_one_or_none()
        if _brand:
            await _update_pm_task_status(run, "approved", _brand, db, get_settings())

    return {"run_id": run_id, "approval_status": "approved"}


class AttachImageRequest(BaseModel):
    drive_file_id: str
    drive_file_name: str = ""
    drive_file_mime: str = "image/jpeg"


@router.patch("/runs/{run_id}/attach-image", status_code=200, summary="Attach a Drive image to a pending artifact")
async def attach_image_to_run(
    run_id: str,
    body: AttachImageRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """Store Drive image metadata in RunTrace.lineage_json.block so the publish
    action can resolve it at execution time."""
    try:
        run_uuid = UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run ID format")

    row = (await db.execute(
        select(RunTrace).join(Run, Run.id == RunTrace.run_id).where(Run.id == run_uuid)
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Run trace not found")

    lineage = dict(row.lineage_json or {})
    block = dict(lineage.get("block") or {})
    block["drive_file_id"] = body.drive_file_id
    block["drive_file_name"] = body.drive_file_name
    block["drive_file_mime"] = body.drive_file_mime
    # Clear any previously set direct image_url so the drive path takes precedence
    block.pop("image_url", None)
    lineage["block"] = block
    row.lineage_json = lineage
    await db.commit()

    return {"run_id": run_id, "drive_file_id": body.drive_file_id, "drive_file_name": body.drive_file_name}


async def execute_declared_run_action(
    db: AsyncSession,
    run_id: str,
    action: str,
    settings,
    overrides: dict | None = None,
) -> RunActionResponse:
    """Execute an action declared by a persisted artifact block.

    Generic core primitive used by Stream/Workspace and CMO chat. The action
    target comes from plugin/capability output metadata, not platform routing.
    """
    try:
        run_uuid = UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run ID format")

    row = (await db.execute(
        select(Run, RunResult, RunTrace)
        .join(RunResult, RunResult.run_id == Run.id, isouter=True)
        .join(RunTrace, RunTrace.run_id == Run.id, isouter=True)
        .where(Run.id == run_uuid)
    )).one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")

    source_run, source_result, source_trace = row
    if not source_result:
        raise HTTPException(status_code=404, detail="Run result not found")

    block = ((source_trace.lineage_json or {}).get("block") if source_trace else None) or {}
    if not isinstance(block, dict):
        block = {}

    action_module_id = _action_module_from_block(block, action)
    if not action_module_id:
        raise HTTPException(status_code=400, detail={"error": {"code": "ACTION_NOT_AVAILABLE", "message": f"Artifact does not declare action '{action}'", "details": {"run_id": run_id}}})
    if not get_module(action_module_id):
        raise HTTPException(status_code=404, detail={"error": {"code": "ACTION_MODULE_NOT_FOUND", "message": f"Action module '{action_module_id}' is not installed", "details": None}})

    ws = await get_singleton(db)
    if not ws:
        raise HTTPException(status_code=412, detail="Workspace not initialized")

    brand_count = (await db.execute(select(func.count()).select_from(Brand).where(Brand.workspace_id == ws.id))).scalar_one()
    if brand_count > 0 and not source_run.brand_id:
        raise HTTPException(status_code=400, detail={"error": {"code": "BRAND_REQUIRED", "message": "Approved external actions require a brand-scoped artifact", "details": {"run_id": run_id}}})

    if source_run.approval_status != "approved":
        source_run.approval_status = "approved"
        source_run.feedback = None
        await write_memory_event(
            db,
            workspace_id=source_run.workspace_id,
            brand_id=source_run.brand_id,
            event_type="artifact_approved",
            topic_tags=[],
            summary=f"Artifact approved for {source_run.module_id}",
            source_ref=f"run:{source_run.id}",
            full_record={"run_id": str(source_run.id), "module_id": source_run.module_id, "approval_status": "approved", "action": action},
        )
        await db.commit()

    if source_run.brand_id:
        _brand = (await db.execute(select(Brand).where(Brand.id == source_run.brand_id))).scalar_one_or_none()
        if _brand:
            await _update_pm_task_status(source_run, "approved", _brand, db, settings)

    action_brief = _brief_from_action_artifact(source_run, source_result, block, overrides)
    action_run = await _execute_module(
        db,
        ws,
        action_module_id,
        action_brief,
        settings,
        campaign_id=source_run.campaign_id,
        brand_id=source_run.brand_id,
    )

    try:
        action_uuid = UUID(action_run.run_id)
        action_row = (await db.execute(select(Run).where(Run.id == action_uuid))).scalar_one_or_none()
        action_block = action_run.result.block if action_run.result and isinstance(action_run.result.block, dict) else {}
        action_succeeded = action_block.get("status") == "succeeded" or (action_run.status == "success" and action_block.get("status") != "failed")
        if action_row and action_succeeded:
            action_row.approval_status = "approved"
            await db.commit()
            action_run.approval_status = "approved"
    except Exception:
        logger.exception("Could not mark action run approved for source run %s", source_run.id)

    return RunActionResponse(
        source_run_id=run_id,
        source_approval_status="approved",
        action=action,
        action_run=action_run,
    )


@router.post("/runs/{run_id}/actions/{action}", response_model=RunActionResponse, summary="Execute an approved artifact action")
async def execute_run_action(
    run_id: str,
    action: str,
    body: RunActionRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """HTTP wrapper for executing a plugin-declared artifact action."""
    if not body.confirm:
        raise HTTPException(status_code=400, detail={"error": {"code": "CONFIRM_REQUIRED", "message": "Set confirm=true to execute an external action", "details": {"action": action}}})
    return await execute_declared_run_action(db, run_id, action, get_settings(), body.overrides)


@router.patch("/runs/{run_id}/reject", status_code=200, summary="Reject a run with feedback")
async def reject_run(
    run_id: str,
    body: ApprovalRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """Mark a run as rejected with feedback for revision."""
    from uuid import UUID
    try:
        run_uuid = UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run ID format")
    
    result = await db.execute(select(Run).where(Run.id == run_uuid))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    run.approval_status = "rejected"
    run.feedback = body.feedback
    await write_memory_event(
        db,
        workspace_id=run.workspace_id,
        brand_id=run.brand_id,
        event_type="artifact_dismissed",
        topic_tags=[],
        summary=f"Artifact rejected for {run.module_id}",
        rationale=body.feedback,
        source_ref=f"run:{run.id}",
        full_record={
            "run_id": str(run.id),
            "module_id": run.module_id,
            "approval_status": "rejected",
            "feedback": body.feedback,
        },
    )
    await db.commit()

    if run.brand_id:
        _brand = (await db.execute(select(Brand).where(Brand.id == run.brand_id))).scalar_one_or_none()
        if _brand:
            await _update_pm_task_status(run, "rejected", _brand, db, get_settings())

    return {"run_id": run_id, "approval_status": "rejected", "feedback": body.feedback}


@router.post("/runs/{run_id}/revise", status_code=201, summary="Revise a rejected run")
async def revise_run(
    run_id: str,
    body: ApprovalRequest = ApprovalRequest(),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """Create a new run based on a rejected run (with feedback incorporated)."""
    from uuid import UUID
    try:
        run_uuid = UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run ID format")
    
    # Get the original run
    result = await db.execute(
        select(Run, RunResult, RunTrace)
        .join(RunResult, RunResult.run_id == Run.id, isouter=True)
        .join(RunTrace, RunTrace.run_id == Run.id, isouter=True)
        .where(Run.id == run_uuid)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    
    run, run_result, run_trace = row
    
    if body.feedback:
        run.approval_status = "rejected"
        run.feedback = body.feedback
        await db.flush()

    if run.approval_status != "rejected":
        raise HTTPException(status_code=400, detail="Can only revise rejected runs")
    
    # Get workspace
    ws = await get_singleton(db)
    if not ws:
        raise HTTPException(status_code=412, detail="Workspace not initialized")
    
    settings = get_settings()
    previous_content = run_result.content if run_result else ""
    feedback = body.feedback or run.feedback or "Improve this draft while preserving the original intent."
    brief = {
        "revision_context": (
            "This is a revision request. Rewrite the asset using the feedback below; "
            "do not explain the changes, only output the revised asset.\n\n"
            f"Previous draft:\n{previous_content}\n\n"
            f"Requested change:\n{feedback}"
        )
    }

    response = await _execute_module(db, ws, run.module_id, brief, settings)
    
    # Link the new run to the original as a revision
    new_run_result = await db.execute(
        select(Run).where(Run.id == UUID(response.run_id))
    )
    new_run = new_run_result.scalar_one_or_none()
    if new_run:
        new_run.parent_run_id = run.id
        await write_memory_event(
            db,
            workspace_id=run.workspace_id,
            brand_id=run.brand_id,
            event_type="artifact_revised",
            topic_tags=[],
            summary=f"Artifact revised for {run.module_id}",
            rationale=feedback,
            source_ref=f"run:{new_run.id}",
            full_record={
                "original_run_id": str(run.id),
                "revised_run_id": str(new_run.id),
                "module_id": run.module_id,
                "feedback": feedback,
            },
        )
        await db.commit()
    
    return response

# ── Export Endpoints ───────────────────────────────────────────────────────

class ExportResponse(BaseModel):
    run_id: str
    module_id: str
    platform: Optional[str]
    content: str
    formatted: dict  # Platform-specific formatted content
    self_check: str


@router.get("/runs/{run_id}/export", response_model=ExportResponse, summary="Export run content in copy-paste ready format")
async def export_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    """Export run content formatted for easy copy-pasting to the platform."""
    from uuid import UUID
    try:
        run_uuid = UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run ID format")
    
    # Get the run and related data
    result = await db.execute(
        select(Run, RunResult, RunAttempt)
        .join(RunResult, RunResult.run_id == Run.id, isouter=True)
        .join(RunAttempt, RunAttempt.run_id == Run.id, isouter=True)
        .where(Run.id == run_uuid)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    
    run, run_result, run_attempt = row
    
    if not run_result:
        raise HTTPException(status_code=404, detail="Run result not found")
    
    # Get module info
    cls = get_module(run.module_id)
    platform = cls.platform_hint if cls else "unknown"
    
    # Format content based on platform
    formatted = _format_for_platform(platform, run_result.content)
    
    return ExportResponse(
        run_id=run_id,
        module_id=run.module_id,
        platform=platform,
        content=run_result.content,
        formatted=formatted,
        self_check=run_result.self_check_verdict,
    )


def _format_for_platform(platform: str, content: str) -> dict:
    """Format content for easy copy-pasting based on platform."""
    
    if platform == "facebook":
        return {
            "type": "text",
            "content": content,
            "copy_paste": content,
            "instructions": "Copy and paste directly into Facebook Ads Manager"
        }
    
    elif platform == "twitter":
        return {
            "type": "text",
            "content": content,
            "copy_paste": content,
            "character_count": len(content),
            "max_chars": 280,
            "instructions": "Copy and paste directly into Twitter Ads"
        }
    
    elif platform == "google":
        # Parse headlines and descriptions
        import re
        headlines = re.findall(r"^Headline\s+\d+:\s*(.+)$", content, re.MULTILINE)
        descriptions = re.findall(r"^Description\s+\d+:\s*(.+)$", content, re.MULTILINE)
        
        return {
            "type": "google_rsa",
            "headlines": headlines,
            "descriptions": descriptions,
            "copy_paste": content,
            "instructions": "Copy each headline and description into the corresponding fields in Google Ads"
        }
    
    elif platform == "email":
        # Parse email components
        lines = content.split("\n")
        subject = ""
        body = content
        
        for line in lines:
            if line.lower().startswith("subject:"):
                subject = line[8:].strip()
                body = content[content.find("\n", content.find("Subject:"))+1:].strip()
                break
        
        return {
            "type": "email",
            "subject": subject,
            "body": body,
            "full_email": content,
            "instructions": "Copy subject and body into your email client"
        }
    
    else:
        return {
            "type": "text",
            "content": content,
            "copy_paste": content,
            "instructions": "Copy and paste the content"
        }
