"""Postcraft Render — full pipeline, gated behind CMO-level text approval.

Gate: _is_render_approved() must pass before any provider call.
If not approved, render fails without creating a draft artifact.

Pipeline (7 steps, each isolated):
  1  Brand asset resolution — auto-inject logo from Drive brand spec
  2  Vision intake          — gpt-4o-mini classify each asset
  3  Prompt construction    — template spec JSON + {{placeholder}} resolution
  4  Composite ref sheet    — Pillow RGBA PNG (OpenAI path only, graceful fallback)
  5  Image generation       — OpenAI / Gemini / ByteDance, one retry on transient
  6  Drive upload           — hard gate; fails if Brand Drive upload does not return drive_file_id
  7  Thumbnail              — 480px JPEG, non-blocking, asset_omitted if Pillow absent
"""
from __future__ import annotations

import base64
import importlib.util
import io
import json
import os
import re
import time
from pathlib import Path

from klaroha_sdk import ChannelModule


_SIZE_MAP = {
    "portrait_feed": "1024x1536",
    "story_reel":    "1024x1536",
    "square":        "1024x1024",
    "landscape":     "1536x1024",
}

_SIZE_DISPLAY = {
    "portrait_feed": "1024×1536",
    "story_reel":    "1024×1536",
    "square":        "1024×1024",
    "landscape":     "1536×1024",
}

_TEMPLATE_DESCRIPTIONS = {
    "promo":       "high-impact sales flyer — large dominant headline, strong CTA band, hero image panel",
    "price_card":  "premium product layout — formal serif headline, price/offer section, CTA ribbon",
    "photo_hero":  "cinematic brand image — full background photo, logo top, elegant text overlay",
    "agent_award": "formal recognition post — logo top, agent portrait right, award text left",
    "educational": "clean editorial card — logo top, icon badge, formal headline, short body copy",
}

_TEMPLATES_DIR = Path(__file__).resolve().parents[3] / "templates"
_AUDIT_DIR = Path(os.environ.get("POSTCRAFT_AUDIT_DIR") or "/var/bos/postcraft-runs")


# ---------------------------------------------------------------------------
# Module loaders
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------

def _is_render_approved(brief: dict) -> bool:
    """Return True only when the operator has explicitly approved the draft.

    Revisions are auto-approved: a prior rendered image in the brief means the
    initial draft gate was already cleared. Mirrors storyboard.render's pattern.
    """
    if not isinstance(brief, dict):
        return False
    truthy_keys = ("render_approved", "approved_draft")
    if any(
        brief.get(k) is True or str(brief.get(k)).lower() in {"true", "yes", "1"}
        for k in truthy_keys
    ):
        return True
    if str(brief.get("action") or brief.get("artifact_action") or "").lower() in {
        "render", "render_approved", "revise"
    }:
        return True
    if str(brief.get("approval_status") or "").lower() == "approved":
        return True
    # Action revise: BOS copies image_data_b64 from prior block into brief
    if brief.get("image_data_b64") or brief.get("source_image_data_b64"):
        return True
    # CMO chat revise: sets revision_context / revision_feedback
    if brief.get("revision_context") or brief.get("revision_feedback"):
        return True
    for key in ("original_artifact_block", "artifact_block", "block"):
        block = brief.get(key)
        if not isinstance(block, dict):
            continue
        if block.get("type") == "postcraft_draft" and str(
            block.get("approval_status") or ""
        ).lower() == "approved":
            return True
    return False


# ---------------------------------------------------------------------------
# Brief helpers
# ---------------------------------------------------------------------------

