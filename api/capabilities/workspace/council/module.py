"""
Council capability. Sessions are initiated via the @council command in chat.py,
which calls api/council.py directly as a core service. This module is not
dispatched via the CMO capability manifest (allowed_from_chat: false).
"""


async def execute(brief: dict, **_kwargs) -> dict:
    return {
        "error": "Council sessions are initiated via @council command, not capability dispatch.",
        "hint": "Use @council <question> in CMO chat.",
    }
