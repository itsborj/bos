"""
Strategy Workflows router.

Endpoints:
  GET   /strategy-workflows/{workflow_id}              — full workflow + components
  PATCH /strategy-workflows/{workflow_id}/components/{component_type}
        — re-run one component via LLM, cascade stale dependents
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_api_key
from capability_router import route
from config import get_settings
from db import get_db
from executor import execute_live, get_platform_key
from models.workflow import WorkflowComponent, WorkflowRun
from models.workspace import Brand
from provider_auth import resolve_stored_provider_credential
from routers.workspace import get_singleton

router = APIRouter(prefix="/strategy-workflows", tags=["strategy_workflows"])
logger = logging.getLogger("bos.strategy_workflows")

# Cascade map from STRATEGY_WORKFLOW.md
_STALE_ON_RERUN: dict[str, list[str]] = {
    "market_context": ["buyer_map"],
    "buyer_map": ["strategic_thesis", "offer_architecture", "channel_stack", "framework_lenses"],
    "strategic_thesis": ["offer_architecture", "channel_stack"],
    "offer_architecture": ["tactical_funnel"],
    "channel_stack": ["tactical_funnel", "channel_content_matrix"],
    "tactical_funnel": ["measurement_model", "work_orders"],
    "measurement_model": ["work_orders"],
    "framework_lenses": [],
}

# Components supported for per-component re-run
_WIRED_COMPONENTS = {
    "buyer_map", "strategic_thesis", "offer_architecture",
    "channel_stack", "channel_content_matrix", "tactical_funnel", "work_orders",
}

# Per-component input field requirements (upstream keys to inject)
_COMPONENT_UPSTREAM: dict[str, list[str]] = {
    "buyer_map": ["market_context"],
    "strategic_thesis": ["buyer_map"],
    "offer_architecture": ["buyer_map", "strategic_thesis"],
    "channel_stack": ["buyer_map", "strategic_thesis", "offer_architecture"],
    "tactical_funnel": ["buyer_map", "strategic_thesis", "offer_architecture", "channel_stack"],
    "work_orders": ["strategic_thesis", "offer_architecture", "channel_stack", "tactical_funnel"],
}

# Per-component prompt body (same format as template.j2 sections)
_COMPONENT_PROMPT_BODY: dict[str, str] = {
    "buyer_map": """\
Generate the buyer map substrate. Write each field as a labelled line.

Awareness level: [unaware | problem_aware | solution_aware | product_aware]
Buyer type: [earlyvangelists | early_majority | late_majority]
Push forces:
- [what is driving the buyer toward a solution]
Pull forces:
- [what the solution promises them]
Blocking forces: [anxiety | habit | low_perceived_likelihood | switching_cost — list all that apply]
Anxiety sources:
- [specific fears, named in buyer language]
Trust gap: [single most important proof deficit — one sentence]
Buyer language:
- [exact phrases buyers use]
Decision roles:
- Champion: [who surfaces or recommends the solution]
- Economic buyer: [who approves spend or commits]
- Veto: [who can block or delay]
Confidence: [inferred | partial | validated]""",

    "strategic_thesis": """\
Generate the strategic thesis. Write each field as a labelled line.

Primary motion: [founder-led | sales-led | product-led | content-led | partner-led | community-led]
Secondary motion: [motion or "none"]
Secondary unlock: [condition that activates it, or "n/a"]
Wedge: [one sentence — the sharpest strategic entry point the brand can own right now]
Decision: [what the business is choosing to do — one sentence]
Not doing:
- [explicit strategic no — channel or approach ruled out, with reason]
Motion rationale: [two to three sentences — why this motion, what it requires to be true, what the failure mode looks like]""",

    "offer_architecture": """\
Generate the offer architecture. Write each field as a labelled line.

Audience need: [specific unmet need this offer addresses]
Resource: [the lead magnet, diagnostic, or entry asset — named, not generic]
Micro commitment: [the lowest-friction first step a buyer can take]
Macro activation: [the actual commercial goal]
Offer ladder:
- [step 1 — zero commitment]
- [step 2 — micro]
- [step 3 — medium]
- [step 4 — full]
Anxiety treatment: [how the offer structure handles the dominant blocking force]
Proof required: [what proof must exist before this offer is credible]""",

    "channel_stack": """\
