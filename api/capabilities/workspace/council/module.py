"""
Council orchestrator — agentic deliberation loop across 5 senior CMO seats.

Each seat is defined by seats/cN/SKILL.md (ideology, model, tools).
The loop runs until all active seats signal ALIGNED or max_rounds is hit.
Settlement extracts marching orders and parked decisions.
"""
from __future__ import annotations

import asyncio
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from providers.connector_registry import get_adapter

logger = logging.getLogger(__name__)

_SEATS_DIR = Path(__file__).parent / "seats"
_TEMPLATE_DIR = Path(__file__).parent
_CONVERGENCE_RE = re.compile(r"\b(ALIGNED|DISSENT|FLAG:\s*.+)$", re.MULTILINE | re.IGNORECASE)

_FALLBACK_MODEL = "openai/gpt-4o"
_FALLBACK_PROVIDER = "openrouter"

_SENIOR_CMO_SYSTEM = """You are a senior Chief Marketing Officer with deep experience in brand strategy,
performance marketing, and business operations. You operate at the executive level — big picture,
high conviction, direct. You speak plainly. You don't hedge.

When deliberating with peers on a strategic question:
- State your position clearly in the first sentence
- Support it with reasoning, not caveats
- Engage directly with peer positions when they are visible
- Challenge what you disagree with; name it specifically
- Close every response with ALIGNED, DISSENT, or FLAG: [specific item]"""


# ── Seat loading ──────────────────────────────────────────────────────────────

def _load_seats() -> list[dict[str, Any]]:
    """Load all active seat definitions from seats/cN/SKILL.md."""
    seats = []
    for seat_dir in sorted(_SEATS_DIR.iterdir()):
        skill_path = seat_dir / "SKILL.md"
        if not skill_path.exists():
            continue
        raw = skill_path.read_text()
        # Strip YAML frontmatter
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
            "seat": meta["seat"],
            "display_name": meta.get("display_name", meta["seat"].upper()),
            "provider": (meta.get("model") or {}).get("provider") or _FALLBACK_PROVIDER,
            "model_id": (meta.get("model") or {}).get("model_id") or _FALLBACK_MODEL,
            "ideology": meta.get("ideology") or "",
            "tools": meta.get("tools") or [],
        })
    return seats


# ── Prompt building ───────────────────────────────────────────────────────────

def _build_system_prompt(ideology: str) -> str:
    if ideology:
        return f"{_SENIOR_CMO_SYSTEM}\n\nYour specific perspective:\n{ideology}"
    return _SENIOR_CMO_SYSTEM


def _build_round_prompt(
    seat: dict,
    brief: str,
    brand_name: str,
    session_id: str,
    round_number: int,
    peer_positions: list[dict],
    operator_injection: str,
) -> str:
    env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)), autoescape=False)
    tmpl = env.get_template("template.j2")
    return tmpl.render(
        round_number=round_number,
        brand_name=brand_name,
        session_id=session_id,
        date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        brief=brief,
        brand_context="",  # extended in future — brand docs, campaign data
        peer_positions=peer_positions if round_number > 1 else [],
        operator_injection=operator_injection,
    )


# ── Single-seat call ──────────────────────────────────────────────────────────

async def _call_seat(
    seat: dict,
    user_prompt: str,
    settings,
) -> dict[str, Any]:
    seat_id = seat["seat"].upper()
    try:
        api_key = settings.platform_openrouter_key
        if not api_key:
            return {"seat_id": seat_id, "content": "[no provider key configured]", "signal": "FLAG: no key"}

        adapter = get_adapter(seat["provider"], api_key)
        messages = [
            {"role": "system", "content": _build_system_prompt(seat["ideology"])},
            {"role": "user", "content": user_prompt},
        ]
        resp = await adapter.complete_messages(messages, seat["model_id"])
        content = resp.content.strip()
        signal = _extract_signal(content)
        return {"seat_id": seat_id, "content": content, "signal": signal}
    except Exception as exc:
        logger.exception("council: seat %s failed: %s", seat_id, exc)
        return {"seat_id": seat_id, "content": f"[error: {exc}]", "signal": "FLAG: seat error"}


