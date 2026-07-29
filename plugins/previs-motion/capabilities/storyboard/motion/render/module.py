from __future__ import annotations

import base64
import importlib.util
import json
import logging
import mimetypes
import os
import time
import uuid
import re
from pathlib import Path
from urllib.parse import quote

import httpx
from klaroha_sdk import ChannelModule
from providers.bytedance import _BASE_URL as _MODELARK_BASE
_DEFAULT_MODEL = "dreamina-seedance-2-0-260128"
_DEFAULT_GEMINI_VEO_MODEL = "veo-3.1-generate-preview"
_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
_SEEDANCE2_MODELS = frozenset({
    "dreamina-seedance-2-0-260128",
})
_GEMINI_VEO_MODELS = frozenset({
    "veo-3.1-generate-preview",
    "veo-3.1-fast-generate-preview",
    "veo-3.1-lite-generate-preview",
})
_INHERITED_IMAGE_MODEL_MARKERS = ("gpt-image", "imagen", "seedream", "image")
_DEFAULT_RESOLUTION = "720p"
_DEFAULT_RATIO = "9:16"
_DEFAULT_DURATION = 15
_DIRECT_T2V_PROMPT_KEYS = (
    "seedance_prompt",
    "raw_prompt",
    "direct_prompt",
    "text_to_video_prompt",
    "prompt",
)


def _split_voiceover_from_visual(text: str) -> tuple[str, str]:
    """Split blueprint text into voiceover lines and visual scene descriptions."""
    if not text:
        return "", ""
    voiceover: list[str] = []
    visual: list[str] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        # Strip bullet/list markers for prefix detection
        clean = re.sub(r'^[-*•]\s*', '', stripped).strip()
        lower = clean.lower()
        # Voiceover lines
        if lower.startswith("voiceover:") or lower.startswith("vo:"):
            content = clean.split(":", 1)[-1].strip().strip('"').strip("'")
            if content:
                voiceover.append(content)
            continue
        # Text overlay lines — skip entirely
        if lower.startswith("text overlay:") or lower.startswith("text:") or lower.startswith("overlay:"):
            continue
        # Visual descriptions
        if lower.startswith("visual:"):
            content = clean.split(":", 1)[-1].strip()
            if content:
                visual.append(content)
            continue
        # Scene/shot markers
        if lower.startswith("scene") or lower.startswith("shot"):
            visual.append(clean)
            continue
        # Keep other lines as visual context
        if not any(kw in lower for kw in ("voiceover", "text overlay", "sound", "music", "audio")):
            if len(clean) > 5:
                visual.append(clean)
    vo_text = "\n".join(voiceover) if voiceover else ""
    vis_text = "\n".join(visual) if visual else ""
    return vo_text, vis_text


def _sanitize_for_seedance(text: str) -> str:
    """Remove content that triggers Seedance copyright/safety violations.

    Seedance 2.0 rejects prompts containing brand names, platform UI references,
    and certain product names as potential copyright violations.
    """
    # Replace brand names with generic descriptions to avoid copyright flags
    replacements = [
        ("Klaroha", "the platform"),
        ("klaroha", "the platform"),
        ("KLAROHA", "the platform"),
        ("Golden Gate Memorial", "the memorial brand"),
        ("Golden Gate", "the memorial brand"),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    return text
# Seedance 2.0 tasks commonly take >2 minutes for 15s i2v, especially with
# audio. Poll long enough for normal completion instead of marking an active
# ModelArk task as failed while it is still running.
_POLL_INTERVAL = 5
_MAX_POLLS = 180  # 15 minutes
_PLUGIN_ROOT = Path(__file__).resolve().parents[4]
_logger = logging.getLogger(__name__)
# External plugin mounts are read-only in BOS containers. Runtime artifacts must
# go to writable storage.
_RUNS_ROOT = Path(os.environ.get("PREVIS_MOTION_RUNS_DIR") or "/var/bos/previs-motion-runs")
_DRIVE_CLIENT_CANDIDATES = [
    Path(__file__).resolve().parents[5] / "google-drive" / "drive_client.py",
    Path("/external_plugins/google-drive/drive_client.py"),
    Path("/app/plugins/google-drive/drive_client.py"),
]


def _slugify(text: str, fallback: str = "previs") -> str:
    out = "".join(ch.lower() if ch.isalnum() else "-" for ch in str(text or ""))
    out = "-".join(part for part in out.split("-") if part)
    return out[:80] or fallback


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _read_json(path: str | Path) -> dict:
    return json.loads(Path(path).expanduser().read_text(encoding="utf-8"))


def _coerce_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"", "0", "false", "no", "n", "off", "none", "null"}:
            return False
    return default


def _first_present(mapping: dict, *keys: str):
    for key in keys:
        if key in mapping and mapping.get(key) is not None:
            return mapping.get(key)
    return None


def _looks_like_inherited_image_model(brief: dict, model: str) -> bool:
    """Detect stale image-stage model IDs copied from a storyboard image block.

    Approved storyboard image artifacts legitimately carry values such as
    `model: gpt-image-2`. If the host fails to stamp `backend_model_id`, do not
    spend a production run failing on that inherited image model; fall back to
    the pinned Seedance 2.0 default. Explicit direct model tests still fail.
    """
    lowered = str(model or "").lower()
    if not any(marker in lowered for marker in _INHERITED_IMAGE_MODEL_MARKERS):
        return False
    return (
        str(brief.get("artifact_action") or brief.get("action") or "").strip() in {"generate_video", "render"}
        or str(brief.get("source_module_id") or "").startswith("storyboard.render")
        or str(brief.get("approved_artifact_type") or "").lower() in {"image_asset", "storyboard_image"}
    )


def _resolve_video_provider(brief: dict) -> str:
    brief = brief or {}
    backend_override = brief.get("_backend_override") if isinstance(brief.get("_backend_override"), dict) else {}
    provider = str(
        brief.get("backend_provider")
        or brief.get("video_gen_provider")
        or backend_override.get("provider")
        or "byteplus_modelark"
    ).strip().lower()
    if provider in {"bytedance", "byteplus", "modelark", "byteplus_modelark"}:
        return "byteplus_modelark"
    if provider in {"gemini", "google_gemini", "google"}:
        return "gemini"
    return provider or "byteplus_modelark"


