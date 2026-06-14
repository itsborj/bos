from __future__ import annotations

import base64
import importlib.util
import json
import logging
import os
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from klaroha_sdk import ChannelModule

_logger = logging.getLogger(__name__)

_DRIVE_CLIENT_CANDIDATES = [
    Path(__file__).resolve().parents[5] / "google-drive" / "drive_client.py",
    Path("/external_plugins/google-drive/drive_client.py"),
    Path("/app/plugins/google-drive/drive_client.py"),
]

# Gemini Veo endpoints — veo-3.0 is the default (veo-2.0 requires separate GCP billing)
_VEO_MODEL = "veo-3.0-generate-001"
_VEO_PREDICT_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{_VEO_MODEL}:predictLongRunning"
)
_VEO_POLL_BASE = "https://generativelanguage.googleapis.com/v1beta"
_VEO_POLL_INTERVAL = 8   # seconds between polls
_VEO_MAX_POLLS = 45      # ~6 minutes total

# BytePlus — Seedance via async task API
_MODELARK_BASE = "https://ark.ap-southeast.bytepluses.com/api/v3"
_MODELARK_POLL_INTERVAL = 4   # seconds
_MODELARK_MAX_POLLS = 45      # ~3 minutes

# Providers — kling reserved for future
_KNOWN_PROVIDERS = frozenset({"gemini", "seedance", "custom", "custom_http", "bytedance"})

_ASPECT_SIZES: dict[str, tuple[int, int]] = {
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
    "1:1": (1080, 1080),
    "4:5": (1080, 1350),
}
_VALID_ASPECT_RATIOS = set(_ASPECT_SIZES)


def _load_drive():
    for p in _DRIVE_CLIENT_CANDIDATES:
        if p.exists():
            spec = importlib.util.spec_from_file_location("google_drive_client_mv", str(p))
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
            return m
    raise ImportError(f"google-drive drive_client.py not found in: {_DRIVE_CLIENT_CANDIDATES}")


def _http_post(url: str, payload: dict, headers: dict, timeout: int = 120) -> dict:
    req = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "BOS/1.1", **headers},
        method="POST",
    )
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _http_get(url: str, headers: dict | None = None, timeout: int = 30) -> dict:
    req = Request(url, headers={"User-Agent": "BOS/1.1", **(headers or {})})
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _generate_gemini_veo(api_key: str, prompt: str, aspect_ratio: str, duration: float, output_path: str, *, auth_mode: str | None = None) -> str | None:
    """Submit to Gemini Veo, poll until done, write MP4 to output_path.
    Returns an external video URL if the provider returns one instead of inline bytes."""
    # Cap duration at Veo's maximum (8 seconds for veo-2)
    veo_duration = int(min(duration, 8))

    if auth_mode == "oauth":
        auth_headers: dict = {"Authorization": f"Bearer {api_key}"}
        key_param = ""
    else:
        auth_headers = {}
        key_param = f"?key={api_key}"

    op = _http_post(
        f"{_VEO_PREDICT_URL}{key_param}",
        {
            "instances": [{"prompt": prompt}],
            "parameters": {
                "aspectRatio": aspect_ratio,
                "sampleCount": 1,
                "durationSeconds": veo_duration,
            },
        },
        auth_headers,
        timeout=60,
    )
    op_name = op.get("name") or op.get("operationId")
    if not op_name:
        raise ValueError(f"Veo did not return an operation name: {list(op)}")

    # Poll for completion
    status: dict = {}
    for _ in range(_VEO_MAX_POLLS):
        time.sleep(_VEO_POLL_INTERVAL)
        status = _http_get(f"{_VEO_POLL_BASE}/{op_name}{key_param}", auth_headers)
        if status.get("done"):
            break

    if not status.get("done"):
        raise TimeoutError(f"Veo operation did not complete after {_VEO_MAX_POLLS * _VEO_POLL_INTERVAL}s")

    error = status.get("error")
    if error:
        raise RuntimeError(f"Veo operation failed: {error.get('message', error)}")

    # Response shape varies — handle multiple formats
    response = status.get("response", status)
    predictions = response.get("predictions") or response.get("generatedVideos") or []

    if not predictions:
        raise ValueError(f"Veo returned no predictions: {list(response)}")

    pred = predictions[0]

    # Inline base64 video
    video_b64 = (
        pred.get("video", {}).get("videoBase64")
        or pred.get("videoBase64")
        or pred.get("video_b64")
    )
    if video_b64:
        with open(output_path, "wb") as fh:
            fh.write(base64.b64decode(video_b64))
        return None

    # URI / URL response
    video_uri = (
        pred.get("video", {}).get("uri")
        or pred.get("videoUri")
        or pred.get("uri")
        or pred.get("url")
    )
    if video_uri:
        # Download into output_path
        vid_req = Request(video_uri, headers={"User-Agent": "BOS/1.1"})
        with urlopen(vid_req, timeout=120) as r:
            with open(output_path, "wb") as fh:
                fh.write(r.read())
        return video_uri

    raise ValueError(f"Veo prediction has no recognisable video field: {list(pred)}")


