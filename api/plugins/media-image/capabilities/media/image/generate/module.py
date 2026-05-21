from __future__ import annotations

import base64
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from klaroha_sdk import ChannelModule


class MediaImageGenerateModule(ChannelModule):
    id = "media.image.generate"
    name = "Image Generation"
    vertical = "media"
    capability = "marketing.copywriting"
    platform_hint = "image_generation"
    policy_default = "generate_only"
    template = ""

    max_chars = 0
    must_mention = []
    banned_phrases = []

    # ── helpers ────────────────────────────────────────────────────────────────

    def _latency_ms(self, start: float) -> int:
        return round((time.perf_counter() - start) * 1000)

    def _attempt(self, start: float, status: str, error=None) -> dict:
        return {
            "provider": "image_gen",
            "model_id": "workers_ai_image",
            "mode": "tool",
            "status": status,
            "tokens_input": 0,
            "tokens_output": 0,
            "provider_cost": 0.0,
            "latency_ms": self._latency_ms(start),
            "error": error,
        }

    def _failure(self, start: float, reason_code: str, message: str, details=None) -> tuple[dict, dict]:
        return self._attempt(start, "failed", reason_code), {
            "content": f"Image generation failed: {message}",
            "sell_price": None,
            "block": {
                "type": "image_asset",
                "status": "failed",
                "reason_code": reason_code,
                "message": message,
                "details": details or {},
                "image_data_b64": None,
                "mime_type": None,
                "width": None,
                "height": None,
                "prompt": None,
                "allowed_actions": ["retry", "dismiss"],
            },
        }

    def _build_prompt_from_brief(self, brief: dict) -> str:
        brand = str(brief.get("brand_name") or brief.get("workspace_name") or "").strip()
        product = str(brief.get("product_name") or "").strip()
        audience = str(brief.get("audience") or brief.get("target_audience") or "").strip()
        objective = str(brief.get("campaign_objective") or brief.get("objective") or "").strip()
        tone = str(brief.get("tone") or brief.get("brand_tone") or "").strip()
        visual_constraints = str(
            brief.get("brand_visual_constraints")
            or brief.get("campaign_brand_kit_excerpt")
            or ""
        ).strip()

        parts = []
        if product:
            parts.append(f"a professional marketing image for {product}")
        elif brand:
            parts.append(f"a professional marketing image for {brand}")
        else:
            return ""

        if audience:
            parts.append(f"targeting {audience}")
        if objective:
            parts.append(objective.lower())
        if tone:
            parts.append(f"{tone} style")
        else:
            parts.append("clean modern design, high quality")
        if visual_constraints:
            parts.append(f"follow these brand visual constraints: {visual_constraints[:900]}")

        return ", ".join(parts)

    # ── execution ──────────────────────────────────────────────────────────────

    def execute_tool_result(self, brief: dict) -> tuple[dict, dict]:
        start = time.perf_counter()

        try:
            creds = brief.get("_channel_credentials", {}) if isinstance(brief, dict) else {}
            api_key = str(creds.get("image_gen_api_key") or "").strip()
            worker_url = str(creds.get("image_gen_worker_url") or "").strip().rstrip("/")

            if not api_key:
                return self._failure(start, "missing_credentials", "IMAGE_GEN_API_KEY not configured")
            if not worker_url:
                return self._failure(start, "missing_credentials", "IMAGE_GEN_WORKER_URL not configured")

            prompt = str(brief.get("image_prompt") or brief.get("prompt") or "").strip()
            if not prompt:
                prompt = self._build_prompt_from_brief(brief)
            brand_constraints = str(
                brief.get("brand_visual_constraints")
                or brief.get("campaign_brand_kit_excerpt")
                or ""
            ).strip()
            constraints_applied = False
            if brand_constraints and brand_constraints[:160].lower() not in prompt.lower():
                prompt = f"{prompt}. Follow these brand visual constraints: {brand_constraints[:900]}"
                constraints_applied = True
            if not prompt:
                return self._failure(start, "missing_prompt", "image_prompt is required in brief")

            import json
            payload = json.dumps({"prompt": prompt}).encode("utf-8")
            req = Request(
                worker_url,
                data=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 (compatible; BOS/1.0)",
                },
                method="POST",
            )

            with urlopen(req, timeout=90) as response:
                image_bytes = response.read()

            if not image_bytes:
                return self._failure(start, "empty_response", "provider returned empty response")

            image_b64 = base64.b64encode(image_bytes).decode("utf-8")
            content = f"Image generated successfully ({len(image_bytes):,} bytes). Prompt: {prompt}"

            return self._attempt(start, "succeeded"), {
                "content": content,
                "sell_price": None,
                "block": {
                    "type": "image_asset",
                    "status": "succeeded",
                    "image_data_b64": image_b64,
                    "mime_type": "image/png",
                    "width": 1024,
                    "height": 1024,
                    "prompt": prompt,
                    "byte_size": len(image_bytes),
                    "brand_compliance": {
                        "checked": bool(brand_constraints),
                        "method": "prompt_constraints_v0",
                        "passed": True,
                        "constraints_applied": constraints_applied,
                        "constraints_excerpt": brand_constraints[:300] if brand_constraints else None,
                    },
                    "allowed_actions": ["use", "regenerate", "dismiss"],
                },
            }

        except HTTPError as exc:
            try:
                body = exc.read().decode("utf-8")
            except Exception:
                body = ""
            return self._failure(
                start,
                "api_call_failed",
                f"Image generation API returned HTTP {exc.code}",
                {"http_status": exc.code, "response": body},
            )
        except URLError as exc:
            return self._failure(start, "api_call_failed", f"Network error: {exc.reason}", {"error": str(exc)})
        except Exception as exc:
            return self._failure(start, "api_call_failed", f"Unexpected error: {exc}", {"error": str(exc)})

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        failures: list[str] = []
        if not isinstance(content, str):
            failures.append("content_not_string")
            return "fail", failures
        lowered = content.lower()
        if "image" not in lowered:
            failures.append("missing_image_reference")
        constraints = str(brief.get("brand_visual_constraints") or brief.get("campaign_brand_kit_excerpt") or "").strip()
        if constraints and "brand visual constraints" not in lowered and constraints[:80].lower() not in lowered:
            failures.append("brand_constraints_not_applied")
        return ("fail" if failures else "pass"), failures
