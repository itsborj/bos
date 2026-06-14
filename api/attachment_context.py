from __future__ import annotations

import base64
import json
import logging
from io import BytesIO
from typing import Any

logger = logging.getLogger("bos.attachment_context")

DOC_EXTRACT_CAP = 6_000
MAX_VARIABLES = 500


def _get(ref: Any, key: str, default: Any = None) -> Any:
    if isinstance(ref, dict):
        return ref.get(key, default)
    return getattr(ref, key, default)


def _set(ref: Any, key: str, value: Any) -> None:
    if isinstance(ref, dict):
        ref[key] = value
    else:
        setattr(ref, key, value)


def infer_status(ref: Any) -> str:
    status = _get(ref, "extraction_status")
    if status:
        return str(status)
    if _get(ref, "text"):
        return "vision_ready" if _get(ref, "kind") == "image" else "provided"
    if _get(ref, "source") == "google_drive" and _get(ref, "drive_file_id"):
        return "pending"
    return "metadata_only"


def read_summary(references: list[Any] | None) -> str:
    refs = references or []
    if not refs:
        return ""
    readable = sum(1 for r in refs if infer_status(r) in {"read", "provided", "vision_ready"})
    failed = sum(1 for r in refs if infer_status(r) == "failed")
    metadata_only = len(refs) - readable - failed
    parts = [f"{readable}/{len(refs)} readable"]
    if failed:
        parts.append(f"{failed} failed")
    if metadata_only:
        parts.append(f"{metadata_only} metadata-only")
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


def build_payload(references: list[Any] | None) -> dict:
    """Return JSON-serialisable attachment context for specialist handoff.

    The extractor is generic: it preserves any JSON found in the source, wraps
    non-JSON text into a minimal JSON document envelope, and exposes JSONPath-like
    scalar variables for downstream revision targeting.
    """
    refs = (references or [])[:8]
    items: list[dict] = []
    all_variables: list[dict] = []
    for idx, ref in enumerate(refs, start=1):
        status = infer_status(ref)
        kind = _get(ref, "kind") or "text"
        mime_type = _get(ref, "mime_type")
        title = _get(ref, "title") or _get(ref, "drive_file_name") or f"Reference {idx}"
        text = (_get(ref, "text") or "")
        is_image_data = bool(kind == "image" and str(text).strip().startswith("data:"))
        text_excerpt = None if is_image_data else (str(text).strip() or None)
        content_json, content_json_status = _content_json_for_ref(ref, title, kind, mime_type, text_excerpt)
        variables = _scalar_variables(content_json, path=f"$.items[{idx - 1}].content_json") if content_json is not None else []
        for var in variables:
            all_variables.append({"item_index": idx, "title": title, **var})
        drive_file_id = _get(ref, "drive_file_id")
        drive_web_view_link = _get(ref, "drive_web_view_link")
        thumbnail_link = _get(ref, "thumbnail_link")
        items.append({
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
            "has_vision_image": bool(is_image_data),
            "drive": {
                "file_id": drive_file_id,
                "file_name": _get(ref, "drive_file_name"),
                "web_view_link": drive_web_view_link,
                "thumbnail_link": thumbnail_link,
            } if drive_file_id or drive_web_view_link or thumbnail_link else None,
        })
    return {
        "schema": "bos.operator_reference_context.v1",
        "summary": read_summary(refs),
        "rules": [
            "content_json is the source-of-truth JSON for specialist handoff when present.",
            "variables are editable JSON paths that can be changed in later revision turns.",
            "Do not claim or rely on contents for items whose extraction_status is failed, skipped, empty, pending, or metadata_only unless content_json is present.",
            "For media generation, pass this JSON as structured context; do not replace it with provider-specific assumptions.",
        ],
        "items": items,
        "variables": all_variables[:MAX_VARIABLES],
    }


def apply_extraction_json(ref: Any) -> None:
    """Populate ref.extraction_json/content JSON from current extracted text."""
    kind = _get(ref, "kind") or "text"
    title = _get(ref, "title") or _get(ref, "drive_file_name") or "Reference"
    text = _get(ref, "text")
    is_image_data = bool(kind == "image" and str(text or "").strip().startswith("data:"))
    text_excerpt = None if is_image_data else (str(text or "").strip() or None)
    content_json, _status = _content_json_for_ref(ref, title, kind, _get(ref, "mime_type"), text_excerpt)
    if content_json is not None:
        _set(ref, "extraction_json", content_json)


def brief_fields(references: list[Any] | None) -> dict:
    if not references:
        return {}
    for ref in references:
        apply_extraction_json(ref)
    payload = build_payload(references)
    return {
        "operator_reference_context": payload,
        "operator_reference_context_json": json.dumps(payload, ensure_ascii=False),
    }


