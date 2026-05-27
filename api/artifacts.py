"""Artifact reference helpers.

Workspace Artifacts are the canonical artifact plane. Chat should reference artifacts;
Workspace/Stream decide how to render native previews.
"""
from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel


class ArtifactRef(BaseModel):
    artifact_id: str
    title: str
    type: str
    status: str
    renderer: str
    workspace_url: str


def _title_case(value: str) -> str:
    return " ".join(part.capitalize() for part in re.sub(r"[_-]+", " ", value).split() if part)


def artifact_type(run: Any) -> str:
    module_id = run.module_id.lower()
    if "plan" in module_id:
        return "plan_artifact"
    if any(token in module_id for token in ("report", "analytics", "inbox", "read")):
        return "intelligence_artifact"
    if any(token in module_id for token in ("send", "publish", "action")):
        return "action_result"
    return "draft_artifact"


def artifact_title(run: Any) -> str:
    module_id = run.module_id.lower()
    platform = _title_case((run.result.platform if run.result and run.result.platform else run.module_id.rsplit(".", 1)[-1]) or "asset")
    platform_key = platform.lower()
    if "gtm_plan" in module_id or "marketing.planning.gtm" in module_id:
        return "GTM Strategy"
    if ("email" in module_id or "gmail" in module_id or "email" in platform_key) and "plan" in module_id:
        return "Email Campaign Plan"
    if "email" in module_id or "gmail" in module_id or "email" in platform_key:
        return "Email Draft"
    if "plan" in module_id:
        return "Campaign Plan"
    if "clickup" in module_id and "read" in module_id:
        return "ClickUp Workspace Status"
    if any(token in module_id for token in ("report", "analytics", "inbox", "read")):
        return "Marketing Intelligence"
    if "google" in module_id:
        return "Google Ad Draft"
    if "facebook" in module_id:
        return "Facebook Draft"
    if "instagram" in module_id:
        return "Instagram Draft"
    if "twitter" in module_id or ".x." in module_id:
        return "Social Post Draft"
    if "pinterest" in module_id:
        return "Pinterest Draft"
    return f"{platform} Artifact"


def artifact_renderer(run: Any) -> str:
    module_id = run.module_id.lower()
    platform = (run.result.platform if run.result and run.result.platform else "").lower()
    channel = f"{module_id} {platform}"
    if "gtm_plan" in module_id or "marketing.planning.gtm" in module_id:
        return "gtm_strategy_preview"
    if "email" in channel:
        return "email_preview"
    if "google" in module_id and ("text" in module_id or "search" in module_id):
        return "google_search_preview"
    if "google" in channel and "display" in channel:
        return "google_display_preview"
    if "facebook" in channel:
        return "facebook_feed_preview"
    if "instagram" in channel and "story" in channel:
        return "instagram_story_preview"
    if "instagram" in channel:
        return "instagram_feed_preview"
    if "twitter" in channel or ".x." in module_id:
        return "twitter_feed_preview"
    if "pinterest" in channel:
        return "pinterest_preview"
    if "clickup" in module_id and "read" in module_id:
        return "clickup_workspace_status"
    if artifact_type(run) == "intelligence_artifact":
        return "performance_report"
    return "artifact_detail"


def artifact_status(run: Any) -> str:
    if run.status == "failed":
        return "failed"
    if run.approval_status == "approved":
        return "approved"
    if run.approval_status in ("rejected", "dismissed"):
        return "dismissed"
    if run.approval_status == "pending":
        return "pending_review"
    return "pending_review" if run.result and run.result.self_check == "pass" else "saved"


def artifact_ref_from_run(run: Any) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=run.run_id,
        title=artifact_title(run),
        type=artifact_type(run),
        status=artifact_status(run),
        renderer=artifact_renderer(run),
        workspace_url=f"/workspace/artifacts/{run.run_id}",
    )
