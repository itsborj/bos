from __future__ import annotations

import base64
import hashlib
import json
import logging
import re
import uuid
from io import BytesIO
from typing import Any

logger = logging.getLogger("bos.attachment_context")

DOC_EXTRACT_CAP = 6_000
# Images larger than this are shrunk before being embedded as vision content.
# ~750KB raw ≈ 1MB base64 ≈ ~250K tokens — safe for most model context windows.
_VISION_MAX_BYTES = 768_000
_VISION_MAX_DIMENSION = 1024
MAX_VARIABLES = 500
_REFERENCE_UUID_NAMESPACE = uuid.UUID("5d947f69-fb60-4e86-9c68-2d1a5965cf49")
_READABLE_STATUSES = {"read", "vision_ready", "provided"}
_SPEC_STATUSES = {"pending", "read", "vision_ready", "failed", "empty", "skipped"}


def _shrink_image_for_vision(data: bytes, mime: str) -> tuple[bytes, str]:
    """Resize image so it fits within _VISION_MAX_BYTES for LLM vision context.

    Strategy:
      1. Resize to max _VISION_MAX_DIMENSION px on longest side.
      2. Always output JPEG (far smaller than PNG for real-world images).
      3. If still over the limit, lower quality until it fits (min q=50).

    Returns (possibly_resized_bytes, output_mime). Falls back to original on any error.
    """
    if len(data) <= _VISION_MAX_BYTES:
        return data, mime
    try:
        from PIL import Image  # type: ignore[import-untyped]
        img = Image.open(BytesIO(data))
        w, h = img.size
        scale = _VISION_MAX_DIMENSION / max(w, h)
        if scale < 1.0:
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")
        quality = 85
        while quality >= 50:
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=quality, optimize=True)
            resized = buf.getvalue()
            if len(resized) <= _VISION_MAX_BYTES:
                break
            quality -= 10
        logger.info("Vision image shrunk %d→%d bytes (%dx%d→%dx%d q=%d)", len(data), len(resized), w, h, img.width, img.height, quality)
        return resized, "image/jpeg"
    except Exception as exc:
        logger.warning("Image resize failed, using original: %s", exc)
        return data, mime


def _get(ref: Any, key: str, default: Any = None) -> Any:
    if isinstance(ref, dict):
        return ref.get(key, default)
    return getattr(ref, key, default)


def _set(ref: Any, key: str, value: Any) -> None:
    if isinstance(ref, dict):
        ref[key] = value
    else:
        setattr(ref, key, value)


def _as_dict_json(value: Any) -> dict | None:
    return value if isinstance(value, dict) else None


def _reference_uuid(value: Any | None = None) -> uuid.UUID:
    if value:
        try:
            return uuid.UUID(str(value))
        except Exception:
            return uuid.uuid5(_REFERENCE_UUID_NAMESPACE, str(value))
    return uuid.uuid4()


def ensure_reference_identity(ref: Any) -> str:
    """Ensure every in-chat reference has a stable UUID string id."""
    raw = _get(ref, "id")
    ref_id = str(_reference_uuid(raw)) if raw else str(uuid.uuid4())
    _set(ref, "id", ref_id)
    return ref_id


def infer_status(ref: Any) -> str:
    status = _get(ref, "extraction_status")
    if status:
        status = str(status)
        if status == "metadata_only":
            return "vision_ready" if _get(ref, "kind") == "image" else "skipped"
        if status in _SPEC_STATUSES or status == "provided":
            return status
    if _get(ref, "text"):
        return "vision_ready" if _get(ref, "kind") == "image" else "read"
    if _get(ref, "source") == "google_drive" and _get(ref, "drive_file_id"):
        return "pending"
    return "skipped"


def read_summary(references: list[Any] | None) -> str:
    refs = references or []
    if not refs:
        return ""
    readable = sum(1 for r in refs if infer_status(r) in _READABLE_STATUSES)
    failed = sum(1 for r in refs if infer_status(r) == "failed")
    pending = sum(1 for r in refs if infer_status(r) == "pending")
    unavailable = len(refs) - readable - failed - pending
    parts = [f"{readable}/{len(refs)} readable"]
    if failed:
        parts.append(f"{failed} failed")
    if pending:
        parts.append(f"{pending} pending")
    if unavailable:
        parts.append(f"{unavailable} unavailable")
    return ", ".join(parts)


