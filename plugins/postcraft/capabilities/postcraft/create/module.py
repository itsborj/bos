"""Postcraft — branded social post image generator.

Pipeline:
  1. Vision-First Intake: classify each attached brand asset
  2. Build composite reference sheet (Pillow)
  3. Build generation prompt from brand_kit + template + copy + asset labels
  4. Call images.edit (OpenAI gpt-image-2)
  5. Vision breakdown of output
  6. Upload result to Drive
  7. Return post_image artifact
"""
from __future__ import annotations

import base64
import importlib.util
import io
import os
import time
from pathlib import Path

from klaroha_sdk import ChannelModule


_SIZE_MAP = {
    "portrait_feed": "1024x1536",
    "story_reel": "1024x1536",
    "square": "1024x1024",
    "landscape": "1536x1024",
}

_TEMPLATE_STYLE = {
    "promo": "high-impact sales flyer — large dominant headline, strong CTA band, hero image panel, brand accent ribbons",
    "price_card": "premium product layout — formal serif headline, price/offer section, CTA ribbon, generous whitespace",
    "photo_hero": "cinematic brand image — full background photo, logo top, elegant text overlay, CTA button",
    "agent_award": "formal recognition post — logo top, agent portrait right, award text left, branded footer",
    "educational": "clean editorial card — logo top, icon badge, formal headline, short body copy, CTA",
}


def _load_lib(name: str):
    path = Path(__file__).resolve().parents[3] / "lib" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"postcraft_lib_{name}", str(path))
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _load_drive():
    candidates = [
        Path(__file__).resolve().parents[4] / "google-drive" / "drive_client.py",
        Path("/external_plugins/google-drive/drive_client.py"),
        Path("/app/plugins/google-drive/drive_client.py"),
    ]
    for path in candidates:
        if path.exists():
            spec = importlib.util.spec_from_file_location("postcraft_drive_client", str(path))
            mod = importlib.util.module_from_spec(spec)
            assert spec.loader is not None
            spec.loader.exec_module(mod)
            return mod
    raise FileNotFoundError("google-drive/drive_client.py not found in plugin search paths")


def _openai_base_url_from_brief(brief: dict) -> str | None:
    creds = brief.get("_channel_credentials") or {}
    if not isinstance(creds, dict):
        return None
    return str(
        creds.get("openai_api_base_url")
        or creds.get("provider_api_base_url")
        or creds.get("provider_api_key_base_url")
        or ""
    ).strip() or None


def _provider_auth_mode_from_brief(brief: dict) -> str:
    creds = brief.get("_channel_credentials") or {}
    return str(creds.get("provider_api_key_auth_mode") or "").strip().lower() if isinstance(creds, dict) else ""


def _get_image_creds(brief: dict) -> tuple[str, str, str]:
    """Return (provider, model, api_key) from channel credentials.

    Provider and model are injected by inject_channel_credentials via
    backend_override_provider / backend_override_model slots, seeded from
    channel.json default_backend when no admin override is set.
    """
    creds = brief.get("_channel_credentials") or {}
    provider = str(creds.get("image_gen_provider") or "").lower().strip()
    model = str(creds.get("image_gen_model") or "").strip()
    provider_key = str(creds.get("provider_api_key") or "").strip()
    provider_auth_mode = str(creds.get("provider_api_key_auth_mode") or "").strip()
    platform_key = str(creds.get("platform_openai_key") or "").strip()
    if provider == "openai" or not provider:
        if provider_key and provider_auth_mode in {"api_key", "oauth"}:
            api_key = provider_key
        elif platform_key:
            api_key = platform_key
        else:
            api_key = provider_key
    else:
        api_key = provider_key

    if not provider:
        raise ValueError(
            "No image generation provider configured for Postcraft. "
            "Set one in Admin → AI Providers."
        )
    if not api_key:
        raise ValueError(
            f"No API key found for provider '{provider}'. "
            "Configure it in Admin → AI Providers."
        )

    return provider, model, api_key


def _extract_copy(brief: dict) -> dict:
    return {
        "headline": str(brief.get("headline") or brief.get("caption") or ""),
        "subheadline": str(brief.get("subheadline") or ""),
        "body": str(brief.get("body_copy") or brief.get("body") or ""),
        "cta": str(brief.get("cta_text") or brief.get("cta") or ""),
        "location": str(brief.get("location") or ""),
    }


