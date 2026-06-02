"""
Council orchestrator — live boardroom deliberation.

Session lifecycle:
  round_1_active → awaiting_c6 → round_N_active → awaiting_c6 → ... → settled

Round 1: all active seats fire in parallel, independent positions, no peer context.
Round 2+: sequential within round — each seat sees all prior rounds plus every seat
          that has already spoken in the current round, producing genuine live dialogue.
C6 (business leader) injects or passes at each round boundary via hardcoded prompt pool.
Settlement is extracted from the final transcript — no separate synthesis model.
"""
from __future__ import annotations

import asyncio
import logging
import random
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from executor import get_adapter

logger = logging.getLogger(__name__)

_SEATS_DIR = Path(__file__).parent / "seats"
_FALLBACK_PROVIDER = "openrouter"
_FALLBACK_MODEL = "openai/gpt-4o"
# Free models tried in order for settlement extraction
_EXTRACTION_MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "poolside/laguna-xs.2:free",
    "openai/gpt-oss-120b:free",
    "google/gemma-2-27b-it:free",
]

C6_PROMPTS = [
    "What do you think?",
    "Any comments before we continue?",
    "Anything to add or redirect?",
    "Do you want the council to keep going?",
    "Any thoughts?",
]

_SENIOR_CMO_SYSTEM = """A senior Chief Marketing Officer with deep experience in brand strategy,
performance marketing, and business operations. You operate at the executive level — big picture,
high conviction, direct. You speak plainly. You don't hedge.

When deliberating with peers on a strategic question:
- State your position clearly in the first sentence using "My position:" or "I believe..."
- Support it with reasoning, not caveats
- Engage directly with peer positions by seat ID — name them explicitly (e.g. "C2 is right that...")
- Challenge what you disagree with by name and give the reason
- Close with a clear one-sentence summary of where you stand
- IMPORTANT: When you see transcript entries attributed to your own seat ID, those are YOUR prior statements — refer to them as "my earlier position", not as if a third party said them"""


# ── Seat loading ──────────────────────────────────────────────────────────────

def _load_seats() -> list[dict[str, Any]]:
    seats = []
    for seat_dir in sorted(_SEATS_DIR.iterdir()):
        skill_path = seat_dir / "SKILL.md"
        if not skill_path.exists():
            continue
        raw = skill_path.read_text()
        parts = raw.split("---", 2)
        if len(parts) < 3:
            continue
        try:
            meta = yaml.safe_load(parts[1]) or {}
        except yaml.YAMLError:
            logger.warning("council: bad SKILL.md in %s", seat_dir.name)
            continue
        if meta.get("status") != "active":
            continue
        seats.append({
            "seat_id": meta["seat"].upper(),
            "display_name": meta.get("display_name") or meta["seat"].upper(),
            "provider": (meta.get("model") or {}).get("provider") or _FALLBACK_PROVIDER,
            "model_id": (meta.get("model") or {}).get("model_id") or _FALLBACK_MODEL,
            "ideology": meta.get("ideology") or "",
        })
    return seats


# ── Prompt building ───────────────────────────────────────────────────────────

def _build_system_prompt(seat_id: str, display_name: str, ideology: str) -> str:
    identity = (
        f"You are {display_name} (seat {seat_id.upper()}) in this Council. "
        f"Your seat ID is {seat_id.upper()}. "
        f"Any transcript entries attributed to {seat_id.upper()} are YOUR prior statements from earlier rounds."
    )
    base = f"{identity}\n\n{_SENIOR_CMO_SYSTEM}"
    if ideology:
        return f"{base}\n\nYour specific perspective:\n{ideology}"
    return base


def _format_transcript(rounds: list[list[dict]], c6_injections: list[dict]) -> str:
    lines: list[str] = []
    for round_idx, positions in enumerate(rounds, 1):
        lines.append(f"--- Round {round_idx} ---")
        for pos in positions:
            name = pos.get("display_name", pos["seat_id"])
            lines.append(f"{pos['seat_id']} ({name}):\n{pos['content']}\n")
        injection = next((c for c in c6_injections if c["round_boundary"] == round_idx), None)
        if injection:
            lines.append(f"C6 (Business Leader):\n{injection['content']}\n")
    return "\n".join(lines)


