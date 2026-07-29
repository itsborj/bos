"""CMO tool layer — current runtime plus ownership guide.

IMPORTANT: This file is intentionally back to the real runtime implementation.
The previous facade + cmo_tool_runtime split made cmo_tools look lean without
fixing the actual problem: wrong ownership of behavior.

The issue is not file size. The issue is that the CMO tool layer currently does
work that should belong to the actual tools/capabilities.

Ownership principle:

    The caller chooses the tool.
    The tool owns the operation.
    The domain owns the state.
    The CMO owns interpretation.

Hand-drill analogy:

    CMO/chat loop = the hand
    tool registry/executor = the hand choosing a drill from the tool belt
    capability/plugin = the drill
    capability internals = motor, torque, battery, safety, failure behavior
    domain service = the material/state being changed

The hand should not open the drill and operate its motor manually. Likewise,
this layer should not know campaign internals, artifact revision internals,
Drive credential mechanics, Postcraft approval internals, Meta publishing
internals, or YouTube publishing internals.

Target direction:

    cmo_tools.py
      - expose available CMO tools
      - dispatch a tool call to its owner
      - normalize generic success/failure envelopes only

    Campaign V2 tools own:
      - campaign_read/create/append/patch/act behavior
      - campaign validation/preflight
      - campaign-specific result contract

    Artifact lifecycle tools own:
      - revise_artifact and run_artifact_action behavior
      - action lookup and parent/child run linkage

    Channel/plugin tools own:
      - Google Drive, Postcraft, Storyboard, Previs Motion, Meta, YouTube
      - provider/channel-specific validation, execution, retries, and failures

    Services own:
      - Campaign DB truth
      - brand/tool context injection
      - credentials and server-owned context

Until that ownership is corrected, moving code into another file is cosmetic.
This file remains large so the real coupling stays visible.
"""
from __future__ import annotations

import importlib.util
import json
import logging
import re
import time
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from capability_manifest import build_dispatchable_manifest, format_manifest_for_brand
from errors import BosError
from models.document import WorkspaceDocument
from models.run import Run, RunResult, RunTrace
from models.workspace import Audience, Brand, Product
from plugin_loader import get_active_plugin_ids, get_loaded_plugins, get_plugin_for_module
from providers.connector_registry import format_connector_status_for_prompt
from registry import get_module
from skills.loader import get_skill

logger = logging.getLogger("bos.cmo_tools")


def _clip(value: Any, limit: int) -> str | None:
    """Fit optional model-provided strings into DB varchar columns.

    Full values should be preserved in JSON/evidence fields by callers when the
    clipped value is only a display/legacy primitive column.
    """
    if value in (None, "", [], {}):
        return None
    text = " ".join(str(value).strip().split())
    if not text:
        return None
    return text if len(text) <= limit else text[: max(0, limit - 1)].rstrip() + "…"


# Process-local cache: brand_id (str) → last image_data_b64 from a succeeded image tool.
# Injected as source_image_data_b64 when a subsequent tool call carries edit_instruction.
# Lost on restart; doesn't survive across multiple workers — acceptable for MVP.
_image_cache: dict[str, str] = {}

# CMO v2 supported surface area. Keep CMO tools intentionally small:
# Campaign V2 primitives + Google Drive + Postcraft + Storyboard + Previs Motion
# + Meta/YouTube posting channels. Other specialist modules should not appear
# in the CMO v2 native tool list until explicitly admitted here.
_ALLOWED_CMO_MODULE_IDS: set[str] = {
    "drive.folder.setup",
    "drive.asset.upload",
    "drive.asset.list",
    "drive.asset.get",
    "postcraft.render",
    "storyboard.render",
    "storyboard.validate",
    "storyboard.motion.render",
    "storyboard.motion.edit",
    "marketing.channel.meta.pages.read",
    "marketing.channel.meta.pages.insights.report",
    "marketing.channel.meta.posts.read",
    "marketing.channel.meta.posts.draft",
    "marketing.channel.meta.posts.publish",
    "marketing.channel.meta.video.publish",
    "marketing.channel.youtube.connection.validate",
    "marketing.channel.youtube.video.publish",
    "marketing.channel.tiktok.connection.validate",
    "marketing.channel.tiktok.video.publish",
}


# ── Registry ─────────────────────────────────────────────────────────────────