def _resolve_brand_spec(brief: dict) -> dict:
    brand_kit = brief.get("brand_kit") or {}
    spec = brand_kit.get("brand_spec") or {}
    if spec:
        return spec
    for key in ("brand_spec", "brand_json"):
        val = brief.get(key)
        if isinstance(val, dict):
            return val
    return {}


def _campaign_alignment(brief: dict) -> dict:
    val = brief.get("campaign_alignment")
    return val if isinstance(val, dict) else {}


def _postcraft_preflight(brief: dict) -> list[str]:
    """Hard gate: no Postcraft provider call without Brand Kit, logo, and campaign alignment."""
    brand_kit = brief.get("brand_kit") if isinstance(brief.get("brand_kit"), dict) else {}
    brand_name = str(brand_kit.get("brand_name") or brand_kit.get("name") or brief.get("brand_name") or "").strip()
    generic_names = {"", "brand", "this brand", "this business"}
    colors = brand_kit.get("color_palette") or brand_kit.get("colors") or {}
    has_style = bool(colors or brand_kit.get("visual_tone") or brand_kit.get("tone") or brand_kit.get("voice") or brand_kit.get("brand_visual_constraints") or brief.get("brand_visual_constraints"))
    brand_spec = _resolve_brand_spec(brief)
    logo_id = str(brand_spec.get("logo_drive_file_id") or "").strip()
    creds = brief.get("_channel_credentials") or {}
    drive_token = str(creds.get("google_drive_page_token") or creds.get("page_token") or creds.get("access_token") or "").strip()
    drive_root = str(creds.get("drive_root_folder_id") or brand_spec.get("drive_root_folder_id") or "").strip()
    alignment = _campaign_alignment(brief)
    has_campaign = bool(
        alignment and str(brief.get("campaign_id") or alignment.get("campaign_id") or "").strip()
    )

    missing: list[str] = []
    if not brand_kit.get("brand_id") or brand_name.lower() in generic_names or not has_style:
        missing.append("brand_kit")
    if not drive_token:
        missing.append("google_drive_credentials")
    if not drive_root:
        missing.append("google_drive_root_folder")
    if not logo_id:
        missing.append("official_logo_drive_file_id")
    if not has_campaign:
        missing.append("campaign_alignment")
    return missing


def _preflight_block(missing: list[str], brief: dict) -> dict:
    brand_kit = brief.get("brand_kit") if isinstance(brief.get("brand_kit"), dict) else {}
    brand_id = str(brand_kit.get("brand_id") or brief.get("brand_id") or "").strip()
    brand_base = f"/admin/brands/{brand_id}" if brand_id else "/admin/brands"
    checklist = {
        "brand_kit": {
            "fix": "Load/approve the brand kit so Postcraft has brand_id, real brand_name, voice, colors, and visual constraints.",
            "href": f"{brand_base}?tab=brand-kit" if brand_id else brand_base,
            "label": "Open Brand Kit",
        },
        "official_logo_drive_file_id": {
            "fix": "Select a Brand Kit Drive folder containing the official logo, or set brand_spec.logo_drive_file_id.",
            "href": f"{brand_base}?tab=integrations" if brand_id else brand_base,
            "label": "Choose Logo Drive Source",
        },
        "google_drive_credentials": {
            "fix": "Connect Google Drive for this brand so Postcraft can read brand assets and save generated files before Stream review.",
            "href": f"{brand_base}?tab=integrations" if brand_id else brand_base,
            "label": "Connect Google Drive",
        },
        "google_drive_root_folder": {
            "fix": "Select and validate the Brand Kit Drive folder. It must contain the official logo and may contain mascot/product/location reference assets.",
            "href": f"{brand_base}?tab=integrations" if brand_id else brand_base,
            "label": "Choose Brand Kit Drive Folder",
        },
        "campaign_alignment": {
            "fix": "Select or create an active campaign so Postcraft can align goal, audience, offer, and message angle.",
            "href": "/admin/campaigns",
            "label": "Open Campaigns",
        },
    }
    items = [{"key": k, "status": "missing", **checklist.get(k, {"fix": k, "href": "/admin", "label": "Open Admin"})} for k in missing]
    return {
        "type": "setup_blocker",
        "status": "failed",
        "reason_code": "postcraft_preflight_failed",
        "message": "Postcraft blocked before image generation: missing " + ", ".join(missing),
        "preflight_checklist": items,
        "setup_links": items,
        "allowed_actions": ["dismiss"],
    }


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