Generate the channel stack. Maximum three do-now channels. Write as labelled subsections.

Do now:
**[Channel name]**
Role: [acquisition | conversion hub | intent capture | trust-building | reactivation]
Buyer map signal: [the specific field and value that makes this channel right e.g. awareness_level: solution_aware]
Proof required to scale: [what proof asset must exist before this channel is scaled]
Rationale: [one sentence — why this channel fits this buyer at this awareness level]

[Repeat for up to 3 channels]

Hold:
- [Channel] — [hold reason] — [specific unlock condition]

Avoid:
- [Channel] — [avoid reason referencing buyer map signal]""",

    "tactical_funnel": """\
Generate the REAP tactical funnel. Write as labelled subsections.

Reach:
Tactic: [how to reach the buyer — channel and method]
Parallel track: [any secondary reach path running simultaneously, or "none"]

Engage:
Resource: [the specific engagement asset]
Sequence: [how the buyer moves from reach to the micro commitment]
Objection surface: [where objections are most likely to appear in this sequence]

Action:
CTA: [the primary call to action]
Commitment level: [zero | micro | medium | full]
Next step after: [what happens immediately after the buyer takes the action]

Patronage and learning:
Response categories: [how to categorize and use buyer responses]
Proof capture: [how first engagements become proof assets]
Learning loop: [what data from this funnel informs the next version of the strategy]""",

    "work_orders": """\
Generate 4–6 specialist-ready execution briefs. Number each one.

Each work order must follow this exact format:
[N]. [Title]
Purpose: [one sentence — what this artifact does and why it matters at this stage]
Contents:
- [specific content element]
- [specific content element]
Gate: [what must be true before this work order is executed]""",
}


class ComponentOut(BaseModel):
    id: str
    component_type: str
    status: str
    version: int
    data: dict[str, Any]
    summary: Optional[str]
    run_id: Optional[str]
    updated_at: str


class WorkflowOut(BaseModel):
    workflow_id: str
    brand_id: Optional[str]
    brand_name: Optional[str] = None
    archetype: str
    request: str
    status: str
    run_id: Optional[str]
    components: list[ComponentOut]
    created_at: str
    updated_at: str


class ComponentPatchRequest(BaseModel):
    override: Optional[str] = None
    cascade: bool = True


class ComponentPatchResponse(BaseModel):
    workflow_id: str
    component_type: str
    stale_components: list[str]
    status: str
    message: str
    component_data: dict[str, Any] = {}
    summary: Optional[str] = None


def _to_component_out(c: WorkflowComponent) -> ComponentOut:
    return ComponentOut(
        id=str(c.id),
        component_type=c.component_type,
        status=c.status,
        version=c.version,
        data=c.data or {},
        summary=c.summary,
        run_id=str(c.run_id) if c.run_id else None,
        updated_at=c.updated_at.isoformat(),
    )


def _format_upstream_section(comp_type: str, data: dict) -> str:
    """Render a component's data as a readable upstream context block."""
    lines = [f"[{comp_type.replace('_', ' ').title()} — already generated]"]
    for k, v in data.items():
        if k == "raw" or not v:
            continue
        if isinstance(v, list):
            if v:
                lines.append(f"  {k}: {', '.join(str(i) for i in v[:4])}")
        elif isinstance(v, dict):
            pass  # skip nested dicts in upstream summary
        else:
            lines.append(f"  {k}: {v}")
    return "\n".join(lines)


def _build_component_prompt(
    component_type: str,
    brand_name: str,
    request: str,
    archetype: str,
    upstream_comps: dict[str, WorkflowComponent],
    override: str | None,
) -> str:
    upstream_text = ""
    for dep in _COMPONENT_UPSTREAM.get(component_type, []):
        comp = upstream_comps.get(dep)
        if comp and comp.data:
            upstream_text += "\n" + _format_upstream_section(dep, comp.data)

    override_text = f"\n\nAdditional instruction: {override}" if override else ""

    body = _COMPONENT_PROMPT_BODY.get(component_type, "")
    return f"""You are the Klaroha Strategy Workflow Architect regenerating a single component.

Brand: {brand_name}
Request/scope: {request}
GTM archetype: {archetype}

Do not invent numeric targets, conversion rates, or budgets without a baseline.
Do not mention module IDs, RUN syntax, or internal tools.
{override_text}

Upstream context (already generated):
{upstream_text or "None yet."}

---

Regenerate the {component_type.replace("_", " ")} component. Output ONLY the section below — no preamble, no explanation.

## COMPONENT: {component_type}
{body}"""


