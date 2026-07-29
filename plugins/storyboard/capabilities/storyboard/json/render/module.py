from __future__ import annotations

import base64
import importlib.util
import inspect
import time
from pathlib import Path

from klaroha_sdk import ChannelModule


def _extract_visual_descriptions(text: str) -> str:
    """Extract visual descriptions, stripping voiceover/text overlay lines."""
    lines: list[str] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        clean = stripped.replace("**", "").replace("__", "").replace("*", "").strip()
        lower = clean.lower()
        if lower.startswith("voiceover:") or lower.startswith("vo:"):
            continue
        if lower.startswith("text overlay:") or lower.startswith("text:") or lower.startswith("overlay:"):
            continue
        if lower in {"hook", "body", "call to action", "cta", "script structure", "visual style", "sound"}:
            continue
        if lower == "visual style:" or lower == "sound:":
            continue
        if lower.startswith("duration:"):
            continue
        if clean in {"---", "***", "==="}:
            continue
        if any(kw in lower for kw in ("bright", "color", "colour", "hopeful colors", "warmth", "soothing", "inviting tone")):
            continue
        if not any(kw in lower for kw in ("voiceover", "text overlay", "sound", "music", "audio", "next steps", "would you", "let me know")):
            if len(clean) > 10 and not clean.startswith("#"):
                lines.append(clean)
    if not lines:
        fallback: list[str] = []
        for raw in text.splitlines():
            s = raw.strip()
            if not s:
                continue
            s = s.replace("**", "").replace("__", "").replace("*", "")
            lower = s.lower()
            if any(skip in lower for skip in ("voiceover:", "text overlay:", "next steps", "would you", "let me know", "duration:")):
                continue
            fallback.append(s)
        return "\n".join(fallback[:30])
    return "\n".join(lines[:40])


def _load_core():
    path = Path(__file__).resolve().parents[4] / "lib" / "json_image_storyboard.py"
    spec = importlib.util.spec_from_file_location("storyboard_json_image_core", str(path))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _openai_base_url(core, brief: dict) -> str | None:
    """Use the same OpenAI API root Postcraft receives from channel credentials."""
    resolver = getattr(core, "_openai_base_url_from_brief", None)
    if callable(resolver):
        return resolver(brief)
    creds = brief.get("_channel_credentials") if isinstance(brief, dict) else {}
    if not isinstance(creds, dict):
        return None
    return str(
        creds.get("openai_api_base_url")
        or creds.get("provider_api_base_url")
        or creds.get("provider_api_key_base_url")
        or ""
    ).strip().rstrip("/") or None


def _call_core_openai_generate(core, spec, image_prompt, brief, api_key, model, size, base_url):
    call = core._call_openai_generate
    params = inspect.signature(call).parameters
    kwargs = {"base_url": base_url} if base_url and "base_url" in params else {}
    if "size" in params:
        return call(spec, image_prompt, brief, api_key, model, size, **kwargs)
    return call(spec, image_prompt, brief, api_key, model, **kwargs)


def _call_core_openai_edit(core, spec, image_prompt, ref_paths, brief, api_key, model, size, base_url):
    call = core._call_openai_edit
    params = inspect.signature(call).parameters
    kwargs = {"base_url": base_url} if base_url and "base_url" in params else {}
    return call(spec, image_prompt, ref_paths, brief, api_key, model, size, **kwargs)


def _load_drive():
    candidates = [
        Path(__file__).resolve().parents[5] / "google-drive" / "drive_client.py",
        Path("/external_plugins/google-drive/drive_client.py"),
        Path("/app/plugins/google-drive/drive_client.py"),
    ]
    for path in candidates:
        if path.exists():
            spec = importlib.util.spec_from_file_location("storyboard_google_drive_client", str(path))
            module = importlib.util.module_from_spec(spec)
            assert spec.loader is not None
            spec.loader.exec_module(module)
            return module
    raise FileNotFoundError("google-drive/drive_client.py not found")


def _resolve_brand_spec(brief: dict) -> dict:
    brand_kit = brief.get("brand_kit") if isinstance(brief.get("brand_kit"), dict) else {}
    spec = brand_kit.get("brand_spec") if isinstance(brand_kit.get("brand_spec"), dict) else {}
    if spec:
        return spec
    for key in ("brand_spec", "brand_json"):
        val = brief.get(key)
        if isinstance(val, dict):
            return val
    return {}


