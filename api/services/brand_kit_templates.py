from __future__ import annotations

import re
import uuid
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.document import WorkspaceDocument
from models.social import SocialConnection
from models.workspace import Brand, Workspace

MANIFEST_VERSION = "brand_kit_templates.v1"
DEFAULT_SELECTION_POLICY = {
    "default_renderer": "postcraft",
    "confidence_threshold": 0.75,
    "manual_review_required": False,
}

FORMAT_ALIASES = {
    "square": "square_feed",
    "square_feed": "square_feed",
    "feed_square": "square_feed",
    "1:1": "square_feed",
    "portrait": "portrait_feed",
    "portrait_feed": "portrait_feed",
    "4:5": "portrait_feed",
    "story": "story_reel",
    "reel": "story_reel",
    "story_reel": "story_reel",
    "9:16": "story_reel",
    "landscape": "landscape",
    "landscape_feed": "landscape",
    "16:9": "landscape",
}

RESOURCE_KEYS: tuple[tuple[str, str, str], ...] = (
    ("logo", "logo_files", "Logo / mark"),
    ("brand_character", "brand_character_files", "Brand character"),
    ("brand_character", "mascot_files", "Brand character"),
    ("hero_image", "hero_imagery_files", "Hero imagery"),
    ("lifestyle", "lifestyle_files", "Lifestyle / people"),
    ("location", "location_files", "Location / space"),
    ("reference", "creative_reference_files", "Creative reference"),
    ("asset", "visual_asset_files", "Supporting visual"),
)


class TemplateSelectionError(Exception):
    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, **self.details}


@dataclass
class TemplateSelection:
    template_id: str
    confidence: float
    reason: list[str]
    template: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "template_id": self.template_id,
            "confidence": self.confidence,
            "reason": self.reason,
            "template": self.template,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(value: Any) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "_", str(value or "").strip()).strip("_").lower()
    return text[:48] or uuid.uuid4().hex[:12]


def template_id_for_source(source_id: str) -> str:
    return f"bk_tpl_{_slug(source_id)}"


def default_template_manifest() -> dict[str, Any]:
    return {
        "version": MANIFEST_VERSION,
        "templates": [],
        "selection_policy": dict(DEFAULT_SELECTION_POLICY),
    }


def ensure_template_manifest(metadata: dict[str, Any] | None) -> dict[str, Any]:
    """Return metadata with a canonical template_manifest subtree."""
    meta = deepcopy(metadata) if isinstance(metadata, dict) else {}
    manifest = meta.get("template_manifest") if isinstance(meta.get("template_manifest"), dict) else {}
    normalized = default_template_manifest()
    normalized.update({k: deepcopy(v) for k, v in manifest.items() if k not in {"templates", "selection_policy"}})
    normalized["version"] = MANIFEST_VERSION
    templates = manifest.get("templates") if isinstance(manifest.get("templates"), list) else []
    normalized["templates"] = [dict(t) for t in templates if isinstance(t, dict)]
    policy = dict(DEFAULT_SELECTION_POLICY)
    if isinstance(manifest.get("selection_policy"), dict):
        policy.update({k: v for k, v in manifest["selection_policy"].items() if v is not None})
    normalized["selection_policy"] = policy
    meta["template_manifest"] = normalized
    return meta


def _manifest(metadata: dict[str, Any] | None) -> dict[str, Any]:
    return ensure_template_manifest(metadata).get("template_manifest", default_template_manifest())


def _normalize_format(value: Any) -> str:
    text = str(value or "").strip().lower()
    return FORMAT_ALIASES.get(text, text)


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if value in (None, "", {}, []):
        return []
    return [str(value).strip()]


def _copy_density_from_copy(copy: dict[str, Any]) -> str:
    text = " ".join(str(copy.get(k) or "") for k in ("headline", "subheadline", "body", "body_copy", "cta", "cta_text"))
    words = [w for w in re.split(r"\s+", text.strip()) if w]
    if len(words) <= 12:
        return "low"
    if len(words) <= 35:
        return "medium"
    return "high"