def _parse_component_data(component_type: str, content: str) -> tuple[dict[str, Any], str]:
    """Parse LLM output for a specific component. Returns (data_dict, summary)."""
    import re

    def _field(text: str, label: str) -> str:
        m = re.search(rf"^{re.escape(label)}:\s*(.+?)$", text, re.MULTILINE | re.IGNORECASE)
        return m.group(1).strip() if m else ""

    def _after_label(text: str, label: str) -> str:
        m = re.search(rf"^{re.escape(label)}:\s*$([\s\S]*?)(?=^\w|\Z)", text, re.MULTILINE | re.IGNORECASE)
        if m:
            return m.group(1).strip()
        m2 = re.search(rf"^{re.escape(label)}:(.+?)(?=^\w|\Z)", text, re.MULTILINE | re.IGNORECASE | re.DOTALL)
        return m2.group(1).strip() if m2 else ""

    def _dash_items(text: str) -> list[str]:
        items = []
        for line in text.splitlines():
            item = re.sub(r"^[-*•]\s*", "", line.strip()).strip()
            if item and not item.endswith(":"):
                items.append(item)
        return items

    # Ensure the content has the COMPONENT header so parsers can find it
    if f"## COMPONENT: {component_type}" not in content.lower():
        content = f"## COMPONENT: {component_type}\n{content}"

    # Extract the section (stop at next ## COMPONENT or end)
    pattern = rf"^##\s+COMPONENT:\s+{re.escape(component_type)}\s*$([\s\S]*?)(?=^##\s+COMPONENT:|\Z)"
    m = re.search(pattern, content, re.MULTILINE | re.IGNORECASE)
    text = m.group(1).strip() if m else content

    if component_type == "buyer_map":
        data = {
            "awareness_level": _field(text, "Awareness level"),
            "buyer_type": _field(text, "Buyer type"),
            "blocking_forces": _field(text, "Blocking forces"),
            "trust_gap": _field(text, "Trust gap"),
            "push_forces": _dash_items(_after_label(text, "Push forces")),
            "pull_forces": _dash_items(_after_label(text, "Pull forces")),
            "anxiety_sources": _dash_items(_after_label(text, "Anxiety sources")),
            "buyer_language": _dash_items(_after_label(text, "Buyer language")),
            "decision_roles": {
                r: _field(text, f"- {r.replace('_', ' ').title()}")
                for r in ("champion", "economic_buyer", "veto")
            },
            "confidence": _field(text, "Confidence"),
            "raw": text,
        }
        summary = f"Awareness: {data['awareness_level']}; Trust gap: {data['trust_gap']}"

    elif component_type == "strategic_thesis":
        data = {
            "primary_motion": _field(text, "Primary motion"),
            "secondary_motion": _field(text, "Secondary motion"),
            "secondary_unlock": _field(text, "Secondary unlock"),
            "wedge": _field(text, "Wedge"),
            "decision": _field(text, "Decision"),
            "not_doing": _dash_items(_after_label(text, "Not doing")),
            "motion_rationale": _field(text, "Motion rationale"),
            "raw": text,
        }
        summary = f"Motion: {data['primary_motion']}; Wedge: {data['wedge']}"

    elif component_type == "offer_architecture":
        data = {
            "audience_need": _field(text, "Audience need"),
            "resource": _field(text, "Resource"),
            "micro_commitment": _field(text, "Micro commitment"),
            "macro_activation": _field(text, "Macro activation"),
            "offer_ladder": _dash_items(_after_label(text, "Offer ladder")),
            "anxiety_treatment": _field(text, "Anxiety treatment"),
            "proof_required": _field(text, "Proof required"),
            "raw": text,
        }
        summary = f"Resource: {data['resource']}; Entry: {data['micro_commitment']}"

    elif component_type == "channel_stack":
        # Parse do_now blocks
        def _after_label_stop(t: str, label: str) -> str:
            pattern2 = rf"^{re.escape(label)}:\s*$([\s\S]*?)(?=^(?:Do now|Hold|Avoid|##)|\Z)"
            m2 = re.search(pattern2, t, re.MULTILINE | re.IGNORECASE)
            return m2.group(1).strip() if m2 else ""

        do_now_raw = _after_label_stop(text, "Do now")
        do_now_items: list[dict[str, str]] = []
        blocks = re.split(r"(?=^\*\*.+?\*\*)", do_now_raw, flags=re.MULTILINE)
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            h = re.search(r"^\*\*(.+?)\*\*", block, re.MULTILINE)
            if not h:
                continue
            do_now_items.append({
                "channel": h.group(1).strip(),
                "role": _field(block, "Role"),
                "buyer_map_signal": _field(block, "Buyer map signal"),
                "proof_required": _field(block, "Proof required to scale"),
                "rationale": _field(block, "Rationale"),
            })
        data = {
            "do_now": do_now_items,
            "hold": _dash_items(_after_label_stop(text, "Hold")),
            "avoid": _dash_items(_after_label_stop(text, "Avoid")),
            "raw": text,
        }
        ch_names = ", ".join(c["channel"] for c in do_now_items) or "none"
        summary = f"Do now: {ch_names}"

    elif component_type == "tactical_funnel":
        reach_block = re.search(r"^Reach:\s*$([\s\S]*?)(?=^Engage:|\Z)", text, re.MULTILINE | re.IGNORECASE)
        reach_text = reach_block.group(1).strip() if reach_block else ""
        data = {
            "reach_tactic": _field(reach_text or text, "Tactic"),
            "engage_resource": _field(text, "Resource"),
            "action_cta": _field(text, "CTA"),
            "proof_capture": _field(text, "Proof capture"),
            "raw": text,
        }
        summary = f"Reach: {data['reach_tactic']}; CTA: {data['action_cta']}"

    elif component_type == "work_orders":
        briefs: list[dict[str, Any]] = []
        blocks = re.split(r"(?=^\d+\.\s+)", text, flags=re.MULTILINE)
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            h = re.match(r"^\d+\.\s+(.+?)$", block, re.MULTILINE)
            if not h:
                continue
            purpose = _field(block, "Purpose")
            gate = _field(block, "Gate")
            contents_raw = _after_label(block, "Contents")
            briefs.append({
                "title": re.sub(r"\*+", "", h.group(1)).strip(),
                "purpose": purpose,
                "contents": _dash_items(contents_raw),
                "gate": gate,
            })
        data = {"briefs": briefs, "raw": text}
        summary = f"{len(briefs)} work order{'s' if len(briefs) != 1 else ''}"

    else:
        data = {"raw": text}
        summary = f"{component_type} regenerated"

    return data, summary