def build_tools(db, active_plugin_ids: set[str] | None = None) -> dict[str, dict]:
    """Build tool schemas from capability_manifest.py.

    Each dispatchable capability with execute_tool_result becomes a tool.
    One tool per module. If the module declares `actions`, typed parameters
    are built from the actions dict. Otherwise falls back to opaque brief:string.

    Returns {tool_name: {description, parameters, required, module_id, label}}.
    """
    entries = build_dispatchable_manifest(active_plugin_ids=active_plugin_ids)
    tools: dict[str, dict] = {}

    for entry in entries:
        module_id = entry.module_id
        if module_id not in _ALLOWED_CMO_MODULE_IDS:
            continue
        if active_plugin_ids is not None:
            plugin = get_plugin_for_module(module_id)
            if plugin and plugin.manifest.plugin_id not in active_plugin_ids:
                continue
        tool_name = module_id.replace(".", "_")

        module_cls = get_module(module_id)
        if not module_cls:
            continue

        has_execute = callable(getattr(module_cls, "execute_tool_result", None))
        if not has_execute:
            continue  # LLM-routed modules not yet supported as native tools

        # Read declared actions — typed parameters or opaque brief fallback
        actions = getattr(module_cls, "actions", None)
        if actions and isinstance(actions, dict):
            # Merge all action parameters into a single typed schema.
            # The LLM fills in whichever fields are relevant; the module
            # dispatches internally based on which fields are present.
            #
            # Required fields: when there is only one action, use its required
            # fields directly. When there are multiple actions with different
            # requirements, set required=[] and let the module validate internally.
            params: dict[str, dict] = {}
            desc_parts: list[str] = [entry.description or f"Execute {entry.label}"]
            all_required_sets: list[set[str]] = []
            for action_name, action_def in actions.items():
                if not isinstance(action_def, dict):
                    continue
                adesc = action_def.get("description", "")
                if adesc:
                    desc_parts.append(f"[{action_name}] {adesc}")
                action_required = set(action_def.get("required") or [])
                if action_required:
                    all_required_sets.append(action_required)
                for pname, pdef in (action_def.get("parameters") or {}).items():
                    if not isinstance(pdef, dict):
                        continue
                    # Merge: later actions override earlier ones for same param name
                    params[pname] = {
                        "type": pdef.get("type", "string"),
                        "description": pdef.get("description", ""),
                    }
                    if "enum" in pdef:
                        params[pname]["enum"] = pdef["enum"]
            # Derive required: single action → use its required; multiple actions
            # with identical required sets → use the common set; otherwise empty
            if len(all_required_sets) == 1:
                required = sorted(all_required_sets[0])
            elif len(all_required_sets) > 1:
                common = all_required_sets[0].intersection(*all_required_sets[1:])
                required = sorted(common) if common else []
            else:
                required = []
            tools[tool_name] = {
                "description": "\n".join(desc_parts),
                "parameters": params,
                "required": required,
                "module_id": module_id,
                "label": entry.label,
            }
        else:
            # Fallback: opaque brief:string for modules without actions declared
            tools[tool_name] = {
                "description": entry.description or f"Execute {entry.label}",
                "parameters": {
                    "brief": {
                        "type": "string",
                        "description": f"JSON brief for {entry.label}.",
                    },
                },
                "required": ["brief"],
                "module_id": module_id,
                "label": entry.label,
            }

    # Built-in artifact lifecycle tools. These are not plugin modules; they are
    # typed continuations over persisted Run artifacts. The CMO loop still sees
    # them as normal native tool calls.
    tools["revise_artifact"] = {
        "description": "Revise an existing persisted artifact by source run ID using the artifact's declared revise action.",
        "parameters": {
            "source_run_id": {"type": "string", "description": "Run ID of the artifact to revise."},
            "feedback": {"type": "string", "description": "Operator edit instruction / requested change."},
        },
        "required": ["source_run_id", "feedback"],
        "module_id": "__artifact_lifecycle__",
        "label": "Revise artifact",
    }
    tools["run_artifact_action"] = {
        "description": "Run a downstream action on an EXISTING persisted artifact (one that already has a run_id from a prior tool call). Use only for deploy/publish/schedule/send/upload actions on artifacts that already appear in the actionable artifacts list. For scheduled Meta/Facebook posts, use the artifact's schedule_facebook action with overrides.scheduled_at as an ISO-8601 datetime. Do NOT use this for initial creation or rendering — use the specific tool for that (e.g. storyboard_render for storyboard images, postcraft_render for approved social post images).",
        "parameters": {
            "source_run_id": {"type": "string", "description": "Run ID of the source artifact."},
            "action": {"type": "string", "description": "Declared artifact action to execute."},
            "confirm": {"type": "boolean", "description": "Must be true when the operator explicitly requested/approved this action."},
            "overrides": {"type": "object", "description": "Optional action-specific overrides, e.g. message, caption, title, privacy, scheduled_at."},
            "notes": {"type": "string", "description": "Optional operator notes to pass to the action module, such as video generation guidance."},
        },
        "required": ["source_run_id", "action", "confirm"],
        "module_id": "__artifact_lifecycle__",
        "label": "Run artifact action",
    }
    # Campaign V2 cutover: campaign_read is the only CMO campaign truth pull.
    # No keyword shortcut, legacy inventory helper, daily brief, memory snapshot,
    # or overview projection should answer campaign truth for the CMO.
    tools["campaign_read"] = {
        "description": (
            "Read the canonical Campaign V2 operating sheet: Campaign + Objective + Distribution Channel + "
            "Time Period + Snapshot + Verdict. Use when the operator asks what BOS knows, what changed, "
            "what is off track, what needs verification, or where the campaign stands. This is the "
            "single CMO campaign truth pull. When the operator asks to check/compare/read both or all active campaigns, set all_active=true. "
            "For broad account/campaign discussion, read the data first and then synthesize strategically in the reply; do not bounce back with 'which campaign' unless the operator explicitly needs to edit/update one campaign."
        ),
        "parameters": {
            "campaign_id": {"type": "string", "description": "Campaign ID to read. Omit to use selected/auto-resolved active campaign. Use 'all' only when all_active=true."},
            "all_active": {"type": "boolean", "description": "Read all active campaigns for the active brand instead of requiring one selected campaign."},
            "limit": {"type": "number", "description": "Maximum Campaign operating-sheet rows to return per campaign."},
        },
        "required": [],
        "module_id": "__campaign__",
        "label": "Read campaign",
    }
    tools["campaign_append"] = {
        "description": (
            "Append producer-reported truth to the canonical Campaign V2 operating sheet. Use for human, "
            "plugin, channel, report, or validator updates such as up/down/null/stale/blocked/verified, "
            "metrics, verdicts, what changed, blockers, and next actions. JSON is evidence only; core "
            "truth goes into typed fields."
        ),
        "parameters": {
            "campaign_id": {"type": "string", "description": "Campaign ID. Omit to use selected/auto-resolved active campaign."},
            "distribution_channel": {"type": "string", "description": "Channel/source, e.g. meta_paid, meta_organic, google_ads, seo, retail, sales, partner."},
            "channel_role": {"type": "string", "description": "Role of this channel/source in the campaign, e.g. awareness, acquisition, conversion, retention, partner, sales support."},
            "market": {"type": "string", "description": "Country, region, store group, local radius, audience segment, or account segment."},
            "time_period": {"type": "string", "description": "Period/window label, e.g. 2026-W29, Q4, last_7_days."},
            "period_start": {"type": "string", "description": "Optional ISO-8601 period start."},
            "period_end": {"type": "string", "description": "Optional ISO-8601 period end."},
            "primary_kpi": {"type": "string", "description": "The main success metric for this reported row, defined by the campaign/channel."},
            "actual": {"type": "string", "description": "Actual result for the primary KPI in this period."},
            "planned_activity": {"type": "string", "description": "Planned campaign/channel activity for this row."},
            "actual_activity": {"type": "string", "description": "Actual observed/reported campaign/channel activity for this row."},
            "reach_metric": {"type": "string", "description": "Provider-validated reach result, e.g. impressions, reach, traffic, accounts reached, store footfall."},
            "engagement_metric": {"type": "string", "description": "Provider-validated engagement result, e.g. clicks, CTR, views, replies, sessions, content consumption."},
            "action_metric": {"type": "string", "description": "Provider-validated action result, e.g. purchase, order, lead, qualified lead, call, booking, demo, pipeline, signup."},
            "efficiency_metric": {"type": "string", "description": "Provider-validated efficiency result, e.g. CPA, CPL, CPC, CPM, ROAS, CAC, cost per booking/opportunity."},
            "value_metric": {"type": "string", "description": "Commercial value result, e.g. revenue, pipeline, sell-through, booked value, opportunity value."},
            "reach": {"type": "number", "description": "Optional numeric reach count when the provider supplies a comparable number."},
            "impressions": {"type": "number", "description": "Impressions count."},
            "engagement": {"type": "number", "description": "Engagement count."},
            "engagement_rate": {"type": "number", "description": "Engagement rate for this period/source."},
            "clicks": {"type": "number", "description": "Clicks count."},
            "leads": {"type": "number", "description": "Leads count."},
            "calls": {"type": "number", "description": "Calls count."},
            "qualified_calls": {"type": "number", "description": "Qualified calls count."},
            "conversions": {"type": "number", "description": "Conversions count."},
            "spend": {"type": "number", "description": "Spend amount."},
            "revenue": {"type": "number", "description": "Revenue amount."},
            "source_health": {"type": "string", "enum": ["reported", "fresh", "stale", "blocked", "not_connected", "connected_no_data", "unknown"], "description": "Producer-reported source health."},
            "freshness": {"type": "string", "description": "Optional freshness note/window, e.g. pulled_today, stale_7d, blocked_by_credentials."},
            "verification_status": {"type": "string", "enum": ["producer_reported", "producer_verified", "unverified", "verified", "rejected", "needs_review"], "description": "Producer or validator status."},
            "objective_verdict": {"type": "string", "enum": ["true", "false", "inconclusive", "needs_data"], "description": "Verdict against the business objective."},
            "confidence": {"type": "string", "enum": ["low", "medium", "high"], "description": "Confidence."},
            "what_changed": {"type": "string", "description": "Concise reported change."},
            "top_learning": {"type": "string", "description": "Most important campaign learning from this row."},
            "recommended_action": {"type": "string", "description": "Provider/operator recommended marketing or sales action."},
            "note": {"type": "string", "description": "Optional human note for meeting context."},
            "blocker": {"type": "string", "description": "Blocker if any."},
            "decision_needed": {"type": "string", "description": "Decision needed if any."},
            "owner": {"type": "string", "description": "Owner for follow-up."},
            "next_action": {"type": "string", "description": "Next safe action."},
            "source_ref": {"type": "string", "description": "Evidence/source reference."},
            "producer": {"type": "string", "description": "Who/what produced this truth."},
            "raw_payload": {"type": "object", "description": "Optional supporting evidence JSON. Typed fields remain the source of truth."},
            "evidence_refs": {"type": "array", "description": "Optional evidence references/IDs backing this row."},
        },
        "required": [],
        "module_id": "__campaign__",
        "label": "Append campaign truth",
    }
    tools["campaign_create"] = {
        "description": (
            "Create a new Campaign record for the active brand when the operator explicitly asks to save, start, "
            "open, or create a campaign. This creates the campaign container; use campaign_append afterwards "
            "to add operating-sheet truth rows such as objective, channel, period, snapshot, verdict, blockers, or next actions."
        ),
        "parameters": {
            "name": {"type": "string", "description": "Campaign name/title."},
            "status": {"type": "string", "enum": ["draft", "active"], "description": "Initial status. Use active when the operator wants this tracked now; draft for tentative saved ideas."},
            "initial_intent": {"type": "string", "description": "What the operator is trying to make happen; saved in campaign_json.initial_intent and an initial Campaign V2 strategy row."},
            "audience": {"type": "string", "description": "Optional initial audience/persona."},
            "message_angle": {"type": "string", "description": "Optional initial message focus/angle."},
            "objective_id": {"type": "string", "description": "Optional existing Objective UUID to link."},
            "campaign_json": {"type": "object", "description": "Optional supporting campaign metadata. Canonical operating truth should still be appended as Campaign V2 rows."},
        },
        "required": ["name"],
        "module_id": "__campaign__",
        "label": "Create campaign",
    }
    tools["campaign_patch"] = {
        "description": (
            "Patch verifier/operator-controlled fields on an existing Campaign V2 row: mark verified, "
            "change source health, correct verdict, add blocker/decision/next action. Only include fields "
            "the operator explicitly asked to change; the server ignores unspecified patch fields. Do not use "
            "this to hide history; append a new row for materially new source data."
        ),
        "parameters": {
            "row_id": {"type": "string", "description": "Campaign row ID to patch."},
            "source_health": {"type": "string", "enum": ["reported", "fresh", "stale", "blocked", "not_connected", "connected_no_data", "unknown"], "description": "Updated source health."},
            "verification_status": {"type": "string", "enum": ["producer_reported", "producer_verified", "unverified", "verified", "rejected", "needs_review"], "description": "Updated verification status."},
            "primary_kpi": {"type": "string", "description": "Updated primary KPI label."},
            "actual": {"type": "string", "description": "Updated actual result for the primary KPI."},
            "reach_metric": {"type": "string", "description": "Updated reach result."},
            "engagement_metric": {"type": "string", "description": "Updated engagement result."},
            "action_metric": {"type": "string", "description": "Updated action result."},
            "efficiency_metric": {"type": "string", "description": "Updated efficiency result."},
            "value_metric": {"type": "string", "description": "Updated commercial value result."},
            "objective_verdict": {"type": "string", "enum": ["true", "false", "inconclusive", "needs_data"], "description": "Updated verdict."},
            "confidence": {"type": "string", "enum": ["low", "medium", "high"], "description": "Updated confidence."},
            "what_changed": {"type": "string", "description": "Updated change note."},
            "top_learning": {"type": "string", "description": "Updated top learning."},
            "recommended_action": {"type": "string", "description": "Updated recommended action."},
            "note": {"type": "string", "description": "Updated meeting note."},
            "blocker": {"type": "string", "description": "Updated blocker."},
            "decision_needed": {"type": "string", "description": "Updated decision needed."},
            "owner": {"type": "string", "description": "Updated owner."},
            "next_action": {"type": "string", "description": "Updated next action."},
        },
        "required": ["row_id"],
        "module_id": "__campaign__",
        "label": "Patch campaign truth",
    }
    tools["campaign_act"] = {
        "description": (
            "Record or prepare a safe Campaign action in the Campaign V2 operating sheet. Use for internal "
            "tasks, report refresh requests, verification requests, draft-prep decisions, or next control "
            "moves. For publish/send/budget/live-campaign mutations, call the appropriate approval-gated "
            "channel/plugin tool instead."
        ),
        "parameters": {
            "campaign_id": {"type": "string", "description": "Campaign ID. Omit to use selected/auto-resolved active campaign."},
            "action_type": {"type": "string", "description": "Action type, e.g. verify_source, refresh_report, draft_variant, create_task."},
            "description": {"type": "string", "description": "Action/decision to record."},
            "owner": {"type": "string", "description": "Owner for the action."},
            "distribution_channel": {"type": "string", "description": "Related channel if any."},
            "channel_role": {"type": "string", "description": "Role of the related channel/source if any."},
            "time_period": {"type": "string", "description": "Related period/window if any."},
            "decision_needed": {"type": "string", "description": "Decision needed if action requires human judgment."},
        },
        "required": ["action_type", "description"],
        "module_id": "__campaign__",
        "label": "Act on campaign",
    }

    return tools


# ── System prompt cache ───────────────────────────────────────────────────────
# The brand scaffold (profile, products, audiences, brand kit, guidelines,
# capability manifest, connector status) is expensive to build — 6+ sequential
# DB queries. Cache it per brand with a short TTL; only the per-turn dynamic
# parts (workflow state, actionable artifacts) are built fresh.
_SYSTEM_PROMPT_CACHE: dict[str, tuple[float, str]] = {}
_SYSTEM_PROMPT_CACHE_TTL = 30  # seconds


def _load_skill_body(skill_id: str) -> str:
    """Load a skill's body text for injection into the system prompt."""
    skill = get_skill(skill_id)
    return skill.body.strip() if skill and skill.body else ""



async def _brand_drive_asset_context(db: AsyncSession, brand: Brand) -> str:
    """Brand visual asset inventory from Google Drive for CMO session context.

    Loaded first in the scaffold so the LLM knows immediately whether image/video
    generation is possible and what brand visual references exist.
    """
    from models.social import SocialConnection

    row = (await db.execute(
        select(SocialConnection).where(
            SocialConnection.brand_id == brand.id,
            SocialConnection.platform == "google_drive",
            SocialConnection.status == "connected",
        ).order_by(SocialConnection.created_at.desc()).limit(1)
    )).scalar_one_or_none()

    async def _template_inventory_line() -> str:
        try:
            from services.brand_kit_templates import available_approved_postcraft_templates

            kit_doc = (await db.execute(
                select(WorkspaceDocument)
                .where(
                    WorkspaceDocument.brand_id == brand.id,
                    WorkspaceDocument.doc_type == "campaign_brand_kit",
                    WorkspaceDocument.status == "approved",
                )
                .order_by(WorkspaceDocument.approved_at.desc().nullslast(), WorkspaceDocument.updated_at.desc())
                .limit(1)
            )).scalar_one_or_none()
            manifest = (kit_doc.metadata_json or {}).get("template_manifest", {}) if kit_doc else {}
            validation = (row.token_meta_json or {}).get("imprint_asset_validation", {}) if row else {}
            indexed_resources: list[dict] = []
            if isinstance(validation, dict):
                seen: set[str] = set()
                for value in validation.values():
                    if not isinstance(value, list):
                        continue
                    for item in value:
                        if isinstance(item, dict) and item.get("id") and str(item["id"]) not in seen:
                            seen.add(str(item["id"]))
                            indexed_resources.append(item)
            indexed = available_approved_postcraft_templates(manifest, indexed_resources)
            if indexed:
                return f"- Postcraft Approved Templates: {len(indexed)} indexed template(s) with stored Drive sources — use only when the operator explicitly requests a Brand Kit template; ordinary renders use original composition"
            approved_count = sum(1 for t in (manifest.get("templates") or []) if isinstance(t, dict) and t.get("status") == "approved")
            if approved_count:
                return f"- Postcraft Approved Templates: 0 indexed — {approved_count} approved manifest entr{'y is' if approved_count == 1 else 'ies are'} stale, missing from the stored Drive index, or not Postcraft-compatible; ordinary renders remain template-free, while explicit template requests require re-indexing/review in Admin → Brands → Brand Kit"
            return "- Postcraft Approved Templates: 0 — no approved social-post design templates are loaded; ordinary renders use original composition, while explicit Brand Kit template requests will surface a blocker"
        except Exception:
            return "- Postcraft Approved Templates: unknown — Brand Kit manifest or Drive index could not be read"

    template_inventory = await _template_inventory_line()

    if not row:
        return (
            "Brand visual assets — NOT CONFIGURED:\n"
            "- Google Drive is not connected for this brand.\n"
            f"{template_inventory}\n"
            "- Image and video generation (Postcraft, Storyboard, Previs Motion) will be blocked.\n"
            "- Direct the operator to Admin → Brands → connect Google Drive, then validate the Brand Kit folder.\n"
        )

    meta = dict(row.token_meta_json or {})
    folder_id = str(meta.get("drive_root_folder_id") or "").strip()
    if not folder_id:
        return (
            "Brand visual assets — DRIVE CONNECTED, FOLDER NOT SET:\n"
            "- Google Drive is connected but no Brand Kit folder has been validated.\n"
            f"{template_inventory}\n"
            "- Image and video generation will be blocked until a Brand Kit folder is selected and validated.\n"
            "- Direct the operator to Admin → Brands → Google Drive → validate Brand Kit folder.\n"
        )

    validation = meta.get("imprint_asset_validation") if isinstance(meta.get("imprint_asset_validation"), dict) else {}
    logo_files = [f for f in (validation.get("logo_files") or []) if isinstance(f, dict) and f.get("id")]

    if not logo_files:
        return (
            f"Brand visual assets — FOLDER SET, BRAND MARK MISSING (root: {meta.get('drive_root_name') or folder_id}):\n"
            "- Google Drive folder is set but contains no Brand Mark (logo, wordmark, or brandmark image).\n"
            f"{template_inventory}\n"
            "- Image and video generation will be blocked until a logo/wordmark is added to the Brand Kit folder.\n"
            "- Direct the operator to add a logo file (named logo.*, wordmark.*, or brandmark.*) to the Brand Kit folder and re-validate.\n"
        )

    def _count(key_primary: str, key_fallback: str = "") -> int:
        files = validation.get(key_primary) or (validation.get(key_fallback) if key_fallback else []) or []
        return sum(1 for f in files if isinstance(f, dict) and f.get("id"))

    brand_char_count = _count("brand_character_files", "mascot_files")
    hero_count = _count("hero_imagery_files")
    lifestyle_count = _count("lifestyle_files")
    location_count = _count("location_files")
    creative_reference_count = _count("creative_reference_files")
    other_count = _count("visual_asset_files") - brand_char_count - hero_count - lifestyle_count - location_count - creative_reference_count
    other_count = max(other_count, 0)

    first_logo_name = str(logo_files[0].get("name") or "logo")
    lines = [
        f"Brand visual assets — READY (Drive folder: {meta.get('drive_root_name') or folder_id}):",
        f"- Brand Mark: {len(logo_files)} file(s) — official logo/wordmark for image generation (primary: {first_logo_name})",
    ]
    if brand_char_count:
        lines.append(f"- Brand Character: {brand_char_count} file(s) — mascot/spokesperson for campaigns")
    if hero_count:
        lines.append(f"- Hero Imagery: {hero_count} file(s) — product/packshot references")
    if lifestyle_count:
        lines.append(f"- Lifestyle & People: {lifestyle_count} file(s) — team/portrait/lifestyle references")
    if location_count:
        lines.append(f"- Location & Space: {location_count} file(s) — venue/property visual references")
    if creative_reference_count:
        lines.append(f"- Creative References: {creative_reference_count} file(s) — Brand Kit visual references, not templates until approved in the manifest")
    lines.append(template_inventory)
    if other_count:
        lines.append(f"- Supporting Visuals: {other_count} other brand image(s)")
    lines.append(
        "- These assets are injected automatically into image/video generation tools as brand visual references.\n"
        "- Do NOT ask the operator to upload or describe these assets; they are already loaded."
    )
    return "\n".join(lines)


