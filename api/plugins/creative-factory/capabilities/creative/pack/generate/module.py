from __future__ import annotations
import time
from typing import Any, List, Dict

from klaroha_sdk import ChannelModule


class CreativePackGenerateModule(ChannelModule):
    id = "creative.pack.generate"
    name = "Creative Pack Generation"
    vertical = "creative"
    capability = "marketing.plan"
    platform_hint = "creative pack generation"
    policy_default = "generate_only"

    def execute_tool_result(self, brief: dict) -> tuple[dict, dict]:
        """Stage 2: LLM-driven strategic planning for a creative production run."""
        start = time.perf_counter()

        visual_theme = brief.get("visual_theme", "Premium Minimalist")
        product = brief.get("product_name") or brief.get("product", "the product")
        audience = brief.get("audience") or brief.get("target_audience", "target audience")
        mood = brief.get("mood", "calm and premium")
        volume = int(brief.get("volume", 10))

        # LLM-backed generation would go here — for now produce a structured
        # scaffold that the operator can revise before primitive generation.
        hooks: List[str] = [
            f"Experience clarity in every {product} moment.",
            f"The quiet space {audience} deserves.",
            "A private moment for your next big decision.",
            f"What {product} feels like when it's right for you.",
            "Designed for people who value the details.",
        ]

        ctas: List[str] = [
            "Book your private discovery call.",
            "Request a confidential consultation.",
            "Reserve your spot today.",
        ]

        primitive_requirements: List[Dict[str, Any]] = [
            {
                "type": "video_plate",
                "count": max(1, volume // 5),
                "description": f"{mood.capitalize()} lifestyle scene — no text, no logos, clean background",
            },
            {
                "type": "image_plate",
                "count": max(2, volume // 3),
                "description": f"Minimalist {product} setting, soft lighting, high-end feel",
            },
            {
                "type": "motion_card",
                "count": 2,
                "description": "Intro card and end card with brand overlay slots",
            },
        ]

        pack = {
            "pack_id": f"pack_{int(time.time())}",
            "visual_theme": visual_theme,
            "hooks": hooks,
            "ctas": ctas,
            "primitive_requirements": primitive_requirements,
            "status": "draft",
        }

        return {
            "provider": "creative_factory",
            "model_id": "pack_planner_v1",
            "status": "succeeded",
            "latency_ms": round((time.perf_counter() - start) * 1000),
        }, {
            "content": f"Creative Pack drafted: {visual_theme} — {len(hooks)} hooks, {len(primitive_requirements)} primitive types needed.",
            "block": {
                "type": "creative_pack",
                "pack": pack,
                "allowed_actions": ["approve", "revise", "generate_primitives"],
            },
        }