def _resolve_video_model(brief: dict, provider: str) -> str:
    brief = brief or {}
    backend_override = brief.get("_backend_override") if isinstance(brief.get("_backend_override"), dict) else {}
    explicit_backend_model = str(
        brief.get("backend_model_id")
        or brief.get("video_gen_model")
        or backend_override.get("model_id")
        or ""
    ).strip()
    default_model = _DEFAULT_GEMINI_VEO_MODEL if provider == "gemini" else _DEFAULT_MODEL
    model = str(explicit_backend_model or brief.get("model") or default_model).strip() or default_model

    if provider == "gemini":
        if model not in _GEMINI_VEO_MODELS and not _coerce_bool(os.environ.get("PREVIS_MOTION_ALLOW_UNKNOWN_GEMINI_VIDEO_MODEL"), False):
            raise ValueError(
                "Previs Motion Gemini backend requires a Veo video model. "
                f"Refusing model '{model}'."
            )
        return model

    if provider == "byteplus_modelark":
        if model not in _SEEDANCE2_MODELS and not explicit_backend_model and _looks_like_inherited_image_model(brief, model):
            _logger.warning("Ignoring inherited image model '%s' for Previs Motion action; using %s", model, _DEFAULT_MODEL)
            model = _DEFAULT_MODEL
        if model not in _SEEDANCE2_MODELS and not explicit_backend_model and not _coerce_bool(os.environ.get("PREVIS_MOTION_ALLOW_NON_SEEDANCE2"), False):
            raise ValueError(
                "Previs Motion is pinned to Seedance 2.0. "
                f"Refusing non-Seedance-2 model '{model}'. "
                "Set PREVIS_MOTION_ALLOW_NON_SEEDANCE2=true only for explicit provider tests."
            )
    return model


def _resolve_seedance2_model(brief: dict) -> str:
    """Backward-compatible helper for existing tests/callers."""
    return _resolve_video_model(brief, "byteplus_modelark")


def _data_url_from_path(path: str | Path) -> str:
    p = Path(path).expanduser()
    raw = p.read_bytes()
    mime = mimetypes.guess_type(str(p))[0] or "image/png"
    return f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")


def _data_url_from_b64(b64: str, mime_type: str = "image/png") -> str:
    s = str(b64 or "").strip()
    if s.startswith("data:"):
        return s
    return f"data:{mime_type};base64,{s}"


def _load_drive():
    for p in _DRIVE_CLIENT_CANDIDATES:
        if p.exists():
            spec = importlib.util.spec_from_file_location("previs_motion_google_drive_client", str(p))
            module = importlib.util.module_from_spec(spec)
            assert spec.loader is not None
            spec.loader.exec_module(module)
            return module
    raise FileNotFoundError("google-drive/drive_client.py not found")


def _ark_request(method: str, path: str, api_key: str, body: dict | None = None, timeout: int = 180) -> dict:
    with httpx.Client(timeout=timeout) as client:
        resp = client.request(
            method,
            _MODELARK_BASE + path,
            json=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "BOS-Previs-Motion/0.1",
            },
        )
    if not resp.is_success:
        try:
            parsed = resp.json()
        except Exception:
            parsed = {"raw": resp.text}
        raise RuntimeError(f"ModelArk HTTP {resp.status_code}: {json.dumps(parsed, ensure_ascii=False)}")
    return resp.json() if resp.text else {}


def _gemini_auth_mode(brief: dict) -> str:
    creds = brief.get("_channel_credentials", {}) if isinstance(brief, dict) else {}
    return str(creds.get("provider_api_key_auth_mode") or creds.get("gemini_api_key_auth_mode") or "api_key").strip() or "api_key"


def _gemini_request(method: str, path: str, api_key: str, body: dict | None = None, *, auth_mode: str = "api_key", timeout: int = 180) -> dict:
    headers = {"User-Agent": "BOS-Previs-Motion/0.1"}
    params = None
    if auth_mode == "oauth":
        headers["Authorization"] = f"Bearer {api_key}"
    else:
        params = {"key": api_key}
    with httpx.Client(timeout=timeout) as client:
        resp = client.request(method, _GEMINI_BASE + path, params=params, json=body, headers=headers)
    if not resp.is_success:
        try:
            parsed = resp.json()
        except Exception:
            parsed = {"raw": resp.text}
        raise RuntimeError(f"Gemini Veo HTTP {resp.status_code}: {json.dumps(parsed, ensure_ascii=False)}")
    return resp.json() if resp.text else {}


def _gemini_operation_path(name: str) -> str:
    value = str(name or "").strip()
    if not value:
        return ""
    if value.startswith("/"):
        return value
    return "/" + value


def _download(url: str, dest: Path) -> bytes:
    with httpx.Client(timeout=300) as client:
        resp = client.get(url, headers={"User-Agent": "BOS-Previs-Motion/0.1"})
        resp.raise_for_status()
        data = resp.content
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return data


def _download_gemini_video(uri: str, dest: Path, api_key: str, auth_mode: str = "api_key") -> bytes:
    url = str(uri or "").strip()
    if not url:
        raise RuntimeError("Gemini Veo returned an empty video URI")
    if not url.startswith("http"):
        url = _GEMINI_BASE + (url if url.startswith("/") else f"/{url}")
    sep = "&" if "?" in url else "?"
    headers = {"User-Agent": "BOS-Previs-Motion/0.1"}
    if auth_mode == "oauth":
        headers["Authorization"] = f"Bearer {api_key}"
    elif "key=" not in url:
        url = f"{url}{sep}key={quote(api_key)}"
    if "alt=media" not in url and "generativelanguage.googleapis.com" in url:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}alt=media"
    with httpx.Client(timeout=300) as client:
        resp = client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.content
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return data


def _is_url_accessible(url: str, timeout: int = 10) -> bool:
    # BytePlus TOS presigned URLs are signed for GET, not HEAD — HEAD returns 403
    # even on a valid live URL. Use a range-GET to probe without fetching the video.
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url, headers={"User-Agent": "BOS-Previs-Motion/0.1", "Range": "bytes=0-0"})
            return resp.status_code < 400
    except Exception:
        return False


def _refresh_video_url(task_id: str, api_key: str) -> str | None:
    """Re-fetch a completed Seedance task to get a fresh presigned TOS URL.

    Seedance output URLs are TOS presigned with X-Tos-Expires=86400 (24 h).
    The task itself persists for 48 h (execution_expires_after=172800).
    Re-fetching a succeeded task within that window returns a freshly-signed URL.
    Returns None if the task is expired, unknown, or did not succeed.
    """
    try:
        task = _ark_request("GET", f"/contents/generations/tasks/{quote(str(task_id))}", api_key, None, timeout=60)
        if task.get("status") == "succeeded":
            return _extract_video_url(task)
    except Exception as exc:
        _logger.warning("Seedance task re-fetch failed for %s: %s", task_id, exc)
    return None


def _resolve_ref_task_id(brief: dict) -> str | None:
    """Find the Seedance task_id for the reference video in the brief."""
    task_id = _first_present(brief, "task_id", "reference_task_id")
    if task_id:
        return str(task_id)
    for art in _get_nested_artifacts(brief):
        tid = art.get("task_id") or art.get("reference_task_id")
        if tid:
            return str(tid)
    return None