def _brand_visual_asset_refs(brand_spec: dict) -> list[dict]:
    vals = brand_spec.get("brand_visual_assets") or brand_spec.get("visual_assets") or brand_spec.get("supporting_brand_assets") or []
    refs: list[dict] = []
    if isinstance(vals, list):
        for item in vals:
            if isinstance(item, dict) and item.get("drive_file_id"):
                refs.append(item)
            elif isinstance(item, str) and item.strip():
                refs.append({"drive_file_id": item.strip(), "title": "brand visual asset"})
    for file_id in brand_spec.get("visual_asset_drive_file_ids") or []:
        if file_id and not any(str(r.get("drive_file_id") or "") == str(file_id) for r in refs):
            refs.append({"drive_file_id": str(file_id), "title": "brand visual asset"})
    return refs


def _inject_logo_reference(brief: dict, brand_spec: dict) -> list[dict]:
    """Download brand logo from Drive for storyboard reference.

    Only downloads the logo — brand visual assets are skipped for storyboard
    renders since the output is a pencil sketch, not a polished image.
    """
    reference_images: list[dict] = list(brief.get("reference_images") or [])
    logo_file_id = str(brand_spec.get("logo_drive_file_id") or "").strip()
    creds = brief.get("_channel_credentials") or {}
    token = str(creds.get("google_drive_page_token") or creds.get("access_token") or creds.get("page_token") or "").strip()
    if not token or not logo_file_id:
        return reference_images
    try:
        drive_mod = _load_drive()
        with drive_mod.DriveClient(token) as client:
            meta = client.get_file_meta(logo_file_id)
            logo_bytes = client.download_file(logo_file_id)
            filename = str(meta.get("name") or brand_spec.get("logo_file_name") or "brand-logo.png")
            mime = str(meta.get("mimeType") or brand_spec.get("logo_mime_type") or "image/png")
            injected = [{
                "title": filename,
                "filename": filename,
                "drive_file_id": logo_file_id,
                "vision_b64": base64.b64encode(logo_bytes).decode(),
                "mime_type": mime,
                "panel_label": "OFFICIAL BRAND LOGO",
                "placement_role": "logo",
                "_auto_injected": True,
            }]
        injected_ids = {str(r.get("drive_file_id") or "") for r in injected}
        return injected + [r for r in reference_images if str(r.get("drive_file_id") or "") not in injected_ids]
    except Exception:
        return reference_images


def _refs_to_paths(refs: list[dict], runs_root: Path) -> list[str]:
    """Write base64 brand ref images to files so the OpenAI SDK can open them."""
    paths: list[str] = []
    refs_dir = runs_root / "brand_refs"
    refs_dir.mkdir(parents=True, exist_ok=True)
    for ref in refs:
        b64 = str(ref.get("vision_b64") or "").strip()
        if not b64:
            continue
        suffix = ".png" if "png" in str(ref.get("mime_type") or "") else ".jpg"
        file_id = str(ref.get("drive_file_id") or ref.get("filename") or f"ref_{len(paths)}")
        path = refs_dir / f"{file_id[:48]}{suffix}"
        path.write_bytes(base64.b64decode(b64))
        paths.append(str(path))
    return paths


def _source_image_ref_to_path(brief: dict, runs_root: Path) -> str | None:
    """Resolve the previous storyboard image for revision/edit calls."""
    for key in ("source_image_path", "output_path", "image_path"):
        value = brief.get(key)
        if value:
            try:
                p = Path(str(value)).expanduser()
                if p.exists() and p.is_file():
                    return str(p)
            except Exception:
                pass
    b64 = str(brief.get("source_image_data_b64") or brief.get("image_data_b64") or "").strip()
    if b64:
        if b64.startswith("data:") and "," in b64:
            b64 = b64.split(",", 1)[1]
        path = runs_root / "revision_refs" / "source_storyboard.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(base64.b64decode(b64))
        return str(path)
    return None