def _json_path_key(key: str) -> str:
    if key.replace("_", "").replace("-", "").isalnum():
        return f".{key}"
    return "[" + json.dumps(key, ensure_ascii=False) + "]"


def _extract_json_from_text(text: str) -> Any | None:
    raw = (text or "").strip()
    if not raw:
        return None
    candidates = [raw]
    if "```" in raw:
        parts = raw.split("```")
        candidates.extend(part.strip().removeprefix("json").strip() for part in parts if part.strip())
    first_obj = raw.find("{")
    last_obj = raw.rfind("}")
    if first_obj >= 0 and last_obj > first_obj:
        candidates.append(raw[first_obj:last_obj + 1])
    first_arr = raw.find("[")
    last_arr = raw.rfind("]")
    if first_arr >= 0 and last_arr > first_arr:
        candidates.append(raw[first_arr:last_arr + 1])
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except Exception:
            continue
    return None


def _scalar_variables(value: Any, path: str = "$", limit: int = MAX_VARIABLES) -> list[dict]:
    variables: list[dict] = []

    def walk(node: Any, current_path: str) -> None:
        if len(variables) >= limit:
            return
        if isinstance(node, dict):
            for key, child in node.items():
                walk(child, current_path + _json_path_key(str(key)))
        elif isinstance(node, list):
            for idx, child in enumerate(node):
                walk(child, f"{current_path}[{idx}]")
        else:
            variables.append({
                "path": current_path,
                "type": type(node).__name__,
                "value": node if isinstance(node, (str, int, float, bool)) or node is None else str(node),
                "editable": True,
            })

    walk(value, path)
    return variables


def variables_for_extraction_json(extraction_json: Any) -> list[dict]:
    return _scalar_variables(extraction_json, path="$") if isinstance(extraction_json, (dict, list)) else []


def _content_json_for_ref(ref: Any, title: str, kind: str, mime_type: str | None, text_excerpt: str | None) -> tuple[dict | list | None, str]:
    explicit = _get(ref, "extraction_json")
    if isinstance(explicit, (dict, list)):
        return explicit, "provided_json"
    parsed = _extract_json_from_text(text_excerpt or "")
    if isinstance(parsed, (dict, list)):
        return parsed, "parsed_json"
    if text_excerpt:
        return {
            "document": {
                "title": title,
                "kind": kind,
                "mime_type": mime_type,
                "text_excerpt": text_excerpt,
            }
        }, "text_wrapped_json"
    return None, "none"


def _reference_analysis(ref: Any, content_json: Any | None = None) -> dict | None:
    kind = str(_get(ref, "kind") or "").lower()
    metadata = _as_dict_json(_get(ref, "metadata_json")) or {}
    existing = metadata.get("analysis") if isinstance(metadata.get("analysis"), dict) else None
    if existing:
        return existing
    title_notes = " ".join(str(_get(ref, k) or "") for k in ("title", "drive_file_name", "notes")).lower()
    if kind == "image":
        possible_roles = ["visual_reference"]
        risks: list[str] = []
        detected_panels = metadata.get("detected_panels") if isinstance(metadata.get("detected_panels"), list) else []
        is_storyboard = any(token in title_notes for token in ("storyboard", "story board", "panel", "scene", "bw", "b&w", "black-and-white", "black white", "sketch", "wireframe"))
        is_color_final = any(token in title_notes for token in ("final", "color", "colour", "lighting", "mood", "look")) and not any(token in title_notes for token in ("bw", "b&w", "black-and-white", "black white"))
        if is_storyboard:
            possible_roles = ["storyboard_reference", "composition_reference"]
        elif is_color_final:
            possible_roles = ["final_shot_reference", "color_reference", "lighting_reference", "mood_reference"]
        return {
            "facts": ["Image reference is available for vision analysis."],
            "style": "black-and-white storyboard/composition reference" if is_storyboard else ("colored final-shot or mood reference" if is_color_final else None),
            "composition": "Treat as panel/scene composition input before treating it as final visual style." if is_storyboard else None,
            "possible_roles": possible_roles,
            "risks": risks,
            "detected_panels": detected_panels,
        }
    if kind in {"document", "text"} and content_json is not None:
        return {
            "facts": ["Readable structured reference context is available."],
            "style": None,
            "composition": None,
            "possible_roles": ["concept_reference", "variable_source"],
            "risks": [],
            "detected_panels": [],
        }
    return None