def _extract_signal(text: str) -> str:
    m = _CONVERGENCE_RE.search(text)
    return m.group(1).strip() if m else "no signal"


# ── Convergence check ─────────────────────────────────────────────────────────

def _is_converged(positions: list[dict], threshold: int) -> bool:
    aligned = sum(1 for p in positions if p["signal"].upper().startswith("ALIGNED"))
    return aligned >= threshold


# ── Settlement synthesis ──────────────────────────────────────────────────────

async def _synthesize_settlement(
    brief: str,
    all_rounds: list[list[dict]],
    settings,
) -> dict[str, Any]:
    final_positions = all_rounds[-1] if all_rounds else []
    positions_text = "\n\n".join(
        f"{p['seat_id']}: {p['content']}" for p in final_positions
    )

    prompt = f"""You are synthesizing a council deliberation. Below are the final positions
from {len(final_positions)} senior CMOs on a strategic question.

QUESTION:
{brief}

FINAL POSITIONS:
{positions_text}

Your task — produce two sections exactly as formatted:

MARCHING ORDERS
(numbered list of concrete actions the council has agreed on)

PARKED DECISIONS
(items flagged as unresolved; each on its own line as: - [item] | tags: [tag1 · tag2])

Be direct. Use concrete language. No preamble."""

    try:
        api_key = settings.platform_openrouter_key
        adapter = get_adapter(_FALLBACK_PROVIDER, api_key)
        resp = await adapter.complete(prompt, _FALLBACK_MODEL)
        return _parse_settlement(resp.content)
    except Exception as exc:
        logger.exception("council: settlement synthesis failed: %s", exc)
        return {"marching_orders": [], "parked_decisions": [], "raw": ""}


def _parse_settlement(text: str) -> dict[str, Any]:
    marching: list[str] = []
    parked: list[dict] = []
    section = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.upper().startswith("MARCHING ORDERS"):
            section = "marching"
            continue
        if stripped.upper().startswith("PARKED DECISIONS"):
            section = "parked"
            continue
        if section == "marching":
            clean = re.sub(r"^\d+[\.\)]\s*", "", stripped)
            if clean:
                marching.append(clean)
        elif section == "parked":
            clean = re.sub(r"^[-•]\s*", "", stripped)
            if clean:
                parts = clean.split("|")
                item = parts[0].strip()
                tags = parts[1].replace("tags:", "").strip() if len(parts) > 1 else ""
                parked.append({"item": item, "tags": tags})
    return {"marching_orders": marching, "parked_decisions": parked, "raw": text}


# ── Format output ─────────────────────────────────────────────────────────────

def _format_session_output(
    session_id: str,
    brand_name: str,
    seats: list[dict],
    rounds: list[list[dict]],
    settlement: dict,
    rounds_completed: int,
) -> str:
    lines: list[str] = []
    seat_count = len(seats)

    lines.append(f"{'━' * 50}")
    lines.append("  COUNCIL CONVENED")
    lines.append(f"  Brand: {brand_name}  ·  Session #{session_id[:8]}")
    lines.append(f"  Seats: {seat_count} active")
    lines.append(f"{'━' * 50}")
    lines.append("")

    for i, round_positions in enumerate(rounds, 1):
        lines.append(f"  Round {i} —")
        lines.append("")
        for pos in round_positions:
            label = f"  {pos['seat_id']}:"
            content_lines = pos["content"].splitlines()
            lines.append(f"{label} {content_lines[0]}")
            for cl in content_lines[1:]:
                lines.append(f"       {cl}")
            lines.append("")

    lines.append(f"{'━' * 50}")
    aligned = sum(1 for p in rounds[-1] if p["signal"].upper().startswith("ALIGNED")) if rounds else 0
    lines.append(f"  SETTLED  ·  {rounds_completed} round{'s' if rounds_completed != 1 else ''}  ·  {aligned}/{seat_count} aligned")
    lines.append(f"{'━' * 50}")
    lines.append("")

    if settlement["marching_orders"]:
        lines.append("  MARCHING ORDERS")
        lines.append("")
        for idx, order in enumerate(settlement["marching_orders"], 1):
            lines.append(f"  {idx}. {order}")
        lines.append("")

    if settlement["parked_decisions"]:
        lines.append("  PARKED DECISIONS")
        lines.append("")
        for pd in settlement["parked_decisions"]:
            lines.append(f"  ┌─ {pd['item']}")
            if pd["tags"]:
                lines.append(f"  └─ tags: {pd['tags']}")
            else:
                lines.append(f"  └─ awaiting operator decision")
        lines.append("")

    lines.append(f"  Artifact: council_brief #{session_id[:8]}")

    return "\n".join(lines)


