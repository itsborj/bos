from __future__ import annotations

import base64
import json
import math
import struct
import time
import zlib
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from klaroha_sdk import ChannelModule

_OPENAI_IMAGE_URL = "https://api.openai.com/v1/images/generations"
_OPENAI_IMAGE_MODEL_DEFAULT = "gpt-image-2"
_GEMINI_IMAGE_MODEL_DEFAULT = "gemini-2.5-flash-image"
_GEMINI_GEN_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
_MODELARK_BASE = "https://ark.ap-southeast.bytepluses.com/api/v3"
_MODELARK_IMAGE_URL = f"{_MODELARK_BASE}/images/generations"


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
                "allowed_actions": ["use", "regenerate", "dismiss"],
                "action_modules": {},
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
            or brief.get("brand_guidelines_excerpt")
            or brief.get("campaign_brand_kit_excerpt")
            or ""
        ).strip()

        if not (product or brand):
            return ""

        subject = product or brand
        parts = [
            f"Create a brand-aligned marketing image for {subject}.",
            "The image must feel like it belongs to the active brand, not a generic stock or SaaS visual.",
            "Do not include readable text, fake UI labels, random signage, captions, CTA text, or logos inside the generated image; BOS will apply typography, captions, CTA, and logo during stitching.",
        ]
        if audience:
            parts.append(f"Audience: {audience}.")
        if objective:
            parts.append(f"Commercial objective: {objective}.")
        if tone:
            parts.append(f"Brand tone to express visually: {tone}.")
        else:
            parts.append("Visual tone: clean, composed, premium, and commercially grounded.")
        if visual_constraints:
            parts.append(f"Brand constraints to follow: {visual_constraints[:1800]}")
        image_spec = brief.get("image_spec") or brief.get("image_spec_json")
        if image_spec:
            spec_text = image_spec if isinstance(image_spec, str) else json.dumps(image_spec, ensure_ascii=False)
            parts.append("Canonical BOS ImageSpec (provider-neutral source of truth; compile it into this provider prompt, do not replace it): " + spec_text[:5000])
        reference_context = brief.get("operator_reference_context") or brief.get("operator_reference_context_json")
        if reference_context:
            ref_text = reference_context if isinstance(reference_context, str) else json.dumps(reference_context, ensure_ascii=False)
            parts.append("Structured operator reference context JSON. Use readable document excerpts, notes, and vision-ready image references as source context; ignore failed, pending, skipped, or empty items: " + ref_text[:6000])
        return " ".join(parts)

    def _http_post(self, url: str, payload: dict, headers: dict, timeout: int = 120) -> dict:
        req = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "BOS/1.1", **headers},
            method="POST",
        )
        with urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())

    def _generate_openai(self, api_key: str, prompt: str, model: str | None = None) -> tuple[bytes, str]:
        m = (model or _OPENAI_IMAGE_MODEL_DEFAULT).strip()
        data = self._http_post(
            _OPENAI_IMAGE_URL,
            {"model": m, "prompt": prompt, "n": 1, "size": "1024x1024"},
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

    def _generate_bytedance(self, api_key: str, prompt: str, model: str | None = None) -> tuple[bytes, str]:
        """Generate an image via BytePlus (Seedream) using the OpenAI-compatible images endpoint."""
        model_id = model or "seedream-4-5-251128"
        payload = json.dumps({
            "model": model_id,
            "prompt": prompt,
            "n": 1,
            "response_format": "b64_json",
        }).encode("utf-8")
        req = Request(
            _MODELARK_IMAGE_URL,
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "BOS/1.1",
            },
            method="POST",
        )
        with urlopen(req, timeout=120) as r:
            data = json.loads(r.read())
        b64 = data["data"][0]["b64_json"]
        return base64.b64decode(b64), "image/png"

    def _generate_local_sample(self, prompt: str, width: int = 1024, height: int = 1024) -> bytes:
        """Render a deterministic local sample PNG when no external image backend is available.

        This is deliberately labeled as a local renderer in the artifact provider; it
        is not presented as third-party AI output. It keeps the CMO image artifact
        path testable on localhost without storing fake provider success.
        """
        pixels = bytearray()
        prompt_hash = sum(ord(ch) for ch in prompt) % 360
        for y in range(height):
            row = bytearray([0])  # PNG filter type 0
            fy = y / max(1, height - 1)
            for x in range(width):
                fx = x / max(1, width - 1)
                # Racing-green background with subtle warm-gold glow.
                r = int(8 + 38 * fx + 40 * (1 - fy))
                g = int(42 + 70 * (1 - fx) + 30 * fy)
                b = int(36 + 42 * fy)
                glow = max(0.0, 1.0 - math.hypot(fx - 0.72, fy - 0.28) / 0.42)
                r = min(255, int(r + 126 * glow))
                g = min(255, int(g + 92 * glow))
                b = min(255, int(b + 26 * glow))

                # Laptop body and screen.
                if 210 < x < 814 and 300 < y < 660:
                    r, g, b = 18, 34, 36
                if 240 < x < 784 and 335 < y < 620:
                    r, g, b = 236, 229, 204
                if 160 < x < 864 and 660 < y < 715:
                    r, g, b = 34, 40, 39
                if 120 < x < 904 and 716 < y < 742:
                    r, g, b = 196, 160, 82

                # Dashboard cards on the screen.
                cards = [
                    (275, 370, 470, 500, (20, 75, 62)),
                    (500, 370, 745, 430, (205, 162, 78)),
                    (500, 455, 745, 585, (42, 94, 82)),
                    (275, 525, 470, 585, (132, 104, 57)),
                ]
                for x1, y1, x2, y2, color in cards:
                    if x1 < x < x2 and y1 < y < y2:
                        r, g, b = color
                    if (x1 <= x <= x2 and y in (y1, y2)) or (y1 <= y <= y2 and x in (x1, x2)):
                        r, g, b = 248, 240, 216

                # Abstract trend line; varied slightly by prompt hash.
                wave_y = 535 - int(85 * math.sin((x / 1024) * math.pi + prompt_hash / 90))
                if 292 < x < 738 and abs(y - wave_y) <= 3:
                    r, g, b = 235, 184, 86

                row.extend((r, g, b))
            pixels.extend(row)

        def chunk(tag: bytes, data: bytes) -> bytes:
            return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

        raw = bytes(pixels)
        return (
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, level=6))
            + chunk(b"IEND", b"")
        )

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
            or brief.get("brand_guidelines_excerpt")
            or brief.get("campaign_brand_kit_excerpt")
            or ""
        ).strip()
        constraints_applied = False
        if brand_constraints and brand_constraints[:160].lower() not in prompt.lower():
            prompt = f"{prompt}. Follow these brand visual constraints: {brand_constraints[:1800]}"
            constraints_applied = True

        try:
            if provider == "openai":
                api_key = str(creds.get("provider_api_key") or creds.get("image_gen_api_key") or "").strip()
                if not api_key:
                    return self._failure(start, "missing_credentials", "OpenAI platform key not configured — set PLATFORM_OPENAI_KEY", provider)
                openai_model = str(creds.get("image_gen_model") or "").strip() or None
                image_bytes, mime = self._generate_openai(api_key, prompt, model=openai_model)

            elif provider == "gemini":
                api_key = str(creds.get("provider_api_key") or creds.get("image_gen_api_key") or "").strip()
                if not api_key:
                    return self._failure(start, "missing_credentials", "Gemini platform key not configured — set PLATFORM_GEMINI_KEY", provider)
                gemini_model = str(creds.get("image_gen_model") or "").strip() or None
                image_bytes, mime = self._generate_gemini(api_key, prompt, model=gemini_model)

            elif provider == "bytedance":
                api_key = str(creds.get("provider_api_key") or creds.get("image_gen_api_key") or "").strip()
                if not api_key:
                    return self._failure(start, "missing_credentials", "BytePlus API key not configured — add it via Admin → AI Providers", provider)
                bd_model = str(creds.get("image_gen_model") or "").strip() or None
                image_bytes, mime = self._generate_bytedance(api_key, prompt, model=bd_model)

            elif provider in {"local", "local_sample", "local_renderer"}:
                image_bytes = self._generate_local_sample(prompt)
                mime = "image/png"

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
        if "image generation failed" in lowered:
            failures.append("generation_failed")
        if "image" not in lowered:
            failures.append("missing_image_reference")
        constraints = str(brief.get("brand_visual_constraints") or brief.get("campaign_brand_kit_excerpt") or "").strip()
        if constraints and "brand visual constraints" not in lowered and constraints[:80].lower() not in lowered:
            failures.append("brand_constraints_not_applied")
        return ("fail" if failures else "pass"), failures