def derive_selection_context(brief: dict[str, Any]) -> dict[str, Any]:
    copy = brief.get("copy") if isinstance(brief.get("copy"), dict) else {}
    merged_copy = dict(copy)
    for src, dst in (("headline", "headline"), ("subheadline", "subheadline"), ("body_copy", "body"), ("body", "body"), ("cta_text", "cta"), ("cta", "cta")):
        if brief.get(src) and not merged_copy.get(dst):
            merged_copy[dst] = brief.get(src)

    alignment = brief.get("campaign_alignment") if isinstance(brief.get("campaign_alignment"), dict) else {}
    brand_kit = brief.get("brand_kit") if isinstance(brief.get("brand_kit"), dict) else {}
    nested_brand_spec = brand_kit.get("brand_spec") if isinstance(brand_kit.get("brand_spec"), dict) else {}
    brand_spec = brief.get("brand_spec") if isinstance(brief.get("brand_spec"), dict) else nested_brand_spec
    assets = set(_as_list(brief.get("assets_available")))
    if brand_spec.get("logo_drive_file_id") or nested_brand_spec.get("logo_drive_file_id"):
        assets.add("logo")
    for ref in brief.get("reference_images") or []:
        if not isinstance(ref, dict):
            continue
        role = str(ref.get("placement_role") or ref.get("role") or "").strip()
        if role:
            assets.add(role)
        if role in {"hero", "hero_image", "product", "product_image"}:
            assets.add("hero_image")
    return {
        "renderer": brief.get("renderer") or "postcraft",
        "format": _normalize_format(brief.get("format") or brief.get("post_format") or "square_feed"),
        "content_type": brief.get("content_type") or brief.get("base_family") or brief.get("template_type") or "promo",
        "objective": brief.get("objective") or alignment.get("objective") or alignment.get("goal"),
        "tone": brief.get("tone") or alignment.get("tone"),
        "copy_density": brief.get("copy_density") or _copy_density_from_copy(merged_copy),
        "assets_available": sorted(assets),
        "copy": merged_copy,
    }


def template_source_drive_id(template: dict[str, Any]) -> str:
    source = template.get("source") if isinstance(template.get("source"), dict) else {}
    return str(source.get("drive_file_id") or template.get("source_drive_file_id") or "").strip()


def is_postcraft_template(template: dict[str, Any]) -> bool:
    return str(template.get("renderer") or "postcraft").strip().lower() == "postcraft"