def _store_in_drive(brief: dict, image_bytes: bytes, output_path: str) -> dict:
    creds = brief.get("_channel_credentials", {}) if isinstance(brief, dict) else {}
    token = str(creds.get("google_drive_page_token") or creds.get("access_token") or creds.get("page_token") or "").strip()
    if not token:
        return {"drive_upload_status": "failed", "drive_upload_error": "Google Drive credentials missing"}
    root = str(creds.get("drive_root_folder_id") or "").strip()
    if not root:
        return {"drive_upload_status": "failed", "drive_upload_error": "Brand Google Drive root folder missing"}
    try:
        drive_mod = _load_drive()
        with drive_mod.DriveClient(token) as client:
            folder = client.ensure_folder("Storyboard", root)
            filename = Path(output_path).name
            meta = client.upload_file(filename, image_bytes, "image/png", folder["id"])
        return {
            "drive_file_id": meta.get("id"),
            "drive_file_name": meta.get("name"),
            "drive_file_mime": meta.get("mimeType") or "image/png",
            "drive_web_view_link": meta.get("webViewLink"),
            "drive_folder": "Storyboard",
            "reusable": True,
        }
    except Exception as exc:
        return {"drive_upload_status": "failed", "drive_upload_error": str(exc)[:300]}


def _storyboard_preflight(brief: dict) -> list[str]:
    creds = brief.get("_channel_credentials", {}) if isinstance(brief, dict) else {}
    provider_key = str(creds.get("provider_api_key") or "").strip()
    provider_auth_mode = str(creds.get("provider_api_key_auth_mode") or "").strip()
    platform_key = str(creds.get("platform_openai_key") or "").strip()
    image_key = provider_key if provider_auth_mode in {"api_key", "oauth"} else platform_key
    drive_token = str(creds.get("google_drive_page_token") or creds.get("access_token") or creds.get("page_token") or "").strip()
    drive_root = str(creds.get("drive_root_folder_id") or "").strip()
    missing: list[str] = []
    if not image_key:
        missing.append("image_generation_key")
    if not drive_token:
        missing.append("google_drive_credentials")
    if not drive_root:
        missing.append("google_drive_root_folder")
    return missing


def _storyboard_preflight_block(missing: list[str], brief: dict) -> dict:
    brand_kit = brief.get("brand_kit") if isinstance(brief.get("brand_kit"), dict) else {}
    brand_id = str(brand_kit.get("brand_id") or brief.get("brand_id") or "").strip()
    brand_base = f"/admin/brands/{brand_id}" if brand_id else "/admin/brands"
    checklist = {
        "image_generation_key": {
            "fix": "Connect or reconnect OpenAI for this brand in Admin → AI Providers.",
            "href": f"{brand_base}?tab=integrations" if brand_id else brand_base,
            "label": "Open Integrations",
        },
        "google_drive_credentials": {
            "fix": "Connect Google Drive for this brand so Storyboard can save the generated image before Stream review.",
            "href": f"{brand_base}?tab=integrations" if brand_id else brand_base,
            "label": "Connect Google Drive",
        },
        "google_drive_root_folder": {
            "fix": "Select and validate the Brand Kit Drive folder so Storyboard knows where to store artifacts.",
            "href": f"{brand_base}?tab=integrations" if brand_id else brand_base,
            "label": "Choose Brand Kit Drive Folder",
        },
    }
    items = [{"key": k, "status": "missing", **checklist.get(k, {"fix": k, "href": "/admin", "label": "Open Admin"})} for k in missing]
    return {
        "type": "setup_blocker",
        "status": "failed",
        "reason_code": "storyboard_preflight_failed",
        "message": "Storyboard blocked before image generation: missing " + ", ".join(missing),
        "preflight_checklist": items,
        "setup_links": items,
        "allowed_actions": ["dismiss"],
    }


