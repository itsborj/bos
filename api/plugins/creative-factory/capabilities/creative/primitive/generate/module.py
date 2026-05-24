from __future__ import annotations
import time
import uuid
from typing import Any

from klaroha_sdk import ChannelModule

# Modality inferred from primitive type
_MODALITY_MAP = {
    "video_plate": "video",
    "motion_card": "video",
    "image_plate": "image",
    "product_cutout": "image",
    "brand_overlay": "image",
    "thumbnail_frame": "image",
    "audio_bed": "audio",
    "voiceover": "audio",
}


class CreativePrimitiveGenerateModule(ChannelModule):
    id = "creative.primitive.generate"
    name = "Primitive Production"
    vertical = "creative"
    capability = "marketing.execute"
    platform_hint = "creative primitive generation"
    policy_default = "generate_only"

    def execute_tool_result(self, brief: dict) -> tuple[dict, dict]:
        """Stage 3: Route to the correct generation backend and register the primitive."""
        start = time.perf_counter()

        primitive_type = brief.get("primitive_type", "image_plate")
        prompt = brief.get("prompt", "").strip()
        brand_id = brief.get("brand_id")

        if not prompt:
            return {"status": "failed", "error": "prompt is required"}, {
                "content": "Primitive generation failed: no prompt provided."
            }

        modality = _MODALITY_MAP.get(primitive_type, "image")

        # Routing hint for the executor layer — the media-image plugin handles
        # image generation; video routes to a video provider when available.
        # The executor injects provider results via _image_data_b64 / _video_url.
        image_b64 = brief.get("_image_data_b64")
        video_url = brief.get("_video_url")

        if modality == "image" and not image_b64:
            # Forward to media-image plugin via the brief's image_prompt field.
            # The executor pre-generation hook will populate _image_data_b64 on
            # the next pass if the caller sets image_prompt.
            return {
                "provider": "creative_factory",
                "model_id": "primitive_router_v1",
                "status": "needs_generation",
                "latency_ms": round((time.perf_counter() - start) * 1000),
            }, {
                "content": f"Primitive queued for generation: {primitive_type} — set image_prompt in brief to trigger media-image.",
                "block": {
                    "type": "creative_primitive_pending",
                    "primitive_type": primitive_type,
                    "prompt": prompt,
                    "image_prompt": prompt,
                    "allowed_actions": ["retry_with_provider", "upload_manually"],
                },
            }

        asset_id = f"prim_{uuid.uuid4().hex[:12]}"
        source = "media_image" if image_b64 else (brief.get("preferred_provider") or "manual")

        primitive = {
            "primitive_id": asset_id,
            "brand_id": brand_id,
            "type": primitive_type,
            "modality": modality,
            "asset_id": asset_id,
            "source": source,
            "metadata": {
                "prompt": prompt,
                "has_image": bool(image_b64),
                "has_video": bool(video_url),
            },
            "approval_status": "draft",
        }

        return {
            "provider": "creative_factory",
            "model_id": "primitive_router_v1",
            "status": "succeeded",
            "latency_ms": round((time.perf_counter() - start) * 1000),
        }, {
            "content": f"Primitive produced: {asset_id} ({primitive_type})",
            "block": {
                "type": "creative_primitive",
                "primitive": primitive,
                "image_b64": image_b64,
                "allowed_actions": ["approve", "regenerate", "add_to_blueprint"],
            },
        }
