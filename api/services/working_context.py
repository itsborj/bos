"""CMO working context — prompt view around Campaign V2, not campaign truth.

Campaign truth lives in Campaign V2 rows and is accessed through campaign_read.
This module may provide brand, selected Campaign V2 prompt context, desk, and
reference context. It must not assemble campaign truth from deprecated derived
surfaces, reports, run traces, or chat history.
"""
from __future__ import annotations

import logging
import time as _time
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from models.workspace import Brand, Workspace

logger = logging.getLogger("bos.working_context")

PAYLOAD_TYPE = "cmo_working_context@v2_campaign_view"

_FRESHNESS = {
    "brand": "cached_5m",
    "campaign": "live_campaign_v2",
    "desk": "live",
    "references": "session",
}


async def build_working_context(
    db: AsyncSession,
    ws: Workspace | None,
    brand: Brand | None,
    campaign_id: str | None,
    *,
    references_text: str = "",
) -> dict:
    """Assemble a compact prompt view.

    The campaign section is rendered from Campaign V2 only. Deprecated derived
    campaign views do not enter this document.
    """
    from routers.cmo_tools import (
        _SYSTEM_PROMPT_CACHE,
        _SYSTEM_PROMPT_CACHE_TTL,
        _actionable_artifacts_context,
        _build_brand_scaffold,
        _campaign_context_for_prompt,
        _workflow_state_context,
    )

    sections: dict[str, object] = {}
    coverage: dict[str, str] = {}

    def mark(name: str, value, *, error: bool = False) -> None:
        sections[name] = value
        coverage[name] = "error" if error else ("present" if value else "none")

    try:
        cache_key = f"{brand.id if brand else 'ws'}:{ws.id if ws else 'no-ws'}"
        now = _time.time()
        cached = _SYSTEM_PROMPT_CACHE.get(cache_key)
        if cached and now - cached[0] < _SYSTEM_PROMPT_CACHE_TTL:
            scaffold = cached[1]
        else:
            scaffold = await _build_brand_scaffold(db, ws, brand)
            _SYSTEM_PROMPT_CACHE[cache_key] = (now, scaffold)
        mark("brand", scaffold)
    except Exception:
        logger.warning("Working context: brand section failed", exc_info=True)
        mark("brand", "", error=True)

    try:
        campaign_ctx = await _campaign_context_for_prompt(db, ws, campaign_id, brand=brand)
        mark("campaign", campaign_ctx)
    except Exception:
        logger.warning("Working context: campaign section failed", exc_info=True)
        mark("campaign", "", error=True)

    try:
        workflow_state = await _workflow_state_context(db, ws, brand=brand)
        actionable = await _actionable_artifacts_context(db, ws, brand=brand)
        desk = {"workflow_state": workflow_state, "actionable_artifacts": actionable}
        mark("desk", desk if (workflow_state or actionable) else None)
    except Exception:
        logger.warning("Working context: desk section failed", exc_info=True)
        mark("desk", None, error=True)

    mark("references", references_text or "")

    return {
        "payload_type": PAYLOAD_TYPE,
        "assembled_at": datetime.now(timezone.utc).isoformat(),
        "freshness": dict(_FRESHNESS),
        "coverage": coverage,
        "sections": sections,
    }


def working_context_prompt_block(doc: dict) -> str:
    """Render the prompt view.

    This is not a truth document. It orients the CMO, while campaign status and
    updates must still be grounded through Campaign V2 tools/rows.
    """
    if not doc:
        return ""
    sections = doc.get("sections") or {}
    coverage = doc.get("coverage") or {}
    freshness = doc.get("freshness") or {}

    parts: list[str] = [
        f"=== CMO prompt context ({doc.get('payload_type', PAYLOAD_TYPE)}, "
        f"assembled {doc.get('assembled_at', 'unknown')}) ===",
        "This is prompt context only. Campaign truth must be read/written through Campaign V2 tools. "
        "Section freshness: "
        + ", ".join(f"{k}={freshness.get(k, '?')}" for k in _FRESHNESS)
        + ". Sections marked error/none in coverage carry no data — say what you cannot see.",
        "Coverage: " + ", ".join(f"{k}={v}" for k, v in coverage.items()),
    ]

    brand = sections.get("brand")
    if brand:
        parts.append(f"--- brand ---\n{brand}")

    campaign = sections.get("campaign")
    parts.append(
        "--- campaign ---\n"
        + (campaign or
           "No selected Campaign V2 context is loaded in this prompt. For campaign status, inventory, "
           "what changed, blockers, or next action, call campaign_read (use all_active=true when the "
           "operator asks about all/running campaigns). For broad account discussion with multiple active "
           "campaigns, synthesize the portfolio after the read instead of asking which campaign. For open-ended "
           "discussion, do not force a fixed scorecard shape; talk like a CMO using the rows as grounding. "
           "Onboarding now creates a live campaign from the brand profile; creative execution should bind to that live campaign, not a separate foundation mode.")
    )

    desk = sections.get("desk")
    if desk:
        workflow_state = desk.get("workflow_state") if isinstance(desk, dict) else ""
        actionable = desk.get("actionable_artifacts") if isinstance(desk, dict) else ""
        desk_lines = ["--- desk ---"]
        if workflow_state:
            desk_lines.append(
                "Package workflow state, for multi-step artifact processes:\n"
                f"{workflow_state}\n"
                "- Treat workflow state generically: use only declared available_actions/current_artifact_id "
                "for continuation; use fresh_start_module only when the user asks for a new concept/start-over "
                "or no artifact is bound."
            )
        if actionable:
            desk_lines.append(
                "Actionable approved/reviewable artifacts, for explicit deploy/publish/send/upload commands only:\n"
                f"{actionable}\n"
                "- To deploy an artifact action from this list, call the appropriate tool with the run_id and action."
            )
        parts.append("\n".join(desk_lines))

    references = sections.get("references")
    if references:
        parts.append(f"--- references (this conversation only) ---\n{references}")

    parts.append("=== end prompt context ===")
    return "\n\n".join(parts)
