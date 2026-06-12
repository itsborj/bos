from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class ProviderResponse:
    content: str
    tokens_input: int
    tokens_output: int
    latency_ms: int
    actual_model: str | None = None  # set when provider routed to a different model (e.g. OR native failover)


@runtime_checkable
class ProviderAdapter(Protocol):
    provider_id: str

    async def complete(self, prompt: str, model_id: str, extra_body: dict | None = None) -> ProviderResponse: ...

    async def check(self) -> bool: ...