# ── Public entry point ────────────────────────────────────────────────────────

async def convene(
    brief: str,
    db: AsyncSession,
    ws,
    brand=None,
    operator_injection: str = "",
) -> dict[str, Any]:
    """
    Run a full council session and return the result dict.

    Returns:
        session_id, formatted_output, marching_orders, parked_decisions, rounds
    """
    from models.council import CouncilSession
    from sqlalchemy import select

    settings = get_settings()
    brand_name = (brand.name if brand else None) or (ws.name if ws else "this business")
    session_id = str(uuid.uuid4())

    seats = _load_seats()
    if not seats:
        return {
            "session_id": session_id,
            "formatted_output": (
                "No council seats are active.\n\n"
                "Recruit council members by editing seats/cN/SKILL.md and setting status: active."
            ),
            "marching_orders": [],
            "parked_decisions": [],
            "rounds": [],
        }

    max_rounds = 5
    convergence_threshold = len(seats)
    all_rounds: list[list[dict]] = []
    current_injection = operator_injection

    # Persist session row
    ws_id = ws.id if ws else None
    brand_id = brand.id if brand else None
    session_row = CouncilSession(
        id=uuid.UUID(session_id),
        workspace_id=ws_id,
        brand_id=brand_id,
        brief=brief,
        status="running",
        rounds=[],
        marching_orders=[],
        parked_decisions=[],
        rounds_completed=0,
    )
    db.add(session_row)
    await db.flush()

    # ── Agentic loop ──────────────────────────────────────────────────────────
    for round_num in range(1, max_rounds + 1):
        prompts = [
            _build_round_prompt(
                seat=seat,
                brief=brief,
                brand_name=brand_name,
                session_id=session_id,
                round_number=round_num,
                peer_positions=all_rounds[-1] if all_rounds else [],
                operator_injection=current_injection if round_num == 1 or current_injection else "",
            )
            for seat in seats
        ]
        current_injection = ""  # injection consumed after first use

        calls = [_call_seat(seat, prompt, settings) for seat, prompt in zip(seats, prompts)]
        positions = await asyncio.gather(*calls)
        all_rounds.append(list(positions))

        if _is_converged(positions, convergence_threshold):
            break

    rounds_completed = len(all_rounds)
    settlement = await _synthesize_settlement(brief, all_rounds, settings)

    # ── Persist result ─────────────────────────────────────────────────────────
    session_row.rounds = [
        [{"seat_id": p["seat_id"], "content": p["content"], "signal": p["signal"]} for p in r]
        for r in all_rounds
    ]
    session_row.marching_orders = settlement["marching_orders"]
    session_row.parked_decisions = settlement["parked_decisions"]
    session_row.rounds_completed = rounds_completed
    session_row.status = "settled"
    session_row.settled_at = datetime.now(timezone.utc)
    await db.commit()

    formatted = _format_session_output(
        session_id=session_id,
        brand_name=brand_name,
        seats=seats,
        rounds=all_rounds,
        settlement=settlement,
        rounds_completed=rounds_completed,
    )

    return {
        "session_id": session_id,
        "formatted_output": formatted,
        "marching_orders": settlement["marching_orders"],
        "parked_decisions": settlement["parked_decisions"],
        "rounds": session_row.rounds,
    }