def _build_round_1_prompt(brief: str, brand_name: str) -> str:
    return (
        f"The Council has been convened for: {brief}\n\n"
        f"Brand in focus: {brand_name}\n\n"
        "ROUND 1 INSTRUCTION:\n"
        "This is Round 1. Present your independent position. "
        "Do not reference other council members — you have not heard them yet. "
        "Speak as a senior CMO addressing the question directly."
    )


def _build_round_n_prompt(
    brief: str,
    brand_name: str,
    round_num: int,
    completed_rounds: list[list[dict]],
    c6_injections: list[dict],
    round_so_far: list[dict],
    c6_input_this_boundary: str | None,
) -> str:
    parts = [
        f"The Council is deliberating on: {brief}",
        f"Brand: {brand_name}",
        "",
        "TRANSCRIPT TO DATE:",
        _format_transcript(completed_rounds, c6_injections),
    ]

    if round_so_far:
        parts.append(f"--- Round {round_num} (in progress) ---")
        for pos in round_so_far:
            name = pos.get("display_name", pos["seat_id"])
            parts.append(f"{pos['seat_id']} ({name}):\n{pos['content']}\n")

    if c6_input_this_boundary:
        parts += [
            "",
            f"C6 (Business Leader) has added:\n{c6_input_this_boundary}",
            "Factor this into your position.",
            "",
        ]

    parts += [
        f"ROUND {round_num} INSTRUCTION:",
        f"This is Round {round_num}. You have now heard your peers. "
        "Address their positions directly — name who you agree with and why, "
        "name who you disagree with and why. "
        "If your view has shifted from an earlier round, say so and state what changed it.",
    ]

    return "\n".join(parts)


# ── LLM call ─────────────────────────────────────────────────────────────────

def _resolve_api_key(provider: str, settings) -> str | None:
    if provider == "nvidia":
        return getattr(settings, "platform_nvidia_key", None)
    if provider == "openai":
        return getattr(settings, "platform_openai_key", None)
    if provider == "gemini":
        return getattr(settings, "platform_gemini_key", None)
    return getattr(settings, "platform_openrouter_key", None)


async def _call_seat(seat: dict, system_prompt: str, user_prompt: str, settings) -> dict[str, Any]:
    seat_id = seat["seat_id"]
    provider = seat["provider"]
    now = datetime.now(timezone.utc).isoformat()

    api_key = _resolve_api_key(provider, settings)
    if not api_key:
        api_key = getattr(settings, "platform_openrouter_key", None)
        if not api_key:
            return {
                "seat_id": seat_id,
                "display_name": seat["display_name"],
                "content": "[no provider key configured]",
                "timestamp": now,
            }
        provider = _FALLBACK_PROVIDER

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    max_attempts = 4  # initial + 3 retries
    for attempt in range(max_attempts):
        try:
            adapter = get_adapter(provider, api_key)
            resp = await adapter.complete_messages(messages, seat["model_id"])
            return {
                "seat_id": seat_id,
                "display_name": seat["display_name"],
                "content": resp.content.strip(),
                "timestamp": now,
            }
        except Exception as exc:
            if "429" in str(exc) and attempt < max_attempts - 1:
                wait = 4 * (attempt + 1)  # 4s, 8s, 12s
                logger.warning("council: seat %s rate-limited (attempt %d/%d), retrying in %ds",
                               seat_id, attempt + 1, max_attempts, wait)
                await asyncio.sleep(wait)
                continue
            logger.exception("council: seat %s failed: %s", seat_id, exc)
            return {
                "seat_id": seat_id,
                "display_name": seat["display_name"],
                "content": f"[error: {exc}]",
                "timestamp": now,
            }


# ── Settlement extraction ─────────────────────────────────────────────────────

