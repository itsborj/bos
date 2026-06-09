"""
Klaroha BOS Plugin SDK
======================
Stable public interface for external channel plugins.

Usage in your plugin's module.py:

    from klaroha_sdk import ChannelModule, ArtifactBlock, RunResult

    class MyPlugin(ChannelModule):
        id = "marketing.channel.myplugin.task"
        vertical = "marketing"
        capability = "marketing.execute"
        platform_hint = "myplugin"

        async def execute(self, brief: dict) -> RunResult:
            block = ArtifactBlock(
                block_type="my_result",
                content={"key": "value"},
                renderer_hint="stream_card",
                allowed_actions=[],
            )
            return RunResult(
                run_id=brief.get("run_id", ""),
                status="success",
                artifact_blocks=[block],
                self_check="pass",
            )

Forbidden imports:
    from api.* import anything      # BOS internals — not on plugin path
    from config import get_settings  # BOS config — not on plugin path
    from db import get_db            # BOS database — not on plugin path
"""
from .channel import ChannelModule
from .types import (
    ArtifactBlock,
    CredentialPayload,
    HookPayload,
    RunResult,
    hook_subscriber,
)

__version__ = "1.0.0"

__all__ = [
    "ChannelModule",
    "ArtifactBlock",
    "RunResult",
    "HookPayload",
    "CredentialPayload",
    "hook_subscriber",
]
