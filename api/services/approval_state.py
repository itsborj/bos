"""Approval state machine — single source of truth for approval_status transitions.

Extracted from routers/runs.py to eliminate duplicated transition logic across
SDK, tool, and AI routing execution paths.
"""

from __future__ import annotations

from typing import Literal

ApprovalStatus = Literal[
    "pending", "approved", "rejected", "revised", "failed", "supporting", "dismissed"
]


# ── Transition rules ──────────────────────────────────────────────────────────

def derive_approval_status(
    *,
    run_status: str,
    attempt_failed: bool,
    block_failed: bool,
    is_supporting: bool,
    block: dict | None = None,
    allowed_actions: list[str] | None = None,
) -> ApprovalStatus:
    """Derive the correct approval_status from execution outcomes.

    This is the single source of truth. All three execution paths (SDK, tool, AI)
    call this function instead of duplicating the logic.
    """
    # Supporting runs (contract hydration) never enter the approval queue
    if is_supporting:
        return "supporting"

    # Failed provider/setup/tool results are reviewable facts, not approvable drafts.
    # Keep the run visible for audit/history, but remove it from the approval queue.
    if attempt_failed or block_failed:
        return "failed"

    # Honor artifact-provided review defaults. A successful text artifact
    # can still require operator review before the next workflow stage.
    if isinstance(block, dict) and block.get("approval_status"):
        return str(block.get("approval_status") or "pending")

    # Don't auto-approve artifacts that still require a human publish action.
    # These arrive on Stream as 'pending' so the operator can review and publish.
    _allowed = allowed_actions or []
    _needs_publish = any(str(a).startswith("publish") for a in _allowed)
    if run_status == "success" and not _needs_publish:
        return "approved"

    return "pending"


def derive_run_status(
    *,
    verdict: str,
    attempt_failed: bool,
    block_failed: bool,
) -> str:
    """Derive the run status from self-check verdict and attempt/block outcomes."""
    if verdict == "pass" and not attempt_failed and not block_failed:
        return "success"
    return "partial"


# ── Action transitions ────────────────────────────────────────────────────────

def transition_on_approve(current: ApprovalStatus) -> ApprovalStatus:
    """Transition approval_status when an operator approves a run."""
    return "approved"


def transition_on_reject(current: ApprovalStatus) -> ApprovalStatus:
    """Transition approval_status when an operator rejects a run."""
    return "rejected"


def transition_on_revise(current: ApprovalStatus) -> ApprovalStatus:
    """Transition approval_status when a revision is created from this run."""
    return "revised"


def transition_on_action_failed(current: ApprovalStatus) -> ApprovalStatus:
    """Revert to pending when an external publish/send action fails."""
    return "pending"
