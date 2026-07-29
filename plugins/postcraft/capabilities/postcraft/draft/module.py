"""Postcraft Draft — zero-cost structured preview before any image generation.

No provider calls. No Pillow. No composite. Just structured text from the brief.
Operator sees template, assets, copy, and colors before approving the render.
"""
from __future__ import annotations

import time

from klaroha_sdk import ChannelModule


_SIZE_DISPLAY = {
    "portrait_feed": "1024×1536",
    "story_reel":    "1024×1536",
    "square":        "1024×1024",
    "landscape":     "1536×1024",
}

_TEMPLATE_DESCRIPTIONS = {
    "promo":       "high-impact sales flyer — large dominant headline, strong CTA band, hero image panel, brand accent ribbons",
    "price_card":  "premium product layout — formal serif headline, price/offer section, CTA ribbon, generous whitespace",
    "photo_hero":  "cinematic brand image — full background photo, logo top, elegant text overlay, CTA button",
    "agent_award": "formal recognition post — logo top, agent portrait right, award text left, branded footer",
    "educational": "clean editorial card — logo top, icon badge, formal headline, short body copy, CTA",
}


def _resolve_brand_spec(brief: dict) -> dict:
    """Read postcraft_brand_spec from brand_kit.brand_spec, brand_json, or workspace docs."""
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


def _first_campaign_pain(alignment: dict) -> str:
    audience = str(alignment.get("audience") or "")
    marker = "pains:"
    if marker in audience.lower():
        tail = audience.lower().split(marker, 1)[1]
        first = tail.split(",", 1)[0].split(";", 1)[0].strip()
        return first[:80]
    return ""


def _title_case_phrase(raw: str) -> str:
    small = {"a", "an", "and", "as", "at", "for", "from", "in", "of", "on", "or", "the", "to", "with"}
    words = str(raw or "").replace("_", " ").split()
    out = []
    for i, word in enumerate(words):
        lw = word.lower()
        out.append(lw if i and lw in small else lw[:1].upper() + lw[1:])
    return " ".join(out)


def _campaign_default_copy(brief: dict) -> dict:
    brand_kit = brief.get("brand_kit") if isinstance(brief.get("brand_kit"), dict) else {}
    brand_name = str(brand_kit.get("brand_name") or brand_kit.get("name") or brief.get("brand_name") or "").strip()
    alignment = _campaign_alignment(brief)
    pain = _first_campaign_pain(alignment)
    goal = str(alignment.get("goal") or alignment.get("message_angle") or alignment.get("name") or brief.get("objective") or brief.get("request") or "").strip()
    offer = str(alignment.get("offer") or "").split(";", 1)[0].strip()
    headline = ""
    if pain:
        headline = "Stop " + _title_case_phrase(pain)
    elif goal:
        headline = _title_case_phrase(goal)
    body_bits = []
    if brand_name:
        body_bits.append(brand_name)
    if offer:
        body_bits.append(f"helps turn demand into clearer next steps with {offer}")
    elif goal:
        body_bits.append(f"helps teams act on {goal.lower()}")
    body = " ".join(body_bits).strip()
    if body and not body.endswith("."):
        body += "."
    return {"headline": headline, "body": body, "cta": "Learn More"}


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


def _extract_copy(brief: dict) -> dict:
    defaults = _campaign_default_copy(brief)
    nested_copy = brief.get("copy") if isinstance(brief.get("copy"), dict) else {}
    revised_copy = brief.get("revised_copy") if isinstance(brief.get("revised_copy"), dict) else {}
    prior = _restore_from_prior(brief)
    prior_copy = prior.get("copy") if isinstance(prior.get("copy"), dict) else {}
    is_revision = bool(
        brief.get("revision_context")
        or brief.get("revision_feedback")
        or brief.get("feedback")
        or brief.get("edit_instruction")
        or brief.get("source_run_id")
        or prior
    )

    def pick(field: str, *brief_keys: str) -> str:
        for key in brief_keys:
            val = brief.get(key)
            if val:
                return str(val)
        for source in (revised_copy, nested_copy):
            val = source.get(field)
            if val:
                return str(val)
        if is_revision:
            val = prior_copy.get(field)
            if val:
                return str(val)
        return str(defaults.get(field) or "")

    return {
        "headline":    pick("headline", "headline", "caption"),
        "subheadline": pick("subheadline", "subheadline"),
        "body":        pick("body", "body_copy", "body"),
        "cta":         pick("cta", "cta_text", "cta"),
        "location":    pick("location", "location"),
    }


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
        "message": "Postcraft blocked before draft/render: missing " + ", ".join(missing),
        "preflight_checklist": items,
        "setup_links": items,
        "allowed_actions": ["dismiss"],
    }



