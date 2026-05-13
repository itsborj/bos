from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class ProviderResponse:
    content: str
    tokens_input: int
    tokens_output: int
    latency_ms: int


@runtime_checkable
class ProviderAdapter(Protocol):
    provider_id: str

    async def complete(self, prompt: str, model_id: str) -> ProviderResponse: ...

    async def check(self) -> bool: ...