def build_payload(references: list[Any] | None) -> dict:
    """Return JSON-serialisable attachment context for specialist handoff.

    The extractor preserves JSON, wraps non-JSON text into a JSON envelope, and
    exposes scalar variables as JSONPath-like paths relative to each reference's
    extraction_json (not to a transient chat packet index).
    """
    refs = (references or [])[:8]
    items: list[dict] = []
    all_variables: list[dict] = []
    for idx, ref in enumerate(refs, start=1):
        ref_id = ensure_reference_identity(ref)
        status = infer_status(ref)
        kind = _get(ref, "kind") or "text"
        mime_type = _get(ref, "mime_type")
        title = _get(ref, "title") or _get(ref, "drive_file_name") or f"Reference {idx}"
        text = (_get(ref, "text") or "")
        is_image_data = bool(kind == "image" and str(text).strip().startswith("data:"))
        text_excerpt = None if is_image_data else (str(text).strip() or None)
        content_json, content_json_status = _content_json_for_ref(ref, title, kind, mime_type, text_excerpt)
        if content_json is not None and not _get(ref, "extraction_json"):
            _set(ref, "extraction_json", content_json)
        variables = variables_for_extraction_json(content_json)
        _set(ref, "variables_json", {"variables": variables[:MAX_VARIABLES]})
        for var in variables:
            all_variables.append({"reference_id": ref_id, "item_index": idx, "title": title, **var})
        drive_file_id = _get(ref, "drive_file_id")
        drive_web_view_link = _get(ref, "drive_web_view_link")
        thumbnail_link = _get(ref, "thumbnail_link")
        analysis = _reference_analysis(ref, content_json)
        items.append({
            "id": ref_id,
            "index": idx,
            "title": title,
            "kind": kind,
            "source": _get(ref, "source") or "inline",
            "mime_type": mime_type,
            "extraction_status": status,
            "extraction_error": _get(ref, "extraction_error"),
            "extracted_chars": _get(ref, "extracted_chars") if _get(ref, "extracted_chars") is not None else (len(text_excerpt) if text_excerpt else None),
            "notes": _get(ref, "notes"),
            "text_excerpt": text_excerpt,
            "content_json_status": content_json_status,
            "content_json": content_json,
            "variables": variables,
            "analysis": analysis,
            "has_vision_image": bool(kind == "image" and (is_image_data or status == "vision_ready")),
            "drive": {
                "file_id": drive_file_id,
                "file_name": _get(ref, "drive_file_name"),
                "web_view_link": drive_web_view_link,
                "thumbnail_link": thumbnail_link,
            } if drive_file_id or drive_web_view_link or thumbnail_link else None,
            "storage_url": _get(ref, "storage_url"),
            "sha256": _get(ref, "sha256"),
            "metadata": _get(ref, "metadata_json"),
        })
    return {
        "schema": "bos.operator_reference_context.v1",
        "summary": read_summary(refs),
        "rules": [
            "Each item has a stable id; patches and canonical specs must target ids, scene_ids, or JSON paths, not chat indexes.",
            "content_json is the BOS-owned source-of-truth JSON for specialist handoff when present.",
            "variables are editable JSON paths relative to the reference extraction_json.",
            "Do not claim or rely on contents for items whose extraction_status is failed, skipped, empty, or pending unless content_json is present.",
            "For media generation, pass this JSON as structured context; provider JSON is only an execution artifact.",
        ],
        "items": items,
        "variables": all_variables[:MAX_VARIABLES],
    }


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(p) for p in parts if p is not None)
    return f"{prefix}_{uuid.uuid5(_REFERENCE_UUID_NAMESPACE, raw).hex[:16]}"


def _reference_role(item: dict) -> str:
    roles = (((item.get("analysis") or {}).get("possible_roles")) or []) if isinstance(item.get("analysis"), dict) else []
    if roles:
        return str(roles[0])
    if item.get("kind") == "image":
        return "visual_reference"
    if item.get("kind") == "document":
        return "concept_reference"
    return "text_reference"


