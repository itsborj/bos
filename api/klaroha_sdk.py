"""
Klaroha Channel Plugin SDK — container-side shim
-------------------------------------------------
Inside the BOS container, this file takes precedence over the installed
packages/klaroha_sdk pip package because /app (the api/ dir) is first on sys.path.

- ChannelModule: alias of ModuleBase (backward compat for all api/plugins/)
- New types (ArtifactBlock, RunResult, HookPayload, CredentialPayload,
  hook_subscriber) are defined here so external plugins loaded at runtime
  get the same symbols as the pip package provides for development.

Plugin authors: install `pip install -e packages/klaroha_sdk` for development.
Do NOT import from any other klaroha module. This file IS the stable boundary.
"""
from __future__ import annotations

import functools
from dataclasses import dataclass, field
from typing import ClassVar, Literal

from module_base import ModuleBase as ChannelModule


# ─── Types ────────────────────────────────────────────────────────────────────

@dataclass
class ArtifactBlock:
    block_type: str
    content: dict
    renderer_hint: str
    allowed_actions: list[str]


@dataclass
class RunResult:
    run_id: str
    status: Literal["success", "failed", "pending_review"]
    artifact_blocks: list[ArtifactBlock]
    self_check: Literal["pass", "fail"] | None = None
    error: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class HookPayload:
    event: str
    brief: dict
    context: dict
    metadata: dict = field(default_factory=dict)


@dataclass
class CredentialPayload:
    platform: str
    page_token: str | None = None
    page_id: str | None = None
    extra: dict = field(default_factory=dict)


def hook_subscriber(event: str):
    """Decorator: marks a ChannelModule method as a subscriber for a hook event."""
    def decorator(fn):
        if not hasattr(fn, "_hook_subscriptions"):
            fn._hook_subscriptions = []
        fn._hook_subscriptions.append(event)
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            return await fn(*args, **kwargs)
        wrapper._hook_subscriptions = fn._hook_subscriptions
        return wrapper
    return decorator


__all__ = [
    "ChannelModule",
    "ArtifactBlock",
    "RunResult",
    "HookPayload",
    "CredentialPayload",
    "hook_subscriber",
]