async def _extract_settlement(brief: str, full_transcript: str, settings) -> dict[str, Any]:
    """Extract structured settlement from the transcript. Extraction only — no new synthesis."""
    prompt = (
        "You are reading a council deliberation transcript. "
        "Extract the settlement from what was actually said — do not add new ideas.\n\n"
        f"QUESTION:\n{brief}\n\n"
        f"FULL TRANSCRIPT:\n{full_transcript}\n\n"
        "Extract exactly three sections:\n\n"
        "SETTLEMENT\n"
        "(1-3 sentences: what did the council agree on, or where does it remain split? "
        "Use only what was actually said.)\n\n"
        "MARCHING ORDERS\n"
        "(numbered list of concrete actions derived from what was agreed)\n\n"
        "PARKED DECISIONS\n"
        "(bullet list of open items explicitly left unresolved; each as: - [item])"
    )
    api_key = settings.platform_openrouter_key
    adapter = get_adapter(_FALLBACK_PROVIDER, api_key)
    messages = [{"role": "user", "content": prompt}]
    last_exc: Exception | None = None
    for model in _EXTRACTION_MODELS:
        try:
            resp = await adapter.complete_messages(messages, model)
            logger.debug("council: extraction raw (first 300): %s", resp.content[:300])
            result = _parse_settlement(resp.content)
            if result["settlement"] or result["marching_orders"]:
                return result
            logger.warning("council: extraction model %s returned empty parse, trying next", model)
        except Exception as exc:
            logger.warning("council: extraction model %s failed: %s", model, exc)
            last_exc = exc
    logger.error("council: all extraction models failed or returned empty; last error: %s", last_exc)
    return {"settlement": "", "marching_orders": [], "parked_decisions": []}


def _parse_settlement(text: str) -> dict[str, Any]:
    settlement_lines: list[str] = []
    marching: list[str] = []
    parked: list[str] = []
    section: str | None = None

    for line in text.splitlines():
        stripped = line.strip()
        # Strip markdown so "**SETTLEMENT**" and "## Marching Orders" both match
        header_check = re.sub(r"[#*_`]", "", stripped).strip().upper()
        if header_check.startswith("SETTLEMENT"):
            section = "settlement"
            continue
        if header_check.startswith("MARCHING ORDERS"):
            section = "marching"
            continue
        if header_check.startswith("PARKED DECISIONS"):
            section = "parked"
            continue
        if not stripped:
            continue
        if section == "settlement":
            settlement_lines.append(stripped)
        elif section == "marching":
            clean = re.sub(r"^\d+[\.\)]\s*", "", stripped)
            if clean:
                marching.append(clean)
        elif section == "parked":
            clean = re.sub(r"^[-•]\s*", "", stripped)
            if clean:
                parked.append(clean)

    return {
        "settlement": " ".join(settlement_lines),
        "marching_orders": marching,
        "parked_decisions": parked,
    }


# ── Session state helper ──────────────────────────────────────────────────────

def _session_state(row, seats: list[dict]) -> dict[str, Any]:
    return {
        "session_id": str(row.id),
        "status": row.status,
        "current_round": row.current_round,
        "rounds_completed": row.rounds_completed,
        "rounds": row.rounds,
        "c6_injections": row.c6_injections,
        "pending_c6_prompt": row.pending_c6_prompt,
        "safety_ceiling": row.safety_ceiling,
        "seats": seats,
    }


# ── Public API ────────────────────────────────────────────────────────────────

async def start_session(
    brief: str,
    db: AsyncSession,
    ws,
    brand=None,
    safety_ceiling: int = 10,
) -> dict[str, Any]:
    """
    Create session and run Round 1 in parallel.
    All seats receive only the question — no peer context yet.
    Returns session state + first C6 prompt.
    """
    from models.council import CouncilSession

    settings = get_settings()
    brand_name = (brand.name if brand else None) or (ws.name if ws else "this business")
    session_id = str(uuid.uuid4())
    seats = _load_seats()

    if not seats:
        return {
            "session_id": session_id,
            "status": "settled",
            "current_round": 0,
            "rounds_completed": 0,
            "rounds": [],
            "c6_injections": [],
            "pending_c6_prompt": None,
            "safety_ceiling": safety_ceiling,
            "seats": [],
            "error": "No active council seats. Activate seats in Admin → Council Seats.",
        }

    row = CouncilSession(
        id=uuid.UUID(session_id),
        workspace_id=ws.id if ws else None,
        brand_id=brand.id if brand else None,
        brief=brief,
        status="round_1_active",
        current_round=1,
        rounds=[],
        c6_injections=[],
        marching_orders=[],
        parked_decisions=[],
        rounds_completed=0,
        safety_ceiling=safety_ceiling,
    )
    db.add(row)
    await db.flush()

    # Round 1 — staggered (2s apart) to avoid bursting free-tier rate limits
    prompt = _build_round_1_prompt(brief, brand_name)
    positions: list[dict] = []
    for i, seat in enumerate(seats):
        if i > 0:
            await asyncio.sleep(2)
        pos = await _call_seat(seat, _build_system_prompt(seat["seat_id"], seat["display_name"], seat["ideology"]), prompt, settings)
        positions.append(pos)
    for p in positions:
        p["round"] = 1

    c6_prompt = random.choice(C6_PROMPTS)

    row.rounds = [positions]
    row.rounds_completed = 1
    row.status = "awaiting_c6"
    row.pending_c6_prompt = c6_prompt
    await db.commit()

    return _session_state(row, seats)