def _extract_video_url(task: dict) -> str | None:
    content = task.get("content") if isinstance(task, dict) else None
    if isinstance(content, dict):
        return content.get("video_url") or content.get("videoUrl") or content.get("file_url")
    if isinstance(task, dict):
        return task.get("video_url") or task.get("videoUrl") or task.get("file_url")
    return None


def _get_nested_artifacts(brief: dict) -> list[dict]:
    artifacts: list[dict] = []
    for key in ("artifact", "input_artifact", "previous_artifact", "storyboard_artifact", "image_asset", "video_asset"):
        val = brief.get(key)
        if isinstance(val, dict):
            artifacts.append(val)
    for key in ("artifacts", "artifact_blocks", "blocks"):
        val = brief.get(key)
        if isinstance(val, list):
            artifacts.extend([x for x in val if isinstance(x, dict)])
    return artifacts


def _attach_blueprint_context(spec: dict, brief: dict) -> dict:
    """Keep the approved text blueprint with the storyboard image → video prompt."""
    if not isinstance(spec, dict):
        spec = {}
    out = json.loads(json.dumps(spec))
    bp = brief.get("production_blueprint") if isinstance(brief.get("production_blueprint"), dict) else None
    blueprint_text = str(brief.get("approved_production_blueprint_text") or brief.get("storyboard_text") or "").strip()
    if bp and not isinstance(out.get("production_blueprint"), dict):
        out["production_blueprint"] = bp
    if blueprint_text:
        out.setdefault("source_storyboard_text", blueprint_text)
        if isinstance(out.get("production_blueprint"), dict):
            out["production_blueprint"].setdefault("source_text", blueprint_text)
        else:
            out["production_blueprint"] = {"source_text": blueprint_text}
    return out


def _resolve_storyboard_spec(brief: dict) -> dict:
    for key in ("storyboard_spec", "storyboard_json", "json_spec", "spec"):
        val = brief.get(key)
        if isinstance(val, dict):
            return _attach_blueprint_context(val, brief)
    for art in _get_nested_artifacts(brief):
        for key in ("storyboard_spec", "storyboard_json", "spec"):
            val = art.get(key)
            if isinstance(val, dict):
                merged_brief = dict(brief)
                merged_brief.update({k: v for k, v in art.items() if k not in merged_brief or not merged_brief.get(k)})
                return _attach_blueprint_context(val, merged_brief)
    spec_path = brief.get("spec_path") or brief.get("storyboard_spec_path")
    if spec_path:
        return _attach_blueprint_context(_read_json(spec_path), brief)
    # Minimal fallback: enough to render if the caller passes an image and text but
    # not a full Storyboard block. We still do not invent new shots; the message is
    # recorded only as operator context.
    return _attach_blueprint_context({
        "project": {"title": brief.get("title") or "Previs Motion Render"},
        "operator_context": brief.get("message") or "",
    }, brief)


def _resolve_title(spec: dict, brief: dict) -> str:
    project = spec.get("project") if isinstance(spec.get("project"), dict) else {}
    return str(brief.get("title") or project.get("title") or spec.get("project_title") or "previs-motion")


def _path_if_readable(value) -> str | None:
    if not value:
        return None
    try:
        p = Path(str(value)).expanduser()
        if p.exists() and p.is_file():
            return str(p)
    except Exception:
        return None
    return None


def _resolve_image_reference(brief: dict) -> tuple[str | None, str | None]:
    """Resolve an approved storyboard/keyframe image for Seedance I2V.

    Seedance 2.0 accepts image references as either public URLs or data URIs.
    BOS action briefs usually provide local paths or base64 data from Storyboard
    artifacts, so resolve paths first and fall back to embedded base64 when a
    container-local path has gone stale.
    """
    if not isinstance(brief, dict):
        return None, None

    def _b64_if_present(mapping: dict) -> str | None:
        for key in ("source_image_data_b64", "image_data_b64", "_image_data_b64", "data_b64", "b64"):
            val = mapping.get(key)
            if val:
                return str(val).strip()
        return None

    top_b64 = _b64_if_present(brief)
    if brief.get("_image_swapped") and top_b64:
        return None, top_b64

    for key in ("source_image_path", "image_path", "output_path", "path"):
        found = _path_if_readable(brief.get(key))
        if found:
            return found, None
    if top_b64:
        return None, top_b64

    for art in _get_nested_artifacts(brief):
        for key in ("source_image_path", "image_path", "output_path", "path"):
            found = _path_if_readable(art.get(key))
            if found:
                return found, None
        art_b64 = _b64_if_present(art)
        if art_b64:
            return None, art_b64
    return None, None


def _resolve_image_b64_fallback(brief: dict) -> str | None:
    """Find embedded image data even when a readable path won resolution.

    Previs video artifacts must preserve enough source-image data for I2V fallback
    after Seedance video URLs/tasks expire. Storyboard image blocks often contain
    both `output_path` and `image_data_b64`; `_resolve_image_reference()` prefers
    the path for the current run, while this helper preserves the durable b64.
    """
    if not isinstance(brief, dict):
        return None
    for mapping in [brief, *_get_nested_artifacts(brief)]:
        if not isinstance(mapping, dict):
            continue
        val = _first_present(mapping, "source_image_data_b64", "image_data_b64", "_image_data_b64", "data_b64", "b64")
        if val:
            return str(val).strip()
    return None


def _resolve_image_role(brief: dict) -> str:
    """Return the official Seedance role for an image input.

    `reference_image` is best for storyboard/contact-sheet guidance; `first_frame`
    is available for strict first-frame I2V when explicitly requested.
    """
    role = str(_first_present(brief or {}, "image_role", "source_image_role", "seedance_image_role") or "reference_image").strip()
    return role if role in {"reference_image", "first_frame"} else "reference_image"


def _image_reference_content(brief: dict, image_path: str | None, image_b64: str | None) -> dict | None:
    if image_path:
        return {"type": "image_url", "image_url": {"url": _data_url_from_path(image_path)}, "role": _resolve_image_role(brief)}
    if image_b64:
        mime_type = str(_first_present(brief or {}, "source_image_mime_type", "image_mime_type", "_image_mime", "mime_type", "drive_file_mime") or "image/png")
        return {"type": "image_url", "image_url": {"url": _data_url_from_b64(image_b64, mime_type)}, "role": _resolve_image_role(brief)}
    return None