def assemble_creative_context(references: list[Any] | None, *, brand_id: str | None = None, conversation_id: str | None = None, creative_decisions: list[dict] | None = None, constraints: dict | None = None) -> dict:
    payload = build_payload(references)
    ref_ids = [item["id"] for item in payload["items"]]
    candidates: list[str] = []
    if any(item.get("kind") == "image" for item in payload["items"]):
        candidates.append("discuss_reference_image")
        candidates.append("compose_image_spec")
    if any(item.get("kind") == "document" for item in payload["items"]):
        candidates.append("extract_concept")
    if len([i for i in payload["items"] if i.get("kind") == "image"]) >= 2:
        candidates.append("compose_storyboard_spec")
        candidates.append("compose_video_spec")
    return {
        "schema": "bos.creative_context.v1",
        "context_id": _stable_id("ctx", brand_id or "", conversation_id or "", ",".join(ref_ids)),
        "brand_id": brand_id,
        "conversation_id": conversation_id,
        "reference_ids": ref_ids,
        "source_summary": payload["summary"],
        "references": payload["items"],
        "creative_decisions": creative_decisions or [],
        "constraints": constraints or {},
        "production_candidates": candidates,
        "rules": [
            "Discussion mode never triggers generation by itself.",
            "Production mode starts only on clear user intent and should use ImageSpec, StoryboardSpec, or VideoSpec.",
        ],
    }


def compose_image_spec(references: list[Any] | None, *, objective: str | None = None, brand_id: str | None = None, conversation_id: str | None = None) -> dict:
    ctx = assemble_creative_context(references, brand_id=brand_id, conversation_id=conversation_id)
    refs = [{"reference_id": item["id"], "role": _reference_role(item), "title": item.get("title")} for item in ctx["references"]]
    return {
        "schema": "bos.image_spec.v1",
        "spec_id": _stable_id("imgspec", ctx["context_id"], objective or ""),
        "version": 1,
        "objective": objective or "Draft a brand-safe generated image from the confirmed creative context.",
        "references": refs,
        "prompt_components": {
            "source_summary": ctx["source_summary"],
            "creative_decisions": ctx["creative_decisions"],
        },
        "constraints": ctx["constraints"],
        "status": "draft",
    }


def compose_storyboard_spec(references: list[Any] | None, *, brand_id: str | None = None, conversation_id: str | None = None) -> dict | None:
    ctx = assemble_creative_context(references, brand_id=brand_id, conversation_id=conversation_id)
    image_items = [item for item in ctx["references"] if item.get("kind") == "image"]
    if len(image_items) < 2:
        return None
    storyboard_items = [i for i in image_items if _reference_role(i) in {"storyboard_reference", "composition_reference", "visual_reference"}]
    final_items = [i for i in image_items if _reference_role(i) in {"final_shot_reference", "color_reference", "lighting_reference", "mood_reference"}]
    # MVP deterministic scene candidates: use detected panels when available, otherwise
    # default to 4 panels per storyboard sheet for multi-sheet storyboard uploads.
    scenes: list[dict] = []
    sheet_count = max(1, len(storyboard_items))
    default_panels_per_sheet = 4 if sheet_count >= 2 else 1
    order = 1
    for item in storyboard_items:
        if item in final_items and len(storyboard_items) > 1:
            continue
        detected = ((item.get("analysis") or {}).get("detected_panels") or []) if isinstance(item.get("analysis"), dict) else []
        panel_count = len(detected) or default_panels_per_sheet
        for panel_index in range(1, panel_count + 1):
            scene_id = _stable_id("scene", item["id"], panel_index)
            scenes.append({
                "scene_id": scene_id,
                "order": order,
                "source_reference_id": item["id"],
                "panel_id": _stable_id("panel", item["id"], panel_index),
                "title": f"Scene {order}",
                "description": "Scene candidate inferred from storyboard/composition reference; user confirmation required before generation.",
                "role": "storyboard_scene",
                "assumptions": ["Panel boundary and scene description are inferred and should be reviewed."],
            })
            order += 1
    if not scenes:
        return None
    return {
        "schema": "bos.storyboard_spec.v1",
        "storyboard_id": _stable_id("storyboard", ctx["context_id"]),
        "source_reference_ids": ctx["reference_ids"],
        "scene_count": len(scenes),
        "scenes": scenes,
        "final_shot_reference_ids": [i["id"] for i in final_items],
        "assumptions": [
            "Black-and-white/storyboard-like images default to composition/storyboard roles, not final color/style.",
            "Colored final-look images default to final-shot/color/lighting roles unless the user says to apply them globally.",
            "Human approval is required before generation when scene order or roles are inferred.",
        ],
        "status": "draft_review_required",
    }