def _inject_logo(brief: dict, brand_spec: dict) -> list[dict]:
    """Fetch official logo from Drive and prepend it to reference_images.

    Raises ValueError when a declared logo cannot be sent to the image model;
    Postcraft must not spend credits while merely mentioning a logo in text.
    """
    reference_images: list[dict] = list(brief.get("reference_images") or [])
    logo_file_id = str(brand_spec.get("logo_drive_file_id") or "").strip()
    if not logo_file_id:
        return reference_images
    creds = brief.get("_channel_credentials") or {}
    token = str(creds.get("google_drive_page_token") or creds.get("access_token") or creds.get("page_token") or "").strip()
    if not token:
        raise ValueError("Postcraft preflight failed: Google Drive credentials are required to load the official logo and Brand visual references.")
    try:
        drive_mod = _load_drive()
        injected: list[dict] = []
        with drive_mod.DriveClient(token) as client:
            meta = client.get_file_meta(logo_file_id)
            logo_bytes = client.download_file(logo_file_id)
            filename = str(meta.get("name") or brand_spec.get("logo_file_name") or "brand-logo.png")
            mime = str(meta.get("mimeType") or brand_spec.get("logo_mime_type") or "image/png")
            injected.append({
                "title": filename,
                "filename": filename,
                "drive_file_id": logo_file_id,
                "vision_b64": base64.b64encode(logo_bytes).decode(),
                "mime_type": mime,
                "panel_label": "BRAND LOGO — place at top center of design",
                "placement_role": "logo",
                "_auto_injected": True,
            })
            for idx, asset in enumerate(_brand_visual_asset_refs(brand_spec)[:6], start=1):
                file_id = str(asset.get("drive_file_id") or "").strip()
                if not file_id or file_id == logo_file_id:
                    continue
                meta = client.get_file_meta(file_id)
                raw = client.download_file(file_id)
                filename = str(meta.get("name") or asset.get("filename") or asset.get("title") or f"brand-visual-{idx}.png")
                mime = str(meta.get("mimeType") or asset.get("mime_type") or "image/png")
                injected.append({
                    "title": str(asset.get("title") or filename),
                    "filename": filename,
                    "drive_file_id": file_id,
                    "vision_b64": base64.b64encode(raw).decode(),
                    "mime_type": mime,
                    "panel_label": str(asset.get("panel_label") or f"BRAND VISUAL ASSET {idx} — mascot, product, location, people, or style reference; use when relevant"),
                    "placement_role": str(asset.get("placement_role") or "brand_visual_asset"),
                    "_auto_injected": True,
                })
        injected_ids = {str(r.get("drive_file_id") or "") for r in injected}
        return injected + [r for r in reference_images if str(r.get("drive_file_id") or "") not in injected_ids]
    except Exception as exc:
        raise ValueError(f"Postcraft preflight failed: could not load required Brand assets from Drive ({exc}).") from exc


def _select_reference_images(reference_images: list[dict]) -> list[dict]:
    logo_refs = [
        r for r in reference_images
        if r.get("placement_role") == "logo" or "logo" in str(r.get("panel_label") or "").lower()
    ]
    operator_input_refs = [r for r in reference_images if not r.get("_auto_injected")]
    selected: list[dict] = []
    seen_ids: set[str] = set()

    def _append(ref: dict) -> None:
        key = str(ref.get("id") or ref.get("drive_file_id") or ref.get("title") or id(ref))
        if key in seen_ids or len(selected) >= 4:
            return
        seen_ids.add(key)
        selected.append(ref)

    if logo_refs:
        _append(logo_refs[0])
    for ref in operator_input_refs:
        _append(ref)
    for ref in reference_images:
        _append(ref)
    return selected