def _resolve_logo_reference(brief: dict) -> dict | None:
    """Download the brand logo from Drive and return it as a Seedance reference_image.

    Option D: sends the clean logo file to Seedance so it renders the brand mark
    correctly rather than copying a degraded pencil sketch version.
    """
    brand_spec = brief.get("brand_spec") if isinstance(brief.get("brand_spec"), dict) else {}
    brand_kit = brief.get("brand_kit") if isinstance(brief.get("brand_kit"), dict) else {}
    if not brand_spec:
        brand_spec = brand_kit.get("brand_spec") if isinstance(brand_kit.get("brand_spec"), dict) else {}
    logo_file_id = str(brand_spec.get("logo_drive_file_id") or "").strip()
    if not logo_file_id:
        return None
    creds = brief.get("_channel_credentials") or {}
    token = str(creds.get("google_drive_page_token") or creds.get("access_token") or creds.get("page_token") or "").strip()
    if not token:
        return None
    try:
        drive_mod = _load_drive()
        with drive_mod.DriveClient(token) as client:
            logo_bytes = client.download_file(logo_file_id)
            meta = client.get_file_meta(logo_file_id)
            mime = str(meta.get("mimeType") or brand_spec.get("logo_mime_type") or "image/png")
            b64 = base64.b64encode(logo_bytes).decode()
        return {
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{b64}"},
            "role": "reference_image",
        }
    except Exception:
        _logger.warning("Could not download brand logo for Seedance reference", exc_info=True)
        return None


def _resolve_reference_video_url(brief: dict) -> tuple[str | None, str | None]:
    url = brief.get("reference_video_url") or brief.get("video_url")
    if url:
        return str(url), None
    path = brief.get("reference_video_url_path") or brief.get("video_url_path")
    if path:
        p = Path(path).expanduser()
        return p.read_text(encoding="utf-8").strip(), str(p)
    for art in _get_nested_artifacts(brief):
        url = art.get("video_url") or art.get("reference_video_url")
        if url:
            return str(url), None
        path = art.get("video_url_path") or art.get("reference_video_url_path")
        if path:
            p = Path(path).expanduser()
            return p.read_text(encoding="utf-8").strip(), str(p)
    return None, None


def _generation_preflight_missing(brief: dict) -> list[str]:
    creds = brief.get("_channel_credentials", {}) if isinstance(brief, dict) else {}
    token = str(creds.get("google_drive_page_token") or creds.get("access_token") or creds.get("page_token") or "").strip()
    root = str(creds.get("drive_root_folder_id") or "").strip()
    brand_kit = brief.get("brand_kit") if isinstance(brief.get("brand_kit"), dict) else {}
    brand_spec = brand_kit.get("brand_spec") if isinstance(brand_kit.get("brand_spec"), dict) else {}
    if not brand_spec and isinstance(brief.get("brand_spec"), dict):
        brand_spec = brief.get("brand_spec") or {}
    logo_id = str(brand_spec.get("logo_drive_file_id") or "").strip()
    missing: list[str] = []
    provider = _resolve_video_provider(brief)
    try:
        _extract_credentials(brief, provider)
    except Exception:
        missing.append("gemini_api_key" if provider == "gemini" else "byteplus_api_key")
    if not token:
        missing.append("google_drive_credentials")
    if not root:
        missing.append("google_drive_root_folder")
    if not logo_id:
        missing.append("official_logo_drive_file_id")
    return missing


def _preflight_block(missing: list[str], brief: dict) -> dict:
    brand_kit = brief.get("brand_kit") if isinstance(brief.get("brand_kit"), dict) else {}
    brand_id = str(brand_kit.get("brand_id") or brief.get("brand_id") or "").strip()
    brand_base = f"/admin/brands/{brand_id}" if brand_id else "/admin/brands"
    checklist = {
        "byteplus_api_key": {
            "fix": "Add a BytePlus ModelArk API key to this brand's channel credentials (ark_api_key or byteplus_api_key).",
            "href": f"{brand_base}?tab=integrations" if brand_id else brand_base,
            "label": "Open Integrations",
        },
        "gemini_api_key": {
            "fix": "Add a Google Gemini API key in Admin → AI Providers, then choose Google Gemini / Veo for Previs Motion.",
            "href": "/admin/providers",
            "label": "Open AI Providers",
        },
        "google_drive_credentials": {
            "fix": "Connect Google Drive for this brand so Previs Motion can save the generated video before Stream review.",
            "href": f"{brand_base}?tab=integrations" if brand_id else brand_base,
            "label": "Connect Google Drive",
        },
        "google_drive_root_folder": {
            "fix": "Select and validate the Brand Kit Drive folder so Previs Motion knows where to store artifacts.",
            "href": f"{brand_base}?tab=integrations" if brand_id else brand_base,
            "label": "Choose Brand Kit Drive Folder",
        },
        "official_logo_drive_file_id": {
            "fix": "Set brand_spec.logo_drive_file_id so Previs Motion can inject the brand logo as a visual reference for Seedance.",
            "href": f"{brand_base}?tab=integrations" if brand_id else brand_base,
            "label": "Choose Logo Drive Source",
        },
    }
    items = [{"key": k, "status": "missing", **checklist.get(k, {"fix": k, "href": "/admin", "label": "Open Admin"})} for k in missing]
    return {
        "type": "setup_blocker",
        "status": "failed",
        "reason_code": "previs_motion_preflight_failed",
        "message": "Previs Motion blocked before video generation: missing " + ", ".join(missing),
        "preflight_checklist": items,
        "setup_links": items,
        "allowed_actions": ["dismiss"],
    }


def _store_in_drive(brief: dict, video_bytes: bytes, filename: str) -> dict:
    """Persist Previs MP4 to the selected Brand's Google Drive directory.

    The local video_path is only a playback cache. The durable artifact
    identity must be the Drive file under the brand's configured Drive root.
    """
    creds = brief.get("_channel_credentials", {}) if isinstance(brief, dict) else {}
    token = str(creds.get("google_drive_page_token") or creds.get("access_token") or creds.get("page_token") or "").strip()
    if not token:
        return {"drive_upload_status": "failed", "drive_upload_error": "Google Drive token not injected for this Brand"}
    root = str(creds.get("drive_root_folder_id") or "").strip()
    if not root:
        return {"drive_upload_status": "failed", "drive_upload_error": "Brand Google Drive root folder missing"}
    root_name = str(creds.get("drive_root_name") or "Brand Drive root").strip() or "Brand Drive root"
    try:
        drive_mod = _load_drive()
        with drive_mod.DriveClient(token) as client:
            folder_id = client.ensure_path(["Previs Motion"], root)
            meta = client.upload_file(filename, video_bytes, "video/mp4", folder_id)
        return {
            "drive_file_id": meta.get("id"),
            "drive_file_name": meta.get("name"),
            "drive_file_mime": meta.get("mimeType") or "video/mp4",
            "drive_web_view_link": meta.get("webViewLink"),
            "drive_folder": "Previs Motion",
            "drive_folder_id": folder_id,
            "drive_root_folder_id": root,
            "drive_root_name": root_name,
            "storage_policy": "drive_durable",
            "reusable": True,
        }
    except Exception as exc:
        return {"drive_upload_status": "failed", "drive_upload_error": str(exc)[:300], "storage_policy": "tmp_cache_only"}


