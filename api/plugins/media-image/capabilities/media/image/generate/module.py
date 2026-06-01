from __future__ import annotations

import base64
import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from klaroha_sdk import ChannelModule

_OPENAI_IMAGE_URL = "https://api.openai.com/v1/images/generations"
# gemini-2.5-flash-image uses generateContent (same tier as text Gemini calls).
# imagen-4.0-* uses predict but requires a paid Gemini plan — configure IMAGE_GEN_MODEL
# to switch (e.g. imagen-4.0-generate-001).
_GEMINI_IMAGE_MODEL_DEFAULT = "gemini-2.5-flash-image"
_GEMINI_GEN_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


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

    def _latency_ms(self, start: float) -> int:
        return round((time.perf_counter() - start) * 1000)

    def _attempt(self, start: float, status: str, provider: str = "image_gen", error=None) -> dict:
        return {
            "provider": provider,
            "model_id": "image_generate_v1",
            "mode": "tool",
            "status": status,
            "tokens_input": 0,
            "tokens_output": 0,
            "provider_cost": 0.0,
            "latency_ms": self._latency_ms(start),
            "error": error,
        }

    def _failure(self, start: float, reason_code: str, message: str, provider: str = "image_gen", details=None) -> tuple[dict, dict]:
        return self._attempt(start, "failed", provider, reason_code), {
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

    def _success(self, start: float, image_b64: str, mime: str, prompt: str, provider: str, byte_size: int, brand_constraints: str, constraints_applied: bool) -> tuple[dict, dict]:
        return self._attempt(start, "succeeded", provider), {
            "content": f"Image generated successfully ({byte_size:,} bytes). Prompt: {prompt}",
            "sell_price": None,
            "block": {
                "type": "image_asset",
                "status": "succeeded",
                "image_data_b64": image_b64,
                "mime_type": mime,
                "width": 1024,
                "height": 1024,
                "prompt": prompt,
                "provider": provider,
                "byte_size": byte_size,
                "brand_compliance": {
                    "checked": bool(brand_constraints),
                    "method": "prompt_constraints_v0",
                    "passed": True,
                    "constraints_applied": constraints_applied,
                    "constraints_excerpt": brand_constraints[:300] if brand_constraints else None,
                },
                "allowed_actions": ["publish_facebook", "use", "regenerate", "dismiss"],
                "action_modules": {
                    "publish_facebook": "marketing.channel.meta.posts.publish",
                },
            },
        }

    def _build_prompt(self, brief: dict) -> str:
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

    def _http_post(self, url: str, payload: dict, headers: dict, timeout: int = 120) -> dict:
        req = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "BOS/1.1", **headers},
            method="POST",
        )
        with urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())

    def _generate_openai(self, api_key: str, prompt: str) -> tuple[bytes, str]:
        data = self._http_post(
            _OPENAI_IMAGE_URL,
            {"model": "gpt-image-1", "prompt": prompt, "n": 1, "size": "1024x1024"},
            {"Authorization": f"Bearer {api_key}"},
        )
        item = data["data"][0]
        if item.get("b64_json"):
            return base64.b64decode(item["b64_json"]), "image/png"
        # URL response — download
        img_req = Request(item["url"], headers={"User-Agent": "BOS/1.1"})
        with urlopen(img_req, timeout=60) as r:
            return r.read(), "image/png"

    def _generate_gemini(self, api_key: str, prompt: str, model: str | None = None) -> tuple[bytes, str]:
        m = (model or _GEMINI_IMAGE_MODEL_DEFAULT).strip()

        if m.startswith("imagen-"):
            # Imagen 4+ uses predict endpoint (requires paid Gemini plan)
            data = self._http_post(
                f"{_GEMINI_GEN_BASE}/{m}:predict?key={api_key}",
                {"instances": [{"prompt": prompt}], "parameters": {"sampleCount": 1}},
                {},
            )
            pred = data["predictions"][0]
            return base64.b64decode(pred["bytesBase64Encoded"]), pred.get("mimeType", "image/png")

        # generateContent path — gemini-2.5-flash-image et al. (standard Gemini API tier)
        data = self._http_post(
            f"{_GEMINI_GEN_BASE}/{m}:generateContent?key={api_key}",
            {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
            },
            {},
            timeout=60,
        )
        parts = data["candidates"][0]["content"]["parts"]
        for part in parts:
            if part.get("inlineData"):
                inline = part["inlineData"]
                return base64.b64decode(inline["data"]), inline.get("mimeType", "image/png")
        raise ValueError(f"Gemini image response contained no inlineData; parts: {[list(p) for p in parts]}")

    def _generate_custom(self, api_key: str, worker_url: str, prompt: str) -> bytes:
        req = Request(
            worker_url,
            data=json.dumps({"prompt": prompt}).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "BOS/1.1",
            },
            method="POST",
        )
        with urlopen(req, timeout=90) as r:
            return r.read()

    def execute_tool_result(self, brief: dict) -> tuple[dict, dict]:
        start = time.perf_counter()
        creds = brief.get("_channel_credentials", {}) if isinstance(brief, dict) else {}

        provider = str(creds.get("image_gen_provider") or "custom").lower().strip()

        prompt = str(brief.get("image_prompt") or brief.get("prompt") or "").strip()
        if not prompt:
            prompt = self._build_prompt(brief)
        if not prompt:
            return self._failure(start, "missing_prompt", "image_prompt is required in brief", provider)

        brand_constraints = str(
            brief.get("brand_visual_constraints")
            or brief.get("campaign_brand_kit_excerpt")
            or ""
        ).strip()
        constraints_applied = False
        if brand_constraints and brand_constraints[:160].lower() not in prompt.lower():
            prompt = f"{prompt}. Follow these brand visual constraints: {brand_constraints[:900]}"
            constraints_applied = True

        try:
            if provider == "openai":
                api_key = str(creds.get("provider_api_key") or creds.get("image_gen_api_key") or "").strip()
                if not api_key:
                    return self._failure(start, "missing_credentials", "OpenAI platform key not configured — set PLATFORM_OPENAI_KEY", provider)
                image_bytes, mime = self._generate_openai(api_key, prompt)

            elif provider == "gemini":
                api_key = str(creds.get("provider_api_key") or creds.get("image_gen_api_key") or "").strip()
                if not api_key:
                    return self._failure(start, "missing_credentials", "Gemini platform key not configured — set PLATFORM_GEMINI_KEY", provider)
                gemini_model = str(creds.get("image_gen_model") or "").strip() or None
                image_bytes, mime = self._generate_gemini(api_key, prompt, model=gemini_model)

            else:
                # custom / default — existing Cloudflare Workers AI path
                api_key = str(creds.get("image_gen_api_key") or "").strip()
                worker_url = str(creds.get("image_gen_worker_url") or "").strip().rstrip("/")
                if not api_key:
                    return self._failure(start, "missing_credentials", "IMAGE_GEN_API_KEY not configured", provider)
                if not worker_url:
                    return self._failure(start, "missing_credentials", "IMAGE_GEN_WORKER_URL not configured", provider)
                image_bytes = self._generate_custom(api_key, worker_url, prompt)
                mime = "image/png"

        except HTTPError as exc:
            try:
                body = exc.read().decode("utf-8")
            except Exception:
                body = ""
            return self._failure(start, "api_call_failed", f"Provider returned HTTP {exc.code}", provider, {"http_status": exc.code, "response": body[:400]})
        except URLError as exc:
            return self._failure(start, "api_call_failed", f"Network error: {exc.reason}", provider, {"error": str(exc)})
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            return self._failure(start, "unexpected_response", f"Unexpected provider response: {exc}", provider)
        except Exception as exc:
            return self._failure(start, "api_call_failed", f"Unexpected error: {exc}", provider)

        if not image_bytes:
            return self._failure(start, "empty_response", "Provider returned empty response", provider)

        image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        return self._success(start, image_b64, mime, prompt, provider, len(image_bytes), brand_constraints, constraints_applied)

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