def available_approved_postcraft_templates(
    manifest: dict[str, Any], resources: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Approved Postcraft templates whose source still exists in the Drive index."""
    resource_ids = {str(resource.get("id") or "").strip() for resource in resources}
    return [
        dict(template)
        for template in manifest.get("templates", [])
        if isinstance(template, dict)
        and template.get("status") == "approved"
        and is_postcraft_template(template)
        and template_source_drive_id(template) in resource_ids
        and bool(template_source_drive_id(template))
    ]


def unavailable_approved_template_details(
    manifest: dict[str, Any], resources: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    resource_ids = {str(resource.get("id") or "").strip() for resource in resources}
    details: list[dict[str, Any]] = []
    for template in manifest.get("templates", []):
        if not isinstance(template, dict) or template.get("status") != "approved":
            continue
        source_id = template_source_drive_id(template)
        reasons: list[str] = []
        if not is_postcraft_template(template):
            reasons.append("renderer is not postcraft")
        if not source_id:
            reasons.append("missing source Drive file ID")
        elif source_id not in resource_ids:
            reasons.append("source Drive file is absent from the current index")
        if reasons:
            details.append({"template_id": template.get("id"), "source_drive_file_id": source_id or None, "reasons": reasons})
    return details


def _available_manifest(manifest: dict[str, Any], resources: list[dict[str, Any]]) -> dict[str, Any]:
    filtered = deepcopy(manifest)
    filtered["templates"] = available_approved_postcraft_templates(manifest, resources)
    return filtered


def _slot_available(slot: str, assets: set[str], copy: dict[str, Any]) -> bool:
    aliases = {
        "body_copy": "body",
        "cta_text": "cta",
        "product_image": "hero_image",
        "hero": "hero_image",
        "brand_mark": "logo",
    }
    normalized = aliases.get(slot, slot)
    if normalized in {"headline", "subheadline", "body", "cta", "caption", "price"}:
        return bool(copy.get(normalized) or copy.get(slot))
    return normalized in assets or slot in assets


def score_template(template: dict[str, Any], context: dict[str, Any]) -> tuple[float, float, list[str], list[str]]:
    """Return score, applicable maximum score, positive reasons, invalid reasons.

    Confidence should measure fit against metadata the approved template actually
    declares. Unspecified optional routing fields (for example tone/objective on
    a simple approved template) should not make a valid template look like a low
    confidence match.
    """
    reasons: list[str] = []
    invalid: list[str] = []
    score = 0.0
    max_score = 0.0

    requested_renderer = str(context.get("renderer") or "postcraft")
    if str(template.get("renderer") or requested_renderer) != requested_renderer:
        invalid.append("renderer mismatch")

    requested_format = _normalize_format(context.get("format"))
    template_format = _normalize_format(template.get("format"))
    if requested_format and template_format:
        max_score += 30
        if requested_format == template_format:
            score += 30
            reasons.append("format match")
        else:
            invalid.append("format mismatch")

    if context.get("content_type") and template.get("content_type"):
        max_score += 15
        if str(context["content_type"]).lower() == str(template["content_type"]).lower():
            score += 15
            reasons.append("content type match")

    objectives = [o.lower() for o in _as_list(template.get("objective_fit"))]
    objective = str(context.get("objective") or "").lower()
    if objective and objectives:
        max_score += 12
        if objective in objectives or any(objective in item or item in objective for item in objectives):
            score += 12
            reasons.append("objective fit")

    tones = [t.lower() for t in _as_list(template.get("tone"))]
    tone = str(context.get("tone") or "").lower()
    if tone and tones:
        max_score += 10
        if tone in tones or any(tone in item or item in tone for item in tones):
            score += 10
            reasons.append("tone fit")

    if context.get("copy_density") and template.get("copy_density"):
        max_score += 8
        if str(context["copy_density"]).lower() == str(template["copy_density"]).lower():
            score += 8
            reasons.append("copy density fit")

    assets = {str(a).strip() for a in _as_list(context.get("assets_available"))}
    copy = context.get("copy") if isinstance(context.get("copy"), dict) else {}
    required_slots = _as_list(template.get("required_slots"))
    missing = [s for s in required_slots if not _slot_available(s, assets, copy)]
    if required_slots:
        max_score += 15
    if missing:
        invalid.append("missing required slots/assets: " + ", ".join(missing))
    elif required_slots:
        score += 15
        reasons.append("required assets available")

    forbidden = [s for s in _as_list(template.get("forbidden_slots")) if _slot_available(s, assets, copy)]
    if forbidden:
        invalid.append("forbidden slot conflict: " + ", ".join(forbidden))

    return score, max_score, reasons, invalid


def _template_tiebreakers(template: dict[str, Any]) -> tuple[float, float]:
    try:
        priority = max(0.0, min(float(template.get("priority") or 0), 10.0))
    except (TypeError, ValueError):
        priority = 0.0
    try:
        performance = max(0.0, min(float(template.get("performance_score") or 0), 1.0))
    except (TypeError, ValueError):
        performance = 0.0
    return priority, performance


def select_template_from_manifest(manifest: dict[str, Any], context: dict[str, Any]) -> TemplateSelection:
    policy = manifest.get("selection_policy") if isinstance(manifest.get("selection_policy"), dict) else DEFAULT_SELECTION_POLICY
    if policy.get("manual_review_required"):
        raise TemplateSelectionError("manual_review_required", "Brand template policy requires manual review.")
    threshold = float(policy.get("confidence_threshold") or DEFAULT_SELECTION_POLICY["confidence_threshold"])
    templates = [t for t in manifest.get("templates", []) if isinstance(t, dict) and t.get("status") == "approved"]
    if not templates:
        raise TemplateSelectionError("no_approved_templates", "No approved Brand Kit templates are available for this brand.")

    candidates: list[tuple[float, float, float, float, dict[str, Any], list[str]]] = []
    invalids: list[dict[str, Any]] = []
    for template in templates:
        score, max_score, reasons, invalid = score_template(template, context)
        if invalid:
            invalids.append({"template_id": template.get("id"), "reasons": invalid})
            continue
        confidence = min(score / max_score, 1.0) if max_score > 0 else 0.0
        priority, performance = _template_tiebreakers(template)
        candidates.append((confidence, priority, performance, score, template, reasons))
    if not candidates:
        raise TemplateSelectionError("no_matching_template", "No approved Brand Kit template fits the requested creative.", details={"invalid_templates": invalids})

    eligible = [candidate for candidate in candidates if candidate[0] >= threshold]
    ranking_key = lambda item: (item[0], item[1], item[2], item[3])
    if not eligible:
        best = max(candidates, key=ranking_key)
        confidence, _priority, _performance, _score, template, reasons = best
        raise TemplateSelectionError(
            "selection_confidence_below_threshold",
            "Best Brand Kit template match is below the brand confidence threshold.",
            details={"best_template_id": template.get("id"), "confidence": round(confidence, 2), "threshold": threshold, "reason": reasons},
        )

    confidence, priority, performance, _score, template, reasons = max(eligible, key=ranking_key)
    selection_reasons = list(reasons)
    if priority:
        selection_reasons.append("brand priority tie-breaker")
    if performance:
        selection_reasons.append("historical performance tie-breaker")
    return TemplateSelection(str(template.get("id")), round(confidence, 2), selection_reasons, template)


async def latest_brand_kit_document(db: AsyncSession, ws: Workspace, brand_id: UUID, *, approved_only: bool = False) -> WorkspaceDocument | None:
    filters = [
        WorkspaceDocument.workspace_id == ws.id,
        WorkspaceDocument.brand_id == brand_id,
        WorkspaceDocument.doc_type == "campaign_brand_kit",
    ]
    if approved_only:
        filters.append(WorkspaceDocument.status == "approved")
    return (await db.execute(
        select(WorkspaceDocument)
        .where(*filters)
        .order_by(WorkspaceDocument.approved_at.desc().nullslast(), WorkspaceDocument.updated_at.desc())
        .limit(1)
    )).scalar_one_or_none()


async def select_brand_kit_template(db: AsyncSession, ws: Workspace, brand_id: UUID, selection_context: dict[str, Any]) -> TemplateSelection:
    doc = await latest_brand_kit_document(db, ws, brand_id, approved_only=True)
    if not doc:
        raise TemplateSelectionError("brand_kit_not_approved", "Approve a Campaign Brand Kit before selecting Brand Kit templates.")
    manifest = _manifest(doc.metadata_json)
    resources = await latest_drive_resources(db, ws, brand_id)
    available_manifest = _available_manifest(manifest, resources)
    if not available_manifest.get("templates"):
        unavailable = unavailable_approved_template_details(manifest, resources)
        if unavailable:
            raise TemplateSelectionError(
                "approved_template_source_unavailable",
                "Approved Brand Kit templates are stale, missing from the current Drive index, or not compatible with Postcraft.",
                details={"unavailable_templates": unavailable},
            )
    return select_template_from_manifest(available_manifest, selection_context)


async def validate_brand_kit_template_id(db: AsyncSession, ws: Workspace, brand_id: UUID, template_id: str) -> TemplateSelection:
    doc = await latest_brand_kit_document(db, ws, brand_id, approved_only=True)
    if not doc:
        raise TemplateSelectionError("brand_kit_not_approved", "Approve a Campaign Brand Kit before using Brand Kit templates.")
    manifest = _manifest(doc.metadata_json)
    resources = await latest_drive_resources(db, ws, brand_id)
    available = available_approved_postcraft_templates(manifest, resources)
    for template in available:
        if str(template.get("id")) == str(template_id):
            return TemplateSelection(str(template_id), 1.0, ["explicit approved Postcraft template with available Drive source"], template)
    matching = next((template for template in manifest.get("templates", []) if isinstance(template, dict) and str(template.get("id")) == str(template_id)), None)
    if matching and matching.get("status") == "approved":
        raise TemplateSelectionError(
            "approved_template_source_unavailable",
            "The approved Brand Kit template is stale, missing from the current Drive index, or not compatible with Postcraft.",
            details={"unavailable_templates": unavailable_approved_template_details({"templates": [matching]}, resources)},
        )
    raise TemplateSelectionError("template_not_approved", "template_id is not an approved Brand Kit template for this brand.")


async def latest_drive_resources(db: AsyncSession, ws: Workspace, brand_id: UUID) -> list[dict[str, Any]]:
    row = (await db.execute(
        select(SocialConnection).where(
            SocialConnection.workspace_id == ws.id,
            SocialConnection.brand_id == brand_id,
            SocialConnection.platform == "google_drive",
            SocialConnection.status.in_(["connected", "needs_reauth"]),
        ).order_by(SocialConnection.created_at.desc()).limit(1)
    )).scalar_one_or_none()
    if not row:
        return []
    meta = row.token_meta_json if isinstance(row.token_meta_json, dict) else {}
    validation = meta.get("imprint_asset_validation") if isinstance(meta.get("imprint_asset_validation"), dict) else {}
    seen: set[str] = set()
    resources: list[dict[str, Any]] = []
    for kind, key, label in RESOURCE_KEYS:
        for item in validation.get(key) or []:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            rid = str(item.get("id"))
            if rid in seen:
                continue
            seen.add(rid)
            resources.append({
                "id": rid,
                "provider": "google_drive",
                "name": item.get("name") or rid,
                "mime_type": item.get("mimeType") or item.get("mime_type"),
                "web_view_link": item.get("webViewLink") or item.get("web_view_link"),
                "resource_type": kind,
                "resource_label": label,
                "validation_key": key,
            })
    return resources


async def list_brand_kit_resources(db: AsyncSession, ws: Workspace, brand_id: UUID) -> dict[str, Any]:
    doc = await latest_brand_kit_document(db, ws, brand_id, approved_only=False)
    manifest = _manifest(doc.metadata_json if doc else None)
    templates_by_drive = {template_source_drive_id(t): t for t in manifest.get("templates", []) if template_source_drive_id(t)}
    resources = await latest_drive_resources(db, ws, brand_id)
    for res in resources:
        tmpl = templates_by_drive.get(str(res.get("id")))
        if tmpl:
            res["classification"] = "template"
            res["template"] = tmpl
        else:
            res["classification"] = res.get("resource_type")
    return {
        "brand_id": str(brand_id),
        "brand_kit_document_id": str(doc.id) if doc else None,
        "template_manifest": manifest,
        "resources": resources,
    }


def _resource_to_template(brand_id: UUID, resource: dict[str, Any], defaults: dict[str, Any] | None = None) -> dict[str, Any]:
    defaults = defaults if isinstance(defaults, dict) else {}
    now = _now_iso()
    template = {
        "id": defaults.get("id") or template_id_for_source(str(resource.get("id") or uuid.uuid4().hex)),
        "brand_id": str(brand_id),
        "source": {
            "provider": "google_drive",
            "drive_file_id": str(resource.get("id") or ""),
            "web_view_link": resource.get("web_view_link"),
        },
        "name": defaults.get("name") or resource.get("name") or "Approved template",
        "status": defaults.get("status") or "draft",
        "renderer": defaults.get("renderer") or "postcraft",
        "format": _normalize_format(defaults.get("format") or "square_feed"),
        "content_type": defaults.get("content_type") or "promo",
        "objective_fit": _as_list(defaults.get("objective_fit")),
        "tone": _as_list(defaults.get("tone")),
        "copy_density": defaults.get("copy_density") or "medium",
        "required_slots": _as_list(defaults.get("required_slots") or ["headline", "logo"]),
        "optional_slots": _as_list(defaults.get("optional_slots") or ["cta"]),
        "forbidden_slots": _as_list(defaults.get("forbidden_slots")),
        "aesthetic_notes": defaults.get("aesthetic_notes") or "",
        "negative_rules": _as_list(defaults.get("negative_rules")),
        "priority": defaults.get("priority") or 0,
        "performance_score": defaults.get("performance_score"),
        "created_at": defaults.get("created_at") or now,
        "updated_at": now,
    }
    for key, value in defaults.items():
        if value is not None and key not in {"source"}:
            template[key] = value
    return template


async def _brand_or_404(db: AsyncSession, ws: Workspace, brand_id: UUID) -> Brand:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id, Brand.workspace_id == ws.id))).scalar_one_or_none()
    if not brand:
        raise TemplateSelectionError("brand_not_found", "Brand not found")
    return brand


async def update_template_manifest(db: AsyncSession, ws: Workspace, brand_id: UUID, updater) -> WorkspaceDocument:
    await _brand_or_404(db, ws, brand_id)
    doc = await latest_brand_kit_document(db, ws, brand_id, approved_only=False)
    if not doc:
        raise TemplateSelectionError("brand_kit_not_found", "Create a Campaign Brand Kit before classifying templates.")
    meta = ensure_template_manifest(doc.metadata_json)
    manifest = meta["template_manifest"]
    updater(manifest)
    doc.metadata_json = meta
    await db.commit()
    await db.refresh(doc)
    return doc


async def classify_brand_kit_resources(db: AsyncSession, ws: Workspace, brand_id: UUID, resource_ids: list[str], classification: str, template_defaults: dict[str, Any] | None = None) -> WorkspaceDocument:
    resources = {str(r.get("id")): r for r in await latest_drive_resources(db, ws, brand_id)}
    missing = [rid for rid in resource_ids if str(rid) not in resources]
    if missing:
        raise TemplateSelectionError("resource_not_found", "One or more Brand Kit resources were not found in the validated Drive folder.", details={"missing_resource_ids": missing})

    def _apply(manifest: dict[str, Any]) -> None:
        existing = [dict(t) for t in manifest.get("templates", []) if isinstance(t, dict)]
        by_id = {str(t.get("id")): t for t in existing if t.get("id")}
        if classification == "template":
            for rid in resource_ids:
                tmpl = _resource_to_template(brand_id, resources[str(rid)], template_defaults)
                old = by_id.get(str(tmpl["id"]))
                if old:
                    old.update({k: v for k, v in tmpl.items() if k not in {"created_at"} or not old.get("created_at")})
                    old["updated_at"] = _now_iso()
                else:
                    existing.append(tmpl)
        else:
            # Non-template classification means it must not be an active approved template.
            ids = {str(rid) for rid in resource_ids}
            for tmpl in existing:
                if template_source_drive_id(tmpl) in ids and tmpl.get("status") == "approved":
                    tmpl["status"] = "inactive"
                    tmpl["updated_at"] = _now_iso()
        manifest["templates"] = existing
    return await update_template_manifest(db, ws, brand_id, _apply)


async def bulk_update_templates(
    db: AsyncSession,
    ws: Workspace,
    brand_id: UUID,
    template_ids: list[str] | None,
    updates: dict[str, Any],
    templates: list[dict[str, Any]] | None = None,
    selection_policy: dict[str, Any] | None = None,
) -> WorkspaceDocument:
    updates = updates if isinstance(updates, dict) else {}
    templates = templates if isinstance(templates, list) else []
    selection_policy = selection_policy if isinstance(selection_policy, dict) else {}
    ids = {str(tid) for tid in (template_ids or [])}
    if updates and not ids:
        raise TemplateSelectionError("template_ids_required", "Bulk template updates require explicit template_ids; implicit update-all is disabled.")

    def _apply(manifest: dict[str, Any]) -> None:
        if selection_policy:
            policy = dict(DEFAULT_SELECTION_POLICY)
            if isinstance(manifest.get("selection_policy"), dict):
                policy.update(manifest["selection_policy"])
            policy.update({k: v for k, v in selection_policy.items() if v is not None})
            manifest["selection_policy"] = policy
        existing = [dict(t) for t in manifest.get("templates", []) if isinstance(t, dict)]
        for tmpl in existing:
            if str(tmpl.get("id")) in ids:
                tmpl.update({k: v for k, v in updates.items() if v is not None})
                tmpl["updated_at"] = _now_iso()
        by_id = {str(t.get("id")): t for t in existing if t.get("id")}
        for incoming in templates:
            if not isinstance(incoming, dict):
                continue
            tid = str(incoming.get("id") or template_id_for_source(template_source_drive_id(incoming) or incoming.get("name") or uuid.uuid4().hex))
            incoming = {**incoming, "id": tid, "brand_id": str(brand_id), "updated_at": _now_iso()}
            incoming.setdefault("created_at", _now_iso())
            incoming.setdefault("renderer", "postcraft")
            incoming.setdefault("status", "draft")
            if tid in by_id:
                by_id[tid].update(incoming)
            else:
                existing.append(incoming)
        manifest["templates"] = existing
    return await update_template_manifest(db, ws, brand_id, _apply)


async def update_one_template(db: AsyncSession, ws: Workspace, brand_id: UUID, template_id: str, updates: dict[str, Any]) -> WorkspaceDocument:
    found = False
    def _apply(manifest: dict[str, Any]) -> None:
        nonlocal found
        for tmpl in manifest.get("templates", []):
            if isinstance(tmpl, dict) and str(tmpl.get("id")) == str(template_id):
                tmpl.update({k: v for k, v in updates.items() if v is not None})
                tmpl["updated_at"] = _now_iso()
                found = True
                break
    doc = await update_template_manifest(db, ws, brand_id, _apply)
    if not found:
        raise TemplateSelectionError("template_not_found", "Brand Kit template not found.")
    return doc