async def _call_llm(prompt: str, db: AsyncSession, workspace_id: uuid.UUID) -> str:
    """Route and execute a text prompt, returning the content string."""
    settings = get_settings()
    candidates, _ = await route(db, "marketing.copywriting", "balanced")
    if not candidates:
        raise RuntimeError("No eligible provider candidates for component re-run")

    for candidate in candidates:
        provider = candidate["provider"]
        api_key, auth_mode = await resolve_stored_provider_credential(
            db,
            workspace_id,
            provider,
            settings,
            tolerate_decryption_failure=True,
        )
        if not api_key:
            api_key = get_platform_key(provider, settings)
            auth_mode = None
        if not api_key:
            continue
        try:
            _, result = await execute_live(candidate, prompt, api_key, settings.markup_multiplier, auth_mode=auth_mode)
            return result["content"]
        except Exception as exc:
            logger.warning("Component re-run: candidate %s/%s failed: %s", provider, candidate["model_id"], exc)

    raise RuntimeError("All provider candidates failed for component re-run")


@router.get("/{workflow_id}", dependencies=[Depends(require_api_key)], responses={404: {"description": "Workflow not found"}})
async def get_workflow(
    workflow_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> WorkflowOut:
    ws = await get_singleton(db)

    wf = (await db.execute(
        select(WorkflowRun).where(
            WorkflowRun.id == workflow_id,
            WorkflowRun.workspace_id == ws.id,
        )
    )).scalar_one_or_none()

    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    components = (await db.execute(
        select(WorkflowComponent)
        .where(WorkflowComponent.workflow_run_id == wf.id)
        .order_by(WorkflowComponent.created_at.asc())
    )).scalars().all()

    brand_name: str | None = None
    if wf.brand_id:
        brand = (await db.execute(select(Brand).where(Brand.id == wf.brand_id))).scalar_one_or_none()
        brand_name = brand.name if brand else None

    return WorkflowOut(
        workflow_id=str(wf.id),
        brand_id=str(wf.brand_id) if wf.brand_id else None,
        brand_name=brand_name,
        archetype=wf.archetype,
        request=wf.request,
        status=wf.status,
        run_id=str(wf.run_id) if wf.run_id else None,
        components=[_to_component_out(c) for c in components],
        created_at=wf.created_at.isoformat(),
        updated_at=wf.updated_at.isoformat(),
    )


@router.patch(
    "/{workflow_id}/components/{component_type}",
    dependencies=[Depends(require_api_key)],
)
async def patch_component(
    workflow_id: uuid.UUID,
    component_type: str,
    body: ComponentPatchRequest,
    db: AsyncSession = Depends(get_db),
) -> ComponentPatchResponse:
    ws = await get_singleton(db)

    wf = (await db.execute(
        select(WorkflowRun).where(
            WorkflowRun.id == workflow_id,
            WorkflowRun.workspace_id == ws.id,
        )
    )).scalar_one_or_none()

    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    components = (await db.execute(
        select(WorkflowComponent).where(WorkflowComponent.workflow_run_id == wf.id)
    )).scalars().all()

    comp_map = {c.component_type: c for c in components}

    target = comp_map.get(component_type)
    if not target:
        raise HTTPException(status_code=404, detail=f"Component '{component_type}' not found in this workflow")

    # Components not yet wired to LLM execution fall back to stale-marking only
    if component_type not in _WIRED_COMPONENTS:
        target.status = "pending"
        stale_types = _STALE_ON_RERUN.get(component_type, []) if body.cascade else []
        for st in stale_types:
            if st in comp_map:
                comp_map[st].status = "stale"
        wf.status = "stale"
        await db.commit()
        return ComponentPatchResponse(
            workflow_id=str(workflow_id),
            component_type=component_type,
            stale_components=stale_types,
            status="pending",
            message=f"'{component_type}' is not yet wired for LLM re-run. Marked pending.",
        )

    # Resolve brand name for the prompt
    brand_name = ws.name
    if wf.brand_id:
        brand = (await db.execute(
            select(Brand).where(Brand.id == wf.brand_id)
        )).scalar_one_or_none()
        if brand:
            brand_name = brand.name

    # Build and execute the per-component prompt
    target.status = "pending"
    await db.commit()

    try:
        prompt = _build_component_prompt(
            component_type=component_type,
            brand_name=brand_name,
            request=wf.request,
            archetype=wf.archetype,
            upstream_comps=comp_map,
            override=body.override,
        )
        content = await _call_llm(prompt, db, ws.id)
        new_data, summary = _parse_component_data(component_type, content)

        target.data = new_data
        target.summary = summary
        target.version += 1
        target.status = "complete"
        target.updated_at = datetime.now(timezone.utc)

    except Exception as exc:
        logger.error("Component re-run failed for %s/%s: %s", workflow_id, component_type, exc)
        target.status = "failed"
        await db.commit()
        raise HTTPException(status_code=502, detail=f"Component re-run failed: {exc}") from exc

    # Cascade stale to dependents
    stale_types: list[str] = []
    if body.cascade:
        stale_types = _STALE_ON_RERUN.get(component_type, [])
        for st in stale_types:
            if st in comp_map:
                comp_map[st].status = "stale"

    # Workflow is complete if all wired components are complete, else stale
    all_complete = all(
        comp_map.get(ct) and comp_map[ct].status == "complete"
        for ct in _WIRED_COMPONENTS
        if ct in comp_map
    )
    wf.status = "complete" if all_complete else "stale"
    wf.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return ComponentPatchResponse(
        workflow_id=str(workflow_id),
        component_type=component_type,
        stale_components=stale_types,
        status="complete",
        message=(
            f"'{component_type}' regenerated. "
            + (f"Stale: {', '.join(stale_types)}." if stale_types else "No downstream components affected.")
        ),
        component_data=target.data,
        summary=target.summary,
    )