class StoryboardRenderModule(ChannelModule):
    """Render an operator-approved storyboard text directly to an image via gpt-image-2."""

    id = "storyboard.render"
    name = "Storyboard Render"
    vertical = "storyboard"
    capability = "storyboard.render"
    platform_hint = "storyboard"
    policy_default = "generate_with_gates"
    template = ""

    actions = {
        "render": {
            "description": (
                "Render a storyboard or video script into an image. "
                "ONLY call this after you have already written a script in the conversation AND the operator has responded affirmatively (any approval: 'yes', 'good', 'good enough', 'looks good', 'proceed', 'go', 'fine', 'use that', or similar). "
                "A request for a video is NOT approval — write the script first, then wait for affirmation. "
                "Pass the full approved text as storyboard_text."
            ),
            "parameters": {
                "title": {"type": "string", "description": "Short title for the storyboard image."},
                "storyboard_text": {"type": "string", "description": "The full approved storyboard or video script text from the conversation."},
                "size": {"type": "string", "description": "Image size or aspect ratio alias. Examples: 1536x1024, 1024x1536, 1024x1024, 16:9, 9:16, 3:4. Default: 1536x1024."},
                "image_quality": {"type": "string", "enum": ["low", "medium", "high", "auto"], "description": "gpt-image-2 quality. Default: medium."},
                "video_style": {"type": "string", "description": "Target video production style for downstream Previs Motion render. Examples: hyperrealistic, anime, cinematic, 3d-render, hand-drawn-animation, documentary. Default: hyperrealistic."},
            },
            "required": ["storyboard_text"],
            "produces": "storyboard_image",
        },
        "revise": {
            "description": (
                "Revise a rendered storyboard image using the previous image as visual anchor. "
                "Describe exactly which panels to change and what to preserve."
            ),
            "parameters": {
                "source_run_id": {"type": "string", "description": "Run ID of the storyboard image artifact to revise."},
                "revision_prompt": {"type": "string", "description": "Precise instruction describing what to change and what to preserve."},
                "storyboard_text": {"type": "string", "description": "Updated storyboard text if the script changed."},
            },
            "required": ["source_run_id", "revision_prompt"],
            "produces": "storyboard_image",
            "consumes": "storyboard_image",
        },
    }

    def _attempt(self, start: float, status: str, provider: str = "openai", error=None) -> dict:
        return {
            "provider": provider,
            "model_id": "gpt-image-2",
            "mode": "tool",
            "status": status,
            "tokens_input": 0,
            "tokens_output": 0,
            "provider_cost": 0.0,
            "latency_ms": round((time.perf_counter() - start) * 1000),
            "error": error,
        }

    def execute_tool_result(self, brief: dict) -> tuple[dict, dict]:
        start = time.perf_counter()
        brief = brief if isinstance(brief, dict) else {}

        text = str(brief.get("storyboard_text") or brief.get("message") or "").strip()
        title = str(brief.get("title") or "Storyboard Image").strip()
        video_style = str(brief.get("video_style") or brief.get("style") or "").strip().lower()
        edit_instruction = str(
            brief.get("edit_instruction")
            or brief.get("revision_prompt")
            or brief.get("revision_feedback")
            or brief.get("approval_notes")
            or ""
        ).strip()

        if not text:
            return self._attempt(start, "failed", error="missing_storyboard_text"), {
                "content": "Storyboard text is required to render.",
                "block": {"type": "storyboard_image", "status": "failed", "message": "No storyboard text provided.", "allowed_actions": ["dismiss"]},
            }

        missing = _storyboard_preflight(brief)
        if missing:
            return self._attempt(start, "failed", error="storyboard_preflight_failed"), {
                "content": "Storyboard blocked before image generation: missing " + ", ".join(missing),
                "block": _storyboard_preflight_block(missing, brief),
            }

        core = _load_core()
        try:
            provider, model, api_key = core._get_image_creds(brief)
            openai_base_url = _openai_base_url(core, brief)
        except ValueError as exc:
            return self._attempt(start, "failed", error=str(exc)), {
                "content": f"Storyboard setup error: {exc}",
                "block": {"type": "storyboard_image", "status": "failed", "reason_code": "credentials", "message": str(exc), "allowed_actions": ["dismiss"]},
            }

        try:
            # Non-blocking logo/brand injection — if Drive fails, still generate
            brand_spec = _resolve_brand_spec(brief)
            reference_images = _inject_logo_reference(brief, brand_spec)

            runs_root = Path(str(core.RUNS_ROOT)).expanduser()
            runs_root.mkdir(parents=True, exist_ok=True)
            ts = int(time.time())
            output_path = str(runs_root / f"storyboard_{ts}.png")

            # Force low quality for storyboard renders — gpt-image-2 at high
            # quality ignores style directives and produces photorealistic output.
            # Low quality produces rougher, sketch-like images that Seedance 2.0
            # accepts as reference media.
            brief["image_quality"] = "low"

            # Normalize friendly aspect-ratio aliases (e.g. 3:4) and stale
            # legacy sizes to provider-safe OpenAI image dimensions before the
            # API call. CMO chat often emits ratio strings for storyboard work.
            requested_size = brief.get("size") or brief.get("aspect_ratio") or "16:9"
            normalized_size = core._normalize_requested_size(requested_size)
            brief["size"] = normalized_size

            # Minimal spec — just carries normalized size for the API call
            spec = {"job": {"size": normalized_size}}

            # Build the image prompt with enforced pencil/hand-drawn style.
            # Seedance 2.0 rejects photorealistic human faces, so storyboard
            # images must be rough conceptual sketches, not finished art.
            # The AI video renderer (Previs Motion) handles hyperrealism.
            #
            # Extract only visual descriptions from the script — strip voiceover
            # lines, text overlays, and structural labels so gpt-image-2 doesn't
            # render the script text into the image.
            visual_only = _extract_visual_descriptions(text)
            style_note = ""
            if video_style:
                style_note = (
                    f"Target video style: {video_style}. "
                    f"The rendered image is a storyboard REFERENCE for this video style — "
                    f"suggest the mood/composition/lighting of {video_style} but keep the rendering "
                    f"as rough hand-drawn pencil/ink storyboard sketch, not finished {video_style} art. "
                )
            revision_note = ""
            if edit_instruction:
                revision_note = (
                    f"Revision instruction (authoritative): {edit_instruction}. "
                    "Preserve the approved storyboard structure and only change what the revision requests. "
                )
            image_prompt = (
                f"Hand-drawn pencil storyboard sketch. Black ink on white paper. "
                f"{style_note}"
                f"{revision_note}"
                f"{visual_only}"
            )

            source_ref = _source_image_ref_to_path(brief, runs_root) if edit_instruction else None
            ref_paths = ([source_ref] if source_ref else []) + (_refs_to_paths(reference_images, runs_root) if reference_images else [])

            auth_mode = core._provider_auth_mode_from_brief(brief) if hasattr(core, "_provider_auth_mode_from_brief") else ""
            if auth_mode == "oauth":
                if ref_paths:
                    image_inputs = [(Path(p).read_bytes(), f"storyboard/reference image {idx}", "image/png") for idx, p in enumerate(ref_paths[:4], start=1)]
                    image_bytes = core._call_openai_codex_image_generation(
                        image_prompt,
                        brief,
                        api_key,
                        model,
                        normalized_size,
                        images=image_inputs,
                        action="edit" if source_ref else "generate",
                    )
                else:
                    image_bytes = core._call_openai_codex_image_generation(
                        image_prompt,
                        brief,
                        api_key,
                        model,
                        normalized_size,
                        action="generate",
                    )
            else:
                if ref_paths:
                    response = _call_core_openai_edit(core, spec, image_prompt, ref_paths, brief, api_key, model, normalized_size, openai_base_url)
                else:
                    response = _call_core_openai_generate(core, spec, image_prompt, brief, api_key, model, normalized_size, openai_base_url)
                image_bytes, _ = core._image_response_to_bytes(response)
            Path(output_path).write_bytes(image_bytes)

            drive_meta = _store_in_drive(brief, image_bytes, output_path)

        except Exception as exc:
            return self._attempt(start, "failed", error=type(exc).__name__), {
                "content": f"Storyboard render failed: {exc}",
                "block": {"type": "storyboard_image", "status": "failed", "reason_code": type(exc).__name__, "message": str(exc), "allowed_actions": ["retry", "dismiss"]},
            }

        if not drive_meta.get("drive_file_id"):
            detail = drive_meta.get("drive_upload_error") or drive_meta.get("drive_upload_status") or "Google Drive upload did not return a file ID"
            return self._attempt(start, "failed", error="drive_storage_unavailable"), {
                "content": f"Storyboard image was generated but could not be saved to the Brand's Google Drive: {detail}",
                "block": {"type": "storyboard_image", "status": "failed", "reason_code": "drive_storage_unavailable", "message": detail, "allowed_actions": ["retry", "dismiss"]},
            }

        image_data_b64 = base64.b64encode(image_bytes).decode()

        block: dict = {
            "type": "image_asset",
            "legacy_type": "storyboard_image",
            "status": "succeeded",
            "title": title,
            "display_title": title,
            "mime_type": "image/png",
            "storyboard_text": text,
            "image_data_b64": image_data_b64,
            "output_path": output_path,
            "byte_size": len(image_bytes),
            "brand_reference_count": len(reference_images),
            "approval_status": "pending",
            "video_style": video_style or None,
            "allowed_actions": ["approve", "revise", "dismiss", "generate_video"],
            "action_modules": {"revise": "storyboard.render", "generate_video": "storyboard.motion.render"},
            **drive_meta,
        }

        return self._attempt(start, "succeeded", provider), {
            "content": f"Storyboard image ready ({len(image_bytes):,} bytes)",
            "block": block,
        }

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        if not isinstance(content, str):
            return "fail", ["content_not_string"]
        if "failed" in content.lower():
            return "fail", ["render_failed"]
        return "pass", []