def _sanitize_copy_field(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    blocked_prefixes = (
        "template:", "format:", "headline:", "subheadline:", "body copy:", "body:",
        "cta:", "visual direction:", "asset/brand notes:", "campaign:",
        "json_revision_spec:", "source_render_spec:", "revision source panel:",
    )
    kept: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if kept and kept[-1] != "":
                kept.append("")
            continue
        if line.lower().startswith(blocked_prefixes):
            continue
        kept.append(line)
    while kept and kept[-1] == "":
        kept.pop()
    cleaned = "\n".join(kept).strip()
    return cleaned if cleaned not in {"-", "—", "_"} else ""


def _extract_copy(brief: dict) -> dict:
    source_text = str(
        brief.get("postcraft_text")
        or brief.get("approved_post_text")
        or brief.get("creative_text")
        or brief.get("message")
        or brief.get("brief")
        or ""
    )
    parsed: dict[str, str] = {}
    field_map = {
        "headline": "headline",
        "subheadline": "subheadline",
        "body": "body",
        "body copy": "body",
        "caption": "body",
        "cta": "cta",
        "call to action": "cta",
        "location": "location",
    }
    lines = source_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip().lstrip("-*• ").strip()
        m = re.match(r"^(?:\*\*)?([A-Za-z][A-Za-z ]{1,30})(?:\*\*)?\s*[:：]\s*(.*)$", line)
        if not m:
            i += 1
            continue
        key = field_map.get(m.group(1).strip().lower())
        if not key:
            i += 1
            continue
        value = m.group(2).strip().strip("`*_ ")
        if not value:
            collected: list[str] = []
            j = i + 1
            while j < len(lines):
                nxt = lines[j].strip()
                nxt_clean = nxt.lstrip("-*• ").strip()
                if re.match(r"^(?:\*\*)?[A-Za-z][A-Za-z ]{1,30}(?:\*\*)?\s*[:：]", nxt_clean):
                    break
                if nxt_clean and nxt_clean not in {"-", "—", "_"}:
                    collected.append(nxt_clean)
                j += 1
            value = " ".join(collected).strip().strip("`*_ ")
            i = j - 1
        value = value.strip().strip('"“”')
        if value and value not in {"-", "—", "_"}:
            parsed[key] = value
        i += 1
    if source_text and not parsed:
        # Fallback only when the model used freeform prose and no structured
        # fields were parsed. Do not stuff the entire approved draft scaffold
        # into body_copy when the operator intentionally left body blank.
        parsed["body"] = source_text[:900]
    return {
        "headline":    _sanitize_copy_field(str(brief.get("headline") or parsed.get("headline") or brief.get("caption") or "")),
        "subheadline": _sanitize_copy_field(str(brief.get("subheadline") or parsed.get("subheadline") or "")),
        "body":        _sanitize_copy_field(str(brief.get("body_copy") or brief.get("body") or parsed.get("body") or "")),
        "cta":         _sanitize_copy_field(str(brief.get("cta_text") or brief.get("cta") or parsed.get("cta") or "")),
        "location":    _sanitize_copy_field(str(brief.get("location") or parsed.get("location") or "")),
    }


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
    creds = brief.get("_channel_credentials") or {}
    provider = str(creds.get("image_gen_provider") or "").lower().strip()
    model    = str(creds.get("image_gen_model") or "").strip()
    provider_key = str(creds.get("provider_api_key") or "").strip()
    provider_auth_mode = str(creds.get("provider_api_key_auth_mode") or "").strip()
    platform_key = str(creds.get("platform_openai_key") or "").strip()
    # Use the same OpenAI credential selected by CMO Brain, including auth-mode
    # OAuth. Prefer user-saved provider credentials over platform fallback.
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


def _resolve_brand_spec(brief: dict) -> dict:
    brand_kit = brief.get("brand_kit") or {}
    spec = brand_kit.get("brand_spec") or {}
    if spec:
        return spec
    for key in ("brand_spec", "brand_json"):
        val = brief.get(key)
        if isinstance(val, dict):
            return val
    docs = brief.get("workspace_documents") or brief.get("workspace_docs") or []
    for doc in docs:
        if isinstance(doc, dict) and doc.get("type") == "postcraft_brand_spec":
            content = doc.get("content") or doc.get("data") or {}
            if isinstance(content, dict):
                return content
    return {}


def _restore_from_prior(brief: dict) -> dict:
    for key in ("original_artifact_block", "artifact_block", "artifact_data", "previous_artifact"):
        val = brief.get(key)
        if isinstance(val, dict):
            return val
    for key in ("artifact_blocks", "artifacts", "blocks"):
        val = brief.get(key)
        if isinstance(val, list) and val and isinstance(val[0], dict):
            return val[0]
    return {}


def _campaign_alignment(brief: dict) -> dict:
    val = brief.get("campaign_alignment")
    return val if isinstance(val, dict) else {}


def _postcraft_preflight(brief: dict) -> list[str]:
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


def _postcraft_template_blocker(brief: dict) -> dict | None:
    blocker = brief.get("_postcraft_template_blocker") if isinstance(brief, dict) else None
    return blocker if isinstance(blocker, dict) and blocker.get("status") == "blocked" else None


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


# ---------------------------------------------------------------------------
# Step 1: Brand asset resolution — logo injection
# ---------------------------------------------------------------------------

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
    """Fetch logo from Drive and prepend to reference_images."""
    reference_images: list[dict] = list(brief.get("reference_images") or [])
    logo_file_id = str(brand_spec.get("logo_drive_file_id") or "").strip()
    if not logo_file_id:
        return reference_images
    creds = brief.get("_channel_credentials") or {}
    token = str(
        creds.get("google_drive_page_token")
        or creds.get("access_token")
        or creds.get("page_token")
        or ""
    ).strip()
    if not token:
        raise ValueError("Postcraft preflight failed: Google Drive credentials are required to load the official logo and Brand visual references.")
    try:
        drive_mod = _load_drive()
        injected: list[dict] = []
        with drive_mod.DriveClient(token) as client:
            meta = client.get_file_meta(logo_file_id)
            logo_bytes = client.download_file(logo_file_id)
            filename = str(meta.get("name") or "brand-logo.png")
            mime = str(meta.get("mimeType") or "image/png")
            injected.append({
                "title": filename,
                "filename": filename,
                "drive_file_id": logo_file_id,
                "vision_b64": base64.b64encode(logo_bytes).decode(),
                "mime_type": mime,
                "panel_label": "OFFICIAL BRAND LOGO — preserve exactly; place with creative judgment in a clear, legible safe area",
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


# ---------------------------------------------------------------------------
# Revision spec helpers
# ---------------------------------------------------------------------------

_OPERATOR_REF_SOURCES = {"operator_attachment", "chat_attachment", "revision_attachment", "upload"}


def _is_operator_revision_ref(ref: dict) -> bool:
    if not isinstance(ref, dict):
        return False
    return bool(
        ref.get("revision_reference")
        or ref.get("priority") == "operator_revision"
        or ref.get("source") in _OPERATOR_REF_SOURCES
    )


def _infer_revision_ref_role(ref: dict, feedback: str = "") -> str:
    explicit = str(ref.get("role") or ref.get("placement_role") or "").strip()
    if explicit and explicit not in {"unknown", "unknown_revision_reference"}:
        return explicit
    text = f"{feedback} {ref.get('title') or ''} {ref.get('filename') or ''}".lower()
    if "logo" in text or "wordmark" in text:
        return "logo_update"
    if "background" in text or "location" in text or "venue" in text or "property" in text:
        return "location_reference"
    if "product" in text or "pack" in text or "hero" in text:
        return "replacement_hero_image"
    if "portrait" in text or "person" in text or "people" in text or "family" in text or "agent" in text:
        return "person_or_portrait_reference"
    if "style" in text or "mood" in text or "inspiration" in text or "look" in text:
        return "style_reference"
    return "unknown_revision_reference"


def _sort_reference_images_for_revision(reference_images: list[dict], is_revision: bool) -> list[dict]:
    if not is_revision:
        return reference_images

    def key(ref: dict) -> tuple[int, str]:
        if _is_operator_revision_ref(ref):
            return (0, str(ref.get("title") or ref.get("filename") or ""))
        if ref.get("placement_role") == "logo" or "logo" in str(ref.get("panel_label") or "").lower():
            return (1, str(ref.get("title") or ref.get("filename") or ""))
        if ref.get("_auto_injected"):
            return (2, str(ref.get("title") or ref.get("filename") or ""))
        return (1, str(ref.get("title") or ref.get("filename") or ""))

    return sorted(reference_images, key=key)


def _select_reference_images(reference_images: list[dict], is_revision: bool) -> tuple[list[dict], list[str]]:
    pipeline_notes: list[str] = []
    operator_refs = [r for r in reference_images if _is_operator_revision_ref(r)]
    if is_revision and len(operator_refs) > 8:
        raise ValueError("Postcraft revision received too many operator image references. Please prioritize up to 8 images for this edit.")
    if is_revision:
        brand_refs = [r for r in reference_images if not _is_operator_revision_ref(r)]
        selected = operator_refs + brand_refs[: max(0, 8 - len(operator_refs))]
        if len(brand_refs) > max(0, 8 - len(operator_refs)):
            pipeline_notes.append("optional brand references truncated after operator revision refs were preserved")
        return selected, pipeline_notes

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

    if operator_input_refs and not any(ref in selected for ref in operator_input_refs):
        pipeline_notes.append("operator reference images were supplied but could not be included")
    elif len(operator_input_refs) > max(0, 4 - (1 if logo_refs else 0)):
        pipeline_notes.append("operator reference images truncated to fit provider reference budget")
    elif len(reference_images) > len(selected):
        pipeline_notes.append("optional brand references truncated after operator references were preserved")
    return selected, pipeline_notes


def _reference_asset_records(reference_images: list[dict], feedback: str = "") -> list[dict]:
    records: list[dict] = []
    for idx, ref in enumerate(reference_images, start=1):
        if not isinstance(ref, dict):
            continue
        role = _infer_revision_ref_role(ref, feedback) if _is_operator_revision_ref(ref) else str(ref.get("placement_role") or "brand_reference")
        records.append({
            "id": str(ref.get("id") or ref.get("drive_file_id") or f"ref_{idx}"),
            "title": str(ref.get("title") or ref.get("filename") or f"Reference {idx}"),
            "role": role,
            "source": str(ref.get("source") or ("operator_attachment" if _is_operator_revision_ref(ref) else "brand_asset")),
            "drive_file_id": ref.get("drive_file_id"),
            "revision_reference": _is_operator_revision_ref(ref),
            "priority": ref.get("priority") or ("operator_revision" if _is_operator_revision_ref(ref) else "brand_context"),
        })
    return records


def _build_render_spec(brief: dict, brand_kit: dict, brand_spec: dict, copy: dict, template_type: str, post_format: str, size: str, reference_assets: list[dict]) -> dict:
    colors = brand_spec.get("color_palette") or brand_kit.get("color_palette") or brand_kit.get("colors") or {}
    alignment = _campaign_alignment(brief)
    return {
        "schema": "postcraft.render_spec.v1",
        "artifact_kind": "social_post_image",
        "layout": {
            "template_type": template_type,
            "base_family": brief.get("base_family") or template_type,
            "template_id": brief.get("template_id") or brief.get("selected_template_id"),
            "post_format": post_format,
            "size": size,
            "composition_notes": (
                brief.get("creative_direction")
                or brief.get("visual_direction")
                or ("Follow the explicitly selected optional layout." if brief.get("template_id") else "Create an original channel-appropriate composition with agency-level creative latitude.")
            ),
        },
        "template_selection": {
            "selected_template_id": brief.get("selected_template_id") or brief.get("template_id"),
            "selection_confidence": brief.get("selection_confidence"),
            "selection_reason": brief.get("selection_reason") or [],
            "brand_kit_template": brief.get("brand_kit_template") or {},
        },
        "brand": {
            "brand_id": brand_kit.get("brand_id") or brief.get("brand_id"),
            "name": brand_kit.get("brand_name") or brand_kit.get("name") or brief.get("brand_name"),
            "colors": colors,
            "logo_drive_file_id": brand_spec.get("logo_drive_file_id"),
            "visual_constraints": brand_kit.get("brand_visual_constraints") or brand_spec.get("brand_visual_constraints"),
        },
        "campaign": {
            "campaign_id": brief.get("campaign_id") or alignment.get("campaign_id"),
            "goal": alignment.get("goal") or alignment.get("objective"),
            "audience": alignment.get("audience"),
            "message_angle": alignment.get("message_angle"),
        },
        "copy": copy,
        "visuals": {
            "logo_position": "creative placement in a clear, legible safe area",
            "hero_role": "campaign_and_reference_defined",
            "text_safe_area": "preserve current readable text zones",
            "reference_assets_used": [r.get("id") for r in reference_assets if r.get("id")],
        },
        "locked_elements": [
            "brand identity",
            "approved copy unless explicitly changed",
            "official logo integrity",
            "campaign tone",
            "readability and platform format",
        ],
    }


def _source_render_spec_from_prior(prior: dict, fallback: dict) -> dict:
    for key in ("postcraft_render_spec", "render_spec", "source_render_spec"):
        val = prior.get(key) if isinstance(prior, dict) else None
        if isinstance(val, dict) and val:
            return val
    return fallback


def _build_revision_spec(brief: dict, source_render_spec: dict, reference_assets: list[dict], feedback: str) -> dict:
    operator_assets = [r for r in reference_assets if r.get("revision_reference")]
    edits: list[dict] = []
    for asset in operator_assets:
        role = str(asset.get("role") or "unknown_revision_reference")
        target = "hero_image" if role in {"replacement_hero_image", "product_reference", "location_reference"} else role
        operation = "replace" if role.startswith("replacement") or role in {"logo_update", "location_reference"} else "apply_reference"
        edits.append({
            "target": target,
            "operation": operation,
            "reference_asset_id": asset.get("id"),
            "instructions": f"Use {asset.get('title') or asset.get('id')} as {role}; apply only where the operator feedback requests it.",
            "preserve": ["overall layout", "brand colors", "approved copy", "CTA", "typography style", "campaign tone"],
        })
    if not edits:
        edits.append({
            "target": "current_design",
            "operation": "localized_adjustment",
            "instructions": feedback or "Improve the current design while preserving approved elements.",
            "preserve": ["overall layout", "brand identity", "approved copy unless explicitly changed", "CTA", "platform format"],
        })
    return {
        "schema": "postcraft.revision_spec.v1",
        "source_artifact_id": brief.get("source_run_id"),
        "source_render_spec_schema": source_render_spec.get("schema") if isinstance(source_render_spec, dict) else None,
        "mode": "localized_image_edit",
        "operator_feedback": feedback,
        "change_request": {"summary": feedback[:240] if feedback else "Localized Postcraft revision", "edits": edits},
        "reference_assets": operator_assets,
        "locked_elements": [
            "do not redesign the full ad",
            "do not change copy unless explicitly requested",
            "do not invent a different logo",
            "do not alter the brand palette",
            "do not reinterpret style references as replacement assets",
        ],
    }


# ---------------------------------------------------------------------------
# Step 3: Prompt construction from template spec
# ---------------------------------------------------------------------------

def _load_template_spec(template_type: str) -> dict:
    path = _TEMPLATES_DIR / f"{template_type}.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return {}



def _resolve_placeholders(value: str, context: dict) -> str:
    def replacer(m: re.Match) -> str:
        key = m.group(1).strip()
        val = context.get(key)
        if val is None:
            return ""
        if isinstance(val, list):
            return ", ".join(str(v) for v in val)
        return str(val)
    return re.sub(r"\{\{([^}]+)\}\}", replacer, value)


def _build_prompt(
    template_spec: dict,
    brand_kit: dict,
    brand_spec: dict,
    copy: dict,
    post_format: str,
    labeled_assets: list[dict],
    campaign: dict | None = None,
    edit_instruction: str = "",
    revision_spec: dict | None = None,
    source_render_spec: dict | None = None,
    brand_kit_template: dict | None = None,
) -> str:
    campaign = campaign or {}
    colors = (
        brand_spec.get("color_palette")
        or brand_kit.get("color_palette")
        or brand_kit.get("colors")
        or {}
    )
    visual_tone = (
        brand_spec.get("visual_language")
        or brand_spec.get("visual_tone")
        or brand_kit.get("visual_language")
        or brand_kit.get("brand_tone")
        or brand_kit.get("tone")
        or []
    )
    negative_prompts = list(brand_spec.get("negative_prompts") or [])
    brand_constraints = str(brand_kit.get("brand_visual_constraints") or "").strip()

    context: dict = {
        "brand_name":            str(brand_kit.get("brand_name") or brand_kit.get("name") or ""),
        "headline":              copy.get("headline", ""),
        "subheadline":           copy.get("subheadline", ""),
        "body_copy":             copy.get("body", ""),
        "cta_text":              copy.get("cta", ""),
        "location":              copy.get("location", ""),
        "color_palette.primary":    str(colors.get("primary") or colors.get("color_primary") or colors.get("accent") or ""),
        "color_palette.background": str(colors.get("background") or colors.get("color_background") or colors.get("dark") or ""),
        "color_palette.text":       str(colors.get("text") or colors.get("color_text") or colors.get("light") or ""),
        "visual_tone":           visual_tone if isinstance(visual_tone, list) else [str(visual_tone)],
        "negative_prompts":      negative_prompts,
        "post_format":           post_format,
        "size":                  _SIZE_MAP.get(post_format, "1024x1024"),
    }

    gen = template_spec.get("generation_prompt") or {} if template_spec else {}
    base_prompt  = str(gen.get("prompt") or "")
    important    = str(gen.get("important_instruction") or "")
    spec_negatives: list = gen.get("negative_prompt") or []

    if not base_prompt:
        tone_str = ", ".join(str(t) for t in visual_tone) if isinstance(visual_tone, list) else str(visual_tone)
        base_prompt = (
            f"Create an original, channel-appropriate {context['size']} social media composition for "
            f"{context['brand_name'] or 'this brand'}. Use agency-level creative judgment rather than a fixed layout. "
            f"Visual language: {tone_str or 'derive from the supplied identity, campaign, and reference assets'}. "
            "Preserve the supplied official logo exactly and maintain clear, legible space for approved copy."
        )

    parts: list[str] = []

    if edit_instruction:
        parts.append(
            f"REVISION: {edit_instruction}\n"
            "Apply this change only. Preserve all other brand elements, layout, colors, "
            "typography, and assets exactly as they appear in the source image."
        )
    if revision_spec:
        parts.append(
            "You are editing an existing approved social ad. The current approved design is the visual continuity anchor. "
            "Apply the JSON revision spec exactly. Do not redesign the ad, do not change copy unless the JSON says to, "
            "and use reference assets only for their stated roles."
        )

    if brand_kit_template:
        template_lines = [
            f"Approved Brand Kit template: {brand_kit_template.get('name') or brand_kit_template.get('id')}",
            f"Template content type: {brand_kit_template.get('content_type') or 'unspecified'}",
            f"Required slots: {', '.join(str(s) for s in brand_kit_template.get('required_slots') or []) or 'none'}",
            f"Optional slots: {', '.join(str(s) for s in brand_kit_template.get('optional_slots') or []) or 'none'}",
            f"Forbidden slots: {', '.join(str(s) for s in brand_kit_template.get('forbidden_slots') or []) or 'none'}",
        ]
        if brand_kit_template.get("aesthetic_notes"):
            template_lines.append("Aesthetic notes: " + str(brand_kit_template.get("aesthetic_notes")))
        if brand_kit_template.get("negative_rules"):
            template_lines.append("Template negative rules: " + ", ".join(str(r) for r in brand_kit_template.get("negative_rules") or []))
        parts.append("APPROVED BRAND KIT TEMPLATE CONTRACT:\n" + "\n".join(template_lines))

    if labeled_assets:
        sides = ["LEFT", "RIGHT", "CENTER", "BOTTOM"]
        panel_lines = [
            f"REFERENCE {sides[i] if i < len(sides) else f'PANEL {i+1}'}: "
            f"{a.get('panel_label', a.get('subject', 'brand asset'))}"
            for i, a in enumerate(labeled_assets)
        ]
        parts.append(
            "REFERENCE ASSETS PROVIDED. Use each asset only for its labeled role; "
            "if they are presented as a contact sheet, do not copy the sheet layout into the final design:\n" + "\n".join(panel_lines)
        )

    parts.append(_resolve_placeholders(base_prompt, context))

    if important:
        parts.append(_resolve_placeholders(important, context))

    copy_lines = []
    for field, label in [
        ("headline", "Headline"), ("subheadline", "Subheadline"),
        ("body", "Body copy"),    ("cta", "CTA"),
        ("location", "Location"),
    ]:
        if copy.get(field):
            copy_lines.append(f"{label}: {copy[field]}")
    if copy_lines:
        parts.append("Copy to include:\n" + "\n".join(copy_lines))

    if campaign:
        parts.append(
            "Campaign alignment: "
            + "; ".join(str(v) for v in [
                campaign.get("name"), campaign.get("goal"), campaign.get("audience"), campaign.get("message_angle")
            ] if v)
        )
    if brand_constraints:
        parts.append("Approved brand visual constraints: " + brand_constraints)

    all_negatives = list(spec_negatives) + negative_prompts
    if all_negatives:
        resolved = [_resolve_placeholders(str(n), context) for n in all_negatives]
        parts.append("Negative prompt: " + ", ".join(r for r in resolved if r))

    if revision_spec:
        parts.append("JSON_REVISION_SPEC:\n" + json.dumps(revision_spec, indent=2, ensure_ascii=False))
    if source_render_spec:
        parts.append("SOURCE_RENDER_SPEC:\n" + json.dumps(source_render_spec, indent=2, ensure_ascii=False))

    return "\n\n".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# Step 6: Drive upload
# ---------------------------------------------------------------------------

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
            "drive_file_id":       meta.get("id"),
            "drive_file_name":     meta.get("name"),
            "drive_file_mime":     meta.get("mimeType") or "image/png",
            "drive_web_view_link": meta.get("webViewLink"),
            "drive_folder":        "Postcraft",
            "reusable":            True,
        }
    except Exception as exc:
        return {"drive_upload_status": "failed", "drive_upload_error": str(exc)[:400]}


# ---------------------------------------------------------------------------
# Step 7: Thumbnail
# ---------------------------------------------------------------------------

def _sniff_mime(b: bytes) -> str:
    if b[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    return "image/jpeg"


def _make_thumbnail(image_bytes: bytes, max_px: int = 480) -> tuple[str, str]:
    from PIL import Image as _PIL
    img = _PIL.open(io.BytesIO(image_bytes)).convert("RGB")
    img.thumbnail((max_px, max_px), _PIL.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=75, optimize=True)
    result = buf.getvalue()
    return base64.b64encode(result).decode(), _sniff_mime(result)


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------

def _write_audit(data: dict, label: str) -> None:
    try:
        _AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        path = _AUDIT_DIR / f"{label}_{int(time.time())}.json"
        path.write_text(json.dumps(data, indent=2, default=str))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------

def _run_pipeline(brief: dict) -> dict:
    """Execute all 7 steps. Each step degrades independently on failure."""
    provider, model, api_key = _get_image_creds(brief)
    openai_base_url = _openai_base_url_from_brief(brief)
    openai_auth_mode = _provider_auth_mode_from_brief(brief)
    openai_client = _load_lib("openai_client")
    composite_lib = _load_lib("composite")

    # edit_instruction: CMO-authored revision_prompt takes priority; fall back to legacy names
    edit_instruction = str(
        brief.get("revision_prompt")
        or brief.get("edit_instruction")
        or brief.get("revision_instruction")
        or brief.get("revision_feedback")
        or brief.get("feedback")
        or ""
    ).strip()

    # original_block: explicit nested key OR treat brief itself as prior state
    # (BOS action revise copies block fields directly into the brief top-level)
    original_block = _restore_from_prior(brief)
    is_revision = bool(edit_instruction or original_block or brief.get("source_run_id"))

    brand_kit:    dict = brief.get("brand_kit") or {}
    copy               = _extract_copy(brief)
    template_type      = str(brief.get("template_type") or "")
    post_format        = str(brief.get("post_format") or "")

    if is_revision:
        # For action revise, prior context is in the brief top-level.
        # For explicit original_block, fall back to that.
        prior = original_block or brief
        if not brand_kit:
            brand_kit = prior.get("brand_kit") or {}
        if not template_type:
            template_type = str(prior.get("template_type") or "promo")
        if not post_format:
            post_format = str(prior.get("post_format") or "square")
        prev_copy = prior.get("copy") or {}
        for field in ("headline", "subheadline", "body", "cta", "location"):
            if not copy.get(field):
                copy[field] = str(prev_copy.get(field) or "")

    template_type = template_type or "promo"
    post_format   = post_format or "square"
    size          = _SIZE_MAP.get(post_format, "1024x1024")
    image_quality = str(brief.get("image_quality") or brief.get("quality") or "high").strip().lower()
    if image_quality not in {"low", "medium", "high", "auto"}:
        image_quality = "high"

    # Step 1: Brand asset resolution
    brand_spec = _resolve_brand_spec(brief)
    if is_revision and not brand_spec:
        prior = original_block or brief
        brand_spec = prior.get("brand_spec") or {}
    reference_images = _sort_reference_images_for_revision(_inject_logo(brief, brand_spec), is_revision)

    selected_reference_images, pipeline_notes = _select_reference_images(reference_images, is_revision)

    reference_assets = _reference_asset_records(selected_reference_images, edit_instruction)
    render_spec = _build_render_spec(brief, brand_kit, brand_spec, copy, template_type, post_format, size, reference_assets)
    prior_for_spec = original_block or brief
    source_render_spec = _source_render_spec_from_prior(prior_for_spec, render_spec) if is_revision else None
    revision_spec = _build_revision_spec(brief, source_render_spec or render_spec, reference_assets, edit_instruction) if is_revision else None

    # Step 2: Vision intake (always gpt-4o-mini)
    intake_key = api_key if provider == "openai" else (
        os.environ.get("PLATFORM_OPENAI_KEY") or os.environ.get("OPENAI_API_KEY") or api_key
    )
    labeled_assets:   list[dict]                   = []
    asset_bytes_list: list[tuple[bytes, str, str]]  = []

    for idx, ref in enumerate(selected_reference_images, start=1):
        vision_b64 = str(ref.get("vision_b64") or "")
        if not vision_b64:
            continue
        mime  = str(ref.get("mime_type") or "image/jpeg")
        title = str(ref.get("title") or ref.get("filename") or "brand asset")
        is_operator_ref = _is_operator_revision_ref(ref)
        inferred_role = _infer_revision_ref_role(ref, edit_instruction) if is_operator_ref else str(ref.get("placement_role") or "brand_reference")
        if ref.get("_auto_injected") and ref.get("panel_label"):
            intake: dict = {
                "asset_type":     "logo" if ref.get("placement_role") == "logo" else "brand_asset",
                "subject":        title,
                "panel_label":    str(ref["panel_label"]),
                "placement_role": str(ref.get("placement_role") or "brand_asset"),
            }
        else:
            try:
                intake = openai_client.vision_intake(vision_b64, mime, title, intake_key, base_url=openai_base_url)
            except Exception:
                intake = {
                    "asset_type":     "unknown",
                    "subject":        title,
                    "panel_label":    f"{title.upper()} — use as brand asset",
                    "placement_role": "unknown",
                }
        if is_operator_ref:
            intake["panel_label"] = str(ref.get("panel_label") or f"OPERATOR REVISION REF {idx} — {inferred_role}: {title}")
            intake["placement_role"] = inferred_role
            intake["asset_type"] = inferred_role
        intake["reference_asset_id"] = str(ref.get("id") or ref.get("drive_file_id") or f"ref_{idx}")
        intake["revision_reference"] = is_operator_ref
        intake["source"] = ref.get("source") or ("operator_attachment" if is_operator_ref else "brand_asset")
        intake["role"] = inferred_role
        labeled_assets.append(intake)
        asset_bytes_list.append((base64.b64decode(vision_b64), intake.get("panel_label", title.upper()), mime))

    if is_revision and not labeled_assets:
        labeled_assets = list(original_block.get("vision_intake") or [])

    # Step 3: Prompt construction
    optional_brand_template = brief.get("brand_kit_template") if isinstance(brief.get("brand_kit_template"), dict) else None
    template_spec = _load_template_spec(template_type) if optional_brand_template else {}
    prompt = _build_prompt(
        template_spec, brand_kit, brand_spec, copy, post_format, labeled_assets,
        _campaign_alignment(brief), edit_instruction,
        revision_spec=revision_spec,
        source_render_spec=source_render_spec,
        brand_kit_template=optional_brand_template,
    )

    # Step 4: Composite reference sheet (OpenAI only, Pillow optional)
    composite_bytes: bytes | None = None
    if provider == "openai":
        try:
            if len(asset_bytes_list) == 1:
                from PIL import Image as _PIL
                buf = io.BytesIO()
                _PIL.open(io.BytesIO(asset_bytes_list[0][0])).convert("RGBA").save(buf, format="PNG")
                composite_bytes = buf.getvalue()
            elif len(asset_bytes_list) > 1:
                composite_bytes = composite_lib.build_composite(asset_bytes_list)
        except ImportError:
            pipeline_notes.append("Pillow unavailable — text-only generation")
        except Exception as exc:
            pipeline_notes.append(f"composite failed ({exc}) — text-only generation")

    # On revision, use the prior rendered image as the edit source.
    # BOS copies image_data_b64 from the approved block into the action brief.
    prior_image_bytes: bytes | None = None
    if is_revision and provider == "openai":
        _prior_b64 = str(brief.get("source_image_data_b64") or brief.get("image_data_b64") or "").strip()
        if _prior_b64:
            try:
                from PIL import Image as _PIL
                _raw = base64.b64decode(_prior_b64)
                _buf = io.BytesIO()
                _PIL.open(io.BytesIO(_raw)).convert("RGBA").save(_buf, format="PNG")
                prior_image_bytes = _buf.getvalue()
            except Exception as exc:
                pipeline_notes.append(f"prior image decode failed ({exc}) — using reference sheet")

    if is_revision and prior_image_bytes:
        prompt += (
            "\n\nREVISION SOURCE PANEL: CURRENT APPROVED DESIGN — use it as the visual continuity anchor. "
            "Preserve identity, geometry, layout, colors, typography, and unchanged elements outside the requested change."
        )
    if provider == "openai" and prior_image_bytes and asset_bytes_list:
        # One source image limit: compose current design + logo/references into
        # a single labeled sheet so revisions can see both prior render and new assets.
        composite_bytes = composite_lib.build_composite(
            [(prior_image_bytes, "CURRENT APPROVED DESIGN — preserve layout and unchanged elements", "image/png")]
            + asset_bytes_list
        )
    elif provider == "openai" and prior_image_bytes:
        composite_bytes = prior_image_bytes

    # Step 5: Image generation
    if provider == "gemini":
        gemini_client = _load_lib("gemini_client")
        ref_parts = [
            {"b64": base64.b64encode(b).decode(), "mime_type": m, "label": lbl}
            for b, lbl, m in asset_bytes_list
        ]
        image_bytes = gemini_client.generate_image(api_key, prompt, model, size, ref_parts)

    elif provider == "bytedance":
        bytedance_client = _load_lib("bytedance_client")
        image_bytes = bytedance_client.generate_image(api_key, prompt, model, size)

    else:
        def _gen(key: str) -> bytes:
            edit_source = composite_bytes or prior_image_bytes
            if openai_auth_mode == "oauth":
                refs: list[tuple[bytes, str, str]] = []
                if edit_source:
                    refs.append((edit_source, "CURRENT APPROVED DESIGN / REFERENCE SHEET", "image/png"))
                return openai_client.generate_image_codex(
                    prompt,
                    key,
                    model=model,
                    size=size,
                    quality=image_quality,
                    images=refs,
                    action="edit" if refs else "generate",
                )
            if edit_source:
                try:
                    return openai_client.generate_image(edit_source, prompt, key, model, size, quality=image_quality, base_url=openai_base_url)
                except RuntimeError:
                    pipeline_notes.append("images.edit failed — fell back to images.generate")
                    return openai_client.generate_image_text_only(prompt, key, model, size, quality=image_quality, base_url=openai_base_url)
            return openai_client.generate_image_text_only(prompt, key, model, size, quality=image_quality, base_url=openai_base_url)

        image_bytes = _gen(api_key)

    # Step 6: Drive upload — hard gate before Stream artifact
    ts = int(time.time())
    filename = f"postcraft_{template_type}_{ts}.png"
    drive_meta = _store_in_drive(brief, image_bytes, filename)
    if not drive_meta.get("drive_file_id"):
        detail = drive_meta.get("drive_upload_error") or drive_meta.get("drive_upload_status") or "Google Drive upload did not return drive_file_id"
        raise ValueError(f"Postcraft storage preflight failed: generated image could not be saved to the Brand's Google Drive ({detail}).")

    # Step 7: Thumbnail (non-blocking)
    image_data_b64 = base64.b64encode(image_bytes).decode()
    thumb_b64 = ""
    thumb_mime = "image/jpeg"
    try:
        thumb_b64, thumb_mime = _make_thumbnail(image_bytes)
    except ImportError:
        pipeline_notes.append("Pillow unavailable — thumbnail omitted")
    except Exception as exc:
        pipeline_notes.append(f"thumbnail failed ({exc}) — thumbnail omitted")

    # Audit file: analyze_output — write to disk, never block artifact
    brand_name = str(brand_kit.get("brand_name") or brand_kit.get("name") or "brand")
    try:
        breakdown = openai_client.analyze_output(
            image_bytes, f"{brand_name}|{template_type}|{copy.get('headline', '')}", intake_key, base_url=openai_base_url
        )
        _write_audit(
            {"brief": f"{brand_name}|{template_type}", "breakdown": breakdown},
            f"breakdown_{template_type}",
        )
    except Exception:
        pass

    return {
        "filename":       filename,
        "byte_size":      len(image_bytes),
        "image_data_b64": image_data_b64,
        "image_mime":     _sniff_mime(image_bytes),
        "thumb_b64":      thumb_b64,
        "thumb_mime":     thumb_mime,
        "template_type":  template_type,
        "base_family":    brief.get("base_family") or template_type,
        "template_id":    brief.get("template_id") or brief.get("selected_template_id"),
        "selected_template_id": brief.get("selected_template_id") or brief.get("template_id"),
        "selection_confidence": brief.get("selection_confidence"),
        "selection_reason": brief.get("selection_reason") or [],
        "brand_kit_template": brief.get("brand_kit_template") or {},
        "post_format":    post_format,
        "size":           size,
        "brand_name":     brand_name,
        "brand_kit":      brand_kit,
        "brand_spec":     brand_spec,
        "provider":       provider,
        "model":          model,
        "copy":           copy,
        "prompt":         prompt,
        "image_quality":  image_quality,
        "labeled_assets": labeled_assets,
        "reference_assets": reference_assets,
        "postcraft_render_spec": render_spec,
        "source_render_spec": source_render_spec,
        "postcraft_revision_spec": revision_spec,
        "revision_feedback": edit_instruction,
        "drive_meta":     drive_meta,
        "pipeline_notes": pipeline_notes,
    }


# ---------------------------------------------------------------------------
# Draft fallback (mirrors postcraft.draft output)
# ---------------------------------------------------------------------------

def _draft_fallback_block(brief: dict) -> dict:
    brand_kit:        dict       = brief.get("brand_kit") or {}
    brand_spec:       dict       = _resolve_brand_spec(brief)
    reference_images: list[dict] = brief.get("reference_images") or []
    copy               = _extract_copy(brief)
    template_type      = str(brief.get("template_type") or "promo")
    post_format        = str(brief.get("post_format") or "square")

    colors     = brand_spec.get("color_palette") or brand_kit.get("color_palette") or brand_kit.get("colors") or {}
    primary    = str(colors.get("primary") or colors.get("color_primary") or "")
    background = str(colors.get("background") or colors.get("color_background") or "")
    text_c     = str(colors.get("text") or colors.get("color_text") or "")
    negatives  = list(brand_spec.get("negative_prompts") or ["cartoon", "neon", "cheap flyer"])
    logo_id    = str(brand_spec.get("logo_drive_file_id") or "").strip()
    brand_name = str(brand_kit.get("brand_name") or brand_kit.get("name") or "(no brand name)")
    size_str   = _SIZE_DISPLAY.get(post_format, "1024×1024")
    tdesc      = _TEMPLATE_DESCRIPTIONS.get(template_type, _TEMPLATE_DESCRIPTIONS["promo"])

    lines: list[str] = [
        f"Template:     {template_type} — {tdesc}",
        f"Format:       {post_format} ({size_str})",
        f"Brand:        {brand_name}",
    ]
    color_parts = []
    if primary:    color_parts.append(f"primary {primary}")
    if background: color_parts.append(f"background {background}")
    if text_c:     color_parts.append(f"text {text_c}")
    if color_parts:
        lines.append(f"Colors:       {' · '.join(color_parts)}")
    lines.append(
        f"Logo:         [Drive file {logo_id[:16]}…] — BRAND LOGO, auto-injected top center"
        if logo_id else
        "Logo:         (none — add logo_drive_file_id to brand spec)"
    )
    for ref in reference_images:
        lines.append(f"Hero asset:   {ref.get('title') or ref.get('filename') or 'attached asset'} (operator attached)")
    if copy["headline"]:
        lines.append(f"Headline:     {copy['headline']}")
    if copy["subheadline"]:
        lines.append(f"Subheadline:  {copy['subheadline']}")
    if copy["body"]:
        preview = copy["body"][:120] + ("..." if len(copy["body"]) > 120 else "")
        lines.append(f"Body:         {preview}")
    if copy["cta"]:
        lines.append(f"CTA:          {copy['cta']}")
    if copy["location"]:
        lines.append(f"Location:     {copy['location']}")
    lines.append(f"Negative:     {', '.join(negatives)}")

    draft_text = "\n".join(lines)
    return {
        "draft_text":   draft_text,
        "brand_name":   brand_name,
        "brand_kit":    brand_kit,
        "brand_spec":   brand_spec,
        "copy":         copy,
        "template_type": template_type,
        "post_format":  post_format,
        "reference_image_count":  len(reference_images),
        "reference_image_titles": [str(r.get("title") or r.get("filename") or "") for r in reference_images],
    }


# ---------------------------------------------------------------------------
# Module
# ---------------------------------------------------------------------------

class PostcraftRenderModule(ChannelModule):
    """Render a branded social post image — gated behind CMO-level text approval."""

    id = "postcraft.render"
    name = "Postcraft Render"
    vertical = "creative"
    capability = "postcraft.render"
    platform_hint = "postcraft"
    policy_default = "generate_with_gates"

    actions = {
        "render": {
            "description": (
                "Render a high-quality branded social post image ONLY after the CMO has written the full social image creative in chat and the operator has explicitly approved it. "
                "Never call this on the initial request. Pass render_approved=true, approved_draft=true, image_quality=high, and the approved copy/creative text."
            ),
            "parameters": {
                "render_approved": {"type": "boolean", "description": "Must be true after explicit operator approval."},
                "approved_draft": {"type": "boolean", "description": "Must be true after explicit operator approval."},
                "image_quality": {"type": "string", "enum": ["high", "medium", "low", "auto"], "description": "OpenAI image quality. Use high for Postcraft."},
                "postcraft_text": {"type": "string", "description": "Full approved CMO social image creative text."},
                "headline": {"type": "string", "description": "Approved headline."},
                "subheadline": {"type": "string", "description": "Approved subheadline."},
                "body_copy": {"type": "string", "description": "Approved body/caption copy."},
                "cta_text": {"type": "string", "description": "Approved CTA text."},
                "template_id": {"type": "string", "description": "Optional approved Brand Kit template id. Pass only when the operator explicitly requests a registered Brand Kit template; ordinary renders must omit it."},
                "auto_select_template": {"type": "boolean", "description": "Optional template selection. Set true only when the operator explicitly requests automatic selection of an approved Brand Kit template; omit for ordinary original-composition renders."},
                "selection_context": {"type": "object", "description": "Template routing context: renderer, format, content_type, objective, tone, copy_density, assets_available, copy."},
                "creative_direction": {"type": "string", "description": "Prompt/concept label only; never treated as template identity."},
                "post_format": {"type": "string", "enum": ["square", "portrait_feed", "story_reel", "landscape"], "description": "Output format."},
                "location": {"type": "string", "description": "Optional location text."},
            },
            "required": ["render_approved", "postcraft_text"],
            "produces": "image_asset",
        },
        "revise": {
            "description": "Revise an existing Postcraft image artifact using the previous image as visual anchor.",
            "parameters": {
                "source_run_id": {"type": "string", "description": "Run ID of the current post image artifact."},
                "revision_prompt": {"type": "string", "description": "Precise instruction describing what to change and preserve."},
                "postcraft_text": {"type": "string", "description": "Updated approved creative text if copy changed."},
                "image_quality": {"type": "string", "enum": ["high", "medium", "low", "auto"], "description": "OpenAI image quality. Use high for Postcraft."},
            },
            "required": ["source_run_id", "revision_prompt"],
            "produces": "image_asset",
            "consumes": "image_asset",
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

        template_blocker = _postcraft_template_blocker(brief)
        if template_blocker:
            return self._attempt(start, "failed", "none", template_blocker.get("reason_code") or "postcraft_template_blocked"), {
                "content": str(template_blocker.get("message") or "Postcraft Brand Kit template selection blocked."),
                "block": {
                    "type": "setup_blocker",
                    "status": "blocked",
                    "reason_code": template_blocker.get("reason_code") or "postcraft_template_blocked",
                    "message": template_blocker.get("message") or "Postcraft Brand Kit template selection blocked.",
                    "details": template_blocker.get("details") or {},
                    "suggested_resolution": template_blocker.get("suggested_resolution"),
                    "allowed_actions": ["dismiss"],
                },
            }

        missing = _postcraft_preflight(brief)
        if missing:
            block = _preflight_block(missing, brief)
            return self._attempt(start, "failed", "none", "postcraft_preflight_failed"), {
                "content": block["message"],
                "block": block,
            }

        # Gate — CMO chat approval happens in text before this module is called.
        # Do not fall back to a Postcraft draft artifact; that workflow is retired.
        if not _is_render_approved(brief):
            return self._attempt(start, "failed", "none", "approval_required"), {
                "content": "Postcraft render blocked: write the social image creative in CMO chat and get explicit operator approval before image generation.",
                "block": {
                    "type": "image_asset",
                    "status": "failed",
                    "reason_code": "approval_required",
                    "message": "Postcraft render requires explicit CMO-level text approval before image generation.",
                    "allowed_actions": ["dismiss"],
                },
            }

        # Credential check before pipeline
        try:
            _get_image_creds(brief)
        except ValueError as exc:
            return self._attempt(start, "failed", error=str(exc)), {
                "content": f"Postcraft setup error: {exc}",
                "block": {
                    "type": "image_asset",
                    "status": "failed",
                    "reason_code": "credentials",
                    "message": str(exc),
                    "allowed_actions": ["dismiss"],
                },
            }

        # Full pipeline
        try:
            result = _run_pipeline(brief)
        except Exception as exc:
            return self._attempt(start, "failed", error=type(exc).__name__), {
                "content": f"Postcraft render failed: {exc}",
                "block": {
                    "type": "image_asset",
                    "status": "failed",
                    "reason_code": type(exc).__name__,
                    "message": str(exc),
                    "allowed_actions": ["retry", "dismiss"],
                },
            }

        copy        = result["copy"]
        drive_meta  = result["drive_meta"]
        labeled     = result["labeled_assets"]
        size        = result["size"]

        drive_suffix = (
            f" — saved to Drive: {drive_meta.get('drive_web_view_link', '')}"
            if drive_meta.get("drive_file_id") else ""
        )
        notes_suffix = (
            f" [{'; '.join(result['pipeline_notes'])}]"
            if result.get("pipeline_notes") else ""
        )

        block: dict = {
            "type":          "image_asset",
            "legacy_type":   "post_image",
            "status":        "succeeded",
            "title":         f"Post: {copy.get('headline') or result['template_type']}",
            "display_title": f"Post: {copy.get('headline') or result['template_type']}",
            # `image_data_b64` is the full generated image; do not label it
            # with the thumbnail MIME type (the browser may refuse to decode a
            # PNG advertised as JPEG, especially on revision artifacts).
            "mime_type":     result.get("image_mime") or result["thumb_mime"],
            "byte_size":     result["byte_size"],
            "width":         int(size.split("x")[0]),
            "height":        int(size.split("x")[1]),
            "filename":      result["filename"],
            "template_type": result["template_type"],
            "base_family":   result.get("base_family"),
            "template_id":   result.get("template_id"),
            "selected_template_id": result.get("selected_template_id"),
            "selection_confidence": result.get("selection_confidence"),
            "selection_reason": result.get("selection_reason", []),
            "brand_kit_template": result.get("brand_kit_template", {}),
            "post_format":   result["post_format"],
            "brand_name":    result["brand_name"],
            "brand_kit":     result["brand_kit"],
            "brand_spec":    result["brand_spec"],
            "campaign_alignment": _campaign_alignment(brief),
            "prompt":        result["prompt"],
            "headline":      copy.get("headline", ""),
            "subheadline":   copy.get("subheadline", ""),
            "body_copy":     copy.get("body", ""),
            "cta_text":      copy.get("cta", ""),
            "copy":          copy,
            "assets_used":   [a.get("asset_type", "unknown") for a in labeled],
            "asset_labels":  [a.get("panel_label", "") for a in labeled],
            "vision_intake": labeled,
            "reference_assets": result.get("reference_assets", []),
            "postcraft_render_spec": result.get("postcraft_render_spec"),
            "source_render_spec": result.get("source_render_spec"),
            "postcraft_revision_spec": result.get("postcraft_revision_spec"),
            "revision_feedback": result.get("revision_feedback", ""),
            "pipeline_notes": result.get("pipeline_notes", []),
            "provider":      result["provider"],
            "model":         result["model"],
            "image_quality": result.get("image_quality", "high"),
            "source_run_id": brief.get("source_run_id"),
            "workflow": {
                "id": "postcraft_pipeline",
                "stage": "postcraft_image_review",
                "continuation_policy": "artifact_bound_else_fresh",
                "fresh_start_module": "postcraft.render",
            },
            "approval_status": "pending",
            "allowed_actions": ["approve", "revise", "dismiss", "publish_facebook", "schedule_facebook", "publish_instagram", "publish_linkedin", "publish_twitter"],
            "action_modules": {
                "revise": "postcraft.render",
                # Approval-gated Facebook publishing/scheduling is owned by the
                # Meta plugin. Do not use pseudo IDs like meta.pages.post; the
                # generic action executor resolves only installed module IDs.
                "publish_facebook": "marketing.channel.meta.posts.publish",
                "schedule_facebook": "marketing.channel.meta.posts.publish",
                "publish_instagram": "meta.pages.post",
                "publish_linkedin": "linkedin.pages.post",
                "publish_twitter": "twitter.post",
            },
            **drive_meta,
        }

        if result.get("image_data_b64"):
            block["image_data_b64"] = result["image_data_b64"]
            if result["thumb_b64"]:
                block["thumb_data_b64"] = result["thumb_b64"]
        elif result["thumb_b64"]:
            block["image_data_b64"] = result["thumb_b64"]
        else:
            block["asset_omitted"] = True

        return self._attempt(start, "succeeded", result["provider"]), {
            "content": f"Post image ready: {result['filename']} ({result['byte_size']:,} bytes){drive_suffix}{notes_suffix}",
            "block": block,
        }

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        if not isinstance(content, str):
            return "fail", ["content_not_string"]
        if content.lower().startswith(("postcraft render failed", "postcraft setup error", "postcraft blocked", "postcraft render blocked")):
            return "fail", ["render_failed"]
        return "pass", []