def compose_video_spec(references: list[Any] | None, *, objective: str | None = None, brand_id: str | None = None, conversation_id: str | None = None) -> dict:
    ctx = assemble_creative_context(references, brand_id=brand_id, conversation_id=conversation_id)
    storyboard = compose_storyboard_spec(references, brand_id=brand_id, conversation_id=conversation_id)
    scenes = storyboard["scenes"] if storyboard else [{
        "scene_id": _stable_id("scene", ctx["context_id"], 1),
        "order": 1,
        "description": objective or "Single-scene video concept from confirmed creative context.",
        "source_reference_ids": ctx["reference_ids"],
    }]
    return {
        "schema": "bos.video_spec.v1",
        "spec_id": _stable_id("videospec", ctx["context_id"], objective or ""),
        "version": 1,
        "format": {"duration_seconds": 15, "aspect_ratio": "9:16"},
        "creative_direction": {"objective": objective or "Generate a short-form brand-safe video from confirmed creative context.", "source_summary": ctx["source_summary"]},
        "source_references": [{"reference_id": item["id"], "role": _reference_role(item), "title": item.get("title")} for item in ctx["references"]],
        "scenes": scenes,
        "audio": {"mode": "provider_default_or_silent"},
        "cta": None,
        "constraints": ctx["constraints"],
        "revision_policy": "Patch canonical spec fields or scene_id values; if partial regeneration is unavailable, regenerate from patched spec.",
        "status": "draft",
    }


def apply_extraction_json(ref: Any) -> None:
    """Populate ref.extraction_json/content JSON from current extracted text."""
    ensure_reference_identity(ref)
    kind = _get(ref, "kind") or "text"
    title = _get(ref, "title") or _get(ref, "drive_file_name") or "Reference"
    text = _get(ref, "text")
    is_image_data = bool(kind == "image" and str(text or "").strip().startswith("data:"))
    text_excerpt = None if is_image_data else (str(text or "").strip() or None)
    content_json, _status = _content_json_for_ref(ref, title, kind, _get(ref, "mime_type"), text_excerpt)
    if content_json is not None:
        _set(ref, "extraction_json", content_json)
        _set(ref, "variables_json", {"variables": variables_for_extraction_json(content_json)})


def _extract_b64_and_mime(text: str | None, fallback_mime: str | None = None) -> tuple[str, str] | None:
    """Return (bare_b64, mime) from a data URI or raw base64 string. Returns None if no image data."""
    import re as _re
    raw = (text or "").strip()
    if not raw:
        return None
    if raw.startswith("data:"):
        m = _re.match(r"data:([^;]+);base64,(.+)", raw, _re.DOTALL)
        if m:
            return m.group(2).strip(), m.group(1)
        return None
    return raw, fallback_mime or "image/png"