def _extract_credentials(brief: dict, provider: str | None = None) -> str:
    creds = brief.get("_channel_credentials", {}) if isinstance(brief, dict) else {}
    provider = provider or _resolve_video_provider(brief)
    if provider == "gemini":
        candidates = [
            creds.get("provider_api_key"),
            creds.get("gemini_api_key"),
            creds.get("GEMINI_API_KEY"),
            os.environ.get("GEMINI_API_KEY"),
            os.environ.get("GOOGLE_GEMINI_API_KEY"),
        ]
        for val in candidates:
            if val and str(val).strip():
                return str(val).strip()
        raise RuntimeError("Google Gemini API key not configured. Add a Gemini key in Admin → AI Providers.")

    candidates = [
        creds.get("ark_api_key"),
        creds.get("byteplus_api_key"),
        creds.get("provider_api_key"),
        creds.get("video_gen_api_key"),
        # Admin plugin_vars may store platform variable names verbatim.
        creds.get("ARK_API_KEY"),
        creds.get("BYTEPLUS_API_KEY"),
        os.environ.get("ARK_API_KEY"),
        os.environ.get("BYTEPLUS_API_KEY"),
    ]
    key_file = Path("/tmp/ark_api_key_for_pi")
    if key_file.exists():
        candidates.append(key_file.read_text(encoding="utf-8").strip())
    for val in candidates:
        if val and str(val).strip():
            return str(val).strip()
    raise RuntimeError("BytePlus ModelArk API key not configured. Set ARK_API_KEY or BYTEPLUS_API_KEY for Previs Motion.")


def _compile_target_json(brief: dict, spec: dict, mode: str, image_path: str | None, video_url_path: str | None, image_data_b64: str | None = None) -> dict:
    edit_instruction = str(
        brief.get("edit_instruction")
        or brief.get("approval_notes")
        or brief.get("video_generation_notes")
        or brief.get("revision_instruction")
        or brief.get("message")
        or ""
    ).strip()
    blueprint = spec.get("production_blueprint") if isinstance(spec.get("production_blueprint"), dict) else {}
    direct_t2v_prompt = ""
    if mode == "text_to_video":
        for key in _DIRECT_T2V_PROMPT_KEYS:
            val = brief.get(key)
            if val:
                direct_t2v_prompt = str(val)
                break
    blueprint_text = str(
        direct_t2v_prompt
        or blueprint.get("source_text")
        or spec.get("source_storyboard_text")
        or brief.get("approved_production_blueprint_text")
        or brief.get("storyboard_text")
        or ""
    ).strip()
    target = {
        "plugin": "Previs Motion",
        "version": str(brief.get("version") or brief.get("variation_id") or "v001"),
        "task": "Render approved production blueprint/storyboard output as a motion previs final-cut candidate.",
        "mode": mode,
        "approved_production_blueprint": blueprint or None,
        "approved_production_blueprint_text": blueprint_text or None,
        "direct_text_to_video_prompt": direct_t2v_prompt or None,
        "storyboard_spec": spec,
        "video_style": str(brief.get("video_style") or "").strip() or None,
        "source_image": None,
        "reference_video": None,
        "edit_instruction": edit_instruction or None,
        "render_rules": {
            "consume_storyboard_output_only": True,
            "do_not_create_new_storyboard": True,
            "single_continuous_video": True,
            "not_a_slideshow": True,
            "do_not_show_contact_sheet": True,
            "do_not_show_panel_borders": True,
            "do_not_show_panel_numbers": True,
            "do_not_show_captions_or_text": True,
            "preserve_json_as_source_of_truth": True,
            "preserve_approved_production_blueprint_text": True,
        },
        "provider": {
            "name": _resolve_video_provider(brief),
            "model": None,
            "resolution": str(brief.get("resolution") or _DEFAULT_RESOLUTION),
            "ratio": str(brief.get("ratio") or brief.get("aspect_ratio") or _DEFAULT_RATIO),
            "duration_seconds": min(int(float(brief.get("duration") or brief.get("duration_seconds") or _DEFAULT_DURATION)), _DEFAULT_DURATION),
            # Audio enabled by default. Set generate_audio: false explicitly to disable voice generation.
            "generate_audio": _coerce_bool(_first_present(brief, "generate_audio", "generateAudio"), True),
            "watermark": _coerce_bool(brief.get("watermark"), False),
        },
    }
    if image_path:
        target["source_image"] = {"role": _resolve_image_role(brief), "path": image_path}
    elif image_data_b64:
        target["source_image"] = {"role": _resolve_image_role(brief), "data_b64": "<embedded image data>"}
    if video_url_path:
        target["reference_video"] = {"role": "reference_video", "video_url_path": video_url_path}
    brand_assets = spec.get("brand_assets") if isinstance(spec.get("brand_assets"), dict) else {}
    brand_spec = brief.get("brand_spec") if isinstance(brief.get("brand_spec"), dict) else {}
    visual_assets = brand_spec.get("brand_visual_assets") if isinstance(brand_spec.get("brand_visual_assets"), list) else []
    if brand_assets.get("count") or brand_assets.get("reference_images") or brand_spec.get("logo_drive_file_id") or visual_assets:
        target["brand_assets"] = {
            **brand_assets,
            "logo_drive_file_id": brand_spec.get("logo_drive_file_id") or brand_assets.get("logo_drive_file_id"),
            "reference_images": brand_assets.get("reference_images") or visual_assets,
            "count": brand_assets.get("count") or (1 if brand_spec.get("logo_drive_file_id") else 0) + len(visual_assets),
        }
    provider = target["provider"]["name"]
    target["provider"]["model"] = _resolve_video_model(brief, provider)
    if provider == "gemini":
        # Veo preview models currently cap short clips lower than Seedance; keep
        # the default safe unless the operator explicitly requested a shorter run.
        target["provider"]["duration_seconds"] = min(int(target["provider"].get("duration_seconds") or 8), 8)
    return target


def _build_modelark_body(target: dict, prompt: str) -> dict:
    provider = target.get("provider") if isinstance(target.get("provider"), dict) else {}
    return {
        "model": provider.get("model") or _DEFAULT_MODEL,
        "content": [{"type": "text", "text": prompt}],
        "resolution": provider.get("resolution") or _DEFAULT_RESOLUTION,
        "ratio": provider.get("ratio") or _DEFAULT_RATIO,
        "duration": int(float(provider.get("duration_seconds") or _DEFAULT_DURATION)),
        # ModelArk/Seedance expects snake_case. Sending only the old camelCase
        # field is silently ignored by some endpoints.
        "generate_audio": _coerce_bool(_first_present(provider, "generate_audio", "generateAudio"), True),
        "watermark": _coerce_bool(provider.get("watermark"), False),
    }


