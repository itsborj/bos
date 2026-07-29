"""ChannelModule — base class for external channel plugins."""
from __future__ import annotations

from typing import ClassVar

from module_base import ModuleBase

from .types import ArtifactBlock, RunResult


class ChannelModule(ModuleBase):
    """
    Base class for all Klaroha channel plugins.

    External plugins extend this and override execute(). BOS calls execute()
    after injecting brand context and credentials into the brief.

    Class-level attrs you MUST set on your subclass:
        id          - canonical module ID (matches capability_ids in channel.json)
        vertical    - "marketing"
        capability  - e.g. "marketing.execute"
        platform_hint - e.g. "hello", "gmail"

    Forbidden: do NOT import from api.*, config, db, or any BOS internal module.
    Only import from klaroha_sdk.
    """

    id: ClassVar[str] = ""
    legacy_ids: ClassVar[list[str]] = []
    vertical: ClassVar[str] = "marketing"
    capability: ClassVar[str] = "marketing.execute"
    platform_hint: ClassVar[str] = ""
    policy_default: ClassVar[str] = "balanced"
    name: ClassVar[str | None] = None
    internal: ClassVar[bool] = False
    requires_generated_image: ClassVar[bool] = False
    requires_generated_video: ClassVar[bool] = False
    copywriting_skills: ClassVar[list[str]] = []
    max_chars: ClassVar[int] = 0
    must_mention: ClassVar[list[str]] = []
    banned_phrases: ClassVar[list[str]] = []

    async def execute(self, brief: dict) -> RunResult:
        """
        Main entry point. Receives the enriched brief (brand context +
        _channel_credentials already injected). Returns a RunResult.

        Override this in your plugin. Do not call super().
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement execute()"
        )

    def build_prompt(self, brief: dict) -> str:
        """
        Optional: build an LLM prompt from the brief.
        For external plugins that generate their own content without an LLM,
        this is unused — just override execute() directly.
        """
        return ""

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        """Default self-check: always pass. Override for content validation."""
        return "pass", []

    def module_info(self) -> dict:
        return {
            "id": self.id,
            "name": self.name or (self.id.rsplit(".", 1)[-1] if self.id else ""),
            "vertical": self.vertical,
            "capability": self.capability,
            "platform_hint": self.platform_hint,
            "policy_default": self.policy_default,
            "internal": self.internal,
            "copywriting_skills": list(self.copywriting_skills),
            "uses_llm": False,
            "constraints": {
                "max_chars": self.max_chars,
                "must_mention": self.must_mention,
                "banned_phrases": self.banned_phrases,
            },
        }