def brief_fields(references: list[Any] | None, *, brand_id: str | None = None, conversation_id: str | None = None, objective: str | None = None) -> dict:
    if not references:
        return {}
    for ref in references:
        ensure_reference_identity(ref)
        apply_extraction_json(ref)
    payload = build_payload(references)
    creative_context = assemble_creative_context(references, brand_id=brand_id, conversation_id=conversation_id)
    storyboard_spec = compose_storyboard_spec(references, brand_id=brand_id, conversation_id=conversation_id)
    image_spec = compose_image_spec(references, objective=objective, brand_id=brand_id, conversation_id=conversation_id)
    video_spec = compose_video_spec(references, objective=objective, brand_id=brand_id, conversation_id=conversation_id)

    # Compact image manifest for module hydration (Stage 4).
    # Carries pre-enriched base64 so modules never need to re-download from Drive.
    # Parallel to operator_reference_context items but kept separate to avoid
    # bloating the context JSON that gets logged and returned to clients.
    reference_images: list[dict] = []
    for ref in (references or [])[:8]:
        if _get(ref, "kind") != "image":
            continue
        b64_and_mime = _extract_b64_and_mime(_get(ref, "text"), _get(ref, "mime_type"))
        if not b64_and_mime:
            continue
        vision_b64, mime = b64_and_mime
        reference_images.append({
            "id": _get(ref, "id"),
            "title": _get(ref, "title") or _get(ref, "drive_file_name"),
            "drive_file_id": _get(ref, "drive_file_id"),
            "mime_type": mime,
            "vision_b64": vision_b64,
        })

    fields = {
        "operator_reference_context": payload,
        "operator_reference_context_json": json.dumps(payload, ensure_ascii=False),
        "creative_context": creative_context,
        "creative_context_json": json.dumps(creative_context, ensure_ascii=False),
        "image_spec": image_spec,
        "image_spec_json": json.dumps(image_spec, ensure_ascii=False),
        "video_spec": video_spec,
        "video_spec_json": json.dumps(video_spec, ensure_ascii=False),
        "reference_images": reference_images,
    }
    if storyboard_spec:
        fields["storyboard_spec"] = storyboard_spec
        fields["storyboard_spec_json"] = json.dumps(storyboard_spec, ensure_ascii=False)
    return fields


def format_for_prompt(references: list[Any] | None) -> str:
    refs = (references or [])[:8]
    if not refs:
        return ""
    payload = build_payload(refs)
    lines = [
        "CMO creative references attached by the operator:",
        f"Reference read status: {read_summary(refs)}.",
        "Business rules: uploading or discussing a reference does not imply generation intent; do not RUN image/video modules unless the user clearly asks to make/generate/proceed.",
        "Patch rule: for a requested variable edit, emit a hidden PATCH_REFERENCE JSON directive with reference_id, op, path, value, and optional reason. Do not show the directive in visible text.",
        "Important: only treat a document as read when extraction_status is read/provided and a text excerpt or content_json is present. If extraction failed, pending, skipped, or empty, say that plainly.",
    ]
    for idx, item in enumerate(payload["items"], start=1):
        kind = str(item.get("kind") or "reference").strip().lower()
        source = str(item.get("source") or "inline").strip().lower()
        status = item.get("extraction_status")
        title = str(item.get("title") or f"Reference {idx}").strip()[:160]
        lines.append(f"{idx}. {title} [id: {item['id']}] ({kind}, source: {source}, extraction: {status})")
        if item.get("extracted_chars") is not None:
            lines.append(f"   Extracted characters: {item.get('extracted_chars')}")
        if item.get("extraction_error"):
            lines.append(f"   Extraction error: {str(item.get('extraction_error')).strip()[:300]}")
        if item.get("notes"):
            lines.append(f"   Notes: {str(item.get('notes')).strip()[:800]}")
        text_excerpt = str(item.get("text_excerpt") or "")
        if text_excerpt:
            lines.append("   Text excerpt:")
            lines.append("   " + text_excerpt.strip()[:3000].replace("\n", "\n   "))
        variables = item.get("variables") or []
        if variables:
            sample = ", ".join(f"{v.get('path')}={v.get('value')}" for v in variables[:12])
            lines.append(f"   Editable variables: {sample}")
        analysis = item.get("analysis") or {}
        roles = analysis.get("possible_roles") if isinstance(analysis, dict) else None
        if roles:
            lines.append(f"   Possible roles: {', '.join(str(r) for r in roles)}")
        drive = item.get("drive") or {}
        if drive.get("file_id"):
            lines.append(f"   Drive file id: {drive.get('file_id')}")
        if item.get("mime_type"):
            lines.append(f"   MIME: {item.get('mime_type')}")
        if drive.get("web_view_link"):
            lines.append(f"   Drive link: {drive.get('web_view_link')}")
    storyboard_spec = compose_storyboard_spec(refs)
    if storyboard_spec:
        lines.append("Draft StoryboardSpec available for review before video generation:")
        lines.append(json.dumps(storyboard_spec, ensure_ascii=False)[:2500])
    lines.append("Use these references as reusable creative context for discussion/planning. If the user later asks to produce, reuse these ids in canonical specs.")
    return "\n".join(lines)