def _build_gemini_veo_body(target: dict, prompt: str, image_path: str | None = None, image_b64: str | None = None, mime_type: str = "image/png") -> dict:
    provider = target.get("provider") if isinstance(target.get("provider"), dict) else {}
    ratio = str(provider.get("ratio") or _DEFAULT_RATIO)
    duration = min(int(float(provider.get("duration_seconds") or 8)), 8)
    instance: dict = {"prompt": prompt}
    if image_path:
        raw = Path(image_path).expanduser().read_bytes()
        instance["image"] = {
            "bytesBase64Encoded": base64.b64encode(raw).decode("ascii"),
            "mimeType": mimetypes.guess_type(str(image_path))[0] or mime_type,
        }
    elif image_b64:
        b64 = str(image_b64).strip()
        if b64.startswith("data:") and "," in b64:
            header, b64 = b64.split(",", 1)
            if ";" in header:
                mime_type = header.split(":", 1)[1].split(";", 1)[0] or mime_type
        instance["image"] = {"bytesBase64Encoded": b64, "mimeType": mime_type}
    return {
        "instances": [instance],
        "parameters": {
            "aspectRatio": ratio if ratio in {"16:9", "9:16"} else _DEFAULT_RATIO,
            "sampleCount": 1,
            "durationSeconds": duration,
            "personGeneration": "allow_all",
        },
    }


def _extract_gemini_video_uri(operation: dict) -> str | None:
    response = operation.get("response") if isinstance(operation, dict) else None
    candidates: list = []
    if isinstance(response, dict):
        gvr = response.get("generateVideoResponse") or response.get("generate_video_response") or response
        if isinstance(gvr, dict):
            candidates.extend(gvr.get("generatedSamples") or gvr.get("generated_samples") or [])
            candidates.extend(gvr.get("videos") or [])
    candidates.extend(operation.get("generatedSamples") or operation.get("generated_samples") or []) if isinstance(operation, dict) else None
    for sample in candidates:
        if not isinstance(sample, dict):
            continue
        video = sample.get("video") if isinstance(sample.get("video"), dict) else sample
        for key in ("uri", "gcsUri", "gcs_uri", "fileUri", "file_uri", "downloadUri", "download_uri"):
            if isinstance(video, dict) and video.get(key):
                return str(video.get(key))
    return None


def _prompt_from_target(target: dict, mode: str) -> str:
    spec = target.get("storyboard_spec") or {}
    global_rules = spec.get("global_visual_rules") or spec.get("global_art_direction") or {}
    locked = spec.get("locked_elements") or {}
    edit = target.get("edit_instruction") or ""
    video_style = str(target.get("video_style") or "").strip()
    blueprint_text = target.get("approved_production_blueprint_text") or ""
    direct_t2v_prompt = target.get("direct_text_to_video_prompt") or ""
    if mode == "text_to_video" and direct_t2v_prompt:
        # Direct Seedance T2V accepts long Markdown/storyboard prompts as the
        # single text content item. Preserve operator-authored prompts byte-for-
        # byte after outer form stripping: do not sanitize brand names, split
        # audio/visual sections, append canonical JSON, or rewrite labels.
        return str(direct_t2v_prompt).strip()
    # Sanitize brand names that trigger Seedance copyright policy
    blueprint_text = _sanitize_for_seedance(blueprint_text)
    # Split blueprint into voiceover and visual sections so Seedance knows
    # what to speak vs. what to render.
    voiceover_lines, visual_scenes = _split_voiceover_from_visual(blueprint_text)
    if mode == "video_to_video":
        header = (
            "Video 1 is the locked reference video. Preserve its storyboard continuity, style, pacing, camera language, characters, props, and final reveal. "
            "Perform only the JSON edit requested below. Do not rewrite the story from scratch. "
        )
        if edit:
            header += f"Required edit: {edit}. "
    elif mode == "image_to_video":
        header = (
            "PRODUCTION DIRECTIVE — the TEXT below is the authoritative source of truth for this video. "
            "Image 1 is a ROUGH HAND-DRAWN PENCIL STORYBOARD SKETCH provided ONLY for composition, shot framing, and scene sequencing reference. "
            "DO NOT copy the sketch style, panel borders, handwritten text, logos, or low-quality rendering from Image 1 into the final video. "
            "DO NOT treat Image 1 as pixel truth — it is a conceptual previsualization, not a finished frame. "
            "Render the final video in the target video style specified below, using the text description as the authoritative creative brief. "
        )
        if edit:
            header += f"Operator revision notes: {edit}. OPERATOR ART DIRECTION (authoritative — overrides any conflicting visual cues in the reference image): {edit}. "
    else:
        header = (
            "Render a polished short-form motion previs final-cut candidate. "
            "The VOICEOVER SCRIPT below is the exact narration to speak. "
            "The VISUAL SCENES below describe what to show on screen. "
            "Do NOT speak the visual descriptions as narration. "
        )
        if edit:
            header += f"OPERATOR ART DIRECTION (authoritative): {edit}. "
    constraints = (
        "No panel borders, grid lines, circled shot numbers, captions, subtitles, labels, logos, or generated text unless the storyboard explicitly requires final end-card text. "
        "Use cinematic cuts or soft dissolves between beats. "
    )
    if video_style:
        constraints += f"Target video style: {video_style}. Render the final video in {video_style} visual style. "
    if global_rules:
        constraints += "Global visual rules: " + json.dumps(global_rules, ensure_ascii=False) + ". "
    if locked:
        constraints += "Locked elements: " + json.dumps(locked, ensure_ascii=False) + ". "
    brand_assets = target.get("brand_assets") if isinstance(target.get("brand_assets"), dict) else {}
    brand_count = int(brand_assets.get("count") or len(brand_assets.get("reference_images") or []))
    if brand_count:
        constraints += (
            f"Brand assets: {brand_count} brand reference image(s) were provided by the operator "
            "(logo, hero image, or visual inspiration). "
            "The brand logo MUST appear in the final end-card beat of the video. "
            "Incorporate brand identity and visual language consistently throughout. "
        )
    parts = [header, constraints]
    if voiceover_lines:
        parts.append(f"VOICEOVER SCRIPT (speak exactly this narration):\n{voiceover_lines}")
    if visual_scenes:
        parts.append(f"VISUAL SCENES (show these on screen, do not speak them):\n{visual_scenes}")
    elif blueprint_text:
        parts.append(f"VISUAL SCENES:\n{blueprint_text}")
    return "\n\n".join(parts)