def build_draft_text(
    brand_kit: dict,
    brand_spec: dict,
    copy: dict,
    template_type: str,
    post_format: str,
    reference_images: list[dict],
) -> str:
    brand_name = str(brand_kit.get("brand_name") or brand_kit.get("name") or "(no brand name)")
    colors = brand_spec.get("color_palette") or brand_kit.get("color_palette") or brand_kit.get("colors") or {}
    primary    = str(colors.get("primary") or colors.get("color_primary") or colors.get("accent") or "")
    background = str(colors.get("background") or colors.get("color_background") or colors.get("dark") or "")
    text_c     = str(colors.get("text") or colors.get("color_text") or colors.get("light") or "")
    negatives  = list(brand_spec.get("negative_prompts") or ["cartoon", "neon", "cheap flyer", "distorted text"])
    logo_file_id = str(brand_spec.get("logo_drive_file_id") or "").strip()
    size_str   = _SIZE_DISPLAY.get(post_format, "1024×1024")
    template_desc = _TEMPLATE_DESCRIPTIONS.get(template_type, _TEMPLATE_DESCRIPTIONS["promo"])

    lines: list[str] = [
        f"Template:     {template_type} — {template_desc}",
        f"Format:       {post_format} ({size_str})",
        f"Brand:        {brand_name}",
    ]
    color_parts = []
    if primary:    color_parts.append(f"primary {primary}")
    if background: color_parts.append(f"background {background}")
    if text_c:     color_parts.append(f"text {text_c}")
    if color_parts:
        lines.append(f"Colors:       {' · '.join(color_parts)}")

    if logo_file_id:
        lines.append(f"Logo:         [Drive file {logo_file_id[:16]}…] — BRAND LOGO, auto-injected top center")
    else:
        lines.append("Logo:         (none — add logo_drive_file_id to brand spec to enable auto-injection)")

    for ref in reference_images:
        title = str(ref.get("title") or ref.get("filename") or "attached asset")
        lines.append(f"Hero asset:   {title} (operator attached)")
    for ref in (brand_spec.get("brand_visual_assets") or [])[:6]:
        if isinstance(ref, dict):
            title = str(ref.get("title") or ref.get("filename") or ref.get("drive_file_id") or "brand visual asset")
            lines.append(f"Brand visual: {title} (validated Drive reference)")

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
    return "\n".join(lines)


class PostcraftDraftModule(ChannelModule):
    """Produce a reviewable draft of a branded social post — zero provider cost."""

    id = "postcraft.draft"
    name = "Postcraft Draft"
    vertical = "creative"
    capability = "postcraft.draft"
    platform_hint = "postcraft"
    policy_default = "draft_only"

    actions = {
        "draft": {
            "description": (
                "Create the zero-cost review draft for a new branded social media post. "
                "Use this as Postcraft stage 1 before image rendering unless the operator is explicitly revising an existing image."
            ),
            "parameters": {
                "headline": {"type": "string", "description": "Primary headline text for the post."},
                "subheadline": {"type": "string", "description": "Secondary headline (optional)."},
                "body_copy": {"type": "string", "description": "Body text for the post (optional)."},
                "cta_text": {"type": "string", "description": "Call-to-action text, e.g. 'Learn More' (optional)."},
                "template_type": {
                    "type": "string",
                    "description": "Post layout style. Defaults to 'promo'.",
                    "enum": ["promo", "price_card", "photo_hero", "agent_award", "educational"],
                },
                "post_format": {
                    "type": "string",
                    "description": "Output dimensions. Defaults to 'square'.",
                    "enum": ["square", "portrait_feed", "story_reel", "landscape"],
                },
                "location": {"type": "string", "description": "Location or address to include in the post (optional)."},
            },
            "required": [],
        },
    }

    def _attempt(self, start: float, status: str, error=None) -> dict:
        return {
            "provider": "none",
            "model_id": "draft_only",
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

        brand_kit:         dict       = brief.get("brand_kit") or {}
        brand_spec:        dict       = _resolve_brand_spec(brief)
        reference_images:  list[dict] = brief.get("reference_images") or []
        copy               = _extract_copy(brief)
        prior_block        = _restore_from_prior(brief)
        template_type      = str(brief.get("template_type") or prior_block.get("template_type") or "promo")
        post_format        = str(brief.get("post_format") or prior_block.get("post_format") or "square")

        draft_text = build_draft_text(
            brand_kit, brand_spec, copy, template_type, post_format, reference_images
        )

        no_logo_hint = ""
        if not brand_spec.get("logo_drive_file_id"):
            no_logo_hint = "\n\nTip: Add a `logo_drive_file_id` to this brand's spec to enable automatic logo injection."

        brand_name = str(brand_kit.get("brand_name") or brand_kit.get("name") or "")

        return self._attempt(start, "succeeded"), {
            "content": f"Draft ready — review before rendering:\n\n{draft_text}{no_logo_hint}",
            "block": {
                "type": "postcraft_draft",
                "status": "pending_review",
                "title": f"Draft: {copy.get('headline') or template_type}",
                "display_title": "Post Draft",
                "draft_text": draft_text,
                "body_markdown": draft_text,
                "template_type": template_type,
                "post_format": post_format,
                "brand_name": brand_name,
                "brand_kit": brand_kit,
                "brand_spec": brand_spec,
                "campaign_alignment": _campaign_alignment(brief) or prior_block.get("campaign_alignment") or {},
                "copy": copy,
                "revision_feedback": str(brief.get("revision_feedback") or brief.get("feedback") or brief.get("edit_instruction") or ""),
                "reference_image_count": len(reference_images),
                "reference_image_titles": [
                    str(r.get("title") or r.get("filename") or "") for r in reference_images
                ],
                "approval_status": "pending",
                "workflow": {
                    "id": "postcraft_pipeline",
                    "stage": "postcraft_draft_review",
                    "continuation_policy": "artifact_bound_else_fresh",
                    "fresh_start_module": "postcraft.draft",
                },
                "allowed_actions": ["render", "revise", "dismiss"],
                "action_modules": {"render": "postcraft.render", "revise": "postcraft.draft"},
            },
        }

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        if not isinstance(content, str):
            return "fail", ["content_not_string"]
        if "Draft ready" not in content:
            return "fail", ["draft_not_produced"]
        return "pass", []
