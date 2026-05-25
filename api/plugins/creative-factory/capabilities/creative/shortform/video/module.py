from __future__ import annotations

import importlib.util
import os
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

from klaroha_sdk import ChannelModule

_FFMPEG = os.environ.get("FFMPEG_PATH", "ffmpeg")
_FONT = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
_DRIVE_CLIENT_PATH = "/app/plugins/google-drive/drive_client.py"

_ASPECT_SIZES: dict[str, tuple[int, int]] = {
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
    "1:1": (1080, 1080),
    "4:5": (1080, 1350),
}
_VALID_ASPECT_RATIOS = set(_ASPECT_SIZES)


def _load_drive():
    spec = importlib.util.spec_from_file_location("google_drive_client_sv", _DRIVE_CLIENT_PATH)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _esc(text: str) -> str:
    return (
        text
        .replace("\\", "\\\\")
        .replace("'", "’")
        .replace(":", "\\:")
        .replace(",", "\\,")
        .replace("[", "\\[")
        .replace("]", "\\]")
    )


def _font_arg() -> str:
    return f"fontfile={_FONT}:" if Path(_FONT).exists() else ""


def _build_drawtext_filters(
    hook_text: str,
    cta_text: str,
    brand_name: str,
    duration: float,
    text_color: str,
    h: int,
) -> list[str]:
    fa = _font_arg()
    filters: list[str] = []

    if brand_name:
        fs = max(28, h // 50)
        filters.append(
            f"drawtext={fa}text='{_esc(brand_name.upper())}':"
            f"fontcolor={text_color}:fontsize={fs}:"
            f"x=(w-text_w)/2:y=h*0.05:"
            f"enable='between(t,0,{duration})'"
        )

    if hook_text:
        hook_end = min(duration * 0.6, 8.0)
        fs = max(52, h // 22)
        filters.append(
            f"drawtext={fa}text='{_esc(hook_text[:120])}':"
            f"fontcolor={text_color}:fontsize={fs}:"
            f"x=(w-text_w)/2:y=(h-text_h)/2:"
            f"enable='between(t,0.5,{hook_end:.1f})'"
        )

    if cta_text:
        cta_start = min(duration * 0.7, 10.0)
        fs = max(36, h // 36)
        filters.append(
            f"drawtext={fa}text='{_esc(cta_text)}':"
            f"fontcolor={text_color}:fontsize={fs}:"
            f"x=(w-text_w)/2:y=h*0.85:"
            f"enable='between(t,{cta_start:.1f},{duration})'"
        )

    return filters


def _render(
    hook_text: str,
    cta_text: str,
    brand_name: str,
    duration: float,
    aspect_ratio: str,
    bg_color: str,
    text_color: str,
    output_path: str,
) -> None:
    w, h = _ASPECT_SIZES[aspect_ratio]
    bg = bg_color.lstrip("#")

    filters = _build_drawtext_filters(hook_text, cta_text, brand_name, duration, text_color, h)
    vf = ",".join(filters) if filters else "null"

    cmd = [
        _FFMPEG, "-y",
        "-f", "lavfi",
        "-i", f"color=c=0x{bg}:size={w}x{h}:rate=30",
        "-vf", vf,
        "-t", str(duration),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "fast",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg error: {result.stderr[-600:]}")


class CreativeShortformVideoModule(ChannelModule):
    id = "creative.shortform.video"
    name = "Shortform Video"
    vertical = "creative"
    capability = "marketing.execute"
    platform_hint = "shortform video"
    policy_default = "generate_only"
    template = ""

    def _attempt(self, start: float, status: str, error=None) -> dict:
        return {
            "provider": "ffmpeg",
            "model_id": "ffmpeg_render_v1",
            "mode": "tool",
            "status": status,
            "tokens_input": 0,
            "tokens_output": 0,
            "provider_cost": 0.0,
            "latency_ms": round((time.perf_counter() - start) * 1000),
            "error": error,
        }

    def _fail(self, start: float, reason: str, msg: str) -> tuple[dict, dict]:
        return self._attempt(start, "failed", reason), {
            "content": f"Shortform video failed: {msg}",
            "block": {
                "type": "creative_shortform_video",
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
            return f"{brand} — {benefit}"[:120]
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

    def execute_tool_result(self, brief: dict) -> tuple[dict, dict]:
        start = time.perf_counter()

        creds = brief.get("_channel_credentials", {}) if isinstance(brief, dict) else {}
        drive_token = str(creds.get("page_token") or creds.get("google_drive_page_token") or "").strip()
        drive_root = str(creds.get("drive_root_folder_id") or "").strip()

        hook_text = str(brief.get("hook_text") or brief.get("headline") or "").strip()
        if not hook_text:
            hook_text = self._compose_hook(brief)

        cta_text = str(brief.get("cta_text") or brief.get("cta") or "").strip()
        if not cta_text:
            cta_text = self._compose_cta(brief)
        aspect_ratio = str(brief.get("aspect_ratio") or "9:16").strip()
        if aspect_ratio not in _VALID_ASPECT_RATIOS:
            aspect_ratio = "9:16"
        duration = max(5.0, min(60.0, float(brief.get("duration") or 15)))
        bg_color = str(brief.get("background_color") or brief.get("primary_color") or "#1a1a1a").strip()
        text_color = str(brief.get("text_color") or "#ffffff").strip()
        brand_name = str(brief.get("brand_name") or "").strip()

        output_path = f"/tmp/bos_shortform_{uuid.uuid4().hex[:12]}.mp4"

        try:
            _render(hook_text, cta_text, brand_name, duration, aspect_ratio, bg_color, text_color, output_path)
        except (subprocess.TimeoutExpired, OSError, RuntimeError) as exc:
            return self._fail(start, "render_failed", str(exc))

        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            return self._fail(start, "render_failed", "FFmpeg produced no output file")

        size_kb = os.path.getsize(output_path) // 1024

        # Upload to Drive for durability — non-fatal if Drive is not connected.
        drive_file_id: str | None = None
        drive_web_view_link: str | None = None
        if drive_token and drive_root:
            try:
                dc = _load_drive()
                vid_name = f"shortform_{int(time.time())}.mp4"
                with open(output_path, "rb") as fh:
                    vid_bytes = fh.read()
                with dc.DriveClient(drive_token) as client:
                    folder = client.ensure_path(["Creative Assets", "Shortform Video"], drive_root)
                    meta = client.upload_file(vid_name, vid_bytes, "video/mp4", folder)
                drive_file_id = meta.get("id")
                drive_web_view_link = meta.get("webViewLink")
            except Exception:
                pass  # Drive upload failure does not block the artifact

        return self._attempt(start, "succeeded"), {
            "content": (
                f"Shortform video rendered.\n\n"
                f"Hook: {hook_text}\n"
                f"Format: {aspect_ratio} · {int(duration)}s · {size_kb}KB"
                + (f"\nDrive: {drive_web_view_link}" if drive_web_view_link else "")
            ),
            "block": {
                "type": "creative_shortform_video",
                "status": "succeeded",
                "video_path": output_path,
                "hook_text": hook_text,
                "cta_text": cta_text,
                "aspect_ratio": aspect_ratio,
                "duration": duration,
                "file_size_kb": size_kb,
                "drive_file_id": drive_file_id,
                "drive_web_view_link": drive_web_view_link,
                "drive_folder": "Creative Assets/Shortform Video",
                "reusable": bool(drive_file_id),
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
        if "shortform video rendered" not in lowered and "shortform video failed" not in lowered:
            failures.append("missing_shortform_video_status")
        return ("fail" if failures else "pass"), failures