async def _brand_channel_readiness(db: AsyncSession, brand: Brand) -> str:
    """Brand-scoped connected-channel facts for dispatch decisions.

    Prevents dispatching publish/store capabilities to channels the active brand
    has not connected.
    """
    from models.social import SocialConnection

    active_plugin_ids = await get_active_plugin_ids(db, brand.id)
    active_plugins = [p for pid, p in get_loaded_plugins().items() if pid in active_plugin_ids]
    allowed_platforms = {
        slot.platform
        for plugin in active_plugins
        for slot in plugin.manifest.credential_slots
        if slot.type in {"social_token", "social_meta_field"} and slot.platform
    } | {
        conn.platform
        for plugin in active_plugins
        for conn in plugin.manifest.connections
        if conn.platform
    }
    if not allowed_platforms:
        return ""

    rows = (await db.execute(
        select(SocialConnection).where(
            SocialConnection.brand_id == brand.id,
            SocialConnection.status == "connected",
            SocialConnection.platform.in_(allowed_platforms),
        )
    )).scalars().all()
    connected = sorted({
        r.platform for r in rows
        if r.platform != "google_drive"
        or (r.token_meta_json or {}).get("drive_root_folder_id")
    })
    if connected:
        names = ", ".join(r.replace("_", " ").replace("-", " ").title() for r in connected)
        connected_line = f"Connected for {brand.name}: {names}."
    else:
        connected_line = f"No external channels are connected for {brand.name} yet."
    return (
        "Active-brand channel readiness (use this for dispatch decisions):\n"
        f"- {connected_line}\n"
        "- Only dispatch a capability that PUBLISHES, SENDS, or POSTS to an external platform, "
        "or that STORES to a channel, when that channel is connected for the active brand above.\n"
        "- If a needed channel is not connected: produce the offline deliverable you can (the creative/copy) "
        "and tell the user in ONE line to connect that channel in Admin → Brands. "
        "Never dispatch a publish/send/post action for an unconnected channel.\n"
    )


async def _workflow_state_context(db: AsyncSession, ws, brand: Brand | None = None) -> str:
    """Compact generic workflow state for CMO."""
    if not ws:
        return "No active package workflows."
    stmt = (
        select(Run, RunTrace)
        .join(RunTrace, RunTrace.run_id == Run.id)
        .where(Run.workspace_id == ws.id)
        .where(Run.status.in_(["success", "partial", "running"]))
        .order_by(Run.created_at.desc())
        .limit(20)
    )
    if brand:
        stmt = stmt.where(Run.brand_id == brand.id)
    try:
        rows = (await db.execute(stmt)).all()
    except Exception as exc:
        logger.debug("Could not load workflow state context: %s", exc)
        return "No active package workflows."

    lines: list[str] = []
    seen: set[tuple[str, str]] = set()
    for run, trace in rows:
        block = ((trace.lineage_json or {}).get("block") if trace else None) or {}
        if not isinstance(block, dict) or not isinstance(block.get("workflow"), dict):
            continue
        wf = block.get("workflow") or {}
        wf_id = str(wf.get("id") or "").strip()
        stage = str(wf.get("stage") or "").strip()
        if not wf_id or not stage:
            continue
        key = (wf_id, stage)
        if key in seen:
            continue
        seen.add(key)
        allowed = block.get("allowed_actions") if isinstance(block.get("allowed_actions"), list) else []
        modules = block.get("action_modules") if isinstance(block.get("action_modules"), dict) else {}
        approval = str(run.approval_status or "pending")
        is_approved = approval in {"approved", "render_approved", "approved_json", "blueprint_approved"}
        _GATE_BEHIND_APPROVAL = {"render", "generate_video", "previs", "generate_image", "render_images", "approve_blueprint"}
        actions = [
            str(a) for a in allowed
            if isinstance(a, str)
            and (a in modules or a in {"approve", "dismiss"})
            and (is_approved or a not in _GATE_BEHIND_APPROVAL)
        ]
        policy = str(wf.get("continuation_policy") or "artifact_bound_else_fresh")
        fresh_module = str(wf.get("fresh_start_module") or "")
        lines.append(
            f"- workflow_id: {wf_id}; stage: {stage}; current_artifact_id: {run.id}; "
            f"artifact_type: {block.get('type') or 'artifact'}; approval_status: {run.approval_status or 'pending'}; "
            f"continuation_policy: {policy}; available_actions: {', '.join(actions) or 'none'}"
            + (f"; fresh_start_module: {fresh_module}" if fresh_module else "")
        )
    return "\n".join(lines[:8]) if lines else "No active package workflows."


async def _campaign_context_for_prompt(
    db: AsyncSession,
    ws,
    campaign_id: str | None,
    brand: Brand | None = None,
) -> str:
    """Compact selected-campaign prompt view over Campaign V2 only.

    Campaign V2 cutover rule: this function must not read deprecated derived
    campaign surfaces, reports, run traces, or chat history for current campaign
    truth. It renders the Campaign container plus canonical
    Campaign V2 operating-sheet rows.
    """
    if not ws or not campaign_id:
        return ""

    try:
        cid = UUID(str(campaign_id))
    except (TypeError, ValueError):
        return (
            "Selected campaign context:\n"
            "- The provided campaign_id is invalid. Ask the operator to select a campaign."
        )

    from models.objective import Objective
    from campaign import db as campaign_db

    rows = await campaign_db.rows_for_campaign(db, cid, limit=8)
    if not rows:
        return (
            "Selected campaign context:\n"
            "- The selected Campaign V2 row/campaign was not found. Ask the operator to select a campaign."
        )

    first = rows[0]
    if brand and first.brand_id and first.brand_id != brand.id:
        return (
            "Selected campaign context:\n"
            "- The selected campaign does not belong to the active brand. Do not use it. "
            "Ask the operator to select the correct campaign for this brand."
        )

    raw = first.raw_payload if isinstance(first.raw_payload, dict) else {}
    campaign_json = raw.get("campaign_json") if isinstance(raw.get("campaign_json"), dict) else raw
    lines: list[str] = ["Selected campaign context (Campaign V2 canonical view):"]
    lines.append(f"- campaign_id: {campaign_db.campaign_key(first)}")
    lines.append(f"- name: {first.campaign or 'Untitled Campaign'}")
    lines.append(f"- status: {first.status}")
    if first.objective_id:
        objective = (await db.execute(
            select(Objective).where(Objective.id == first.objective_id)
        )).scalar_one_or_none()
        if objective:
            lines.append(
                "- objective_guardrail: "
                f"{objective.summary}; success_metric: {objective.success_metric}; "
                f"horizon: {objective.horizon}; status: {objective.status}"
            )

    if isinstance(campaign_json, dict) and campaign_json:
        picked_keys = [
            "initial_intent", "goal", "objective", "business_objective",
            "success_metric", "target", "baseline", "offer", "product",
            "channel", "phase", "positioning", "notes", "full_audience",
            "full_message_angle", "audience", "message_angle",
        ]
        picked = {k: campaign_json.get(k) for k in picked_keys if campaign_json.get(k) not in (None, "", [], {})}
        if picked:
            lines.append("- campaign_container_fields: " + json.dumps(picked, ensure_ascii=False)[:1800])

    lines.append("Campaign V2 operating-sheet rows:")
    for row_obj in rows[:8]:
        row = campaign_db.row_dict(row_obj)
        bits = [str(x) for x in (row.get("time_period"), row.get("distribution_channel")) if x]
        metrics = []
        is_strategy_needs_data = row.get("distribution_channel") == "campaign_strategy" and row.get("objective_verdict") == "needs_data"
        for key in ("primary_kpi", "actual", "reach_metric", "engagement_metric", "action_metric", "efficiency_metric", "value_metric"):
            if row.get(key) not in (None, "", [], {}):
                metrics.append(f"{key}={row.get(key)}")
        for key in ("reach", "impressions", "engagement", "clicks", "leads", "calls", "qualified_calls", "conversions", "spend", "revenue"):
            if is_strategy_needs_data and row.get(key) in (0, "0", "0.00"):
                continue
            if row.get(key) is not None:
                metrics.append(f"{key}={row.get(key)}")
        lines.append(
            f"- {' / '.join(bits) or 'latest'}: {', '.join(metrics) or 'metrics not reported'}; "
            f"source={row.get('source_health')}; verification={row.get('verification_status')}; "
            f"verdict={row.get('objective_verdict')}; "
            f"changed={row.get('what_changed') or 'not reported'}; "
            f"learning={row.get('top_learning') or 'none'}; "
            f"recommendation={row.get('recommended_action') or 'none'}; "
            f"note={row.get('note') or 'none'}; "
            f"decision={row.get('decision_needed') or 'none'}; "
            f"next={row.get('next_action') or 'none'}"
        )

    return "\n".join(lines)


