"""SDK types — stable public contract. Breaking changes require major version bump."""
from __future__ import annotations

import functools
from dataclasses import dataclass, field
from typing import Literal


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