async def process_c6(
    row,
    c6_input: str | None,
    brand_name: str,
    db: AsyncSession,
) -> dict[str, Any]:
    """
    C6 injects or passes. Runs the next round sequentially — each seat sees all
    seats that have already spoken in this round, producing genuine live dialogue.
    Returns updated session state + new C6 prompt.
    """
    settings = get_settings()
    seats = _load_seats()
    if not seats:
        raise ValueError("No active council seats")

    all_rounds: list[list[dict]] = list(row.rounds or [])
    c6_injections: list[dict] = list(row.c6_injections or [])
    current_round = row.current_round
    next_round = current_round + 1
    brief = row.brief

    if c6_input and c6_input.strip():
        c6_injections.append({
            "round_boundary": current_round,
            "content": c6_input.strip(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    if next_round > row.safety_ceiling:
        row.c6_injections = c6_injections
        row.pending_c6_prompt = "Safety ceiling reached. Use Finalize to close the session."
        await db.commit()
        return _session_state(row, seats)

    c6_for_round = c6_input.strip() if c6_input and c6_input.strip() else None
    row.status = "round_N_active"
    await db.flush()

    # Round N — sequential within round so each seat reads what peers just said
    round_positions: list[dict] = []
    for seat in seats:
        prompt = _build_round_n_prompt(
            brief=brief,
            brand_name=brand_name,
            round_num=next_round,
            completed_rounds=all_rounds,
            c6_injections=c6_injections,
            round_so_far=round_positions,
            c6_input_this_boundary=c6_for_round,
        )
        pos = await _call_seat(seat, _build_system_prompt(seat["seat_id"], seat["display_name"], seat["ideology"]), prompt, settings)
        pos["round"] = next_round
        round_positions.append(pos)

    all_rounds.append(round_positions)
    c6_prompt = random.choice(C6_PROMPTS)

    row.rounds = all_rounds
    row.c6_injections = c6_injections
    row.rounds_completed = len(all_rounds)
    row.current_round = next_round
    row.status = "awaiting_c6"
    row.pending_c6_prompt = c6_prompt
    await db.commit()

    return _session_state(row, seats)


async def finalize(
    row,
    db: AsyncSession,
) -> dict[str, Any]:
    """
    C6 closes the session. Extract settlement from the full transcript.
    No separate synthesis model — extraction only from what was actually said.
    """
    settings = get_settings()
    seats = _load_seats()
    all_rounds: list[list[dict]] = list(row.rounds or [])
    c6_injections: list[dict] = list(row.c6_injections or [])

    row.status = "finalizing"
    await db.flush()

    full_transcript = _format_transcript(all_rounds, c6_injections)
    extracted = await _extract_settlement(row.brief, full_transcript, settings)

    row.status = "settled"
    row.settlement = extracted["settlement"]
    row.marching_orders = extracted["marching_orders"]
    row.parked_decisions = extracted["parked_decisions"]
    row.pending_c6_prompt = None
    row.settled_at = datetime.now(timezone.utc)
    await db.commit()

    return {
        "session_id": str(row.id),
        "status": "settled",
        "brief": row.brief,
        "settlement": extracted["settlement"],
        "marching_orders": extracted["marching_orders"],
        "parked_decisions": extracted["parked_decisions"],
        "c6_injections": c6_injections,
        "rounds_completed": row.rounds_completed,
        "transcript": full_transcript,
        "seats": seats,
    }