async def _actionable_artifacts_context(db: AsyncSession, ws, brand: Brand | None = None) -> str:
    """Actionable approved/reviewable artifacts for deploy/publish/send/upload commands."""
    if not ws:
        return "No actionable artifacts available."
    stmt = (
        select(Run, RunTrace)
        .join(RunTrace, RunTrace.run_id == Run.id)
        .where(Run.workspace_id == ws.id)
        .where(Run.status.in_(["success", "partial"]))
        .order_by(Run.created_at.desc())
        .limit(20)
    )
    if brand:
        stmt = stmt.where(Run.brand_id == brand.id)
    try:
        rows = (await db.execute(stmt)).all()
    except Exception as exc:
        logger.debug("Could not load actionable artifacts context: %s", exc)
        return "No actionable artifacts available."
    lines: list[str] = []
    for run, trace in rows:
        block = ((trace.lineage_json or {}).get("block") if trace else None) or {}
        if not isinstance(block, dict):
            continue
        action_modules = block.get("action_modules")
        allowed_actions = block.get("allowed_actions")
        if not isinstance(action_modules, dict) or not isinstance(allowed_actions, list):
            continue
        actions = [a for a in allowed_actions if isinstance(a, str) and isinstance(action_modules.get(a), str)]
        if not actions:
            continue
        block_type = block.get("type") or "artifact"
        status = run.approval_status or "pending"
        lines.append(
            f"- run_id: {run.id}; artifact_type: {block_type}; source_module: {run.module_id}; "
            f"approval_status: {status}; actions: {', '.join(actions)}"
        )
    if not lines:
        return "No actionable artifacts available."
    return "\n".join(lines[:8])


async def _build_brand_scaffold(
    db: AsyncSession, ws, brand: Brand | None = None
) -> str:
    """Build the cached brand scaffold — static brand data that changes rarely.

    This is the expensive part: 6+ sequential DB queries for brand profile,
    products, audiences, brand kit, guidelines, capability manifest, channel
    readiness, and connector status. Cached per brand with a 30s TTL.
    """
    if not brand:
        # No active brand — show workspace brand roster so the LLM can ask
        # which brand the user wants to work with.
        if not ws:
            return ""
        from models.workspace import Brand as _Brand
        from sqlalchemy import select as _sel
        org_brands = (await db.execute(
            _sel(_Brand).where(_Brand.workspace_id == ws.id).order_by(_Brand.name.asc())
        )).scalars().all()
        if not org_brands:
            return ""
        brand_lines = [f"- {b.name}" for b in org_brands]
        return (
            f"Known org context (no active brand):\n"
            f"Workspace: {ws.name}\n"
            f"Available brands:\n" + "\n".join(brand_lines) + "\n"
            f"No Brand is active. Do not use workspace products, audiences, or documents as brand facts. "
            f"For brand-specific artifacts, ask which brand unless the user names one.\n"
        )

    ws_name = brand.name or (ws.name if ws else "this business")
    bj = brand.brand_json or {}

    # ── Brand visual assets — loaded first so LLM knows image/video readiness ──
    lines: list[str] = [await _brand_drive_asset_context(db, brand)]
    voice = bj.get("voice", "")
    tone = bj.get("tone", "")
    values = bj.get("values", [])
    domain = bj.get("domain", "")
    website_url = bj.get("website_url", "")
    social_handles = bj.get("social_handles", {}) or {}
    socials = ", ".join(f"{ch}: {h}" for ch, h in social_handles.items() if h)
    parts = [
        f"voice: {voice}" if voice else "",
        f"tone: {tone}" if tone else "",
        f"values: {', '.join(values)}" if values else "",
        f"domain: {domain}" if domain else "",
        f"website: {website_url}" if website_url else "",
        f"social handles: {socials}" if socials else "",
    ]
    brand_ctx = "\nBrand — " + ", ".join(p for p in parts if p) + "." if any(parts) else ""
    if brand_ctx:
        lines.append(brand_ctx)

    # ── Products ─────────────────────────────────────────────────────────
    product_rows = (await db.execute(
        select(Product).where(Product.brand_id == brand.id).order_by(Product.created_at.asc())
    )).scalars().all()
    if product_rows:
        product_lines = []
        for p in product_rows:
            benefits = (p.benefits_json or {}).get("benefits", [])
            product_lines.append(
                f"- {p.name}: {p.tagline or 'no tagline'}"
                + (f"; benefits: {', '.join(benefits)}" if benefits else "")
            )
        lines.append("Products/offers:\n" + "\n".join(product_lines))

    # ── Audiences ────────────────────────────────────────────────────────
    audience_rows = (await db.execute(
        select(Audience).where(Audience.brand_id == brand.id).order_by(Audience.created_at.asc())
    )).scalars().all()
    if audience_rows:
        audience_lines = []
        for a in audience_rows:
            seg = a.segment_json or {}
            pain = seg.get("pain_points", [])
            examples = seg.get("examples", [])
            priority = seg.get("priority", [])
            detail_parts = [seg.get("demographics", "no demographics")]
            if examples:
                detail_parts.append(f"examples: {', '.join(examples)}")
            if priority:
                detail_parts.append(f"priority: {', '.join(priority)}")
            if pain:
                detail_parts.append(f"pains: {', '.join(pain)}")
            audience_lines.append(f"- {a.name}: " + "; ".join(detail_parts))
        lines.append("Target audiences:\n" + "\n".join(audience_lines))

    # ── Documents ────────────────────────────────────────────────────────
    docs = (await db.execute(
        select(WorkspaceDocument)
        .where(WorkspaceDocument.brand_id == brand.id)
        .order_by(WorkspaceDocument.updated_at.desc())
    )).scalars().all()
    by_type: dict[str, list[str]] = {}
    for doc in docs:
        if doc.content_markdown:
            by_type.setdefault(doc.doc_type, []).append(doc.content_markdown)

    guideline_excerpt = "\n\n".join(by_type.get("brand_guideline", []))[:6000]
    if guideline_excerpt:
        lines.append("Brand Guidelines / Strategic Brief excerpt:\n" + guideline_excerpt)

    kit_excerpt = "\n\n".join(by_type.get("campaign_brand_kit", []))[:5000]
    if kit_excerpt:
        lines.append("Campaign Brand Kit excerpt:\n" + kit_excerpt)

    competitor_profiles = "\n\n".join(by_type.get("competitor_profile", []))[:3000]
    if competitor_profiles:
        lines.append("Competitor Profiles excerpt:\n" + competitor_profiles)

    industry_data = "\n\n".join(by_type.get("industry_report", []))[:3000]
    if industry_data:
        lines.append("Industry Data excerpt:\n" + industry_data)

    # ── Capability manifest (brand-filtered) ─────────────────────────────
    modules_str = await format_manifest_for_brand(db, brand.id)
    lines.append("Deployable capabilities:\n" + modules_str)

    # ── Channel readiness ────────────────────────────────────────────────
    channel_ctx = await _brand_channel_readiness(db, brand)
    if channel_ctx:
        lines.append(channel_ctx)

    # ── Connector status ─────────────────────────────────────────────────
    connector_ctx = format_connector_status_for_prompt()
    if connector_ctx:
        lines.append("Connector status:\n" + connector_ctx)

    return "\n\n".join(lines)


def build_system_prompt(
    brand_name: str,
    tools: dict[str, dict],
) -> str:
    """Assemble the instruction/tools half of the system prompt.

    Runtime brand/desk/reference data travels in the working-context prompt
    view appended by the caller. Campaign truth itself must come from Campaign
    V2 tools/rows, not memory, daily brief, overview, or report JSON.
    """
    parts: list[str] = []

    # Brand identity — from skill (fallback)
    brand_skill = _load_skill_body("workspace.cmo_context")
    if brand_skill:
        parts.append(brand_skill)
    elif brand_name:
        parts.append(f"Brand: {brand_name}")

    # workspace.scope_resolution / workspace.marketing_jobs intentionally excluded:
    # those skills teach the v1 text-directive format (SCOPE:/RUN:) which breaks
    # native tool calling. Chat v2 routes through function calls only.

    context = "\n\n".join(parts)

    # Tool listing — prose with produces/consumes for chaining reasoning
    tool_lines = []
    for name, tool in tools.items():
        module_id = tool.get("module_id")
        module_cls = get_module(module_id) if module_id and not str(module_id).startswith("__") else None
        actions = getattr(module_cls, "actions", None) if module_cls else None
        line = f"  {name} — {tool.get('label', name)}: {tool.get('description', '')}"
        if actions and isinstance(actions, dict):
            for action_name, action_def in actions.items():
                if not isinstance(action_def, dict):
                    continue
                produces = action_def.get("produces", "")
                consumes = action_def.get("consumes", "")
                if produces or consumes:
                    meta = []
                    if consumes:
                        meta.append(f"consumes {consumes}")
                    if produces:
                        meta.append(f"produces {produces}")
                    line += f" [{action_name}: {'; '.join(meta)}]"
        tool_lines.append(line)
    tool_section = "\n".join(tool_lines) if tool_lines else "  (no tools available)"

    return f"""You are the CMO for {brand_name or "this business"}. You plan and execute marketing work.

{context}

Available tools:
{tool_section}

Core behavior:
- Do not act like a generic chatbot. Your working context below is a prompt view only; campaign truth comes from Campaign V2 tools and rows.
- Campaign truth lives in Campaign V2 operating-sheet rows. Use campaign_read for campaign status; when the operator asks to check/compare/read both or all active campaigns, call campaign_read with all_active=true. Use campaign_create when the operator explicitly asks to save/start/open/create a Campaign record. Use campaign_append when the operator/source reports new campaign truth; use campaign_patch for verification/corrections; use campaign_act for safe internal next actions. CMO chat cannot delete campaigns; deletion belongs in Admin Campaign Board. Do not write guesses; if no active campaign is selected and the update is campaign-specific, ask which campaign to update.
- If the operator asks about "campaigns", "this campaign", "where are we", "what's next", or "tell me about campaigns", ground the answer with campaign_read. Do not answer from deprecated derived campaign surfaces, run traces, report JSON, or chat history.
- Treat "let's discuss the campaign", "what do you think", and similar prompts as open-ended CMO conversation, not as a status-report template. Use campaign_read as background, then talk strategically: what the campaign is trying to do, what feels strong, what you would challenge or sharpen, and what decision is worth making next. For discussion prompts, do not open with row counts, table mechanics, missing metrics, weak evidence, or "not measurable yet" unless the operator specifically asked for audit/status. Missing metrics are normal in planning-stage discussion; keep the conversation on campaign direction.
- Broad campaign/account discussion is still answerable when multiple campaigns are active. After campaign_read, synthesize what the data means for the client account. Do not stop at "Which campaign?" unless the operator explicitly asked to edit/update a specific campaign or the brand itself is ambiguous.
- For campaign/account status replies, respond like an agency CMO, not a database clerk. Do not force a rigid template; choose the structure that best fits the operator's question. Use data-driven synthesis when useful: business objective, campaign lane/role, available signal, strategic interpretation, and next client/operator decision. If data is thin, do not make the answer feel like a database deficiency report; explain what can still be decided, what assumption should be tested first, and what evidence would make the next discussion sharper. If you infer or recommend a role from incomplete Campaign data, phrase it as CMO judgment/recommendation rather than recorded Campaign truth.
- If no brand is active and the user asks for brand-specific work, ask which brand unless the user named one.
- CRITICAL — POSTCRAFT SOCIAL IMAGE WORKFLOW: When the operator asks to make/create/generate a social media post image, Instagram/Facebook/LinkedIn promo image, or branded post creative, write the full FINAL social image creative as plain text with structured fields exactly like: Template:, Format:, Headline:, Subheadline:, Body copy:, CTA:, Visual direction:, Asset/brand notes:. If no campaign is selected and campaign context is needed, first use campaign_read with all_active=true, then use the canonical Campaign V2 rows plus the operator's wording and conversation context to choose the relevant campaign. If a portfolio read was used, read the chosen campaign again with its campaign_id before creative execution so the selected context is bound to the turn. Ask the operator only if the campaign remains genuinely ambiguous. Do not use keyword labels or hardcoded audience mappings. On an affirmative reply, call postcraft_render directly with render_approved=true, approved_draft=true, image_quality="high", and the approved fields/text after campaign alignment is loaded. Never call postcraft_draft or postcraft_create for this CMO chat workflow. Never call postcraft_render before approval.
- POSTCRAFT TEMPLATES: Brand templates come only from the approved Brand Kit template manifest. Do not offer fallback layout-family choices or ask the operator to pick a template. In the chat draft, `Template:` is only a creative-direction label. For ordinary approved social posts, call postcraft_render without `template_id` or `auto_select_template` and let the renderer create an original composition. Only pass those fields when the operator explicitly requests an approved Brand Kit template; then a missing or invalid template is a real blocker.
- When the operator asks what social-post design/templates are available, answer from "Postcraft Approved Templates" in context. If it is 0, say no approved social-post design templates are loaded yet. You may suggest a creative direction from brand colors/voice, but label it as a proposed direction, not as an available/loaded template.
- For poster-style social images, minimal-text overlays, or requests that explicitly say hook/CTA only, keep the copy sparse. Prefer one short hook in Headline, leave Subheadline and Body copy blank unless truly needed, and keep CTA to 1–4 words. Do not expand into extra audience strategy or long copy when the operator asked for a visually led poster.
- IMPORTANT: video, storyboard, screenplay, reel, shot list, and 15-second ad requests are NOT social media post images. Never call postcraft tools for video/storyboard work. Those go through the storyboard pipeline only.
- For social image/post requests, do not ask for headline/theme/CTA just because they were omitted. Infer a safe first draft from the brand, product/offer, audience, and selected campaign context. Ask only when a required business fact is truly missing.
- CRITICAL — VIDEO/STORYBOARD WORKFLOW: When the operator asks for a video, storyboard, screenplay, reel, shot list, or 15-second ad, you MUST respond with the full FINAL script as a plain text reply in ONE message. NO tool calls. NO concept drafts. NO "shall I proceed" or "here's a concept" preambles. NO asking for scenes, visuals, or branding details. Write the complete final script immediately using the loaded brand, product/offer, audience, and campaign context. The operator will read and react. If the operator's reply is affirmative ("yes", "good", "good enough", "looks good", "proceed", "go", "use that", "fine", "great", "perfect", "love it", or any other clear approval), call storyboard_render with the approved text. Never call storyboard_render on the initial request — only after operator approval. If the operator asks for revisions, stream the revised script as a text reply (no tool call) and wait for approval again.
- Attached JSON/image references are automatically passed to tools as structured context. For image edits, use edit_instruction and rely on the attached/source image context; do not ask the operator to re-upload or describe it again.
- Generated reviewable assets appear in Stream for operator review. Do not tell the user they are going to Workspace.
- Recommend or draft one next action at a time. Do not invent external publishing/sending/budget changes without explicit operator approval.

When calling a tool, provide the brief with the fields the tool needs. Be specific and complete.
When iterating on previous work, carry forward all fields from the prior call — changing only what the operator asked to change.
When you cannot proceed without operator input, stop and state exactly what you need and why.

Be direct, but do not over-compress open-ended campaign discussion. Use brief replies for simple status checks; use a fuller CMO explanation when the operator asks to talk, discuss, diagnose, or get your point of view."""