def format_for_prompt(references: list[Any] | None) -> str:
    refs = (references or [])[:8]
    if not refs:
        return ""
    lines = [
        "CMO discussion/planning references attached by the operator:",
        f"Reference read status: {read_summary(refs)}.",
        "Important: only treat a document as read when its extraction status is read/provided and a text excerpt is present. If extraction failed or is metadata-only, say that plainly.",
    ]
    for idx, ref in enumerate(refs, start=1):
        kind = str(_get(ref, "kind") or "reference").strip().lower()
        source = str(_get(ref, "source") or "inline").strip().lower()
        status = infer_status(ref)
        title = str(_get(ref, "title") or _get(ref, "drive_file_name") or f"Reference {idx}").strip()[:160]
        lines.append(f"{idx}. {title} ({kind}, source: {source}, extraction: {status})")
        if _get(ref, "extracted_chars") is not None:
            lines.append(f"   Extracted characters: {_get(ref, 'extracted_chars')}")
        if _get(ref, "extraction_error"):
            lines.append(f"   Extraction error: {str(_get(ref, 'extraction_error')).strip()[:300]}")
        if _get(ref, "notes"):
            lines.append(f"   Notes: {str(_get(ref, 'notes')).strip()[:800]}")
        text = str(_get(ref, "text") or "")
        if text and not (kind == "image" and text.strip().startswith("data:")):
            lines.append("   Text excerpt:")
            lines.append("   " + text.strip()[:3000].replace("\n", "\n   "))
        if _get(ref, "drive_file_id"):
            lines.append(f"   Drive file id: {_get(ref, 'drive_file_id')}")
        if _get(ref, "mime_type"):
            lines.append(f"   MIME: {_get(ref, 'mime_type')}")
        if _get(ref, "drive_web_view_link"):
            lines.append(f"   Drive link: {_get(ref, 'drive_web_view_link')}")
    lines.append("Use these references only as context for the current discussion/planning turn.")
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


async def enrich_drive_references(
    references: list[Any] | None,
    brand_id: str | None,
    db: Any,
    settings: Any,
) -> None:
    """Download/extract Drive references in-place, then mark extraction status.

    This is intentionally outside CMO chat. Chat only supplies refs/brand; this
    module owns the attachment → JSON readiness step.
    """
    if not references:
        return

    for ref in references:
        if _get(ref, "text") and not _get(ref, "extraction_status"):
            _set(ref, "extraction_status", "vision_ready" if _get(ref, "kind") == "image" else "provided")
            _set(ref, "extracted_chars", len(str(_get(ref, "text"))) if _get(ref, "kind") != "image" else None)

    if not brand_id:
        for ref in references:
            if _get(ref, "source") == "google_drive" and _get(ref, "drive_file_id") and not _get(ref, "text"):
                _set(ref, "extraction_status", "skipped")
                _set(ref, "extraction_error", "No active brand was available to authorize Drive access.")
        return

    drive_refs = [
        r for r in references
        if _get(r, "source") == "google_drive" and _get(r, "drive_file_id") and not _get(r, "text")
        and _get(r, "kind") in ("image", "document")
    ]
    if not drive_refs:
        return

    try:
        from routers.social import _load_google_drive_client  # type: ignore[attr-defined]
        from provider_auth import get_page_token
        DriveClient = _load_google_drive_client()
    except Exception as exc:
        logger.warning("DriveClient unavailable; skipping Drive enrichment")
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
            with DriveClient(token) as drive:
                if mime in google_native_doc_mimes:
                    data = drive.export_file(_get(ref, "drive_file_id"), "text/plain")
                    text = data.decode("utf-8", errors="replace").strip()
                    _set(ref, "text", text[:DOC_EXTRACT_CAP] if text else "")
                    _set(ref, "extraction_status", "read" if _get(ref, "text") else "empty")
                    _set(ref, "extracted_chars", len(_get(ref, "text") or ""))
                    apply_extraction_json(ref)
                elif _get(ref, "kind") == "image":
                    data = drive.download_file(_get(ref, "drive_file_id"))
                    _set(ref, "text", f"data:{mime or 'image/jpeg'};base64,{base64.b64encode(data).decode()}")
                    _set(ref, "extraction_status", "vision_ready")
                    apply_extraction_json(ref)
                else:
                    data = drive.download_file(_get(ref, "drive_file_id"))
                    text = extract_doc_text(data, mime).strip()
                    _set(ref, "text", text[:DOC_EXTRACT_CAP] if text else "")
                    _set(ref, "extraction_status", "read" if _get(ref, "text") else "empty")
                    _set(ref, "extracted_chars", len(_get(ref, "text") or ""))
                    apply_extraction_json(ref)
        except Exception as exc:
            logger.warning("Drive enrichment failed for %s: %s", _get(ref, "drive_file_id"), exc)
            _set(ref, "extraction_status", "failed")
            _set(ref, "extraction_error", str(exc)[:500])
            if _get(ref, "kind") == "document":
                _set(ref, "text", None)