def extract_doc_text(data: bytes, mime: str) -> str:
    """Extract plain text from document bytes. Supports JSON/TXT, DOCX and PDF."""
    if mime in {"application/json", "text/plain", "text/markdown"} or mime.startswith("text/"):
        return data.decode("utf-8", errors="replace")
    if "wordprocessingml" in mime or mime == "application/msword":
        try:
            from docx import Document  # type: ignore[import-untyped]
            doc = Document(BytesIO(data))
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except Exception as exc:
            raise RuntimeError(f"DOCX extraction failed: {exc}") from exc
    if mime == "application/pdf":
        try:
            from pypdf import PdfReader  # type: ignore[import-untyped]
            reader = PdfReader(BytesIO(data))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:
            raise RuntimeError(f"PDF extraction failed: {exc}") from exc
    raise RuntimeError(f"Unsupported doc MIME for extraction: {mime}")


async def persist_chat_references(
    references: list[Any] | None,
    *,
    workspace_id: uuid.UUID | str | None,
    brand_id: uuid.UUID | str | None = None,
    conversation_id: str | None = None,
    campaign_id: uuid.UUID | str | None = None,
    db: Any,
) -> None:
    """Insert original chat reference rows if absent.

    Existing rows are not overwritten with client patched working copies; we only
    update lightweight routing fields and updated_at. This satisfies MVP behavior
    where patched references can be sent on each chat turn without immediately
    persisting a new source version.
    """
    if not references or not workspace_id:
        return
    try:
        from sqlalchemy import select
        from models.chat_reference import ChatReference as ChatReferenceRow
    except Exception as exc:
        logger.warning("ChatReference model unavailable; skipping persistence: %s", exc)
        return

    def as_uuid(value: Any) -> uuid.UUID | None:
        if not value:
            return None
        try:
            return uuid.UUID(str(value))
        except Exception:
            return None

    ws_uuid = as_uuid(workspace_id)
    if not ws_uuid:
        return
    brand_uuid = as_uuid(brand_id)
    campaign_uuid = as_uuid(campaign_id)
    for ref in references[:8]:
        ref_uuid = _reference_uuid(ensure_reference_identity(ref))
        apply_extraction_json(ref)
        variables = variables_for_extraction_json(_get(ref, "extraction_json"))
        row = (await db.execute(select(ChatReferenceRow).where(ChatReferenceRow.id == ref_uuid))).scalar_one_or_none()
        if row:
            row.conversation_id = row.conversation_id or conversation_id
            row.brand_id = row.brand_id or brand_uuid
            row.campaign_id = row.campaign_id or campaign_uuid
            continue
        text = _get(ref, "text")
        text_excerpt = None
        if text and not (_get(ref, "kind") == "image" and str(text).startswith("data:")):
            text_excerpt = str(text)[:DOC_EXTRACT_CAP]
        db.add(ChatReferenceRow(
            id=ref_uuid,
            workspace_id=ws_uuid,
            brand_id=brand_uuid,
            conversation_id=conversation_id,
            campaign_id=campaign_uuid,
            kind=str(_get(ref, "kind") or "text"),
            source=str(_get(ref, "source") or "inline"),
            title=_get(ref, "title") or _get(ref, "drive_file_name"),
            notes=_get(ref, "notes"),
            mime_type=_get(ref, "mime_type"),
            drive_file_id=_get(ref, "drive_file_id"),
            drive_file_name=_get(ref, "drive_file_name"),
            drive_web_view_link=_get(ref, "drive_web_view_link"),
            thumbnail_link=_get(ref, "thumbnail_link"),
            storage_url=_get(ref, "storage_url"),
            sha256=_get(ref, "sha256"),
            metadata_json=_get(ref, "metadata_json"),
            text_excerpt=text_excerpt,
            extraction_status=infer_status(ref),
            extraction_error=_get(ref, "extraction_error"),
            extracted_chars=_get(ref, "extracted_chars"),
            extraction_json=_get(ref, "extraction_json"),
            variables_json={"variables": variables[:MAX_VARIABLES]},
        ))
    await db.flush()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def enrich_drive_references(
    references: list[Any] | None,
    brand_id: str | None,
    db: Any,
    settings: Any,
) -> None:
    """Download/extract Drive references in-place, then mark extraction status."""
    if not references:
        return

    for ref in references:
        ensure_reference_identity(ref)
        if _get(ref, "text") and not _get(ref, "extraction_status"):
            _set(ref, "extraction_status", "vision_ready" if _get(ref, "kind") == "image" else "read")
            _set(ref, "extracted_chars", len(str(_get(ref, "text"))) if _get(ref, "kind") != "image" else None)
            apply_extraction_json(ref)

    if not brand_id:
        for ref in references:
            if _get(ref, "source") in {"google_drive", "upload"} and _get(ref, "drive_file_id") and not _get(ref, "text"):
                _set(ref, "extraction_status", "skipped")
                _set(ref, "extraction_error", "No active brand was available to authorize Drive access.")
        return

    drive_refs = [
        r for r in references
        if _get(r, "source") in {"google_drive", "upload"} and _get(r, "drive_file_id") and not _get(r, "text")
        and _get(r, "kind") in ("image", "document")
    ]
    if not drive_refs:
        return

    try:
        from routers.social import _load_google_drive_client, get_page_token  # type: ignore[attr-defined]
        DriveClient = _load_google_drive_client()
    except Exception as exc:
        logger.warning("DriveClient unavailable; skipping Drive enrichment: %s", exc)
        for ref in drive_refs:
            _set(ref, "extraction_status", "failed")
            _set(ref, "extraction_error", f"Drive reader unavailable: {type(exc).__name__}")
        return

    token, _ = await get_page_token(db, brand_id, "google_drive", settings)
    if not token:
        logger.warning("No Drive token for brand %s; skipping Drive enrichment", brand_id)
        for ref in drive_refs:
            _set(ref, "extraction_status", "failed")
            _set(ref, "extraction_error", "Google Drive is not connected or needs re-authentication for this brand.")
        return

    google_native_doc_mimes = {
        "application/vnd.google-apps.document",
        "application/vnd.google-apps.presentation",
    }
    for ref in drive_refs:
        try:
            mime = str(_get(ref, "mime_type") or "").lower()
            _set(ref, "extraction_error", None)
            with DriveClient(token) as drive:
                if mime in google_native_doc_mimes:
                    data = drive.export_file(_get(ref, "drive_file_id"), "text/plain")
                    text = data.decode("utf-8", errors="replace").strip()
                    _set(ref, "text", text[:DOC_EXTRACT_CAP] if text else "")
                    _set(ref, "extraction_status", "read" if _get(ref, "text") else "empty")
                    _set(ref, "extracted_chars", len(_get(ref, "text") or ""))
                    _set(ref, "sha256", sha256_hex(data))
                    apply_extraction_json(ref)
                elif _get(ref, "kind") == "image":
                    data = drive.download_file(_get(ref, "drive_file_id"))
                    original_bytes = len(data)
                    data, mime = _shrink_image_for_vision(data, mime or "image/jpeg")
                    _set(ref, "text", f"data:{mime};base64,{base64.b64encode(data).decode()}")
                    _set(ref, "extraction_status", "vision_ready")
                    _set(ref, "sha256", sha256_hex(data))
                    _set(ref, "metadata_json", {**(_as_dict_json(_get(ref, "metadata_json")) or {}), "byte_size": original_bytes, "vision_byte_size": len(data)})
                    apply_extraction_json(ref)
                else:
                    data = drive.download_file(_get(ref, "drive_file_id"))
                    text = extract_doc_text(data, mime).strip()
                    _set(ref, "text", text[:DOC_EXTRACT_CAP] if text else "")
                    _set(ref, "extraction_status", "read" if _get(ref, "text") else "empty")
                    _set(ref, "extracted_chars", len(_get(ref, "text") or ""))
                    _set(ref, "sha256", sha256_hex(data))
                    apply_extraction_json(ref)
        except Exception as exc:
            logger.warning("Drive enrichment failed for %s: %s", _get(ref, "drive_file_id"), exc)
            _set(ref, "extraction_status", "failed")
            _set(ref, "extraction_error", str(exc)[:500])
            if _get(ref, "kind") == "document":
                _set(ref, "text", None)