# ── Runtime context ──────────────────────────────────────────────────────────

async def load_brand_name(db: AsyncSession, brand_id: str | None) -> str:
    if not brand_id:
        return ""
    try:
        buuid = UUID(brand_id)
    except (ValueError, TypeError):
        return ""
    from models.workspace import Brand
    from sqlalchemy import select
    brand = (await db.execute(select(Brand).where(Brand.id == buuid))).scalar_one_or_none()
    return brand.name if brand else ""


async def load_campaign_goal(
    db: AsyncSession,
    campaign_id: str | None,
    workspace_id: UUID | str | None = None,
    brand_id: UUID | str | None = None,
) -> str:
    """Return a compact campaign label from Campaign V2/container fields only."""
    if not campaign_id:
        return ""
    try:
        cid = UUID(str(campaign_id))
        wid = UUID(str(workspace_id)) if workspace_id else None
        bid = UUID(str(brand_id)) if brand_id else None
    except (ValueError, TypeError):
        return ""
    from campaign import db as campaign_db

    rows = await campaign_db.rows_for_campaign(db, cid, limit=1)
    if not rows:
        return ""
    row = rows[0]
    if wid and row.workspace_id and row.workspace_id != wid:
        return ""
    if bid and row.brand_id and row.brand_id != bid:
        return ""

    for value in (row.planned_activity, row.what_changed, row.next_action, row.actual_activity, row.business_objective, row.campaign):
        if value:
            return str(value)
    raw = row.raw_payload if isinstance(row.raw_payload, dict) else {}
    cj = raw.get("campaign_json") if isinstance(raw.get("campaign_json"), dict) else raw
    if isinstance(cj, dict):
        for key in ("business_objective", "objective", "goal", "initial_intent", "full_message_angle", "message_angle"):
            if cj.get(key):
                return str(cj.get(key))
    return row.campaign or ""


# ── Execution ────────────────────────────────────────────────────────────────

async def _inject_drive_credentials(
    brief: dict,
    brand_id: UUID,
    db: AsyncSession,
    settings,
) -> dict:
    """Inject Google Drive token and root folder from the google.drive plugin.

    Resolves the brand's Drive connection via SocialConnection, reads the
    stored token and drive_root_folder_id, and merges them into
    _channel_credentials. Modules read these keys without knowing where
    they came from.
    """
    from models.social import SocialConnection
    from routers.social import get_page_token

    token, _ = await get_page_token(db, str(brand_id), "google_drive", settings)
    if not token:
        return brief

    conn = (await db.execute(
        select(SocialConnection).where(
            SocialConnection.brand_id == brand_id,
            SocialConnection.platform == "google_drive",
            SocialConnection.status == "connected",
        ).order_by(SocialConnection.created_at.desc()).limit(1)
    )).scalar_one_or_none()

    if not conn:
        return brief

    meta = conn.token_meta_json or {}
    root_id = str(meta.get("drive_root_folder_id") or "").strip()
    root_name = str(meta.get("drive_root_name") or "").strip()

    creds = dict(brief.get("_channel_credentials") or {})
    creds["google_drive_page_token"] = token
    creds["access_token"] = token
    creds["page_token"] = token
    if root_id:
        creds["drive_root_folder_id"] = root_id
    if root_name:
        creds["drive_root_name"] = root_name

    return {**brief, "_channel_credentials": creds}



async def _brand_kit_for_tool(db: AsyncSession, brand_id: UUID | None) -> dict:
    """Small brand kit injected into native tool briefs.

    The system prompt gives the LLM brand context, but tools like postcraft need
    structured brand fields in their brief. Keep this lightweight; the brand
    scaffold remains the full prompt context.

    Also resolves brand_spec (logo_drive_file_id, drive_root_folder_id) from the
    brand's Google Drive SocialConnection imprint_asset_validation, so Postcraft
    can find the official logo without a separate workspace document.
    """
    if not brand_id:
        return {}
    from models.workspace import Brand
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        return {}
    bj = brand.brand_json or {}

    # Resolve brand_spec (logo + drive root) from the Drive social connection.
    # This bridges the gap between onboarding's imprint_asset_validation and
    # Postcraft's brand_spec.logo_drive_file_id requirement.
    brand_spec: dict = {}
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
            meta = conn.token_meta_json or {}
            from services.brand_kit import _brand_spec_from_asset_metadata
            brand_spec.update(_brand_spec_from_asset_metadata(meta))
            drive_root = str(meta.get("drive_root_folder_id") or "").strip()
            drive_name = str(meta.get("drive_root_name") or "").strip()
            validation = meta.get("imprint_asset_validation") if isinstance(meta.get("imprint_asset_validation"), dict) else {}
            logo_files = validation.get("logo_files") or []
            first_logo = next((f for f in logo_files if isinstance(f, dict) and f.get("id")), None)
            if drive_root:
                brand_spec["drive_root_folder_id"] = drive_root
            if drive_name:
                brand_spec["drive_root_name"] = drive_name
            if first_logo:
                brand_spec["logo_drive_file_id"] = str(first_logo.get("id") or "")
                brand_spec["logo_file_name"] = str(first_logo.get("name") or "")
    except Exception:
        logger.debug("Could not resolve brand_spec from Drive connection for brand %s", brand_id, exc_info=True)

    # Fallback: onboarding stores validated Brand Kit asset metadata on the
    # campaign_brand_kit WorkspaceDocument. Bridge that metadata into the
    # Postcraft brand_spec shape when Drive metadata is incomplete/stale.
    if not brand_spec.get("logo_drive_file_id") or not brand_spec.get("drive_root_folder_id"):
        try:
            kit_doc = (await db.execute(
                select(WorkspaceDocument)
                .where(
                    WorkspaceDocument.brand_id == brand_id,
                    WorkspaceDocument.doc_type == "campaign_brand_kit",
                )
                .order_by(WorkspaceDocument.updated_at.desc())
                .limit(1)
            )).scalar_one_or_none()
            kit_meta = kit_doc.metadata_json if kit_doc and isinstance(kit_doc.metadata_json, dict) else {}
            if kit_meta.get("drive_root_folder_id") and not brand_spec.get("drive_root_folder_id"):
                brand_spec["drive_root_folder_id"] = str(kit_meta.get("drive_root_folder_id") or "")
            if kit_meta.get("drive_root_name") and not brand_spec.get("drive_root_name"):
                brand_spec["drive_root_name"] = str(kit_meta.get("drive_root_name") or "")
            if kit_meta.get("brand_mark_file_id") and not brand_spec.get("logo_drive_file_id"):
                brand_spec["logo_drive_file_id"] = str(kit_meta.get("brand_mark_file_id") or "")
            if kit_meta.get("brand_mark_file_name") and not brand_spec.get("logo_file_name"):
                brand_spec["logo_file_name"] = str(kit_meta.get("brand_mark_file_name") or "")
        except Exception:
            logger.debug("Could not resolve brand_spec from campaign_brand_kit metadata for brand %s", brand_id, exc_info=True)

    result = {
        "brand_id": str(brand.id),
        "brand_name": brand.name,
        "name": brand.name,
        "tone": bj.get("tone") or bj.get("brand_tone"),
        "voice": bj.get("voice"),
        "values": bj.get("values") or [],
        "color_palette": bj.get("color_palette") or bj.get("colors") or {},
        "visual_tone": bj.get("visual_language") or bj.get("visual_tone") or bj.get("tone") or [],
        "visual_language": bj.get("visual_language") or bj.get("visual_tone") or [],
        "typography": bj.get("typography") or {},
        "mandatory_treatments": bj.get("mandatory_treatments") or [],
        "negative_prompts": bj.get("negative_prompts") or [],
    }
    if brand_spec:
        result["brand_spec"] = brand_spec
    return result


def _safe_brief_for_trace(brief: dict | None) -> dict | None:
    """Return a prompt/debug copy with credentials and large inline assets removed."""
    if not isinstance(brief, dict):
        return None
    large = {"image_data_b64", "source_image_data_b64", "vision_b64", "video_b64"}
    out: dict[str, Any] = {}
    for k, v in brief.items():
        if k == "_channel_credentials":
            continue
        if k in large and isinstance(v, str) and v:
            out[k] = "[omitted]"
        elif isinstance(v, list):
            next_items = []
            for item in v[:8]:
                if isinstance(item, dict):
                    next_items.append({ik: ("[omitted]" if ik in large and isinstance(iv, str) and iv else iv) for ik, iv in item.items()})
                else:
                    next_items.append(item)
            out[k] = next_items
        else:
            out[k] = v
    return out


def _run_block(response) -> dict:
    block = getattr(getattr(response, "result", None), "block", None)
    return block if isinstance(block, dict) else {}


