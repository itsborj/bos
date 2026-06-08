"""
BOS Pipeline Hook Registry
---------------------------
Core fires named events; plugins subscribe to them.
Core never imports plugins — plugins register themselves at activation time.

Event names (v1):
  brief.before_dispatch  — enrich brief before module execution
  run.after_complete     — react after a module run is persisted
  manifest.built         — annotate capability entry during scan
  plugin.activated       — plugin sets up resources for a brand
  plugin.deactivated     — plugin tears down cleanly
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Awaitable, Callable

from klaroha_sdk import HookPayload

logger = logging.getLogger("bos.pipeline.hooks")

Handler = Callable[[HookPayload], Awaitable[HookPayload]]


class HookRegistry:
    def __init__(self) -> None:
        self._hooks: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, event: str, handler: Handler) -> None:
        self._hooks[event].append(handler)
        logger.debug("Hook subscriber registered: %s → %s", event, handler.__qualname__)

    async def fire(self, event: str, payload: HookPayload) -> HookPayload:
        for handler in self._hooks.get(event, []):
            try:
                payload = await handler(payload)
            except Exception as exc:
                logger.warning(
                    "Hook handler %s raised for event %s: %s",
                    handler.__qualname__, event, exc,
                )
        return payload

    def handler_count(self, event: str) -> int:
        return len(self._hooks.get(event, []))


# Module-level singleton — import this everywhere:
#   from pipeline.hooks import hooks
hooks = HookRegistry()