def _generate_bytedance_modelark(api_key: str, model_id: str, prompt: str, aspect_ratio: str, duration: float, output_path: str) -> str:
    """Submit a video generation task to BytePlus and poll until done.
    Returns the temporary video URL; does not save to disk (caller handles download if needed)."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "BOS/1.1",
    }
    # Clamp duration to ModelArk accepted range
    ark_duration = int(max(4, min(10, duration)))
    payload = {
        "model": model_id,
        "content": [{"type": "text", "text": prompt}],
        "resolution": "480p",
        "ratio": aspect_ratio.replace(":", "x") if ":" in aspect_ratio else "16x9",
        "duration": ark_duration,
        "generate_audio": False,
        "watermark": True,
    }
    # Use ratio format ModelArk expects
    payload["ratio"] = aspect_ratio  # e.g. "16:9" is accepted by ModelArk
    create_req = Request(
        f"{_MODELARK_BASE}/contents/generations/tasks",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urlopen(create_req, timeout=30) as r:
        task_id = json.loads(r.read())["id"]

    for _ in range(_MODELARK_MAX_POLLS):
        time.sleep(_MODELARK_POLL_INTERVAL)
        poll_req = Request(
            f"{_MODELARK_BASE}/contents/generations/tasks/{task_id}",
            headers={"Authorization": f"Bearer {api_key}", "User-Agent": "BOS/1.1"},
        )
        with urlopen(poll_req, timeout=15) as r:
            data = json.loads(r.read())
        status = data.get("status")
        if status == "succeeded":
            video_url = data["content"]["video_url"]
            vid_req = Request(video_url, headers={"User-Agent": "BOS/1.1"})
            with urlopen(vid_req, timeout=120) as r:
                with open(output_path, "wb") as fh:
                    fh.write(r.read())
            return video_url
        if status in ("failed", "cancelled"):
            raise RuntimeError(f"ModelArk task {status}: {data.get('error', {})}")

    raise TimeoutError(f"ModelArk video task did not complete in {_MODELARK_MAX_POLLS * _MODELARK_POLL_INTERVAL}s")


def _generate_http_provider(provider_url: str, api_key: str, payload: dict, output_path: str) -> str | None:
    """Generic HTTP video provider (Seedance, custom). Returns external URL if available."""
    req = Request(
        provider_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json, video/mp4",
            "User-Agent": "BOS/1.1",
        },
        method="POST",
    )
    with urlopen(req, timeout=240) as response:
        content_type = response.headers.get("Content-Type", "")
        body = response.read()

    # Direct video bytes
    if "video/" in content_type or body[4:8] == b"ftyp":
        with open(output_path, "wb") as fh:
            fh.write(body)
        return None

    data = json.loads(body.decode("utf-8"))

    video_b64 = data.get("video_data_b64") or data.get("video_b64")
    if video_b64:
        with open(output_path, "wb") as fh:
            fh.write(base64.b64decode(video_b64))
        return data.get("video_url") or data.get("url")

    video_url = data.get("video_url") or data.get("url")
    if video_url:
        vid_req = Request(video_url, headers={"User-Agent": "BOS/1.1"})
        with urlopen(vid_req, timeout=120) as r:
            with open(output_path, "wb") as fh:
                fh.write(r.read())
        return video_url

    raise ValueError(f"Provider response has no video field: {list(data)}")


class MediaVideoGenerateModule(ChannelModule):
    id = "media.video.generate"
    legacy_ids = ["creative.shortform.video"]
    name = "Video Generation"
    vertical = "media"
    capability = "media.generate"
    platform_hint = "video generation"
    policy_default = "generate_only"
    template = ""

    def _attempt(self, start: float, status: str, provider: str, error=None) -> dict:
        return {
            "provider": provider or "video_gen",
            "model_id": "video_generate_v1",
            "mode": "tool",
            "status": status,
            "tokens_input": 0,
            "tokens_output": 0,
            "provider_cost": 0.0,
            "latency_ms": round((time.perf_counter() - start) * 1000),
            "error": error,
        }

    def _fail(self, start: float, provider: str, reason: str, msg: str) -> tuple[dict, dict]:
        return self._attempt(start, "failed", provider, reason), {
            "content": f"Video generation failed: {msg}",
            "block": {
                "type": "video_asset",
                "status": "failed",
                "reason_code": reason,
                "message": msg,
                "allowed_actions": ["retry", "dismiss"],
            },
        }

    @staticmethod
    def _compose_hook(brief: dict) -> str:
        brand = str(brief.get("brand_name") or "").strip()
        tagline = str(brief.get("tagline") or "").strip()
        product = str(brief.get("product_name") or "").strip()
        benefit = str(brief.get("key_benefit") or "").strip()
        if tagline:
            return tagline[:120]
        if brand and benefit:
            return f"{brand}: {benefit}"[:120]
        if brand and product and product.lower() != brand.lower():
            return f"Introducing {product} by {brand}"[:120]
        if brand:
            return f"Introducing {brand}"[:120]
        return "See what's possible"

    @staticmethod
    def _compose_cta(brief: dict) -> str:
        domain = str(
            brief.get("domain") or brief.get("website_url") or brief.get("display_url") or ""
        ).strip()
        return f"Visit {domain}" if domain else "Learn more"

    @staticmethod
    def _operator_reference_context_text(brief: dict, cap: int = 7000) -> str:
        payload = brief.get("operator_reference_context")
        if not payload and brief.get("operator_reference_context_json"):
            try:
                payload = json.loads(str(brief.get("operator_reference_context_json") or "{}"))
            except Exception:
                payload = None
        if not isinstance(payload, dict) or not payload.get("items"):
            return ""
        return json.dumps(payload, ensure_ascii=False)[:cap]

    def _compose_video_prompt(self, brief: dict, hook_text: str, cta_text: str) -> str:
        brand = str(brief.get("brand_name") or "").strip()
        request = str(brief.get("request") or brief.get("objective") or brief.get("message") or "").strip()
        audience = str(brief.get("audience") or brief.get("target_audience") or "").strip()
        tone = str(brief.get("tone") or brief.get("voice") or "").strip()
        constraints = str(brief.get("campaign_brand_kit_excerpt") or brief.get("brand_guidelines_excerpt") or "").strip()
        reference_context = self._operator_reference_context_text(brief)
        parts = [
            "Generate a brand-safe short-form marketing video asset.",
            "Use clean cinematic footage/motion; avoid baked-in captions, fake readable text, fake logos, gore, shock, or exploitative grief imagery.",
        ]
        if brand:
            parts.append(f"Brand: {brand}.")
        if request:
            parts.append(f"Operator request: {request}.")
        if audience:
            parts.append(f"Audience: {audience}.")
        if hook_text:
            parts.append(f"Core hook/emotional frame: {hook_text}.")
        if cta_text:
            parts.append(f"CTA intent: {cta_text}.")
        if tone:
            parts.append(f"Brand tone: {tone}.")
        if constraints:
            parts.append(f"Brand constraints: {constraints[:1800]}")
        if reference_context:
            parts.append(
                "Structured operator reference context JSON. Use readable document excerpts, notes, and vision-ready image references as source context; ignore failed or metadata-only items: "
                + reference_context
            )
        return " ".join(parts)

    def execute_tool_result(self, brief: dict) -> tuple[dict, dict]:
        start = time.perf_counter()
        creds = brief.get("_channel_credentials", {}) if isinstance(brief, dict) else {}

        provider = str(creds.get("video_gen_provider") or "bytedance").lower().strip()
        provider_url = str(creds.get("video_gen_api_url") or "").strip()
        api_key = str(creds.get("provider_api_key") or creds.get("video_gen_api_key") or "").strip()

        drive_token = str(creds.get("page_token") or creds.get("google_drive_page_token") or "").strip()
        drive_root = str(creds.get("drive_root_folder_id") or "").strip()

        hook_text = str(brief.get("hook_text") or brief.get("headline") or "").strip() or self._compose_hook(brief)
        cta_text = str(brief.get("cta_text") or brief.get("cta") or "").strip() or self._compose_cta(brief)
        aspect_ratio = str(brief.get("aspect_ratio") or "9:16").strip()
        if aspect_ratio not in _VALID_ASPECT_RATIOS:
            aspect_ratio = "9:16"
        duration = max(5.0, min(60.0, float(brief.get("duration") or 15)))
        # bg_color / text_color are available in brief for future overlay rendering;
        # current provider integrations do not use them yet.
        brand_name = str(brief.get("brand_name") or "").strip()
        reference_context = self._operator_reference_context_text(brief)
        prompt = str(brief.get("video_prompt") or brief.get("prompt") or "").strip()
        if not prompt:
            prompt = self._compose_video_prompt(brief, hook_text, cta_text)
        elif reference_context and "operator reference context" not in prompt.lower():
            prompt = (
                f"{prompt}\n\nStructured operator reference context JSON for source grounding. "
                f"Use readable excerpts and vision-ready references; ignore failed/metadata-only items:\n{reference_context}"
            )

        output_path = f"/tmp/bos_video_{uuid.uuid4().hex[:12]}.mp4"
        external_video_url: str | None = None

        try:
            if provider == "gemini":
                _pk = str(creds.get("provider_api_key") or creds.get("video_gen_api_key") or "").strip()
                if not _pk:
                    return self._fail(start, provider, "missing_credentials", "Gemini platform key not configured — set PLATFORM_GEMINI_KEY or connect via Admin → AI Providers → Login")
                _veo_auth_mode = str(creds.get("provider_api_key_auth_mode") or "").strip() or None
                external_video_url = _generate_gemini_veo(_pk, prompt, aspect_ratio, duration, output_path, auth_mode=_veo_auth_mode)

            elif provider == "bytedance":
                _pk = str(creds.get("provider_api_key") or creds.get("video_gen_api_key") or "").strip()
                if not _pk:
                    return self._fail(start, provider, "missing_credentials", "BytePlus API key not configured — add it via Admin → AI Providers")
                model_id = str(creds.get("video_gen_model") or "").strip()
                if not model_id:
                    return self._fail(start, provider, "missing_credentials", "No BytePlus model selected — choose one via Admin → AI Providers → Media Generation")
                external_video_url = _generate_bytedance_modelark(_pk, model_id, prompt, aspect_ratio, duration, output_path)

            elif provider in ("seedance", "custom", "custom_http"):
                if not provider_url.startswith("http"):
                    return self._fail(start, provider, "missing_credentials", f"VIDEO_GEN_API_URL not configured for {provider} provider")
                if not api_key:
                    return self._fail(start, provider, "missing_credentials", f"VIDEO_GEN_API_KEY not configured for {provider} provider")
                payload = {
                    "prompt": prompt,
                    "hook_text": hook_text,
                    "cta_text": cta_text,
                    "brand_name": brand_name,
                    "aspect_ratio": aspect_ratio,
                    "duration": duration,
                    "metadata": {"provider": provider, "source": "bos.media.video.generate"},
                }
                external_video_url = _generate_http_provider(provider_url, api_key, payload, output_path)

            else:
                return self._fail(start, provider, "missing_credentials", f"Unknown or unconfigured video provider: {provider!r} — configure video_gen_provider via Admin → AI Providers")

        except TimeoutError as exc:
            return self._fail(start, provider, "timeout", str(exc))
        except (HTTPError, URLError) as exc:
            detail = str(getattr(exc, "reason", exc))
            return self._fail(start, provider, "api_call_failed", detail)
        except (json.JSONDecodeError, ValueError, KeyError, IndexError) as exc:
            return self._fail(start, provider, "unexpected_response", str(exc))
        except (OSError, RuntimeError) as exc:
            return self._fail(start, provider, "generation_failed", str(exc))

        if not external_video_url and (not os.path.exists(output_path) or os.path.getsize(output_path) == 0):
            return self._fail(start, provider, "empty_response", "Provider returned no video")

        size_kb = os.path.getsize(output_path) // 1024 if os.path.exists(output_path) else None

        drive_file_id: str | None = None
        drive_web_view_link: str | None = None
        if drive_token and drive_root and os.path.exists(output_path):
            try:
                dc = _load_drive()
                vid_name = f"video_{int(time.time())}.mp4"
                with open(output_path, "rb") as fh:
                    vid_bytes = fh.read()
                with dc.DriveClient(drive_token) as client:
                    folder = client.ensure_path(["Creative Assets", "Video"], drive_root)
                    meta = client.upload_file(vid_name, vid_bytes, "video/mp4", folder)
                drive_file_id = meta.get("id")
                drive_web_view_link = meta.get("webViewLink")
            except Exception as exc:
                _logger.warning("Drive upload failed for video asset: %s", exc)

        return self._attempt(start, "succeeded", provider), {
            "content": (
                f"Video generated.\n\nHook: {hook_text}\nFormat: {aspect_ratio} / {int(duration)}s"
                + (f" / {size_kb}KB" if size_kb is not None else "")
                + (f"\nDrive: {drive_web_view_link}" if drive_web_view_link else "")
            ),
            "block": {
                "type": "video_asset",
                "legacy_type": "creative_shortform_video",
                "status": "succeeded",
                "video_path": output_path if os.path.exists(output_path) else None,
                "video_url": external_video_url,
                "hook_text": hook_text,
                "cta_text": cta_text,
                "prompt": prompt,
                "provider": provider,
                "aspect_ratio": aspect_ratio,
                "duration": duration,
                "file_size_kb": size_kb,
                "drive_file_id": drive_file_id,
                "drive_web_view_link": drive_web_view_link,
                "drive_folder": "Creative Assets/Video" if drive_file_id else None,
                "reusable": bool(drive_file_id or external_video_url),
                "operator_reference_context": brief.get("operator_reference_context"),
                "source_variables": (brief.get("operator_reference_context") or {}).get("variables", []) if isinstance(brief.get("operator_reference_context"), dict) else [],
                "allowed_actions": ["publish_youtube", "publish_facebook", "regenerate", "dismiss"],
                "action_modules": {
                    "publish_youtube": "marketing.channel.youtube.video.publish",
                    "publish_facebook": "marketing.channel.meta.video.publish",
                },
            },
        }

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        failures = []
        lowered = content.lower() if isinstance(content, str) else ""
        if "video generation failed" in lowered:
            failures.append("generation_failed")
        if "video generated" not in lowered and "video generation failed" not in lowered:
            failures.append("missing_video_status")
        return ("fail" if failures else "pass"), failures