def preflight_tool_call(
    tool_name: str,
    tool_args: dict,
    tools: dict,
    extra_brief: dict | None = None,
    campaign_id: UUID | None = None,
) -> dict | None:
    """Validate tool inputs before execution. Returns an error dict for inline
    LLM feedback, or None if the call should proceed to execution.

    Preflight failures are NOT persisted as Runs — they are returned as tool
    feedback so the LLM can correct its call in the same turn.
    """
    # campaign_read is read-only. If no live campaign is selected and the model
    # did not explicitly name a campaign, read the active brand portfolio instead
    # of relying on keyword/phrase gates such as "what campaigns" or "where are
    # we". Mutating Campaign tools still require one resolved campaign.
    if tool_name == "campaign_read":
        requested_campaign = str((tool_args or {}).get("campaign_id") or "").strip().lower()
        if (
            not campaign_id
            and not (tool_args or {}).get("all_active")
            and requested_campaign not in {"all", "both", "active"}
        ):
            tool_args["all_active"] = True
            if not requested_campaign:
                tool_args["campaign_id"] = "all"

    # storyboard_render: must have storyboard_text
    if tool_name == "storyboard_render":
        storyboard_text = str((tool_args or {}).get("storyboard_text") or "").strip()
        if not storyboard_text:
            return {
                "tool": tool_name,
                "input": tool_args,
                "status": "failed",
                "latency_ms": 0,
                "error": "storyboard_text is required. You must pass the full approved storyboard script from the conversation. If the operator just approved a script you wrote earlier, include it verbatim as storyboard_text.",
            }
        if len(storyboard_text) < 50:
            return {
                "tool": tool_name,
                "input": tool_args,
                "status": "failed",
                "latency_ms": 0,
                "error": f"storyboard_text is too short ({len(storyboard_text)} chars). Pass the full approved script (at least 50 characters) that you wrote earlier in the conversation.",
            }

    # postcraft_render: CMO chat uses text approval first, then direct render.
    # Do not let an initial social-post request create a Postcraft draft artifact.
    if tool_name == "postcraft_render":
        args = tool_args or {}
        approved = (
            args.get("render_approved") is True
            or args.get("approved_draft") is True
            or str(args.get("approval_status") or "").lower() == "approved"
            or str(args.get("action") or args.get("artifact_action") or "").lower() in {"render", "render_approved", "revise"}
            or bool(args.get("source_run_id") or args.get("revision_prompt") or args.get("edit_instruction"))
        )
        if not approved:
            return {
                "tool": tool_name,
                "input": tool_args,
                "status": "failed",
                "latency_ms": 0,
                "error": "Do not call postcraft_render on the initial social-post request. First write the complete social image creative in chat for operator approval. After approval, call postcraft_render with render_approved=true, approved_draft=true, image_quality='high', and the approved copy fields/text.",
            }

    return None


def _tool_result_from_run_response(
    tool_name: str,
    tool_args: dict,
    tool_def: dict,
    response,
    start: float,
    *,
    prompt_brief: dict | None = None,
) -> dict:
    """Convert canonical RunResponse/RunActionResponse output to CMO tool state."""
    latency = round((time.perf_counter() - start) * 1000)
    block = _run_block(response)
    block_status = str(block.get("status") or "").lower()
    quality_gate = block.get("quality_gate") if isinstance(block.get("quality_gate"), dict) else {}
    quality_warnings = quality_gate.get("warnings") if isinstance(quality_gate.get("warnings"), list) else []
    failed = (
        getattr(response, "status", None) == "failed"
        or getattr(response, "approval_status", None) == "failed"
        or block_status == "failed"
    )
    needs_revision = block_status == "needs_revision" or (quality_gate and quality_gate.get("ok") is False)
    if needs_revision and quality_warnings:
        summary = "Quality gate failed; retry this tool with a full production-ready storyboard body. " + "; ".join(str(w) for w in quality_warnings[:6])
    elif block.get("type") == "meta_page_insights_report":
        page = block.get("page") if isinstance(block.get("page"), dict) else {}
        metrics = block.get("metrics_overview") if isinstance(block.get("metrics_overview"), dict) else {}
        bullets = block.get("insight_bullets") if isinstance(block.get("insight_bullets"), list) else []
        not_available = block.get("not_available") if isinstance(block.get("not_available"), list) else []
        bullet_text = " | ".join(
            f"{b.get('insight')} ({b.get('confidence', 'unknown')} confidence; {b.get('coverage', 'coverage unknown')})"
            for b in bullets[:4]
            if isinstance(b, dict) and b.get("insight")
        )
        summary = (
            f"Read-only Meta insight artifact for {page.get('name') or 'the connected page'}: "
            f"scope={block.get('report_scope') or 'channel_snapshot'}; "
            f"coverage={block.get('coverage_label') or 'reported'}; "
            f"metrics_overview={{followers:{metrics.get('followers', page.get('followers', 'unknown'))}, "
            f"scheduled_posts:{metrics.get('scheduled_posts', len(block.get('scheduled_posts') or []))}, "
            f"recent_posts:{metrics.get('recent_posts', len(block.get('recent_posts') or []))}, "
            f"insight_metrics:{metrics.get('insight_metrics_reported', len(block.get('insights') or []))}}}; "
            f"insights=[{bullet_text or 'none generated'}]; "
            f"not_available=[{'; '.join(str(x) for x in not_available[:4]) or 'none reported'}]; "
            f"next={block.get('recommended_next_step') or 'review the artifact'}."
        )
    else:
        summary = (block.get("message") if failed else None) or f"{tool_def.get('label', tool_name)} completed."
    image_b64 = block.get("image_data_b64") if isinstance(block, dict) else None
    execution = getattr(response, "execution", None)
    return {
        "tool": tool_name,
        "input": tool_args,
        "status": "failed" if failed else ("needs_revision" if needs_revision else "succeeded"),
        "latency_ms": latency,
        "summary": summary,
        "run_id": getattr(response, "run_id", None),
        "module_id": getattr(response, "module_id", None),
        "artifact_title": block.get("display_title") or block.get("title") or block.get("message"),
        "artifact_type": block.get("artifact_type") or block.get("type"),
        "reason_code": block.get("reason_code") or ("storyboard_quality_gate_failed" if needs_revision and quality_warnings else None),
        "quality_gate": quality_gate or None,
        "preflight_checklist": block.get("preflight_checklist"),
        "setup_links": block.get("setup_links"),
        "image_b64": image_b64,
        "mime_type": block.get("mime_type"),
        "provider": getattr(execution, "provider", None) if execution else None,
        "report_content": getattr(getattr(response, "result", None), "content", None)[:3000] if block.get("type") == "meta_page_insights_report" and getattr(getattr(response, "result", None), "content", None) else None,
        "prompt_used": json.dumps(_safe_brief_for_trace(prompt_brief), ensure_ascii=False) if prompt_brief else None,
        **({"error": block.get("message") or "Execution failed"} if failed else {}),
    }


async def _execute_artifact_action_tool(
    tool_name: str,
    tool_args: dict,
    db: AsyncSession,
    settings,
    start: float,
) -> dict:
    source_run_id = str((tool_args or {}).get("source_run_id") or (tool_args or {}).get("run_id") or "").strip()
    action = str((tool_args or {}).get("action") or "").strip()
    confirm = bool((tool_args or {}).get("confirm"))
    overrides = dict((tool_args or {}).get("overrides") or {}) if isinstance((tool_args or {}).get("overrides"), dict) else {}
    notes = str((tool_args or {}).get("notes") or "").strip()
    if notes:
        overrides.setdefault("edit_instruction", notes)
        overrides.setdefault("approval_notes", notes)
        overrides.setdefault("video_generation_notes", notes)
    if not source_run_id or not action:
        latency = round((time.perf_counter() - start) * 1000)
        return {"tool": tool_name, "input": tool_args, "status": "failed", "latency_ms": latency, "error": "source_run_id and action are required"}
    if not confirm:
        latency = round((time.perf_counter() - start) * 1000)
        return {"tool": tool_name, "input": tool_args, "status": "failed", "latency_ms": latency, "error": "confirm=true is required for artifact actions"}
    try:
        from routers.runs import execute_declared_run_action

        action_response = await execute_declared_run_action(db, source_run_id, action, settings, overrides)
        tool_def = {"label": f"Artifact action {action}"}
        result = _tool_result_from_run_response(tool_name, tool_args, tool_def, action_response.action_run, start, prompt_brief=overrides)
        result["source_run_id"] = source_run_id
        result["action"] = action
        result["source_approval_status"] = action_response.source_approval_status
        return result
    except HTTPException as exc:
        latency = round((time.perf_counter() - start) * 1000)
        detail = exc.detail if isinstance(exc.detail, str) else json.dumps(exc.detail, ensure_ascii=False)
        return {"tool": tool_name, "input": tool_args, "status": "failed", "latency_ms": latency, "error": detail}
    except BosError as exc:
        latency = round((time.perf_counter() - start) * 1000)
        return {"tool": tool_name, "input": tool_args, "status": "failed", "latency_ms": latency, "error": exc.message}
    except Exception as exc:
        latency = round((time.perf_counter() - start) * 1000)
        logger.exception("Artifact action tool failed")
        return {"tool": tool_name, "input": tool_args, "status": "failed", "latency_ms": latency, "error": str(exc)}


