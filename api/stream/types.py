"""Block type registry.

Each entry defines defaults for layout_hint, interaction, and priority.
Adding a new block type = registering it here. No Stream code changes.
"""

BLOCK_TYPES: dict[str, dict] = {
    "alert": {
        "layout_hint": "alert",
        "interaction": "actionable",
        "default_priority": "urgent",
    },
    "performance": {
        "layout_hint": "table",
        "interaction": "passive",
        "default_priority": "normal",
    },
    "narrative": {
        "layout_hint": "narrative",
        "interaction": "passive",
        "default_priority": "normal",
    },
    "recommendation": {
        "layout_hint": "narrative",
        "interaction": "expandable",
        "default_priority": "low",
    },
    "outcome": {
        "layout_hint": "compact",
        "interaction": "expandable",
        "default_priority": "normal",
    },
    "decision_brief": {
        "layout_hint": "narrative",
        "interaction": "actionable",
        "default_priority": "high",
    },
    "gtm_strategy": {
        "layout_hint": "narrative",
        "interaction": "actionable",
        "default_priority": "high",
    },
    "marketing_plan": {
        "layout_hint": "narrative",
        "interaction": "actionable",
        "default_priority": "high",
    },
    "status": {
        "layout_hint": "compact",
        "interaction": "passive",
        "default_priority": "low",
    },
    "asset_ready": {
        "layout_hint": "media",
        "interaction": "expandable",
        "default_priority": "normal",
    },
}

# Priority order for sorting (lower number = shown first)
PRIORITY_ORDER = {"urgent": 0, "high": 1, "normal": 2, "low": 3}


def defaults(block_type: str) -> dict:
    entry = BLOCK_TYPES.get(block_type, BLOCK_TYPES["narrative"])
    return {
        "layout_hint": entry["layout_hint"],
        "interaction": entry["interaction"],
        "priority": entry["default_priority"],
    }
