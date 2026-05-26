from __future__ import annotations
import time
import uuid
from typing import Any, Dict, List

from klaroha_sdk import ChannelModule

# Slot-based templates — channel-agnostic compositions
_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "short_form_v1": {
        "name": "Short-form Video",
        "slots": ["hero_visual", "hook_text", "cta_button", "branding_overlay"],
        "render_rules": {"aspect_ratio": "9:16", "max_duration": 60},
    },
    "static_square_v1": {
        "name": "Static Square Post",
        "slots": ["background_image", "headline", "logo"],
        "render_rules": {"aspect_ratio": "1:1"},
    },
    "feed_landscape_v1": {
        "name": "Feed Landscape",
        "slots": ["hero_visual", "hook_text", "cta_button", "logo"],
        "render_rules": {"aspect_ratio": "16:9", "max_duration": 30},
    },
    "story_v1": {
        "name": "Story / Reel",
        "slots": ["hero_visual", "hook_text", "swipe_cta", "branding_overlay"],
        "render_rules": {"aspect_ratio": "9:16", "max_duration": 15},
    },
}


class CreativeBlueprintAssembleModule(ChannelModule):
    id = "creative.blueprint.assemble"
    name = "Blueprint Assembly"
    vertical = "creative"
    capability = "marketing.execute"
    platform_hint = "creative blueprint assembly"
    policy_default = "generate_only"

    def execute_tool_result(self, brief: dict) -> tuple[dict, dict]:
        """Stage 4: Map approved primitives into template slots — no channel logic."""
        start = time.perf_counter()

        pack_data: dict = brief.get("creative_pack", {})
        primitive_ids: List[str] = brief.get("primitive_ids", [])
        template_id: str = brief.get("template_id", "short_form_v1")

        template = _TEMPLATES.get(template_id) or _TEMPLATES["short_form_v1"]
        slots: List[str] = template["slots"]

        if not primitive_ids and not pack_data:
            return {"status": "failed", "error": "primitive_ids or creative_pack required"}, {
                "content": "Blueprint assembly failed: no primitives or pack provided."
            }

        # Fill slots — primitives first, then text values from pack
        slot_mappings: Dict[str, Any] = {}
        prim_iter = iter(primitive_ids)
        for slot in slots:
            if slot in ("hook_text",) and pack_data.get("hooks"):
                slot_mappings[slot] = pack_data["hooks"][0]
            elif slot in ("cta_button", "swipe_cta") and pack_data.get("ctas"):
                slot_mappings[slot] = pack_data["ctas"][0]
            elif slot == "headline" and pack_data.get("hooks"):
                slot_mappings[slot] = pack_data["hooks"][0]
            else:
                prim_id = next(prim_iter, None)
                if prim_id:
                    slot_mappings[slot] = prim_id
                # unfilled slots remain absent — validator will flag them

        unfilled = [s for s in slots if s not in slot_mappings]

        blueprint = {
            "blueprint_id": f"bp_{uuid.uuid4().hex[:12]}",
            "pack_id": pack_data.get("pack_id"),
            "template_id": template_id,
            "template_name": template["name"],
            "slot_mappings": slot_mappings,
            "render_rules": template["render_rules"],
            "unfilled_slots": unfilled,
            "status": "draft" if not unfilled else "incomplete",
        }

        content = f"Blueprint assembled: {template['name']} — {len(slot_mappings)}/{len(slots)} slots filled."
        if unfilled:
            content += f" Missing: {', '.join(unfilled)}."

        return {
            "provider": "creative_factory",
            "model_id": "blueprint_assembler_v1",
            "status": "succeeded",
            "latency_ms": round((time.perf_counter() - start) * 1000),
        }, {
            "content": content,
            "block": {
                "type": "creative_blueprint",
                "blueprint": blueprint,
                "allowed_actions": ["validate", "render_to_targets", "discard"] if not unfilled else ["fill_missing_slots", "discard"],
            },
        }