def _build_prompt(
    brand_kit: dict,
    copy: dict,
    template_type: str,
    post_format: str,
    labeled_assets: list[dict],
    campaign: dict | None = None,
    edit_instruction: str = "",
) -> str:
    campaign = campaign or {}
    brand_name = str(brand_kit.get("brand_name") or brand_kit.get("name") or "")
    colors = brand_kit.get("color_palette") or brand_kit.get("colors") or {}
    tone = brand_kit.get("brand_tone") or brand_kit.get("tone") or []
    tone_str = ", ".join(str(t) for t in tone) if isinstance(tone, list) else str(tone)
    brand_constraints = str(brand_kit.get("brand_visual_constraints") or "").strip()

    primary_color = str(next((colors[k] for k in ("color_primary", "primary", "accent") if colors.get(k)), ""))
    bg_color = str(next((colors[k] for k in ("color_background", "background", "dark") if colors.get(k)), ""))
    text_color = str(next((colors[k] for k in ("color_text", "text", "light") if colors.get(k)), ""))

    size = _SIZE_MAP.get(post_format, "1024x1024")
    template_desc = _TEMPLATE_STYLE.get(template_type, _TEMPLATE_STYLE["promo"])

    panel_instructions: list[str] = []
    for i, asset in enumerate(labeled_assets):
        side = "LEFT" if i == 0 else "RIGHT" if i == 1 else f"PANEL {i + 1}"
        panel_instructions.append(
            f"REFERENCE SHEET {side} PANEL: {asset.get('panel_label', asset.get('subject', 'brand asset'))}"
        )

    copy_block = ""
    if copy["headline"]:
        copy_block += f"Headline: {copy['headline']}\n"
    if copy["subheadline"]:
        copy_block += f"Subheadline: {copy['subheadline']}\n"
    if copy["body"]:
        copy_block += f"Body copy: {copy['body']}\n"
    if copy["cta"]:
        copy_block += f"CTA: {copy['cta']}\n"
    if copy["location"]:
        copy_block += f"Location: {copy['location']}\n"

    prompt_parts = []

    if edit_instruction:
        prompt_parts.append(
            f"REVISION: {edit_instruction}\n"
            "Apply this change only. Preserve all other brand elements, layout, colors, typography, and assets exactly as they appear in the source image."
        )

    if panel_instructions:
        panel_block = "\n".join(panel_instructions)
        prompt_parts.append(
            f"REFERENCE SHEET PROVIDED. Do not copy the reference sheet layout — "
            f"use the assets inside it for the final design:\n{panel_block}"
        )

    prompt_parts.append(
        f"Create a premium {size} social media post for {brand_name or 'this brand'}. "
        f"Template style: {template_desc}. "
        f"Tone: {tone_str or 'premium, professional'}."
    )

    color_parts = []
    if primary_color:
        color_parts.append(f"primary accent {primary_color}")
    if bg_color:
        color_parts.append(f"background {bg_color}")
    if text_color:
        color_parts.append(f"text {text_color}")
    if color_parts:
        prompt_parts.append(
            f"Brand colors: {', '.join(color_parts)}. "
            "Use generous spacing and strong visual hierarchy. Apply brand colors consistently across all elements."
        )

    if copy_block:
        prompt_parts.append(f"Copy to include:\n{copy_block.strip()}")

    if campaign:
        prompt_parts.append(
            "Campaign alignment: "
            + "; ".join(str(v) for v in [
                campaign.get("name"), campaign.get("goal"), campaign.get("audience"), campaign.get("message_angle")
            ] if v)
        )
    if brand_constraints:
        prompt_parts.append("Approved brand visual constraints: " + brand_constraints)

    prompt_parts.append(
        "Design rules: "
        "large bold headline as dominant element; "
        "keep all text inside safe margins; "
        "footer with contact details if provided; "
        "clean professional layout with clear visual hierarchy."
    )

    return "\n\n".join(prompt_parts)