class PrevisMotionRenderModule(ChannelModule):
    """Render or revise a Previs Motion final-cut candidate from approved Storyboard output."""

    id = "storyboard.motion.render"
    name = "Previs Motion Render"
    vertical = "storyboard"
    capability = "storyboard.motion.render"
    platform_hint = "previs_motion"
    policy_default = "generate_with_gates"
    template = ""

    def _attempt(self, start: float, status: str, error=None, model_id: str | None = None, provider: str = "byteplus_modelark") -> dict:
        return {
            "provider": provider,
            "model_id": model_id or ("previs_motion_veo_v1" if provider == "gemini" else "previs_motion_seedance_v1"),
            "mode": "tool",
            "status": status,
            "tokens_input": 0,
            "tokens_output": 0,
            "provider_cost": 0.0,
            "latency_ms": round((time.perf_counter() - start) * 1000),
            "error": error,
        }

    def _fail(self, start: float, reason: str, message: str) -> tuple[dict, dict]:
        return self._attempt(start, "failed", reason), {
            "content": f"Previs Motion failed: {message}",
            "sell_price": None,
            "block": {
                "type": "previs_motion_video",
                "legacy_type": "video_asset",
                "status": "failed",
                "reason_code": reason,
                "message": message,
                "allowed_actions": ["retry", "dismiss"],
            },
        }

    def execute_tool_result(self, brief: dict) -> tuple[dict, dict]:
        start = time.perf_counter()
        if not isinstance(brief, dict):
            brief = {}
        try:
            provider = _resolve_video_provider(brief)
            missing = _generation_preflight_missing(brief)
            if missing:
                return self._attempt(start, "failed", "previs_motion_preflight_failed"), {
                    "content": "Previs Motion blocked before video generation: missing " + ", ".join(missing),
                    "sell_price": None,
                    "block": _preflight_block(missing, brief),
                }
            api_key = _extract_credentials(brief, provider)
            gemini_auth_mode = _gemini_auth_mode(brief)
            spec = _resolve_storyboard_spec(brief)
            title = _resolve_title(spec, brief)
            video_url, video_url_path = _resolve_reference_video_url(brief)
            image_path, image_b64 = _resolve_image_reference(brief)
            source_image_b64_for_lineage = image_b64 or _resolve_image_b64_fallback(brief)
            requested_mode = str(brief.get("mode") or "auto").strip().lower()
            if requested_mode in {"video_to_video", "v2v", "edit"}:
                mode = "video_to_video"
            elif requested_mode in {"image_to_video", "i2v", "storyboard_to_video", "image"}:
                mode = "image_to_video"
            elif requested_mode in {"text_to_video", "t2v", "blueprint", "blueprint_to_video"}:
                mode = "text_to_video"
            else:
                # Prefer true continuity inputs when available: V2V first, then
                # Seedance 2.0 I2V/reference-image mode, then text-only fallback.
                mode = "video_to_video" if video_url else ("image_to_video" if (image_path or image_b64) else "text_to_video")
            if provider == "gemini" and mode == "video_to_video":
                if image_path or image_b64:
                    _logger.info("Gemini Veo does not support BOS video-to-video edits yet; falling back to image_to_video.")
                    mode = "image_to_video"
                    video_url = None
                    video_url_path = None
                else:
                    return self._fail(start, "gemini_v2v_unsupported", "Gemini Veo is available for text/image-to-video in BOS, but video-to-video edits need a source storyboard image fallback.")
            if mode == "video_to_video" and not video_url:
                return self._fail(start, "missing_reference_video", "JSON video edits require reference_video_url or reference_video_url_path.")
            if mode == "image_to_video" and not (image_path or image_b64):
                return self._fail(start, "missing_source_image", "Image-to-video requires source_image_path, source_image_data_b64, output_path, or image_data_b64.")
            # Seedance TOS presigned URLs expire after 24 h (X-Tos-Expires=86400).
            # Tasks live for 48 h (execution_expires_after=172800). Re-fetch the task
            # to get a fresh URL before falling back to I2V when a source image exists.
            if provider == "byteplus_modelark" and mode == "video_to_video" and video_url and not _is_url_accessible(video_url):
                ref_task_id = _resolve_ref_task_id(brief)
                if ref_task_id:
                    refreshed = _refresh_video_url(ref_task_id, api_key)
                    if refreshed and _is_url_accessible(refreshed):
                        _logger.info("Refreshed expired Seedance TOS URL via task re-fetch (task %s)", ref_task_id)
                        video_url = refreshed
                    else:
                        ref_task_id = None
                if not ref_task_id:
                    if image_path or image_b64:
                        _logger.warning("Previs Motion v2v reference URL expired and task re-fetch failed; falling back to image_to_video. URL: %s", video_url[:120])
                        mode = "image_to_video"
                        video_url = None
                        video_url_path = None
                    else:
                        return self._fail(start, "reference_video_expired", "Reference video URL is expired and no storyboard/source image is available for I2V fallback.")

            run_id = str(brief.get("run_id") or uuid.uuid4().hex[:12])
            run_slug = f"{_slugify(title)}_{_slugify(mode)}_{_slugify(run_id, 'run')}"[:200]
            out_dir = Path(str(brief.get("output_dir") or (_RUNS_ROOT / run_slug))).expanduser()
            out_dir.mkdir(parents=True, exist_ok=True)

            target = _compile_target_json(brief, spec, mode, image_path, video_url_path, image_b64)
            prompt = _prompt_from_target(target, mode)
            provider = target["provider"]["name"]
            model = target["provider"]["model"]
            if provider == "gemini":
                body = _build_gemini_veo_body(target, prompt, image_path if mode == "image_to_video" else None, image_b64 if mode == "image_to_video" else None)
            else:
                body = _build_modelark_body(target, prompt)
                if mode == "video_to_video":
                    body["content"].append({"type": "video_url", "video_url": {"url": video_url}, "role": "reference_video"})
                elif mode == "image_to_video":
                    image_ref = _image_reference_content(brief, image_path, image_b64)
                    if image_ref:
                        body["content"].append(image_ref)
                # Option D: send brand logo as a separate reference image so Seedance
                # renders it cleanly rather than copying it from a pencil sketch.
                logo_ref = _resolve_logo_reference(brief)
                if logo_ref:
                    body["content"].append(logo_ref)
                # Voiceover lines are already included in the main prompt text
                # via _prompt_from_target under "VOICEOVER SCRIPT".
                # A separate content item with role="audio" was rejected by
                # Seedance 2.0 (role not supported in text content).
                # Keep the split for the main prompt only — do not send a
                # duplicate content item.

            target_path = out_dir / "target.json"
            prompt_path = out_dir / "prompt.txt"
            payload_path = out_dir / "payload.json"
            created_path = out_dir / "created.json"
            task_path = out_dir / "task.json"
            video_url_path_out = out_dir / "video_url.txt"
            safe_run_id = "".join(ch for ch in run_id.lower() if ch.isalnum())[:24] or uuid.uuid4().hex[:12]
            video_path = _RUNS_ROOT / f"bos_video_previs{safe_run_id}.mp4"
            _write_json(target_path, target)
            prompt_path.write_text(prompt, encoding="utf-8")
            redacted = json.loads(json.dumps(body))
            for item in redacted.get("content", []):
                if item.get("type") == "image_url" and str(item.get("image_url", {}).get("url", "")).startswith("data:"):
                    item["image_url"]["url"] = "<embedded reference image data>"
            for instance in redacted.get("instances", []):
                if isinstance(instance, dict) and isinstance(instance.get("image"), dict) and instance["image"].get("bytesBase64Encoded"):
                    instance["image"]["bytesBase64Encoded"] = "<embedded reference image data>"
            _write_json(payload_path, redacted)

            final_task = None
            poll_seconds = int(float(brief.get("poll_seconds") or (_POLL_INTERVAL * _MAX_POLLS)))
            max_polls = max(1, min(_MAX_POLLS, poll_seconds // _POLL_INTERVAL))
            if provider == "gemini":
                created = _gemini_request("POST", f"/models/{quote(str(model))}:predictLongRunning", api_key, body, auth_mode=gemini_auth_mode, timeout=180)
                _write_json(created_path, created)
                task_id = created.get("name") or created.get("operation") or created.get("id")
                if not task_id:
                    return self._fail(start, "missing_task_id", f"Gemini Veo returned no operation name: {created}")
                for i in range(max_polls):
                    if i > 0:
                        time.sleep(_POLL_INTERVAL)
                    task = _gemini_request("GET", _gemini_operation_path(str(task_id)), api_key, None, auth_mode=gemini_auth_mode, timeout=120)
                    if task.get("done") is True:
                        final_task = task
                        break
                if final_task is None:
                    final_task = {"name": task_id, "done": False, "status": "timeout"}
                _write_json(task_path, final_task)
                if final_task.get("error"):
                    return self._fail(start, "generation_failed", f"Gemini Veo operation {task_id} failed: {final_task.get('error')}. See {task_path}")
                if final_task.get("done") is not True:
                    return self._fail(start, "generation_failed", f"Gemini Veo operation {task_id} ended with status timeout. See {task_path}")
                out_url = _extract_gemini_video_uri(final_task)
                if not out_url:
                    return self._fail(start, "missing_video_url", f"Gemini Veo operation {task_id} succeeded but returned no video URI. See {task_path}")
                video_url_path_out.write_text(out_url + "\n", encoding="utf-8")
                video_bytes = _download_gemini_video(out_url, video_path, api_key, gemini_auth_mode)
            else:
                created = _ark_request("POST", "/contents/generations/tasks", api_key, body)
                _write_json(created_path, created)
                task_id = created.get("id")
                if not task_id:
                    return self._fail(start, "missing_task_id", f"ModelArk returned no task id: {created}")

                for i in range(max_polls):
                    # Wait before first poll only after first cycle, exit immediately on completion
                    if i > 0:
                        time.sleep(_POLL_INTERVAL)
                    task = _ark_request("GET", f"/contents/generations/tasks/{quote(str(task_id))}", api_key, None, timeout=120)
                    status = str(task.get("status") or "")
                    if status in {"succeeded", "failed", "expired", "cancelled"}:
                        final_task = task
                        break
                if final_task is None:
                    final_task = {"id": task_id, "status": "timeout"}
                _write_json(task_path, final_task)
                if final_task.get("status") != "succeeded":
                    error_detail = final_task.get("error") or final_task.get("message") or ""
                    suffix = f": {error_detail}" if error_detail else ""
                    return self._fail(start, "generation_failed", f"Seedance task {task_id} ended with status {final_task.get('status')}{suffix}. See {task_path}")
                out_url = _extract_video_url(final_task)
                if not out_url:
                    return self._fail(start, "missing_video_url", f"Seedance task {task_id} succeeded but returned no video_url. See {task_path}")
                video_url_path_out.write_text(out_url + "\n", encoding="utf-8")
                video_bytes = _download(out_url, video_path)
            drive_meta = _store_in_drive(brief, video_bytes, video_path.name)
            if not drive_meta.get("drive_file_id"):
                # Drive is the durable artifact store. Do not surface a successful
                # local-only/provider-URL-only video in Stream.
                try:
                    video_path.unlink(missing_ok=True)
                except Exception:
                    pass
                detail = drive_meta.get("drive_upload_error") or drive_meta.get("drive_upload_status") or "Google Drive upload did not return drive_file_id"
                return self._fail(start, "drive_storage_unavailable", f"Previs video was generated but could not be saved to the Brand's Google Drive: {detail}")
        except Exception as exc:
            return self._fail(start, type(exc).__name__, str(exc))

        size_kb = round(len(video_bytes) / 1024, 1)
        content = f"Previs Motion final-cut candidate {mode} succeeded: {video_path} ({size_kb} KB)"
        if drive_meta.get("drive_web_view_link"):
            content += f"\nDrive: {drive_meta['drive_web_view_link']}"
        return self._attempt(start, "succeeded", model_id=model, provider=provider), {
            "content": content,
            "sell_price": None,
            "block": {
                "type": "video_asset",
                "legacy_type": "previs_motion_video",
                "status": "succeeded",
                "approval_status": "pending",
                "artifact_role": "previs_final_cut_candidate",
                "provider": provider,
                "model": model,
                "mode": mode,
                "source_run_id": brief.get("source_run_id"),
                "source_module_id": brief.get("source_module_id"),
                "source_artifact_type": brief.get("approved_artifact_type"),
                "approved_blueprint_source_run_id": brief.get("approved_blueprint_source_run_id"),
                "task_id": task_id,
                "video_path": str(video_path),
                "video_url": out_url,
                "video_url_path": str(video_url_path_out),
                "target_json_path": str(target_path),
                "prompt_path": str(prompt_path),
                "payload_path": str(payload_path),
                "created_path": str(created_path),
                "task_path": str(task_path),
                "storyboard_spec": spec,
                "source_image_path": image_path,
                "source_image_data_b64": source_image_b64_for_lineage,
                "source_image_role": _resolve_image_role(brief),
                "reference_video_url_path": video_url_path,
                "file_size_kb": size_kb,
                "workflow": {
                    "id": "video_storyboard_pipeline",
                    "stage": "previs_final_cut_review",
                    "continuation_policy": "artifact_bound_else_fresh",
                    "fresh_start_module": "storyboard.create",
                },
                **drive_meta,
                "allowed_actions": ["approve_final_cut", "publish_facebook", "publish_youtube", "revise", "regenerate", "dismiss"],
                "action_modules": {
                    "revise": "storyboard.motion.edit",
                    "regenerate": "storyboard.motion.render",
                    "publish_facebook": "marketing.channel.meta.video.publish",
                    "publish_youtube": "marketing.channel.youtube.video.publish",
                },
            },
        }

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        if not isinstance(content, str):
            return "fail", ["content_not_string"]
        lowered = content.lower()
        if "failed" in lowered:
            return "fail", ["previs_motion_failed"]
        if "previs motion" not in lowered:
            return "fail", ["missing_previs_motion_reference"]
        return "pass", []