async def _execute_revise_artifact_tool(
    tool_name: str,
    tool_args: dict,
    db: AsyncSession,
    settings,
    start: float,
    *,
    extra_brief: dict | None = None,
) -> dict:
    source_run_id = str((tool_args or {}).get("source_run_id") or (tool_args or {}).get("run_id") or "").strip()
    feedback = str(
        (tool_args or {}).get("feedback")
        or (tool_args or {}).get("revision_prompt")
        or (tool_args or {}).get("edit_instruction")
        or ""
    ).strip()
    if not source_run_id or not feedback:
        latency = round((time.perf_counter() - start) * 1000)
        return {"tool": tool_name, "input": tool_args, "status": "failed", "latency_ms": latency, "error": "source_run_id and feedback are required"}

    try:
        from routers.runs import _execute_module
        from routers.workspace import get_singleton

        run_uuid = UUID(source_run_id)
        row = (await db.execute(
            select(Run, RunResult, RunTrace)
            .join(RunResult, RunResult.run_id == Run.id, isouter=True)
            .join(RunTrace, RunTrace.run_id == Run.id, isouter=True)
            .where(Run.id == run_uuid)
        )).one_or_none()
        if not row:
            latency = round((time.perf_counter() - start) * 1000)
            return {"tool": tool_name, "input": tool_args, "status": "failed", "latency_ms": latency, "error": "Run not found"}
        source_run, source_result, source_trace = row
        block = ((source_trace.lineage_json or {}).get("block") if source_trace else None) or {}
        if not isinstance(block, dict):
            block = {}
        allowed = block.get("allowed_actions") if isinstance(block.get("allowed_actions"), list) else []
        modules = block.get("action_modules") if isinstance(block.get("action_modules"), dict) else {}
        revise_module_id = modules.get("revise") if "revise" in allowed else None
        if not revise_module_id:
            latency = round((time.perf_counter() - start) * 1000)
            return {"tool": tool_name, "input": tool_args, "status": "failed", "latency_ms": latency, "error": "Artifact does not declare a revise action"}

        ws = await get_singleton(db)
        if not ws:
            latency = round((time.perf_counter() - start) * 1000)
            return {"tool": tool_name, "input": tool_args, "status": "failed", "latency_ms": latency, "error": "Workspace not initialized"}

        skip = {"allowed_actions", "action_modules", "status", "message", "content"}
        brief = {k: v for k, v in block.items() if k not in skip and not str(k).startswith("_")}
        if extra_brief:
            extra_refs = extra_brief.get("reference_images") if isinstance(extra_brief.get("reference_images"), list) else []
            for k, v in extra_brief.items():
                if k == "reference_images":
                    continue
                if k not in brief and v not in (None, "", [], {}):
                    brief[k] = v
            if extra_refs:
                existing_refs = brief.get("reference_images") if isinstance(brief.get("reference_images"), list) else []
                tagged_refs = []
                for idx, ref in enumerate(extra_refs, start=1):
                    if not isinstance(ref, dict):
                        continue
                    tagged = dict(ref)
                    tagged.setdefault("revision_reference", True)
                    tagged.setdefault("priority", "operator_revision")
                    tagged.setdefault("source", "operator_attachment")
                    tagged.setdefault("role", "unknown_revision_reference")
                    tagged.setdefault("panel_label", f"OPERATOR REVISION REF {idx} — use according to revision instruction")
                    tagged_refs.append(tagged)
                brief["reference_images"] = tagged_refs + [r for r in existing_refs if isinstance(r, dict)]
        # Preserve module-specific revision fields when the LLM calls a module's
        # native revise action directly (e.g. postcraft_render with
        # source_run_id + revision_prompt) instead of the generic revise_artifact
        # wrapper. The generic layer still owns source lookup and parent linkage,
        # but the module receives updated copy/layout fields if the caller sent
        # them.
        passthrough_keys = {
            "postcraft_text", "approved_post_text", "creative_text", "headline",
            "subheadline", "body_copy", "body", "cta_text", "cta", "template_type",
            "post_format", "location", "image_quality", "quality",
            "render_approved", "approved_draft", "approval_status",
        }
        for k in passthrough_keys:
            v = (tool_args or {}).get(k)
            if v not in (None, "", [], {}):
                brief[k] = v

        brief.update({
            "source_run_id": source_run_id,
            "edit_instruction": feedback,
            "revision_prompt": feedback,
            "revision_feedback": feedback,
            "previous_content": source_result.content if source_result else "",
            # json-imagen rule: revision modules need the previous artifact state
            # as structured input, not only a flattened updated prompt.
            "original_artifact_block": block,
            "artifact_data": block,
        })
        if block.get("image_data_b64") and "source_image_data_b64" not in brief:
            brief["source_image_data_b64"] = block.get("image_data_b64")
        if block.get("output_path") and "source_image_path" not in brief:
            brief["source_image_path"] = block.get("output_path")

        response = await _execute_module(
            db, ws, str(revise_module_id), brief, settings,
            campaign_id=source_run.campaign_id,
            brand_id=source_run.brand_id,
        )
        new_run = (await db.execute(select(Run).where(Run.id == UUID(response.run_id)))).scalar_one_or_none()
        if new_run:
            new_run.parent_run_id = source_run.id
            await db.commit()

        tool_def = {"label": "Revise artifact"}
        result = _tool_result_from_run_response(tool_name, tool_args, tool_def, response, start, prompt_brief=brief)
        result["source_run_id"] = source_run_id
        result["action"] = "revise"
        return result
    except (ValueError, TypeError):
        latency = round((time.perf_counter() - start) * 1000)
        return {"tool": tool_name, "input": tool_args, "status": "failed", "latency_ms": latency, "error": "Invalid source_run_id"}
    except HTTPException as exc:
        latency = round((time.perf_counter() - start) * 1000)
        detail = exc.detail if isinstance(exc.detail, str) else json.dumps(exc.detail, ensure_ascii=False)
        return {"tool": tool_name, "input": tool_args, "status": "failed", "latency_ms": latency, "error": detail}
    except BosError as exc:
        latency = round((time.perf_counter() - start) * 1000)
        return {"tool": tool_name, "input": tool_args, "status": "failed", "latency_ms": latency, "error": exc.message}
    except Exception as exc:
        latency = round((time.perf_counter() - start) * 1000)
        logger.exception("Revise artifact tool failed")
        return {"tool": tool_name, "input": tool_args, "status": "failed", "latency_ms": latency, "error": str(exc)}


def _normalized_operator_message(extra_brief: dict | None) -> str:
    raw = ""
    if isinstance(extra_brief, dict):
        raw = str(extra_brief.get("_operator_message") or "")
    text = raw.strip().lower().replace("_", " ")
    return re.sub(r"\s+", " ", text)


async def _execute_campaign_tool(
    tool_name: str,
    tool_args: dict,
    db: AsyncSession,
    start: float,
    *,
    brand_id: UUID | None,
    workspace_id: UUID | None,
    session_campaign_id: UUID | None,
    extra_brief: dict | None = None,
) -> dict:
    """Execute Campaign table access through campaign/db.py.

    CMO does not own Campaign storage logic. Campaign is a dated table with
    direct DB read/write/edit helpers; this function is only a caller adapter.
    """
    from campaign import db as campaign_db

    latency = lambda: round((time.perf_counter() - start) * 1000)
    args = tool_args or {}

    def int_arg(name: str):
        value = args.get(name)
        if value in (None, "", [], {}):
            return None
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None

    def metric_bits(row) -> list[str]:
        bits: list[str] = []
        for key in ("primary_kpi", "actual", "reach_metric", "engagement_metric", "action_metric", "efficiency_metric", "value_metric"):
            value = getattr(row, key, None)
            if value not in (None, "", [], {}):
                bits.append(f"{key}={value}")
        for key in ("reach", "impressions", "engagement", "clicks", "leads", "calls", "qualified_calls", "conversions", "spend", "revenue"):
            value = getattr(row, key, None)
            if value is not None:
                bits.append(f"{key}={value}")
        return bits

    try:
        if tool_name == "campaign_create":
            if not brand_id:
                return {"tool": tool_name, "input": tool_args, "status": "failed", "latency_ms": latency(), "error": "No active brand. Ask the operator which brand first."}
            name = _clip(str(args.get("name") or "").strip(), 255)
            if not name:
                return {"tool": tool_name, "input": tool_args, "status": "failed", "latency_ms": latency(), "error": "name is required."}
            if not workspace_id:
                return {"tool": tool_name, "input": tool_args, "status": "failed", "latency_ms": latency(), "error": "Workspace is not initialized."}
            campaign_json = dict(args.get("campaign_json") or {}) if isinstance(args.get("campaign_json"), dict) else {}
            if args.get("initial_intent"):
                campaign_json["initial_intent"] = args.get("initial_intent")
            row = await campaign_db.create_campaign_record(db, {
                "workspace_id": workspace_id,
                "brand_id": brand_id,
                "name": name,
                "status": str(args.get("status") or "active").strip().lower() or "active",
                "objective_id": UUID(str(args.get("objective_id"))) if args.get("objective_id") else None,
                "audience": args.get("audience"),
                "message_angle": args.get("message_angle"),
                "campaign_json": campaign_json,
            })
            return {"tool": tool_name, "input": tool_args, "status": "succeeded", "latency_ms": latency(), "summary": f"Created Campaign table row '{row.campaign}'.", "campaign_id": str(campaign_db.campaign_key(row)), "row": campaign_db.row_dict(row)}

        if tool_name == "campaign_patch":
            row_id = args.get("row_id") or args.get("snapshot_id")
            try:
                rid = UUID(str(row_id))
            except (TypeError, ValueError):
                return {"tool": tool_name, "input": tool_args, "status": "failed", "latency_ms": latency(), "error": "row_id is not a valid UUID."}
            allowed = {"source_health", "freshness", "verification_status", "objective_verdict", "confidence", "primary_kpi", "actual", "reach_metric", "engagement_metric", "action_metric", "efficiency_metric", "value_metric", "what_changed", "top_learning", "recommended_action", "note", "blocker", "decision_needed", "owner", "next_action"}
            updates = {k: v for k, v in args.items() if k in allowed and v not in ([], {})}
            if not updates:
                return {"tool": tool_name, "input": tool_args, "status": "failed", "latency_ms": latency(), "error": "No Campaign row fields supplied to edit."}
            row = await campaign_db.edit_row(
                db, rid, updates, workspace_id=workspace_id, brand_id=brand_id
            )
            if not row:
                return {"tool": tool_name, "input": tool_args, "status": "failed", "latency_ms": latency(), "error": "Campaign row not found for the active workspace/brand."}
            return {"tool": tool_name, "input": tool_args, "status": "succeeded", "latency_ms": latency(), "summary": f"Edited Campaign row {row.id}: " + ", ".join(sorted(updates)), "campaign_id": str(campaign_db.campaign_key(row)), "row_id": str(row.id), "row": campaign_db.row_dict(row)}

        if tool_name in {"campaign_append", "campaign_act"}:
            if not brand_id:
                return {"tool": tool_name, "input": tool_args, "status": "failed", "latency_ms": latency(), "error": "No active brand. Ask the operator which brand first."}
            if not workspace_id:
                return {"tool": tool_name, "input": tool_args, "status": "failed", "latency_ms": latency(), "error": "Workspace is not initialized."}
            requested = args.get("campaign_id") or session_campaign_id
            campaign_id = None
            if requested:
                try:
                    campaign_id = UUID(str(requested))
                except (TypeError, ValueError):
                    return {"tool": tool_name, "input": tool_args, "status": "failed", "latency_ms": latency(), "error": "campaign_id is not a valid UUID."}
            else:
                active = await campaign_db.active_campaigns(
                    db, workspace_id=workspace_id, brand_id=brand_id, limit=2
                )
                if len(active) != 1:
                    error = "No active Campaign exists. Create one first." if not active else "Multiple active Campaigns exist. Select one before writing."
                    return {"tool": tool_name, "input": tool_args, "status": "failed", "latency_ms": latency(), "error": error}
                campaign_id = active[0].id
            campaign = await campaign_db.get_campaign_record(
                db, campaign_id, workspace_id=workspace_id, brand_id=brand_id
            )
            if not campaign:
                return {"tool": tool_name, "input": tool_args, "status": "failed", "latency_ms": latency(), "error": "Campaign not found for the active workspace/brand."}
            raw_payload = args.get("raw_payload") if isinstance(args.get("raw_payload"), dict) else {k: v for k, v in args.items() if v not in (None, "", [], {}) and k != "evidence_refs"}
            evidence_refs = args.get("evidence_refs") if isinstance(args.get("evidence_refs"), list) else ([str(args.get("source_ref"))] if args.get("source_ref") else [])
            description = str(args.get("description") or args.get("next_action") or "").strip()
            row = await campaign_db.append_campaign_row(db, campaign_id, {
                "workspace_id": workspace_id,
                "brand_id": brand_id,
                "campaign": args.get("campaign"),
                "period_type": args.get("period_type") or ("action" if tool_name == "campaign_act" else None),
                "time_period": args.get("time_period") or ("next_action" if tool_name == "campaign_act" else None),
                "period_start": args.get("period_start"),
                "period_end": args.get("period_end"),
                "distribution_channel": args.get("distribution_channel"),
                "channel_role": args.get("channel_role"),
                "market": args.get("market"),
                "primary_kpi": args.get("primary_kpi"),
                "actual": args.get("actual"),
                "planned_activity": args.get("planned_activity"),
                "actual_activity": args.get("actual_activity") or (str(args.get("action_type") or "campaign_action") if tool_name == "campaign_act" else None),
                "reach": int_arg("reach"),
                "impressions": int_arg("impressions"),
                "engagement": int_arg("engagement"),
                "reach_metric": args.get("reach_metric"),
                "engagement_metric": args.get("engagement_metric"),
                "action_metric": args.get("action_metric"),
                "efficiency_metric": args.get("efficiency_metric"),
                "value_metric": args.get("value_metric"),
                "clicks": int_arg("clicks"),
                "leads": int_arg("leads"),
                "calls": int_arg("calls"),
                "qualified_calls": int_arg("qualified_calls"),
                "conversions": int_arg("conversions"),
                "spend": args.get("spend"),
                "budget": args.get("budget"),
                "revenue": args.get("revenue"),
                "source_type": f"cmo_tool.{tool_name}",
                "source_ref": args.get("source_ref") or f"cmo_tool:{tool_name}",
                "producer": args.get("producer") or "cmo_chat",
                "source_health": args.get("source_health") or "reported",
                "freshness": args.get("freshness"),
                "verification_status": args.get("verification_status") or "producer_reported",
                "objective_verdict": args.get("objective_verdict"),
                "confidence": args.get("confidence") or "medium",
                "what_changed": args.get("what_changed") or (f"Campaign action recorded: {description}" if description else None),
                "top_learning": args.get("top_learning"),
                "recommended_action": args.get("recommended_action"),
                "note": args.get("note"),
                "blocker": args.get("blocker"),
                "decision_needed": args.get("decision_needed"),
                "owner": args.get("owner"),
                "next_action": description or args.get("next_action"),
                "evidence_refs": evidence_refs,
                "raw_payload": raw_payload,
            })
            return {"tool": tool_name, "input": tool_args, "status": "succeeded", "latency_ms": latency(), "summary": f"Campaign row written: {row.time_period or 'latest'} / {row.distribution_channel or 'unspecified'}; verdict={row.objective_verdict}; source={row.source_health}; verification={row.verification_status}.", "campaign_id": str(campaign_db.campaign_key(row)), "row_id": str(row.id), "row": campaign_db.row_dict(row)}

        if tool_name == "campaign_read":
            if not workspace_id:
                return {"tool": tool_name, "input": tool_args, "status": "failed", "latency_ms": latency(), "error": "Workspace is not initialized."}
            if not brand_id:
                return {"tool": tool_name, "input": tool_args, "status": "failed", "latency_ms": latency(), "error": "No active brand. Ask the operator which brand first."}
            limit = int(args.get("limit") or 20)
            requested = args.get("campaign_id") or session_campaign_id
            campaign_id = None
            status = None
            broad_read = bool(args.get("all_active")) or str(requested or "").strip().lower() in {"all", "both", "active"}
            if requested and not broad_read:
                try:
                    campaign_id = UUID(str(requested))
                except (TypeError, ValueError):
                    return {"tool": tool_name, "input": tool_args, "status": "failed", "latency_ms": latency(), "error": "campaign_id is not a valid UUID."}
                campaign = await campaign_db.get_campaign_record(
                    db, campaign_id, workspace_id=workspace_id, brand_id=brand_id
                )
                if not campaign:
                    return {"tool": tool_name, "input": tool_args, "status": "failed", "latency_ms": latency(), "error": "Campaign not found for the active workspace/brand."}
            elif broad_read:
                status = "active"
            else:
                return {"tool": tool_name, "input": tool_args, "status": "failed", "latency_ms": latency(), "error": "Select a Campaign or set all_active=true."}
            if status == "active":
                active = await campaign_db.active_campaigns(
                    db, workspace_id=workspace_id, brand_id=brand_id, limit=100
                )
                rows = []
                for campaign in active:
                    rows.extend(await campaign_db.rows_for_campaign(
                        db,
                        campaign.id,
                        workspace_id=workspace_id,
                        brand_id=brand_id,
                        limit=limit,
                    ))
            else:
                rows = await campaign_db.rows_for_campaign(
                    db,
                    campaign_id,
                    workspace_id=workspace_id,
                    brand_id=brand_id,
                    limit=limit,
                )
            groups: dict[str, list[Any]] = {}
            for row in rows:
                groups.setdefault(str(campaign_db.campaign_key(row)), []).append(row)
            summaries: list[str] = []
            for cid, group in groups.items():
                first = group[0]
                lines = []
                for row in group[:limit]:
                    bits = [str(x) for x in (row.time_period, row.distribution_channel) if x]
                    note = row.top_learning or row.recommended_action or row.note or row.what_changed or row.next_action or row.planned_activity or 'no note'
                    lines.append(f"  - {' / '.join(bits) or 'latest'}: {', '.join(metric_bits(row)) or 'metrics not reported'}; source={row.source_health}; verification={row.verification_status}; verdict={row.objective_verdict}; {note}")
                summaries.append(f"- {first.campaign or 'Campaign'} ({first.status}; id={cid}):\n" + "\n".join(lines))
            summary = f"Campaign rows ({len(groups)} campaigns, {len(rows)} rows):\n" + ("\n".join(summaries) if summaries else "No Campaign rows found.")
            return {"tool": tool_name, "input": tool_args, "status": "succeeded", "latency_ms": latency(), "summary": summary, "rows": [campaign_db.row_dict(row) for row in rows]}

        return {"tool": tool_name, "input": tool_args, "status": "failed", "latency_ms": latency(), "error": f"Unsupported Campaign table tool: {tool_name}"}
    except Exception as exc:
        try:
            await db.rollback()
        except Exception:
            logger.debug("Campaign table tool rollback failed", exc_info=True)
        logger.exception("Campaign table tool failed")
        return {"tool": tool_name, "input": tool_args, "status": "failed", "latency_ms": latency(), "error": str(exc)}