def _sniff_mime(image_bytes: bytes) -> str:
    """Detect image format from magic bytes — never trust provider-claimed type."""
    if image_bytes[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    if image_bytes[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    return "image/jpeg"  # safe default: all AI providers output JPEG or PNG


def _make_thumbnail(image_bytes: bytes, max_px: int = 480) -> tuple[str, str]:
    """Return (base64, mime_type) JPEG thumbnail for inline preview.

    JPEG at q=75 keeps photographic previews under ~60KB regardless of source
    size, avoiding JSON truncation when the full image is already in Drive.
    Always returns image/jpeg — sniff the output bytes to confirm, not the input claim.
    """
    from PIL import Image as _PIL
    buf_in = io.BytesIO(image_bytes)
    img = _PIL.open(buf_in).convert("RGB")
    img.thumbnail((max_px, max_px), _PIL.LANCZOS)
    buf_out = io.BytesIO()
    img.save(buf_out, format="JPEG", quality=75, optimize=True)
    result_bytes = buf_out.getvalue()
    return base64.b64encode(result_bytes).decode(), _sniff_mime(result_bytes)


def _store_in_drive(brief: dict, image_bytes: bytes, filename: str) -> dict:
    creds = brief.get("_channel_credentials") or {}
    token = str(
        creds.get("google_drive_page_token")
        or creds.get("access_token")
        or creds.get("page_token")
        or ""
    ).strip()
    if not token:
        return {"drive_upload_status": "failed", "drive_upload_error": "Google Drive credentials missing"}
    root = str(creds.get("drive_root_folder_id") or "").strip()
    if not root:
        return {"drive_upload_status": "failed", "drive_upload_error": "Brand Google Drive root folder missing"}
    try:
        drive_mod = _load_drive()
        with drive_mod.DriveClient(token) as client:
            folder = client.ensure_folder("Postcraft", root)
            meta = client.upload_file(filename, image_bytes, "image/png", folder["id"])
        return {
            "drive_file_id": meta.get("id"),
            "drive_file_name": meta.get("name"),
            "drive_file_mime": meta.get("mimeType") or "image/png",
            "drive_web_view_link": meta.get("webViewLink"),
            "drive_folder": "Postcraft",
            "reusable": True,
        }
    except Exception as exc:
        return {"drive_upload_status": "failed", "drive_upload_error": str(exc)[:400]}


def _run_sync(brief: dict) -> dict:
    """Full Postcraft pipeline — runs synchronously, called via asyncio.to_thread."""
    provider, model, api_key = _get_image_creds(brief)
    openai_base_url = _openai_base_url_from_brief(brief)
    openai_auth_mode = _provider_auth_mode_from_brief(brief)

    openai_client = _load_lib("openai_client")
    composite_lib = _load_lib("composite")

    # Revision detection: edit_instruction signals a targeted copy/layout change;
    # artifact_data carries the previous run's brand context and image.
    edit_instruction = str(
        brief.get("edit_instruction") or brief.get("revision_instruction") or ""
    ).strip()

    artifact_data: dict = {}
    for _key in ("artifact_data", "previous_artifact", "artifact", "input_artifact"):
        _val = brief.get(_key)
        if isinstance(_val, dict):
            artifact_data = _val
            break
    if not artifact_data:
        for _key in ("artifact_blocks", "artifacts", "blocks"):
            _val = brief.get(_key)
            if isinstance(_val, list) and _val and isinstance(_val[0], dict):
                artifact_data = _val[0]
                break

    is_revision = bool(edit_instruction or artifact_data)

    brand_kit: dict = brief.get("brand_kit") or {}
    brand_spec: dict = _resolve_brand_spec(brief)
    reference_images: list[dict] = _inject_logo(brief, brand_spec)
    copy = _extract_copy(brief)
    template_type = str(brief.get("template_type") or "")
    post_format = str(brief.get("post_format") or "")

    # On revision: pull everything the current brief omits from the previous artifact
    if is_revision:
        if not brand_kit:
            brand_kit = artifact_data.get("brand_kit") or {}
            brand_spec = _resolve_brand_spec({"brand_kit": brand_kit, "brand_spec": artifact_data.get("brand_spec") or {}})
        if not template_type:
            template_type = str(artifact_data.get("template_type") or "promo")
        if not post_format:
            post_format = str(artifact_data.get("post_format") or "square")
        prev_copy = artifact_data.get("copy") or {}
        for field in ("headline", "subheadline", "body", "cta", "location"):
            if not copy.get(field):
                copy[field] = str(prev_copy.get(field) or "")

    template_type = template_type or "promo"
    post_format = post_format or "square"
    size = _SIZE_MAP.get(post_format, "1024x1024")

    # Step 1: Vision intake — classify each brand asset
    # Always use OpenAI (gpt-4o-mini) for vision intake regardless of image gen provider,
    # since it's a cheap chat call and avoids provider-specific vision branching.
    labeled_assets: list[dict] = []
    asset_bytes_list: list[tuple[bytes, str, str]] = []

    intake_api_key = api_key if provider == "openai" else (
        os.environ.get("PLATFORM_OPENAI_KEY") or os.environ.get("OPENAI_API_KEY") or api_key
    )

    for ref in _select_reference_images(reference_images):
        vision_b64 = str(ref.get("vision_b64") or "")
        mime = str(ref.get("mime_type") or "image/jpeg")
        title = str(ref.get("title") or "brand asset")
        if not vision_b64:
            continue
        try:
            intake = openai_client.vision_intake(vision_b64, mime, title, intake_api_key, base_url=openai_base_url)
        except Exception:
            intake = {
                "asset_type": "unknown",
                "subject": title,
                "panel_label": f"{title.upper()} — use as brand asset",
                "placement_role": "unknown",
            }
        labeled_assets.append(intake)
        asset_bytes_list.append((base64.b64decode(vision_b64), intake.get("panel_label", title.upper()), mime))

    # On revision with no new assets: restore labeled_assets from previous run so the
    # prompt still references the correct brand assets by label.
    if is_revision and not labeled_assets:
        labeled_assets = list(artifact_data.get("vision_intake") or [])

    # Revision continuity anchor: json-imagen proved revisions need the previous
    # approved/generated image as the visual source, not just an updated prompt.
    prior_image_bytes: bytes | None = None
    if is_revision:
        _prior_b64 = str(brief.get("source_image_data_b64") or brief.get("image_data_b64") or artifact_data.get("image_data_b64") or "").strip()
        if _prior_b64:
            try:
                from PIL import Image as _PIL
                _raw = base64.b64decode(_prior_b64)
                _buf = io.BytesIO()
                _PIL.open(io.BytesIO(_raw)).convert("RGBA").save(_buf, format="PNG")
                prior_image_bytes = _buf.getvalue()
            except Exception:
                prior_image_bytes = None

    # Step 2: Prompt
    prompt = _build_prompt(
        brand_kit, copy, template_type, post_format, labeled_assets,
        _campaign_alignment(brief), edit_instruction,
    )
    if is_revision and prior_image_bytes:
        prompt += (
            "\n\nREVISION SOURCE PANEL: CURRENT APPROVED DESIGN — use it as the visual continuity anchor. "
            "Preserve identity, geometry, layout, colors, typography, and unchanged elements outside the requested change."
        )

    # Step 3: Generate image — dispatch by provider
    if provider == "gemini":
        gemini_client = _load_lib("gemini_client")
        ref_parts = [
            {"b64": base64.b64encode(img_bytes).decode(), "mime_type": mime, "label": label}
            for img_bytes, label, mime in asset_bytes_list
        ]
        image_bytes = gemini_client.generate_image(api_key, prompt, model, size, ref_parts)

    elif provider == "bytedance":
        bytedance_client = _load_lib("bytedance_client")
        image_bytes = bytedance_client.generate_image(api_key, prompt, model, size)

    else:
        # OpenAI — composite reference sheet + images/edits.
        # images/edits requires PNG with alpha channel (RGBA); JPEG or opaque PNG will 403/400.
        if len(asset_bytes_list) == 1:
            from PIL import Image as _PIL
            buf = io.BytesIO()
            _PIL.open(io.BytesIO(asset_bytes_list[0][0])).convert("RGBA").save(buf, format="PNG")
            composite_bytes: bytes | None = buf.getvalue()
        elif len(asset_bytes_list) > 1:
            composite_bytes = composite_lib.build_composite(asset_bytes_list)
        else:
            composite_bytes = None

        if prior_image_bytes and asset_bytes_list:
            # One source image limit: compose current design + logo/references into
            # a single labeled sheet so the model sees both the prior render and
            # the new assets for the revision.
            composite_bytes = composite_lib.build_composite(
                [(prior_image_bytes, "CURRENT APPROVED DESIGN — preserve layout and unchanged elements", "image/png")]
                + asset_bytes_list
            )
        elif prior_image_bytes:
            composite_bytes = prior_image_bytes

        def _env_fallback_key() -> str | None:
            return (
                os.environ.get("PLATFORM_OPENAI_KEY")
                or os.environ.get("OPENAI_API_KEY")
                or None
            )

        def _gen_with_key(key: str) -> bytes:
            edit_source = prior_image_bytes or composite_bytes
            if openai_auth_mode == "oauth":
                refs: list[tuple[bytes, str, str]] = []
                if edit_source:
                    refs.append((edit_source, "CURRENT APPROVED DESIGN / REFERENCE SHEET", "image/png"))
                return openai_client.generate_image_codex(
                    prompt,
                    key,
                    model=model,
                    size=size,
                    quality="high",
                    images=refs,
                    action="edit" if refs else "generate",
                )
            if edit_source:
                try:
                    return openai_client.generate_image(edit_source, prompt, key, model, size, base_url=openai_base_url)
                except RuntimeError:
                    return openai_client.generate_image_text_only(prompt, key, model, size, base_url=openai_base_url)
            return openai_client.generate_image_text_only(prompt, key, model, size, base_url=openai_base_url)

        try:
            image_bytes = _gen_with_key(api_key)
        except openai_client.ScopeError:
            fallback = _env_fallback_key()
            if fallback and fallback != api_key:
                image_bytes = _gen_with_key(fallback)
            else:
                raise RuntimeError(
                    "The configured OpenAI credential was rejected by image generation. "
                    "Reconnect OpenAI in Admin → AI Providers and try again."
                )

    # Step 4: Vision breakdown of generated image
    brand_name = str(brand_kit.get("brand_name") or brand_kit.get("name") or "brand")
    brief_summary = f"{brand_name} | {template_type} | {copy.get('headline', '')}"
    try:
        breakdown = openai_client.analyze_output(image_bytes, brief_summary, intake_api_key, base_url=openai_base_url)
    except Exception:
        breakdown = {}

    # Step 6: Upload to Drive
    ts = int(time.time())
    filename = f"postcraft_{template_type}_{ts}.png"
    drive_meta = _store_in_drive(brief, image_bytes, filename)
    if not drive_meta.get("drive_file_id"):
        detail = drive_meta.get("drive_upload_error") or drive_meta.get("drive_upload_status") or "Google Drive upload did not return drive_file_id"
        raise ValueError(f"Postcraft storage preflight failed: generated image could not be saved to the Brand's Google Drive ({detail}).")

    image_data_b64 = base64.b64encode(image_bytes).decode()
    thumb_b64, thumb_mime = _make_thumbnail(image_bytes)
    return {
        "filename": filename,
        "byte_size": len(image_bytes),
        "image_data_b64": image_data_b64,
        "image_b64": thumb_b64,
        "image_mime": thumb_mime,
        "template_type": template_type,
        "post_format": post_format,
        "size": size,
        "brand_name": brand_name,
        "brand_kit": brand_kit,
        "brand_spec": brand_spec,
        "provider": provider,
        "model": model,
        "copy": copy,
        "prompt": prompt,
        "labeled_assets": labeled_assets,
        "breakdown": breakdown,
        "drive_meta": drive_meta,
    }


class PostcraftCreateModule(ChannelModule):
    """Generate a branded social post image from a brief and attached brand assets."""

    id = "postcraft.create"
    name = "Postcraft Create"
    vertical = "creative"
    capability = "postcraft.create"
    platform_hint = "postcraft"

    actions = {
        "create": {
            "description": (
                "Generate a branded social post image, OR revise an existing one. "
                "For revisions: pass only edit_instruction describing what to change — "
                "the module preserves all other brand elements, layout, and copy from the previous run. "
                "Do NOT pass image_prompt, background_color, aspect_ratio, or any visual/scene direction."
            ),
            "parameters": {
                "headline": {
                    "type": "string",
                    "description": "Primary headline text for the post.",
                },
                "subheadline": {
                    "type": "string",
                    "description": "Secondary headline (optional).",
                },
                "body_copy": {
                    "type": "string",
                    "description": "Body text for the post (optional).",
                },
                "cta_text": {
                    "type": "string",
                    "description": "Call-to-action text, e.g. 'Book Now', 'Learn More' (optional).",
                },
                "template_type": {
                    "type": "string",
                    "description": "Post layout style. Defaults to 'promo' if not specified.",
                    "enum": ["promo", "price_card", "photo_hero", "agent_award", "educational"],
                },
                "post_format": {
                    "type": "string",
                    "description": "Output image dimensions. Defaults to 'square' if not specified.",
                    "enum": ["square", "portrait_feed", "story_reel", "landscape"],
                },
                "location": {
                    "type": "string",
                    "description": "Location or address to include in the post (optional).",
                },
                "edit_instruction": {
                    "type": "string",
                    "description": (
                        "Revision instruction for an existing post image. "
                        "Describe only what to change; the module preserves everything else. "
                        "Example: 'replace the pipes with a vase, keep all other elements unchanged'. "
                        "Use this instead of repeating headline/copy when the user asks to modify a generated image."
                    ),
                },
            },
            "required": [],
        },
    }

    def _attempt(self, start: float, status: str, error=None) -> dict:
        return {
            "provider": "openai",
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

        missing = _postcraft_preflight(brief)
        if missing:
            block = _preflight_block(missing, brief)
            return self._attempt(start, "failed", "postcraft_preflight_failed"), {
                "content": block["message"],
                "block": block,
            }

        try:
            _get_image_creds(brief)
        except ValueError as exc:
            return self._attempt(start, "failed", "credentials"), {
                "content": f"Postcraft setup error: {exc}",
                "block": {
                    "type": "image_asset",
                    "status": "failed",
                    "reason_code": "credentials",
                    "message": str(exc),
                    "allowed_actions": ["dismiss"],
                },
            }

        try:
            result = _run_sync(brief)
        except Exception as exc:
            return self._attempt(start, "failed", type(exc).__name__), {
                "content": f"Postcraft generation failed: {exc}",
                "block": {
                    "type": "image_asset",
                    "status": "failed",
                    "reason_code": type(exc).__name__,
                    "message": str(exc),
                    "allowed_actions": ["retry", "dismiss"],
                },
            }

        copy = result["copy"]
        drive_meta = result["drive_meta"]
        labeled_assets = result["labeled_assets"]
        size = result["size"]

        drive_suffix = (
            f" — saved to Drive: {drive_meta.get('drive_web_view_link', '')}"
            if drive_meta.get("drive_file_id")
            else ""
        )

        return self._attempt(start, "succeeded"), {
            "content": f"Post image ready: {result['filename']} ({result['byte_size']:,} bytes){drive_suffix}",
            "block": {
                "type": "image_asset",
                "legacy_type": "post_image",
                "status": "succeeded",
                "title": f"Post: {copy.get('headline') or result['template_type']}",
                "display_title": f"Post: {copy.get('headline') or result['template_type']}",
                "image_data_b64": result.get("image_data_b64") or result["image_b64"],
                "mime_type": result["image_mime"],
                "byte_size": result["byte_size"],
                "width": int(size.split("x")[0]),
                "height": int(size.split("x")[1]),
                "filename": result["filename"],
                "template_type": result["template_type"],
                "post_format": result["post_format"],
                "brand_name": result["brand_name"],
                "brand_kit": result["brand_kit"],
                "brand_spec": result.get("brand_spec") or {},
                "campaign_alignment": _campaign_alignment(brief),
                "prompt": result["prompt"],
                "headline": copy.get("headline", ""),
                "subheadline": copy.get("subheadline", ""),
                "body_copy": copy.get("body", ""),
                "cta_text": copy.get("cta", ""),
                "copy": copy,
                "assets_used": [a.get("asset_type", "unknown") for a in labeled_assets],
                "asset_labels": [a.get("panel_label", "") for a in labeled_assets],
                "vision_intake": labeled_assets,
                "breakdown": result["breakdown"],
                "provider": result["provider"],
                "model": result["model"],
                "approval_status": "pending",
                "allowed_actions": ["approve", "revise", "dismiss"],
                "action_modules": {"revise": "postcraft.create"},
                **drive_meta,
            },
        }

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        if not isinstance(content, str):
            return "fail", ["content_not_string"]
        if content.lower().startswith(("postcraft generation failed", "postcraft setup error", "postcraft blocked")):
            return "fail", ["generation_failed"]
        return "pass", []
