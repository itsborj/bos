"""
BOS System Hook Subscribers
----------------------------
First-party hook handlers that enrich the dispatch brief with brand context,
memory slots, and channel credentials. These replace the inline logic that
was accumulating in chat.py and runs.py.

Registration: call register_system_hooks(hooks) once at app startup.
"""
from __future__ import annotations

import logging

from klaroha_sdk import HookPayload
from pipeline.hooks import HookRegistry

logger = logging.getLogger("bos.pipeline.system_hooks")


async def _brand_scope_subscriber(payload: HookPayload) -> HookPayload:
    """
    Injects active brand context into payload.brief.
    Reads from payload.context["brand"] (resolved by the dispatcher before firing).
    Mirrors the logic currently in _brand_scoped_brief() in chat.py.
    """
    brand = payload.context.get("brand")
    if not brand:
        return payload

    bj = brand.get("brand_json") or {}
    brief = payload.brief

    brief.setdefault("brand_name", brand.get("name", ""))
    for field in ("tone", "voice", "values", "domain", "website_url", "social_handles"):
        if bj.get(field):
            brief.setdefault(field, bj[field])

    return payload


async def _memory_hydration_subscriber(payload: HookPayload) -> HookPayload:
    """
    Placeholder for memory slot hydration.
    Full extraction from chat.py happens in the A6 chat.py rewrite.
    """
    return payload


def register_system_hooks(registry: HookRegistry) -> None:
    """Call once at app startup (main.py lifespan)."""
    registry.subscribe("brief.before_dispatch", _brand_scope_subscriber)
    registry.subscribe("brief.before_dispatch", _memory_hydration_subscriber)
    logger.info("System hook subscribers registered")