async def execute_one(
    tool_name: str,
    tool_args: dict,
    brand_id: UUID | None,
    db: AsyncSession,
    settings,
    tools: dict,
    workspace_id: UUID | None = None,
    campaign_id: UUID | None = None,
    extra_brief: dict | None = None,
) -> dict:
    """Execute a single tool call. Returns a result dict."""
    start = time.perf_counter()
    tool_def = tools.get(tool_name)

    if not tool_def:
        latency = round((time.perf_counter() - start) * 1000)
        return {"tool": tool_name, "input": tool_args, "status": "failed",
                "latency_ms": latency, "error": f"Unknown tool: {tool_name}"}

    # Built-in artifact lifecycle tools do not correspond to manifest modules.
    if tool_name == "run_artifact_action":
        return await _execute_artifact_action_tool(
            tool_name, tool_args, db, settings, start,
        )
    if tool_name == "revise_artifact":
        return await _execute_revise_artifact_tool(
            tool_name, tool_args, db, settings, start,
            extra_brief=extra_brief,
        )
    if tool_name in {"campaign_read", "campaign_create", "campaign_append", "campaign_patch", "campaign_act"}:
        return await _execute_campaign_tool(
            tool_name, tool_args, db, start,
            brand_id=brand_id, workspace_id=workspace_id, session_campaign_id=campaign_id,
            extra_brief=extra_brief,
        )
    module_id = tool_def["module_id"]

    # If the model calls a module's native revise action directly, normalize it
    # back through the generic revision primitive. Otherwise postcraft_render can
    # receive source_run_id/revision_prompt without the previous Run/RunTrace
    # block or source image, fail its approval gate, or regenerate from scratch.
    # The persisted artifact's action_modules.revise remains the source of truth.
    if module_id == "postcraft.render" and (tool_args or {}).get("source_run_id"):
        revision_text = str(
            (tool_args or {}).get("revision_prompt")
            or (tool_args or {}).get("edit_instruction")
            or (tool_args or {}).get("feedback")
            or ""
        ).strip()
        if revision_text:
            return await _execute_revise_artifact_tool(
                tool_name, tool_args, db, settings, start,
                extra_brief=extra_brief,
            )

    module_cls = get_module(module_id)
    if not module_cls:
        latency = round((time.perf_counter() - start) * 1000)
        return {"tool": tool_name, "input": tool_args, "status": "failed",
                "latency_ms": latency, "error": f"Module not found: {module_id}"}

    # Build brief from tool args (plain dict, no dataclass), then merge
    # server-owned context that the LLM should not have to serialize into the
    # tool call: attachment-derived JSON/image references and brand kit.
    brief: dict[str, Any] = dict(tool_args) if isinstance(tool_args, dict) else {}
    if extra_brief:
        for k, v in extra_brief.items():
            if str(k).startswith("_"):
                continue
            if k not in brief and v not in (None, "", [], {}):
                brief[k] = v
    if brand_id and not isinstance(brief.get("brand_kit"), dict):
        kit = await _brand_kit_for_tool(db, brand_id)
        if kit:
            brief["brand_kit"] = kit
            brief.setdefault("brand_name", kit.get("brand_name"))

    # Campaign truth is provided by Campaign V2 rows/tools. Do not rebuild any
    # retired static campaign context path here.

    # JSON-image/postcraft edit bridge: when the operator attaches a prior image
    # and asks for an edit, use that first attachment as the source image unless
    # a source was already supplied. This mirrors json_image.py --source.
    if "edit_instruction" in brief and "source_image_data_b64" not in brief:
        refs = brief.get("reference_images") if isinstance(brief.get("reference_images"), list) else []
        first_ref = next((r for r in refs if isinstance(r, dict) and r.get("vision_b64")), None)
        if first_ref:
            brief["source_image_data_b64"] = first_ref.get("vision_b64")

    # Inject previous image for revision calls.
    # When the LLM calls the edit action (with locked_elements / change_request / editable_region)
    # or the legacy edit_instruction, but no source_image_data_b64, pull from the
    # per-brand cache populated by the last succeeded image tool in this process.
    has_edit_signal = (
        "edit_instruction" in brief
        or "locked_elements" in brief
        or "change_request" in brief
        or "editable_region" in brief
    )
    if (
        has_edit_signal
        and "source_image_data_b64" not in brief
        and brand_id
    ):
        cached = _image_cache.get(str(brand_id))
        if cached:
            brief["source_image_data_b64"] = cached
            logger.info("Injected cached source image for brand %s revision", brand_id)

    # Inject Google Drive credentials from the google.drive plugin for modules
    # that store assets but do not declare the Drive slot themselves. The
    # canonical run path below still owns module credential injection, hooks,
    # upstream hydration, Run/RunResult/RunTrace persistence, memory events, and
    # approval state.
    if brand_id:
        try:
            brief = await _inject_drive_credentials(brief, brand_id, db, settings)
        except Exception as exc:
            logger.warning("Drive credential injection failed for %s: %s", module_id, exc)

    try:
        from routers.runs import _execute_module
        from routers.workspace import get_singleton

        ws = await get_singleton(db)
        if not ws:
            latency = round((time.perf_counter() - start) * 1000)
            return {"tool": tool_name, "input": tool_args, "status": "failed",
                    "latency_ms": latency, "error": "Workspace not initialized"}

        response = await _execute_module(
            db, ws, module_id, brief, settings,
            campaign_id=campaign_id,
            brand_id=brand_id,
        )
        result = _tool_result_from_run_response(tool_name, tool_args, tool_def, response, start, prompt_brief=brief)
        if result.get("image_b64") and brand_id:
            _image_cache[str(brand_id)] = result["image_b64"]
        return result

    except BosError as exc:
        latency = round((time.perf_counter() - start) * 1000)
        logger.error("Tool %s (%s) failed: %s", tool_name, module_id, exc.message)
        return {"tool": tool_name, "input": tool_args, "status": "failed",
                "latency_ms": latency, "error": exc.message}
    except HTTPException as exc:
        latency = round((time.perf_counter() - start) * 1000)
        detail = exc.detail if isinstance(exc.detail, str) else json.dumps(exc.detail, ensure_ascii=False)
        logger.error("Tool %s (%s) failed: %s", tool_name, module_id, detail)
        return {"tool": tool_name, "input": tool_args, "status": "failed",
                "latency_ms": latency, "error": detail}
    except Exception as exc:
        latency = round((time.perf_counter() - start) * 1000)
        logger.error("Tool %s (%s) failed: %s", tool_name, module_id, exc, exc_info=True)
        return {"tool": tool_name, "input": tool_args, "status": "failed",
                "latency_ms": latency, "error": str(exc)}


async def execute_all(
    tool_calls: list[dict],
    db: AsyncSession,
    settings,
    tools: dict,
    brand_id: UUID | None = None,
    workspace_id: UUID | None = None,
    campaign_id: UUID | None = None,
    extra_brief: dict | None = None,
) -> list[dict]:
    """Execute tool calls and persist artifact-producing outputs for Stream."""
    if not tool_calls:
        return []
    # Use the request DB session sequentially. Tool calls are usually one at a
    # time, and persistence into runs/stream must not share AsyncSession across
    # concurrent tasks.
    results = []
    for tc in tool_calls:
        results.append(await execute_one(
            tc["name"], tc["args"], brand_id, db, settings, tools,
            workspace_id=workspace_id,
            campaign_id=campaign_id,
            extra_brief=extra_brief,
        ))
    return results
