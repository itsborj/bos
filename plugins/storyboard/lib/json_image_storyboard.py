from __future__ import annotations

import base64
import copy
import io
import json
import logging
import os
import re
import tempfile
import time
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

logger = logging.getLogger("bos.storyboard.codex")

DEFAULT_MODEL = "gpt-image-2"
DEFAULT_SIZE = "1024x1024"
DEFAULT_QUALITY = "auto"
_USER_AGENT = "BOS-storyboard/1.0"

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
# External plugins are mounted read-only in BOS containers. Use a writable runtime
# directory by default; callers may still pass `output_dir`/`out` explicitly.
RUNS_ROOT = Path(os.environ.get("STORYBOARD_RUNS_DIR") or "/var/bos/storyboard-runs")
_AUDIT_DIR = Path(os.environ.get("STORYBOARD_AUDIT_DIR") or "/var/bos/storyboard-audits")

# Use only provider-safe sizes. Map friendly aspect ratios to the nearest valid
# OpenAI Images size instead of emitting unsupported exact dimensions.
_SIZE_MAP = {
    "16:9": "1536x1024",
    "9:16": "1024x1536",
    "1:1": "1024x1024",
    "4:3": "1536x1024",
    "3:4": "1024x1536",
    "4:5": "1024x1536",
    "5:4": "1536x1024",
}

_MAX_STORYBOARD_VIDEO_DURATION_S = 15


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_requested_size(value: Any) -> str:
    raw = str(value or "").strip().lower().replace(" ", "")
    if not raw:
        return DEFAULT_SIZE
    if raw in {"1024x1024", "1536x1024", "1024x1536"}:
        return raw
    if raw in _SIZE_MAP:
        return _SIZE_MAP[raw]
    if raw in {"square"}:
        return "1024x1024"
    if raw in {"portrait", "vertical", "tall"}:
        return "1024x1536"
    if raw in {"landscape", "horizontal", "wide"}:
        return "1536x1024"
    m = re.match(r"^(\d+)x(\d+)$", raw)
    if m:
        w, h = int(m.group(1)), int(m.group(2))
        if not w or not h:
            return DEFAULT_SIZE
        ratio = w / h
        if 0.92 <= ratio <= 1.08:
            return "1024x1024"
        return "1024x1536" if h > w else "1536x1024"
    return DEFAULT_SIZE


def _decode_ref_image(value: Any) -> bytes | None:
    """Decode a reference image value (file path, base64 string, data URL, or attachment dict) to bytes."""
    if not value:
        return None
    if isinstance(value, bytes):
        return value
    # Attachment objects: {"vision_b64": "...", "mime_type": "...", "drive_file_id": "...", ...}
    if isinstance(value, dict):
        for key in ("vision_b64", "image_data_b64", "b64_json", "data", "content"):
            raw = value.get(key)
            if raw and isinstance(raw, str):
                s = raw.strip()
                if s.startswith("data:") and "," in s:
                    s = s.split(",", 1)[1]
                try:
                    return base64.b64decode(s)
                except Exception:
                    continue
        return None
    s = str(value).strip()
    p = Path(s).expanduser()
    if not p.is_absolute():
        candidate = PLUGIN_ROOT / p
        if candidate.exists():
            p = candidate
    if p.exists():
        return p.read_bytes()
    if s.startswith("data:") and "," in s:
        s = s.split(",", 1)[1]
    try:
        return base64.b64decode(s)
    except Exception:
        return None


def _save_brand_refs(raw_refs: list[Any], out_dir: Path) -> list[dict[str, Any]]:
    """Write up to 3 brand reference images to out_dir; return path metadata list."""
    out_dir.mkdir(parents=True, exist_ok=True)
    assets: list[dict[str, Any]] = []
    for idx, value in enumerate(raw_refs[:3], start=1):
        data = _decode_ref_image(value)
        if data is None:
            continue
        dest = out_dir / f"brand_asset_{idx}.png"
        dest.write_bytes(data)
        assets.append({"index": idx, "path": str(dest), "role": "brand_reference"})
    return assets


def save_brand_assets(spec: dict[str, Any], raw_refs: list[Any], out_dir: Path) -> dict[str, Any]:
    """Save up to 3 brand reference images alongside the spec and update spec.brand_assets.

    Call this from create and render modules after the run directory is known.
    The paths stored in spec.brand_assets persist across pipeline stages so
    downstream modules (render, previs-motion) can recover the images without
    requiring the caller to re-supply them.
    """
    assets = _save_brand_refs(raw_refs, out_dir)
    spec = copy.deepcopy(spec)
    existing = spec.get("brand_assets") if isinstance(spec.get("brand_assets"), dict) else {}
    existing["reference_images"] = assets
    existing["count"] = len(assets)
    spec["brand_assets"] = existing
    return spec


def slugify(value: str, fallback: str = "storyboard") -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return slug[:80] or fallback


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _sanitize_for_prompt(value: Any, *, max_string: int = 4000) -> Any:
    """Remove binary/runtime-heavy fields before embedding JSON in prompts."""
    drop_keys = {
        "local", "runtime", "provider_response", "audit",
        "image_data_b64", "source_image_data_b64", "mask_image_data_b64",
        "_image_data_b64", "original_artifact_block", "source_image",
        "reference_images", "brand_guidelines_excerpt", "campaign_brand_kit_excerpt",
        "marketing_reports_excerpt", "campaign_reports_excerpt",
        "competitor_profiles_excerpt", "industry_data_excerpt",
    }
    if isinstance(value, dict):
        return {k: _sanitize_for_prompt(v, max_string=max_string) for k, v in value.items() if k not in drop_keys}
    if isinstance(value, list):
        return [_sanitize_for_prompt(v, max_string=max_string) for v in value]
    if isinstance(value, str) and len(value) > max_string:
        return value[:max_string] + "…[truncated]"
    return value


def compact_spec_for_prompt(spec: dict[str, Any]) -> dict[str, Any]:
    return _sanitize_for_prompt(copy.deepcopy(spec))


def _force_video_reference_style_for_prompt(value: Any) -> Any:
    """Rewrite legacy video-blueprint style metadata for Seedance-safe BW references.

    Persisted specs may contain older full-color/photorealistic phrasing. The
    render prompt must not repeat those conflicting instructions because the
    image becomes Seedance reference media.
    """
    if isinstance(value, dict):
        out = {k: _force_video_reference_style_for_prompt(v) for k, v in value.items()}
        if isinstance(out.get("global_visual_rules"), dict):
            rules = dict(out["global_visual_rules"])
            rules["style"] = "clean black-and-white hand-drawn storyboard/previs reference sheet"
            rules["palette"] = "black, white, and grayscale only; no color in the rendered reference image"
            out["global_visual_rules"] = rules
        return out
    if isinstance(value, list):
        return [_force_video_reference_style_for_prompt(v) for v in value]
    if isinstance(value, str):
        replacements = [
            ("Full-color cinematic storyboard/previs keyframe panel.", "Black-and-white hand-drawn storyboard/previs reference panel."),
            ("cinematic full-color storyboard keyframe frames", "black-and-white hand-drawn storyboard/previs reference frames"),
            ("full-color cinematic previs keyframe style", "black-and-white hand-drawn previs reference style"),
            ("full-color cinematic concept frames", "black-and-white hand-drawn storyboard/previs reference frames"),
            ("full-color previs storyboard/keyframe", "black-and-white hand-drawn storyboard/previs reference"),
            ("full-color continuity", "grayscale continuity"),
            ("full color allowed; use brand/scene color intentionally for video storyboard keyframes", "black, white, and grayscale only; no color in the rendered reference image"),
            ("Color is allowed and preferred by default for video-production storyboard images.", "Black-and-white/grayscale is required by default for video-production storyboard reference images."),
        ]
        out = value
        for old, new in replacements:
            out = out.replace(old, new)
        return out
    return value


def _targeted_prompt_spec(prompt_spec: dict[str, Any]) -> dict[str, Any]:
    targets: set[int] = set()
    cr = prompt_spec.get("change_request") if isinstance(prompt_spec.get("change_request"), dict) else {}
    for edit in cr.get("edits") or []:
        if isinstance(edit, dict):
            try:
                targets.add(int(edit.get("shot_number")))
            except Exception:
                pass
    if not targets:
        return prompt_spec
    reduced = copy.deepcopy(prompt_spec)
    for act in reduced.get("acts") or []:
        if not isinstance(act, dict):
            continue
        shots = act.get("shots") or []
        act["shots"] = [s for s in shots if isinstance(s, dict) and int(s.get("shot_number") or -1) in targets]
        act["shot_context"] = "Only changed shots are included to keep the provider prompt below length limits. Preserve all other shots from the source image and prior approved spec."
    return reduced


STORYBOARD_PROTOTYPE_VISUAL_RULES_BW = """
STORYBOARD PROTOTYPE RENDERING CONTRACT — NON-NEGOTIABLE:
- Output ONE cohesive storyboard sheet/image, not separate standalone marketing images.
- Arrange all shots in clear reading order as connected storyboard panels on the same page; preserve shot order.
- Make the panels feel like one continuous story: consistent characters, location logic, props, wardrobe, scale, camera language, and emotional progression across shots.
- Visual style must be rough conceptual previsualization only: black-and-white hand-drawn pencil/ink storyboard sketches, grayscale values, simple gutters/panel borders.
- Do NOT create polished advertising art, photorealistic images, cinematic color frames, rendered social media creative, posters, logos, typography, or finished campaign visuals.
- Use no color except black/white/grayscale. If brand colors appear in the JSON, treat them as tone/contrast guidance only, not actual color to render.
- Avoid readable text, captions, UI, signage, logos, watermarks, speech bubbles, or baked-in brand marks unless explicitly requested.
""".strip()


STORYBOARD_PROTOTYPE_VISUAL_RULES_COLOR = """
STORYBOARD PREVIS REFERENCE CONTRACT — NON-NEGOTIABLE:
- Output ONE cohesive storyboard/keyframe sheet image, not separate standalone marketing images.
- Arrange all shots in clear reading order as connected storyboard panels on the same page; preserve shot order.
- Make the panels feel like one continuous story: consistent characters, location logic, props, wardrobe, scale, camera language, and emotional progression across shots.
- Default visual style for video-production storyboard references is black-and-white hand-drawn / animatic storyboard previsualization with grayscale values and simple panel gutters.
- Do NOT render photorealistic humans, real-person portraits, stock-photo people, finished ad frames, platform-native captions, posters, or polished campaign layouts. Seedance owns final video realism; this image is only a safe storyboard reference.
- Use no color except black/white/grayscale by default. If brand colors appear in the JSON, treat them as tone/contrast guidance only, not actual color to render, unless the operator explicitly asks for a color storyboard render.
- Avoid readable text, captions, UI, signage, logos, watermarks, speech bubbles, or baked-in brand marks unless explicitly requested.
""".strip()



def build_prompt(spec: dict[str, Any], *, has_source: bool = False, has_mask: bool = False, has_brand_refs: bool = False, ref_count: int = 0, revision_prompt: str | None = None, brand_ref_labels: list[str] | None = None) -> str:
    prompt_spec = compact_spec_for_prompt(spec)
    mode = "localized image edit" if has_source else "new storyboard image generation"
    is_video_blueprint = str(spec.get("artifact_kind") or "") == "video_production_blueprint"
    if is_video_blueprint:
        prompt_spec = _force_video_reference_style_for_prompt(prompt_spec)
    visual_rules = STORYBOARD_PROTOTYPE_VISUAL_RULES_COLOR if is_video_blueprint else STORYBOARD_PROTOTYPE_VISUAL_RULES_BW
    logo_render_style = "rough grayscale storyboard previsualization" if is_video_blueprint else "rough grayscale storyboard previsualization"
    if has_mask:
        mask_note = "A mask is provided. Edit only the transparent/unmasked target area and preserve opaque areas exactly."
    elif has_source and has_brand_refs:
        total = 1 + ref_count
        ref_range = "IMAGE 2" if ref_count == 1 else f"IMAGEs 2–{total}"
        ref_word = "asset" if ref_count == 1 else "assets"
        label_note = ""
        if brand_ref_labels:
            label_note = " Reference labels: " + "; ".join(f"IMAGE {i + 2}: {label}" for i, label in enumerate(brand_ref_labels[:ref_count])) + "."
        mask_note = (
            f"You are given {total} images. "
            f"IMAGE 1 is the source storyboard — edit this image and output the revised storyboard. "
            f"{ref_range} {'is a reference' if ref_count == 1 else 'are reference'} {ref_word} — "
            f"use {'it' if ref_count == 1 else 'them'} as specified in the REVISION INSTRUCTION below."
            f"{label_note}"
        )
    elif has_source:
        delta_ref = "the REVISION INSTRUCTION below" if revision_prompt else "the requested storyboard delta"
        mask_note = f"No mask is provided. Treat the source image as the previous approved render; preserve it as much as possible and apply only {delta_ref}."
    elif has_brand_refs:
        label_note = ""
        if brand_ref_labels:
            label_note = " Reference labels: " + "; ".join(f"IMAGE {i + 1}: {label}" for i, label in enumerate(brand_ref_labels[:ref_count])) + "."
        mask_note = (
            f"You are given {ref_count} reference image{'s' if ref_count > 1 else ''}. "
            + "These are brand asset references (logo, hero image, or visual inspiration). "
            + "Use them for brand identity context only unless the SOURCE STORYBOARD TEXT or JSON spec explicitly requests a logo/branded material in a panel. "
            + f"When a logo is explicitly requested, use the official logo reference as the identity anchor, rendered as {logo_render_style} rather than polished advertising art. "
            + ("Create a fresh black-and-white hand-drawn storyboard/previs reference per the rendering contract below." if is_video_blueprint else "Create a fresh black-and-white hand-drawn storyboard prototype per the rendering contract below.")
            + f"{label_note}"
        )
    else:
        mask_note = ""

    revision_block = (
        f"REVISION INSTRUCTION (authoritative — written by the operator with full context of the current storyboard):\n{revision_prompt}"
        if revision_prompt else ""
    )

    def assemble(ps: dict[str, Any]) -> str:
        source_text = str(ps.get("source_storyboard_text") or "").strip()
        parts = [f"You are generating a storyboard prototype image from a structured JSON art direction document.\n\nMODE: {mode}"]
        if mask_note:
            parts.append(mask_note)
        parts.append(visual_rules)
        if revision_block:
            parts.append(revision_block)
        # CMO-authored storyboard text is the primary creative instruction.
        # The JSON spec provides metadata (shot count, style, tone, locked elements)
        # but the actual panel descriptions come from this text.
        if source_text:
            source_scope = (
                "This is authoritative for shot content, order, timing, camera, and intent only; the black-and-white storyboard reference contract above overrides any full-color, photorealistic, or finished-ad styling language in the source text. "
                if is_video_blueprint else
                "This describes every panel in natural language. Use this as the primary instruction for what to draw in each panel. "
            )
            parts.append(
                "SOURCE STORYBOARD TEXT (authoritative — written by the creative operator. "
                + source_scope
                + "):\n" + source_text
            )
        delta_src = "the REVISION INSTRUCTION above" if revision_block else "the `change_request` in the JSON spec"
        source_ref = "The SOURCE STORYBOARD TEXT above is the narrative/shot source of truth — render each panel exactly as described." if source_text else "The `image_prompt` field in each shot below describes what to render."
        parts.append(
            "CRITICAL STORYBOARD RULES:\n"
            + f"1. {source_ref}\n"
            + f"2. Preserve every item in `locked_elements`, global visual rules, scene/act metadata, and unchanged shots unless {delta_src} says otherwise.\n"
            + f"3. Apply only the requested delta from {delta_src}.\n"
            + "4. For revisions, keep stable sections unchanged and respect shot order exactly.\n"
            + "5. Do not invent readable text, fake labels, random logos, watermarks, captions, UI text, or signage unless explicitly requested.\n"
            + ("6. Keep composition, camera, lighting, grayscale palette, style, and emotional tone stable across versions; do not render photorealistic people or full-color finished frames.\n" if is_video_blueprint else "6. Keep composition, camera, lighting, palette, style, and emotional tone stable across versions; palette means grayscale contrast only.\n")
            + "7. If editing a source image, treat it as the previous approved render and preserve identity/geometry outside the requested change.\n"
            + "8. Important constraints may appear in `image_prompt`, `composition`, `must_include`, and `must_avoid`; obey them only when they do not conflict with the prototype contract.\n"
            + "9. Final output should read as a director/agency storyboard board: multiple connected hand-sketched panels on one page, not isolated unrelated illustrations."
        )
        parts.append(f"JSON_SPEC (supplementary metadata — shot count, style, tone, locked elements):\n{json.dumps(ps, indent=2, ensure_ascii=False)}")
        return "\n\n".join(parts).strip()

    prompt = assemble(prompt_spec)
    if len(prompt) > 32000:
        prompt = assemble(_targeted_prompt_spec(prompt_spec))
    if len(prompt) > 32000:
        # Last-resort safety: preserve the control fields and truncate only the
        # JSON serialization so OpenAI never rejects for prompt length.
        prompt = prompt[:31900] + "\n…[prompt truncated to provider limit]"
    return prompt


def _decode_inline_text_value(value: str) -> str:
    """Decode hidden single-line RUN params that carry literal newline escapes."""
    text = str(value or "")
    text = text.strip().strip('"\'')
    return text.replace("\\n", "\n").replace("\\t", "\t")



def _ensure_blueprint_revised_section(text: str, revision_note: str | None = None) -> str:
    """Ensure storyboard/blueprint text has a Revised section.

    If a revision note is supplied, preserve it even when an existing `## Revised`
    section already says the default "No revisions requested yet." This prevents
    review-thread feedback from disappearing before render.
    """
    raw = str(text or "").strip()
    if not raw:
        return ""
    note = revision_note.strip() if revision_note and revision_note.strip() else ""
    existing_heading = re.search(r"^\s*#{1,6}\s+revised\s*$", raw, re.IGNORECASE | re.MULTILINE)
    if existing_heading:
        if not note:
            return raw.rstrip() + "\n"
        section_start = existing_heading.end()
        next_heading = re.search(r"\n\s*#{1,6}\s+\S", raw[section_start:], re.MULTILINE)
        section_end = section_start + next_heading.start() if next_heading else len(raw)
        existing_body = raw[section_start:section_end].strip()
        if note.lower() in existing_body.lower():
            return raw.rstrip() + "\n"
        existing_body = re.sub(r"(?im)^\s*-\s*No revisions requested yet\.?\s*$", "", existing_body).strip()
        replacement = (existing_body + "\n" if existing_body else "") + f"- {note}"
        return raw[:section_start].rstrip() + "\n" + replacement.rstrip() + "\n" + raw[section_end:].lstrip("\n")
    revised_body = note or "No revisions requested yet."
    section = f"\n\n## Revised\n- {revised_body}\n"
    checklist = re.search(r"^\s*#{1,6}\s+approval\s+checklist\s*$", raw, re.IGNORECASE | re.MULTILINE)
    if not checklist:
        return raw.rstrip() + section
    next_heading = re.search(r"\n\s*#{1,6}\s+\S", raw[checklist.end():], re.MULTILINE)
    if not next_heading:
        return raw.rstrip() + section
    insert_at = checklist.end() + next_heading.start()
    return raw[:insert_at].rstrip() + section + raw[insert_at:].lstrip("\n")



def _storyboard_text_from_conversation(value: str) -> str:
    """Extract the latest CMO-authored storyboard from chat history."""
    text = value or ""
    if not text:
        return ""
    parts = re.split(r"\n(?=(?:USER|ASSISTANT|AI|CMO):)", text)
    for part in reversed(parts):
        upper = part[:20].upper()
        if not (upper.startswith("ASSISTANT:") or upper.startswith("AI:") or upper.startswith("CMO:")):
            continue
        body = part.split(":", 1)[1].strip() if ":" in part else part.strip()
        if re.search(r"\b(storyboard|shot list|shot\s*\d+)|\*\*\s*\d+[.)]", body, re.IGNORECASE):
            return body
    return ""



def _title_from_storyboard_text(text: str) -> str:
    raw = (text or "").strip()
    patterns = (
        r"^\s*#\s+(.+?)\s*$",
        r"^\s*#+\s*\*\*(.+?)\*\*\s*$",
        r"^\s*\*\*Title:\*\*\s*(.+?)\s*$",
        r"^\s*Title:\s*(.+?)\s*$",
    )
    for pattern in patterns:
        m = re.search(pattern, raw, re.IGNORECASE | re.MULTILINE)
        if m:
            return re.sub(r"[*_`#]", "", m.group(1)).strip()
    return ""



def _shots_from_storyboard_text(text: str, style: str, tone: str, panel_count: int | None = None, *, colorized: bool = False) -> list[dict[str, Any]]:
    """Return placeholder shots that defer to source_storyboard_text.

    The CMO's natural-language storyboard text is the source of truth.
    Regex-parsing it into structured shots is inherently lossy — the image
    model (GPT-4o, Gemini) interprets the original text directly via
    source_storyboard_text in build_prompt().

    This function exists only to satisfy the spec schema (acts[0].shots must
    be non-empty). The actual panel descriptions come from source_storyboard_text.
    """
    raw = (text or "").strip()
    if not raw:
        return []
    if panel_count is not None:
        count = min(max(1, panel_count), 24)
    else:
        # Count explicit story beats to determine placeholder shot count.
        # Do not invent a fixed default panel count; if the CMO sent only a
        # paragraph summary, keep one placeholder and let the quality gate force
        # a fuller, structured retry.
        panel_matches = re.findall(r"(?:scene|shot|panel)\s*[*_`~]*\s*(\d+)\b", raw, re.IGNORECASE)
        table_matches = []
        for line in raw.splitlines():
            stripped = line.strip()
            if stripped.startswith("|") and stripped.endswith("|"):
                cells = [cell.strip() for cell in stripped.strip("|").split("|")]
                first = re.sub(r"[*_`~]", "", cells[0]).strip() if cells else ""
                if re.match(r"^\d+[A-Za-z]?\b", first) or re.search(r"\b(?:shot|panel|scene)\s*\d+\b", first, re.IGNORECASE):
                    table_matches.append(first)
        numbered_matches = re.findall(r"(?:^|\n)\s*\d+[.)]\s+", raw)
        count = len(panel_matches) or len(table_matches) or len(numbered_matches) or 1
    panel_prompt = (
        "Full-color cinematic storyboard/previs keyframe panel"
        if colorized else
        "Black-and-white hand-drawn storyboard prototype panel"
    )
    panel_style = "full-color previs keyframe style" if colorized else "black-and-white hand-drawn prototype style"
    must_avoid = ["random logos", "watermarks", "off-brief style", "unrequested clutter", "photorealism", "polished advertising art", "finished social media creative"]
    if not colorized:
        must_avoid.insert(4, "color")
    return [
        {
            "shot_number": i,
            "title": f"Panel {i}",
            "image_prompt": f"{panel_prompt} {i}. {style}. Render this panel exactly as described in the storyboard text. No unintended readable text or logos." + ("" if colorized else " No color, no photorealistic finish, no polished advertising art."),
            "composition": "Render exactly as described in the storyboard text.",
            "action": f"Panel {i} — see storyboard text for full description.",
            "emotional_intent": tone,
            "must_include": [f"Panel {i} as described in storyboard text", "consistent visual style", panel_style],
            "must_avoid": must_avoid,
        }
        for i in range(1, count + 1)
    ]



def _looks_like_video_blueprint(text: str, brief: dict[str, Any]) -> bool:
    """Heuristic for tagging text storyboard artifacts that are video production blueprints."""
    explicit_kind = str(brief.get("artifact_kind") or brief.get("kind") or "").lower().strip()
    if explicit_kind in {"storyboard", "storyboard_draft", "image_storyboard"}:
        return False
    if explicit_kind in {"video_production_blueprint", "production_blueprint"}:
        return True
    if any(brief.get(k) for k in ("video_prompt", "screenplay", "voiceover", "cta", "platform", "duration", "duration_seconds")):
        return True
    lowered = text.lower()
    signals = ("script", "screenplay", "voiceover", "on-screen text", "cta", "shot", "camera", "motion", "duration", "reel", "short", "video")
    return sum(1 for s in signals if s in lowered) >= 3


def _markdown_sections(text: str) -> dict[str, str]:
    """Best-effort section extraction for the blueprint artifact renderer/UI."""
    sections: dict[str, list[str]] = {}
    current = "overview"
    sections[current] = []
    for line in (text or "").splitlines():
        if re.match(r"^\s*-{3,}\s*$", line):
            continue
        m = re.match(r"^#{1,3}\s+(.+?)\s*$", line)
        if not m:
            m = re.match(r"^\*\*\s*(?:\d+[.)]\s*)?(.+?)\s*\*\*\s*$", line)
        if m:
            heading = re.sub(r"[^a-z0-9]+", "_", m.group(1).strip().lower()).strip("_") or "section"
            current = heading
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return {k: "\n".join(v).strip() for k, v in sections.items() if "\n".join(v).strip()}


def _extract_markdown_tables(text: str) -> list[str]:
    tables: list[str] = []
    current: list[str] = []
    for line in (text or "").splitlines():
        if line.strip().startswith("|") and line.strip().endswith("|"):
            current.append(line)
        elif current:
            if len(current) >= 2:
                tables.append("\n".join(current))
            current = []
    if current and len(current) >= 2:
        tables.append("\n".join(current))
    return tables


def _split_md_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _norm_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _shots_from_blueprint_table(text: str, style: str, tone: str, *, colorized: bool = False) -> list[dict[str, Any]]:
    """Parse the screenplay table into storyboard shots for downstream render/previs."""
    for table in _extract_markdown_tables(text):
        rows = [r for r in table.splitlines() if r.strip().startswith("|")]
        if len(rows) < 3:
            continue
        headers = [_norm_header(h) for h in _split_md_row(rows[0])]
        if not any("visual" in h or "action" in h for h in headers):
            continue
        shots: list[dict[str, Any]] = []
        for raw in rows[2:]:
            if re.match(r"^\s*\|?\s*:?-{2,}:?", raw):
                continue
            cells = _split_md_row(raw)
            if len(cells) < 3:
                continue
            data = {headers[i]: cells[i] for i in range(min(len(headers), len(cells)))}
            shot_no_raw = next((data.get(k) for k in ("shot", "scene", "number") if data.get(k)), str(len(shots) + 1))
            try:
                shot_no = int(re.sub(r"\D+", "", shot_no_raw) or len(shots) + 1)
            except Exception:
                shot_no = len(shots) + 1
            time_value = next((data.get(k) for k in ("time", "timing", "duration") if data.get(k)), "")
            script_value = next((data.get(k) for k in ("script_audio", "audio", "script", "voiceover_dialogue") if data.get(k)), "")
            text_value = next((data.get(k) for k in ("on_screen_text", "text", "caption") if data.get(k)), "")
            visual_value = next((data.get(k) for k in ("visual_action", "visual", "action") if data.get(k)), "")
            camera_value = next((data.get(k) for k in ("camera_motion", "camera", "motion") if data.get(k)), "")
            constraints_value = next((data.get(k) for k in ("assets_constraints", "asset_notes", "constraints", "assets") if data.get(k)), "")
            action = visual_value or script_value or text_value or f"Shot {shot_no} visual action"
            shots.append({
                "shot_number": shot_no,
                "title": f"Shot {shot_no}" + (f" — {time_value}" if time_value else ""),
                "time": time_value,
                "script_audio": script_value,
                "on_screen_text": text_value,
                "image_prompt": (("Full-color cinematic storyboard/previs keyframe panel. " if colorized else "Black-and-white hand-drawn storyboard prototype panel. ") + f"{style}. {action}. Camera/motion: {camera_value or 'clear simple composition'}. No unintended readable text or logos."),
                "composition": camera_value or "Clear storyboard panel composition with strong subject placement and minimal clutter.",
                "action": action,
                "emotional_intent": tone,
                "must_include": [x for x in [action, constraints_value] if x],
                "must_avoid": ["unapproved claims", "random logos", "watermarks", "off-brief style", "unrequested clutter"],
            })
        if shots:
            return shots[:24]
    return []


def _build_production_blueprint(text: str, brief: dict[str, Any]) -> dict[str, Any]:
    sections = _markdown_sections(text)
    script = "\n\n".join(
        v for k, v in sections.items()
        if any(token in k for token in ("script", "voiceover", "dialogue"))
    ).strip()
    screenplay = "\n\n".join(
        v for k, v in sections.items()
        if any(token in k for token in ("screenplay", "text_storyboard", "storyboard", "shot"))
    ).strip()
    checklist = "\n\n".join(
        v for k, v in sections.items()
        if "checklist" in k or "approval" in k
    ).strip()
    revised = "\n\n".join(
        v for k, v in sections.items()
        if "revised" in k or "revision" in k
    ).strip()
    return {
        "source_text": text,
        "script": script,
        "screenplay": screenplay,
        "text_storyboard": screenplay,
        "approval_checklist": checklist,
        "revised": revised,
        "tables": _extract_markdown_tables(text),
        "sections": sections,
        "metadata": {
            "platform": brief.get("platform") or brief.get("channel"),
            "duration_seconds": _coerce_duration_seconds(brief.get("duration_seconds") or brief.get("duration")),
            "aspect_ratio": brief.get("aspect_ratio"),
            "cta": brief.get("cta"),
        },
        "sections_expected": ["script", "screenplay", "text_storyboard", "approval_checklist", "revised"],
        "approval_gate": "production_blueprint_approved_before_previs",
        "previs_role": "final_cut_candidate",
    }


def _first_nonempty(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _single_line(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _extract_labeled_value(text: str, *labels: str) -> str:
    raw = str(text or "")
    for label in labels:
        esc = re.escape(label)
        patterns = [
            rf"^\s*[-*]?\s*\*\*{esc}\s*:\*\*\s*([^\n]+?)\s*$",
            rf"^\s*[-*]?\s*{esc}:\s*([^\n]+?)\s*$",
            rf"^\s*#+\s*{esc}\s*$\n(.+?)(?=\n#|\Z)",
        ]
        for pattern in patterns:
            m = re.search(pattern, raw, re.IGNORECASE | re.MULTILINE | re.DOTALL)
            if m:
                value = _single_line(m.group(1))
                if value:
                    return value
    return ""


def _extract_creator_shot_notes(text: str) -> list[dict[str, str]]:
    raw = str(text or "")
    out: list[dict[str, str]] = []
    blocks = list(re.finditer(r"(?:^|\n)\s*(?:#{1,6}\s*)?(?:\*\*)?(?:beat|shot|scene|panel)\s*[*_`~]*\s*\d+.*$", raw, re.IGNORECASE | re.MULTILINE))
    if blocks:
        for idx, match in enumerate(blocks):
            start = match.start()
            end = blocks[idx + 1].start() if idx + 1 < len(blocks) else len(raw)
            block = raw[start:end]
            out.append({
                "visual": _extract_labeled_value(block, "Visual", "Visual Action", "Visual / action"),
                "camera": _extract_labeled_value(block, "Camera", "Camera Composition", "Camera / motion"),
                "script": _extract_labeled_value(block, "Script", "Script / audio", "Copy"),
                "text": _extract_labeled_value(block, "On-Screen Text", "On-screen text", "Caption"),
                "emotion": _extract_labeled_value(block, "Emotion", "Emotion being surfaced"),
                "constraints": _extract_labeled_value(block, "Assets/Constraints", "Assets / constraints", "Constraints", "Assets"),
            })
        return [note for note in out if any(note.values())]

    for table in _extract_markdown_tables(raw):
        rows = [r for r in table.splitlines() if r.strip().startswith("|")]
        if len(rows) < 3:
            continue
        headers = [_norm_header(h) for h in _split_md_row(rows[0])]
        if not any("visual" in h or "action" in h for h in headers):
            continue
        notes: list[dict[str, str]] = []
        for row in rows[2:]:
            if re.match(r"^\s*\|?\s*:?-{2,}:?", row):
                continue
            cells = _split_md_row(row)
            data = {headers[i]: cells[i] for i in range(min(len(headers), len(cells)))}
            notes.append({
                "visual": _first_nonempty(data.get("visual_action"), data.get("visual"), data.get("action")),
                "camera": _first_nonempty(data.get("camera_motion"), data.get("camera"), data.get("motion")),
                "script": _first_nonempty(data.get("script_audio"), data.get("audio"), data.get("script"), data.get("voiceover_dialogue")),
                "text": _first_nonempty(data.get("on_screen_text"), data.get("text"), data.get("caption")),
                "emotion": "",
                "constraints": _first_nonempty(data.get("assets_constraints"), data.get("asset_notes"), data.get("constraints"), data.get("assets")),
            })
        if notes:
            return notes
    return []


def _select_three_beats(notes: list[dict[str, str]]) -> list[dict[str, str]]:
    cleaned = [n for n in notes if any(_single_line(v) for v in n.values())]
    if not cleaned:
        return [{}, {}, {}]
    if len(cleaned) == 1:
        return [cleaned[0], cleaned[0], cleaned[0]]
    if len(cleaned) == 2:
        return [cleaned[0], cleaned[1], cleaned[1]]
    return [cleaned[0], cleaned[len(cleaned) // 2], cleaned[-1]]


def _extract_contact_point(text: str, brand_name: str = "") -> str:
    raw = str(text or "")
    for pattern in (
        r"https?://\S+",
        r"www\.\S+",
        r"@[A-Za-z0-9_.]+",
        r"\+?\d[\d\s().-]{6,}\d",
    ):
        m = re.search(pattern, raw)
        if m:
            return m.group(0)
    return brand_name.strip() or "your primary contact point"


def _extract_primary_verb(text: str) -> str:
    lowered = _single_line(text).lower()
    for verb in ("book", "call", "visit", "learn", "message", "apply", "shop", "download", "start", "reserve"):
        if re.search(rf"\b{verb}\b", lowered):
            return verb.capitalize()
    return "Visit"


def _infer_existing_tension(brief: dict[str, Any], raw_text: str, audience: str, objective: str, offer: str) -> str:
    explicit = _first_nonempty(
        brief.get("existing_tension"),
        brief.get("audience_tension"),
        _extract_labeled_value(raw_text, "Existing Tension", "Tension", "Dominant Tension"),
    )
    if explicit:
        return explicit
    text = _single_line(" ".join(x for x in (raw_text, audience, objective, offer) if x)).lower()
    if "ofw" in text or "seafarer" in text or "far from home" in text:
        return "distance guilt about not being there when family needs them most"
    if "trusted connector" in text or "referral" in text or "community leader" in text:
        return "the pressure to guide families toward a dignified next step without making grief feel transactional"
    if any(token in text for token in ("plan ahead", "pre-need", "prepare", "preparedness", "unprepared")):
        return "the fear of leaving loved ones unprepared when a hard moment comes"
    if any(token in text for token in ("memorial", "garden", "columbarium", "resting place")):
        return "the quiet fear of making end-of-life decisions too late"
    return "the unresolved emotional pressure this offer is meant to relieve"


def _infer_resolution_mechanism(brief: dict[str, Any], raw_text: str, offer: str, brand_name: str) -> str:
    explicit = _first_nonempty(
        brief.get("resolution_mechanism"),
        brief.get("solution_mechanism"),
        _extract_labeled_value(raw_text, "Resolution Mechanism", "Resolution", "Solution"),
    )
    if explicit:
        return explicit
    anchor = _first_nonempty(offer, brand_name, "the offer")
    return f"{anchor} turns uncertainty into a concrete, dignified next step the audience can act on now."


def _summarize_15s_cuts(raw_text: str, notes: list[dict[str, str]], audience: str, offer: str) -> list[str]:
    cuts: list[str] = []
    if len(notes) > 3:
        cuts.append(f"Reduced {len(notes)} scene beats to the 3-beat 15-second structure so the ad lands as one tension, one resolution, and one action.")
    if re.search(r"\b(feature|benefit|package|options|services|products)\b", raw_text, re.IGNORECASE):
        cuts.append("Secondary features, package details, and benefit lists were cut so Beat 2 resolves only one dominant tension.")
    if audience and any(sep in audience for sep in ("\n-", ";", ",", " and ")):
        cuts.append("Multiple audience nuances were collapsed into one dominant emotional state so the hook lands immediately.")
    if offer and any(sep in offer for sep in ("/", ",", " and ")):
        cuts.append("Multiple offer angles were collapsed into one visible resolution mechanism to avoid a crowded middle beat.")
    if not cuts:
        cuts.append("No extra story branches were kept; the blueprint was trimmed to one tension, one resolution, and one action by default.")
    return cuts[:4]


def _is_creator_owned_15s_blueprint(text: str) -> bool:
    lowered = str(text or "").lower()
    required = (
        "tension statement",
        "beat 1",
        "beat 2",
        "beat 3",
        "what was cut and why",
        "sound-on / sound-off audit",
    )
    return all(token in lowered for token in required)


def _compose_creator_owned_15s_blueprint(raw_text: str, brief: dict[str, Any], *, title: str, aspect_ratio: str, duration_seconds: int, style: str) -> str:
    raw = _decode_inline_text_value(raw_text).strip()
    if _is_creator_owned_15s_blueprint(raw):
        return _ensure_blueprint_revised_section(raw)

    audience = _first_nonempty(brief.get("audience"), _extract_labeled_value(raw, "Audience"), "TBD audience")
    offer = _first_nonempty(
        brief.get("product_service"),
        brief.get("offer"),
        brief.get("service"),
        brief.get("product"),
        _extract_labeled_value(raw, "Offer", "Product / Service", "Product", "Service"),
        brief.get("cta"),
        "TBD offer",
    )
    objective = _first_nonempty(brief.get("objective"), _extract_labeled_value(raw, "Objective"), raw.splitlines()[0] if raw else "TBD objective")
    platform = _first_nonempty(brief.get("platform"), brief.get("channel"), _extract_labeled_value(raw, "Platform / format", "Platform"), "TBD platform")
    cta_goal = _first_nonempty(brief.get("cta_goal"), brief.get("cta"), _extract_labeled_value(raw, "Call to Action", "CTA Goal", "CTA"), "Prompt one immediate next step.")
    brand_name = _first_nonempty(brief.get("brand_name"), _extract_labeled_value(raw, "Brand"))
    existing_tension = _infer_existing_tension(brief, raw, audience, objective, offer)
    resolution_mechanism = _infer_resolution_mechanism(brief, raw, offer, brand_name)
    notes = _extract_creator_shot_notes(raw)
    beat_notes = _select_three_beats(notes)

    beat1_visual = _first_nonempty(beat_notes[0].get("visual"), "One immediate image that surfaces the audience tension without setup.")
    beat1_camera = _first_nonempty(beat_notes[0].get("camera"), "Single readable frame; no establishing detour.")
    beat1_copy = _first_nonempty(beat_notes[0].get("text"), beat_notes[0].get("script"), _extract_labeled_value(raw, "Hook"), existing_tension.capitalize())
    beat1_emotion = _first_nonempty(beat_notes[0].get("emotion"), existing_tension)

    beat2_visual = _first_nonempty(beat_notes[1].get("visual"), f"Show {offer} arriving as the answer to that tension.")
    beat2_camera = _first_nonempty(beat_notes[1].get("camera"), "One clean shift that makes the resolution legible fast.")
    beat2_copy = _first_nonempty(beat_notes[1].get("text"), beat_notes[1].get("script"), resolution_mechanism)
    beat2_emotion = _first_nonempty(beat_notes[1].get("emotion"), "relief and clarity")

    contact_point = _extract_contact_point(_first_nonempty(brief.get("contact_point"), cta_goal, raw), brand_name=brand_name)
    cta_verb = _extract_primary_verb(_first_nonempty(cta_goal, raw))
    beat3_copy = f"{cta_verb} {contact_point}".strip()
    beat3_visual = _first_nonempty(beat_notes[2].get("visual"), f"Simple branded CTA frame anchored on {contact_point}.")
    beat3_camera = _first_nonempty(beat_notes[2].get("camera"), "Static closing frame with one clear action.")
    beat3_constraints = _first_nonempty(beat_notes[2].get("constraints"), "One verb plus one contact point only; brand identifier only if it fits.")
    cuts = _summarize_15s_cuts(raw, notes, audience, offer)
    works_without_audio = "Yes — the progression is legible from the visual shift plus on-screen text beats."
    if not beat1_copy and not beat2_copy:
        works_without_audio = "No — add stronger on-screen text overlays before approval so the emotional movement lands without sound."

    lines = [
        f"# {title}",
        "",
        "**Format law:** 15-second hard cap — 1 tension / 1 resolution / 1 action.",
        f"**Platform / format:** {platform} / {aspect_ratio} / {duration_seconds}s max",
        f"**Creative direction:** {style}",
        f"**Audience:** {audience}",
        f"**Product / service:** {offer}",
        f"**Existing tension:** {existing_tension}",
        f"**Resolution mechanism:** {resolution_mechanism}",
        f"**CTA goal:** {cta_goal}",
        "",
        "## Tension Statement",
        f"{audience} already feels {existing_tension} before this video starts.",
        "",
        "## Beat Breakdown",
        "",
        "### Beat 1 — Hook (0–4s)",
        f"- **Visual:** {beat1_visual}",
        f"- **Copy:** {beat1_copy}",
        f"- **Emotion being surfaced:** {beat1_emotion}",
        "- **Why the viewer stops scrolling:** It surfaces a tension the audience already carries instead of spending time on setup.",
        "",
        "### Beat 2 — Shift (4–11s)",
        f"- **Visual:** {beat2_visual}",
        f"- **Copy:** {beat2_copy}",
        f"- **What the product/service is doing structurally:** {resolution_mechanism}",
        f"- **What the viewer now feels:** {beat2_emotion}",
        "",
        "### Beat 3 — CTA (11–15s)",
        f"- **Copy:** {beat3_copy}",
        f"- **Why this specific verb:** '{cta_verb}' keeps the ending to one action the viewer can take immediately.",
        "",
        "## Script",
        f"- **Hook:** {beat1_copy}",
        f"- **Voiceover / dialogue:** {beat1_copy} → {beat2_copy} → {beat3_copy}",
        f"- **On-screen text beats:** {beat1_copy} / {beat2_copy} / {beat3_copy}",
        f"- **CTA:** {beat3_copy}",
        f"- **Claims / compliance notes:** {_first_nonempty(brief.get('claims_notes'), brief.get('compliance_notes'), 'No unapproved claims. Keep the language concrete and restrained.')}",
        "",
        "## Screenplay / Text Storyboard",
        "| Shot | Time | Script / audio | On-screen text | Visual / action | Camera / motion | Assets / constraints |",
        "|---|---:|---|---|---|---|---|",
        f"| 01 | 0–4s | {beat1_copy} | {beat1_copy} | {beat1_visual} | {beat1_camera} | {_first_nonempty(beat_notes[0].get('constraints'), 'No setup scene. Surface the tension immediately.') } |",
        f"| 02 | 4–11s | {beat2_copy} | {beat2_copy} | {beat2_visual} | {beat2_camera} | {_first_nonempty(beat_notes[1].get('constraints'), 'Show one resolution mechanism only. No feature list.') } |",
        f"| 03 | 11–15s | {beat3_copy} | {beat3_copy} | {beat3_visual} | {beat3_camera} | {beat3_constraints} |",
        "",
        "## What Was Cut And Why",
    ]
    lines.extend([f"- {item}" for item in cuts])
    lines.extend([
        "",
        "## Sound-On / Sound-Off Audit",
        f"- **Works without audio:** {works_without_audio}",
        "- **If audio is absent:** Keep the same three on-screen text beats and do not add extra explanatory copy.",
        "",
        "## Approval checklist",
        "- 15-second hard cap respected",
        "- One tension / one resolution / one action only",
        "- Message/claims approved",
        "- Scene order and timing approved",
        "- Sound-off legibility approved",
        "- Ready for storyboard image generation after approval",
        "",
        "## Revised",
        "- No revisions requested yet.",
        "",
    ])
    return "\n".join(lines)


def make_storyboard_spec(brief: dict[str, Any]) -> dict[str, Any]:
    """Create a JSON-first storyboard spec from a brief without calling an LLM.

    This is intentionally conservative: BOS/CMO can pass a richer spec when one is
    available. This helper gives the plugin a valid, auditable baseline artifact.
    """
    requested_duration_seconds = _coerce_duration_seconds(brief.get("duration_seconds") or brief.get("duration"))
    conversation_storyboard = _storyboard_text_from_conversation(str(brief.get("conversation_context") or ""))
    message = _decode_inline_text_value(str(brief.get("storyboard_text") or brief.get("body_markdown") or brief.get("script") or brief.get("outline") or brief.get("concept") or "").strip())
    title = str(brief.get("title") or brief.get("project_title") or _title_from_storyboard_text(message) or brief.get("brand_name") or "Untitled Storyboard").strip()
    fallback_message = str(brief.get("message") or "").strip()
    if not message:
        if conversation_storyboard and (not fallback_message or len(fallback_message.split()) <= 8):
            message = conversation_storyboard
        else:
            message = fallback_message
    revision_note = _first_nonempty(
        brief.get("revision_feedback"),
        brief.get("edit_instruction"),
        brief.get("feedback"),
        brief.get("revision_prompt"),
    )

    aspect_ratio = str(brief.get("aspect_ratio") or "16:9").strip()
    tone = str(brief.get("tone") or "clear, cinematic, emotionally readable").strip()
    panel_count: int | None = None
    try:
        raw_pc = brief.get("panel_count")
        if raw_pc is not None:
            panel_count = min(max(1, int(raw_pc)), 24)
    except (TypeError, ValueError):
        pass
    explicit_kind = str(brief.get("artifact_kind") or brief.get("kind") or "").lower().strip()
    style = str(brief.get("visual_style") or brief.get("style") or ("clean black-and-white hand-drawn storyboard/previs reference sheet" if explicit_kind in {"video_production_blueprint", "production_blueprint"} else "clean black-and-white hand-drawn storyboard prototype sketch")).strip()
    creator_owned_video_request = (
        explicit_kind in {"video_production_blueprint", "production_blueprint"}
        or bool(brief.get("duration") or brief.get("duration_seconds"))
        or bool(brief.get("existing_tension") or brief.get("resolution_mechanism") or brief.get("cta_goal") or brief.get("contact_point"))
        or any(token in _single_line(brief.get("format") or "").lower() for token in ("video", "reel", "short"))
    )
    is_video_blueprint = _looks_like_video_blueprint(message, brief)
    if is_video_blueprint and creator_owned_video_request:
        requested_duration_seconds = min(requested_duration_seconds or _MAX_STORYBOARD_VIDEO_DURATION_S, _MAX_STORYBOARD_VIDEO_DURATION_S)
        message = _compose_creator_owned_15s_blueprint(
            message,
            brief,
            title=title,
            aspect_ratio=aspect_ratio,
            duration_seconds=requested_duration_seconds,
            style=style,
        )
    if revision_note and message:
        message = _ensure_blueprint_revised_section(message, revision_note)

    if is_video_blueprint:
        shots = _shots_from_blueprint_table(message, style, tone, colorized=False)
        if not shots and message:
            shots = _shots_from_storyboard_text(message, style, tone, panel_count=3 if creator_owned_video_request else panel_count, colorized=False)
    else:
        # Always generate placeholder shots from the CMO text.
        # The actual panel descriptions come from source_storyboard_text
        # which is passed verbatim to the image model in build_prompt().
        shots = _shots_from_storyboard_text(message, style, tone, panel_count=panel_count) if message else []

    # The creator-owned blueprint/storyboard text is the source of truth.
    source_storyboard_text = message if message else ""

    raw_refs = [r for r in (brief.get("reference_images") or brief.get("refs") or brief.get("brand_images") or []) if r]
    brand_assets_meta: dict[str, Any] = {
        "count": min(len(raw_refs), 3),
        "reference_images": [],  # paths populated by save_brand_assets at create/render time
    }

    return {
        "artifact_kind": "video_production_blueprint" if is_video_blueprint else "storyboard",
        "source_storyboard_text": source_storyboard_text,
        "production_blueprint": _build_production_blueprint(source_storyboard_text or message, brief) if is_video_blueprint else None,
        "project": {
            "title": title,
            "format": str(brief.get("format") or ("Video production blueprint for Previs Motion final-cut candidate" if is_video_blueprint else "Single cohesive black-and-white storyboard prototype sheet")),
            "core_idea": message[:1200],
            "dialogue": str(brief.get("dialogue") or brief.get("voiceover") or "none unless specified"),
            "branding": str(brief.get("branding") or "no readable branding inside frames unless explicitly requested"),
            "aspect_ratio": aspect_ratio,
            "duration_seconds": requested_duration_seconds,
            "platform": brief.get("platform") or brief.get("channel"),
        },
        "revision": {
            "variation_id": "v001",
            "updated_at": utc_now(),
            "change_summary": "Initial video production blueprint created by storyboard plugin." if is_video_blueprint else "Initial JSON-first storyboard spec created by storyboard plugin.",
        },
        "global_visual_rules": {
            "style": style,
            "palette": ("black, white, and grayscale only by default for video storyboard references; Seedance owns final color/realism" if is_video_blueprint else "black, white, and grayscale only; no brand colors in the rendered storyboard prototype"),
            "dialogue_or_text": "No readable text, captions, signage, UI labels, or logos unless explicitly requested.",
            "composition_rule": "Render one cohesive storyboard sheet with ordered panels/gutters; each panel should be sparse enough to read quickly as a storyboard beat.",
            "continuity_rule": ("Preserve characters, props, wardrobe, location logic, grayscale palette, and camera continuity so the panels read as one connected story." if is_video_blueprint else "Preserve characters, props, wardrobe, location logic, grayscale palette, and camera continuity so the panels read as one connected story."),
        },
        "locked_elements": {
            "must_preserve_across_revisions": [
                "visual style",
                "shot order unless change_request says otherwise",
                "character/prop identity",
                "brand constraints as narrative context only" + (", not colored finished art" if is_video_blueprint else ", not colored finished art"),
                "single cohesive storyboard sheet layout",
                ("black-and-white hand-drawn previs reference style" if is_video_blueprint else "black-and-white hand-drawn conceptual prototype style"),
                "no invented readable text or logos",
            ],
            "do_not_add": (["readable text", "random logos", "watermarks", "extra people", "unrequested clutter", "color", "photorealism", "real-person portraits", "polished advertising art", "finished social media creative"] if is_video_blueprint else ["readable text", "random logos", "watermarks", "extra people", "unrequested clutter", "color", "photorealism", "polished advertising art", "finished social media creative"]),
        },
        "acts": [
            {
                "act_number": 1,
                "title": str(brief.get("act_title") or "Storyboard"),
                "location": str(brief.get("location") or "as specified by each shot"),
                "time_of_day": str(brief.get("time_of_day") or "as specified by brief"),
                "emotional_point": tone,
                "visual_treatment": style,
                "shots": shots,
            }
        ],
        "editable_region": {
            "target": "none for initial version",
            "description": "Future revisions should identify exact act, shot, and field to change.",
        },
        "change_request": {
            "summary": "Initial storyboard generation from brief.",
            "edits": [],
        },
        "brand_assets": brand_assets_meta,
    }


def storyboard_text_from_spec(spec: dict[str, Any]) -> str:
    """Return the human-readable text artifact shown before any image/video render."""
    project = spec.get("project") if isinstance(spec.get("project"), dict) else {}
    revision = spec.get("revision") if isinstance(spec.get("revision"), dict) else {}
    global_rules = spec.get("global_visual_rules") if isinstance(spec.get("global_visual_rules"), dict) else {}
    locked = spec.get("locked_elements") if isinstance(spec.get("locked_elements"), dict) else {}

    if spec.get("artifact_kind") == "video_production_blueprint":
        source_text = str((spec.get("production_blueprint") or {}).get("source_text") or spec.get("source_storyboard_text") or "").strip()
        if source_text:
            return _ensure_blueprint_revised_section(source_text)
        return _blueprint_text_from_spec(spec, project, revision, global_rules)

    source_text = str(spec.get("source_storyboard_text") or "").strip()
    if source_text:
        return source_text.rstrip() + "\n"
    return _storyboard_review_text_from_spec(spec, project, revision, global_rules, locked)


def _blueprint_text_from_spec(spec: dict[str, Any], project: dict[str, Any], revision: dict[str, Any], global_rules: dict[str, Any]) -> str:
    """Fallback human-readable production blueprint when CMO did not supply one."""
    lines: list[str] = []
    title = str(project.get("title") or "Untitled Video Production Blueprint")
    lines.append(f"# {title}")
    lines.append("")
    if revision.get("variation_id"):
        lines.append(f"**Version:** {revision.get('variation_id')}")
    if project.get("core_idea"):
        lines.append(f"**Objective:** {project.get('core_idea')}")
    fmt = str(project.get("aspect_ratio") or "").strip()
    if project.get("duration_seconds"):
        fmt = (fmt + " / " if fmt else "") + f"{project.get('duration_seconds')}s"
    if project.get("platform") or fmt:
        lines.append(f"**Platform / format:** {project.get('platform') or 'TBD'}" + (f" / {fmt}" if fmt else ""))
    if global_rules.get("style"):
        lines.append(f"**Creative direction:** {global_rules.get('style')}")
    lines.append("**Audience:** TBD")
    lines.append("**Offer / CTA:** TBD")
    lines.append("")
    lines.append("## Script")
    lines.append("- **Hook:** TBD")
    lines.append("- **Voiceover / dialogue:** TBD")
    lines.append("- **On-screen text beats:** TBD")
    lines.append("- **CTA:** TBD")
    lines.append("- **Claims / compliance notes:** TBD")
    lines.append("")
    lines.append("## Screenplay / Text Storyboard")
    lines.append("| Shot | Time | Script / audio | On-screen text | Visual / action | Camera / motion | Assets / constraints |")
    lines.append("|---|---:|---|---|---|---|---|")
    for act in spec.get("acts") or []:
        if not isinstance(act, dict):
            continue
        for shot in act.get("shots") or []:
            if not isinstance(shot, dict):
                continue
            no = shot.get("shot_number") or "?"
            action = str(shot.get("action") or shot.get("image_prompt") or "TBD")
            camera = str(shot.get("composition") or "TBD")
            constraints = []
            for key in ("must_include", "must_avoid"):
                val = shot.get(key)
                if isinstance(val, list) and val:
                    constraints.append(f"{key.replace('_', ' ')}: " + "; ".join(str(x) for x in val))
            lines.append(f"| {no} | TBD | TBD | TBD | {action} | {camera} | {' / '.join(constraints) or 'TBD'} |")
    lines.append("")
    lines.append("## Approval checklist")
    lines.append("- Message/claims approved")
    lines.append("- Scene order and timing approved")
    lines.append("- Required assets confirmed")
    lines.append("- Text overlay vs post-production text decided")
    lines.append("- Ready for Previs Motion final-cut candidate")
    lines.append("")
    lines.append("## Revised")
    lines.append("- No revisions requested yet.")
    return "\n".join(lines).strip() + "\n"


def _storyboard_review_text_from_spec(spec: dict[str, Any], project: dict[str, Any], revision: dict[str, Any], global_rules: dict[str, Any], locked: dict[str, Any]) -> str:
    lines: list[str] = []
    title = str(project.get("title") or "Untitled Storyboard")
    lines.append(f"# {title}")
    lines.append("")
    if revision.get("variation_id"):
        lines.append(f"**Version:** {revision.get('variation_id')}")
    if project.get("core_idea"):
        lines.append(f"**Core idea:** {project.get('core_idea')}")
    if project.get("aspect_ratio"):
        lines.append(f"**Aspect ratio:** {project.get('aspect_ratio')}")
    if global_rules.get("style"):
        lines.append(f"**Visual style:** {global_rules.get('style')}")
    if global_rules.get("palette"):
        lines.append(f"**Palette:** {global_rules.get('palette')}")

    preserve = locked.get("must_preserve_across_revisions")
    if isinstance(preserve, list) and preserve:
        lines.append("")
        lines.append("## Locked elements")
        for item in preserve:
            lines.append(f"- {item}")

    lines.append("")
    lines.append("## Shot list")
    for act in spec.get("acts") or []:
        if not isinstance(act, dict):
            continue
        act_title = str(act.get("title") or f"Act {act.get('act_number') or ''}" or "Act").strip()
        if act_title:
            lines.append("")
            lines.append(f"### {act_title}")
        for shot in act.get("shots") or []:
            if not isinstance(shot, dict):
                continue
            shot_no = shot.get("shot_number") or "?"
            shot_title = str(shot.get("title") or f"Shot {shot_no}")
            lines.append("")
            lines.append(f"**Shot {shot_no}: {shot_title}**")
            for label, key in (("Action", "action"), ("Composition", "composition"), ("Emotion", "emotional_intent")):
                value = shot.get(key)
                if value:
                    lines.append(f"- {label}: {value}")
            includes = shot.get("must_include")
            avoids = shot.get("must_avoid")
            if isinstance(includes, list) and includes:
                lines.append("- Must include: " + "; ".join(str(x) for x in includes))
            if isinstance(avoids, list) and avoids:
                lines.append("- Must avoid: " + "; ".join(str(x) for x in avoids))
    return "\n".join(lines).strip() + "\n"


def _next_variation_id(current: str) -> str:
    match = re.search(r"(\d+)$", current or "")
    if not match:
        return "v002"
    width = len(match.group(1))
    return f"{(current or 'v')[:match.start(1)]}{int(match.group(1)) + 1:0{width}d}"


def apply_revision_feedback(spec: dict[str, Any], feedback: str) -> dict[str, Any]:
    """Record a revision cycle in the spec for audit trail only.

    Shot-level interpretation is CMO's responsibility — CMO has vision, sees the
    current storyboard, and writes a precise revision_prompt that goes directly
    into the image generation call. This function only bumps the version and
    stores the raw feedback for the audit log.
    """
    feedback = (feedback or "").strip()
    if not feedback:
        return spec
    revised = copy.deepcopy(spec)
    current_rev = revised.get("revision") if isinstance(revised.get("revision"), dict) else {}
    current_id = str(current_rev.get("variation_id") or "v001")
    revised["revision"] = {
        "variation_id": _next_variation_id(current_id),
        "updated_at": utc_now(),
        "change_summary": feedback,
    }
    revised["change_request"] = {
        "summary": feedback,
        "edits": [],
    }
    return revised


def _apply_panel_count(spec: dict[str, Any], panel_count: int) -> dict[str, Any]:
    """Rebuild shots in acts[0] to match the requested panel_count."""
    acts = spec.get("acts")
    if not isinstance(acts, list) or not acts or not isinstance(acts[0], dict):
        return spec
    act = acts[0]
    style = str((spec.get("global_visual_rules") or {}).get("style") or "clean black-and-white hand-drawn storyboard prototype sketch")
    tone = str(act.get("emotional_point") or "clear, cinematic, emotionally readable")
    source_text = str(spec.get("source_storyboard_text") or "")
    spec = copy.deepcopy(spec)
    spec["acts"][0]["shots"] = _shots_from_storyboard_text(source_text, style, tone, panel_count=panel_count)
    return spec


def spec_from_brief(brief: dict[str, Any]) -> dict[str, Any]:
    revision_feedback = str(brief.get("revision_feedback") or brief.get("feedback") or "").strip()
    panel_count: int | None = None
    try:
        raw_pc = brief.get("panel_count")
        if raw_pc is not None:
            panel_count = min(max(1, int(raw_pc)), 24)
    except (TypeError, ValueError):
        pass

    def _finalise(spec: dict[str, Any]) -> dict[str, Any]:
        if revision_feedback:
            spec = apply_revision_feedback(spec, revision_feedback)
        # Creator-owned video blueprints lock to the 15-second structure. Do not
        # let a generic panel_count override mutate them into 4/5/6-shot specs
        # after the creator has already normalized the source text to 3 beats.
        if panel_count is not None and str(spec.get("artifact_kind") or "") != "video_production_blueprint":
            spec = _apply_panel_count(spec, panel_count)
        return spec

    for key in ("storyboard_spec", "json_spec", "spec"):
        value = brief.get(key)
        if isinstance(value, dict):
            return _finalise(copy.deepcopy(value))
        if isinstance(value, str) and value.strip().startswith("{"):
            data = json.loads(value)
            if not isinstance(data, dict):
                raise ValueError(f"{key} must decode to a JSON object")
            return _finalise(data)
    spec_path = str(brief.get("spec_path") or brief.get("storyboard_spec_path") or "").strip()
    if spec_path:
        path = Path(spec_path).expanduser()
        if not path.exists() and not path.is_absolute():
            candidate = PLUGIN_ROOT / path
            if candidate.exists():
                path = candidate
        return _finalise(load_json(path))
    return _finalise(make_storyboard_spec(brief))


def _blueprint_text_warnings(text: str) -> list[str]:
    lowered = (text or "").lower()
    checks = {
        "script section": ("script" in lowered or "voiceover" in lowered or "dialogue" in lowered),
        "screenplay/shot table": ("screenplay" in lowered or ("shot" in lowered and "camera" in lowered and "motion" in lowered)),
        "cta": "cta" in lowered or "call to action" in lowered,
        "timing/duration": "time" in lowered or "duration" in lowered or re.search(r"\b\d+\s*(?:s|sec|seconds)\b", lowered) is not None,
        "asset/constraint notes": "asset" in lowered or "constraint" in lowered or "must avoid" in lowered or "must include" in lowered,
        "tension statement": "tension statement" in lowered,
        "beat breakdown": "beat breakdown" in lowered and all(token in lowered for token in ("beat 1", "beat 2", "beat 3")),
        "what was cut and why": "what was cut and why" in lowered,
        "sound-on / sound-off audit": "sound-on / sound-off audit" in lowered or "sound-on/sound-off audit" in lowered,
    }
    return [f"storyboard quality: production blueprint missing {name}" for name, ok in checks.items() if not ok]


def _count_storyboard_beats(text: str) -> int:
    """Best-effort count of explicit shot/panel/scene beats in markdown or prose.

    Counts markdown table rows too, including common formatting like
    `| **1** | ... |`. This is structure detection only; it does not impose a
    fixed number of panels.
    """
    raw = text or ""
    markers = re.findall(r"(?:^|\n)\s*(?:#{1,6}\s*)?(?:[*_`~]+\s*)?(?:scene|shot|panel)\s*[*_`~]*\s*\d+\b", raw, re.IGNORECASE)
    if markers:
        return len(markers)

    table_count = 0
    for line in raw.splitlines():
        stripped = line.strip()
        if not (stripped.startswith("|") and stripped.endswith("|")):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if not cells:
            continue
        first = re.sub(r"[*_`~]", "", cells[0]).strip()
        if re.match(r"^\d+[A-Za-z]?\b", first) or re.search(r"\b(?:shot|panel|scene)\s*\d+\b", first, re.IGNORECASE):
            table_count += 1
    if table_count:
        return table_count

    numbered = re.findall(r"(?:^|\n)\s*\d+[.)]\s+", raw)
    return len(numbered)


def _seconds_number(value: str) -> int | float:
    secs = float(value)
    return int(secs) if secs.is_integer() else secs


def _coerce_duration_seconds(value: Any) -> int | float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        secs = float(value)
        if secs < 0:
            return None
        return int(secs) if secs.is_integer() else secs
    raw = str(value).strip().lower()
    if not raw:
        return None
    if ":" in raw:
        parts = [p.strip() for p in raw.split(":")]
        if len(parts) == 2 and all(part.isdigit() for part in parts):
            return int(parts[0]) * 60 + int(parts[1])
    m = re.search(r"(?<![\d.])(\d{1,3}(?:\.\d+)?)\s*(?:s|sec|secs|second|seconds)\b", raw)
    if m:
        return _seconds_number(m.group(1))
    if re.fullmatch(r"\d{1,3}(?:\.\d+)?", raw):
        return _seconds_number(raw)
    return None


def _duration_range_seconds(value: str) -> tuple[int | float | None, int | float | None]:
    raw = str(value or "").strip()
    if not raw:
        return None, None
    m = re.search(r"\b(\d{1,2}):(\d{2})\s*[–-]\s*(\d{1,2}):(\d{2})\b", raw)
    if m:
        start = int(m.group(1)) * 60 + int(m.group(2))
        end = int(m.group(3)) * 60 + int(m.group(4))
        return end, max(0, end - start)
    m = re.search(r"(?<![\d.])(\d{1,3}(?:\.\d+)?)\s*[–-]\s*(\d{1,3}(?:\.\d+)?)\s*(?:s|sec|secs|second|seconds)\b", raw, re.IGNORECASE)
    if m:
        start = float(m.group(1))
        end = float(m.group(2))
        return _seconds_number(m.group(2)), _seconds_number(str(max(0.0, end - start)))
    secs = _coerce_duration_seconds(raw)
    return None, secs


def _extract_timeline_end_seconds(text: str) -> int | float | None:
    raw = text or ""
    ends: list[int | float] = []
    for m in re.finditer(r"\b(\d{1,2}):(\d{2})\s*[–-]\s*(\d{1,2}):(\d{2})\b", raw):
        ends.append(int(m.group(3)) * 60 + int(m.group(4)))
    for m in re.finditer(r"(?<![\d.])(\d{1,3}(?:\.\d+)?)\s*[–-]\s*(\d{1,3}(?:\.\d+)?)\s*(?:s|sec|secs|second|seconds)\b", raw, re.IGNORECASE):
        ends.append(_seconds_number(m.group(2)))
    return max(ends) if ends else None


def _extract_explicit_duration_seconds(text: str) -> int | float | None:
    raw = text or ""
    vals = [_seconds_number(m.group(1)) for m in re.finditer(r"(?<![\d.])(\d{1,3}(?:\.\d+)?)\s*(?:-|–)?\s*(?:second|seconds|sec|secs|s)\b", raw, re.IGNORECASE)]
    return max(vals) if vals else None


def _extract_table_runtime_seconds(text: str) -> tuple[str, int] | None:
    for table in _extract_markdown_tables(text):
        rows = [r for r in table.splitlines() if r.strip().startswith("|")]
        if len(rows) < 3:
            continue
        headers = [_norm_header(h) for h in _split_md_row(rows[0])]
        row_count = 0
        summed_durations: list[int] = []
        timeline_ends: list[int] = []
        for raw in rows[2:]:
            if re.match(r"^\s*\|?\s*:?-{2,}:?", raw):
                continue
            cells = _split_md_row(raw)
            if len(cells) < 2:
                continue
            row_count += 1
            data = {headers[i]: cells[i] for i in range(min(len(headers), len(cells)))}
            shot_value = next((data.get(k) for k in ("shot", "shot_panel", "scene", "number") if data.get(k)), "")
            time_value = next((data.get(k) for k in ("time", "timing", "duration") if data.get(k)), "")
            duration_value = data.get("duration") or time_value or shot_value
            end, dur = _duration_range_seconds(time_value or shot_value)
            if end is not None:
                timeline_ends.append(end)
            elif time_value and time_value != duration_value:
                alt_end, alt_dur = _duration_range_seconds(time_value)
                if alt_end is not None:
                    timeline_ends.append(alt_end)
                if alt_dur is not None:
                    dur = dur if dur is not None else alt_dur
            _, duration_secs = _duration_range_seconds(duration_value)
            if duration_secs is not None:
                summed_durations.append(duration_secs)
        candidates: list[tuple[str, int]] = []
        if timeline_ends:
            candidates.append(("screenplay table timeline end", max(timeline_ends)))
        if row_count and len(summed_durations) == row_count:
            candidates.append(("screenplay table summed duration", sum(summed_durations)))
        if candidates:
            return max(candidates, key=lambda item: item[1])
    return None


def _storyboard_duration_warnings(spec: dict[str, Any], source_text: str) -> list[str]:
    warnings: list[str] = []
    project = spec.get("project") if isinstance(spec.get("project"), dict) else {}
    production_blueprint = spec.get("production_blueprint") if isinstance(spec.get("production_blueprint"), dict) else {}
    metadata = production_blueprint.get("metadata") if isinstance(production_blueprint.get("metadata"), dict) else {}

    candidates: list[tuple[str, int]] = []
    for label, value in (
        ("project.duration_seconds", project.get("duration_seconds")),
        ("production_blueprint.metadata.duration_seconds", metadata.get("duration_seconds")),
    ):
        secs = _coerce_duration_seconds(value)
        if secs is not None:
            candidates.append((label, secs))

    table_runtime = _extract_table_runtime_seconds(source_text)
    if table_runtime is not None:
        candidates.append(table_runtime)

    timeline_end = _extract_timeline_end_seconds(source_text)
    if timeline_end is not None:
        candidates.append(("screenplay timeline end", timeline_end))

    # ✅ GLOBAL HARD CAP: All videos are max 15 seconds. NO EXCEPTIONS.
    max_allowed = 15
    detected_duration = max((sec for _, sec in candidates), default=None)
    
    # Assume standard 3.75s per shot when no timings are listed
    if detected_duration is None:
        shot_count = _count_storyboard_beats(source_text)
        if shot_count > 0:
            max_shots = 3  # ✅ 15s maximum = exactly 3 full shots (5s each with 0.5s transitions)
            estimated = shot_count * 5
            if shot_count > max_shots:
                warnings.append(f"storyboard quality: {shot_count} shots requested, only {max_shots} shots fit within 15 second hard cap.")
                warnings.append(f"storyboard quality: Reduce to MAXIMUM 3 shots total for all 15s videos. Combine beats, remove unnecessary transitions.")
                warnings.append(f"storyboard quality: Recommended timing: Shot 1 (0-5s) Hook, Shot 2 (5-10s) Story / Proof, Shot 3 (10-15s) CTA / Payoff.")

    for label, secs in candidates:
        if secs > max_allowed:
            warnings.append(f"storyboard quality: {label} exceeds 15s maximum allowed duration (requested: {secs}s).")
            warnings.append(f"storyboard quality: Compress the narrative, remove extra shots, and fit complete story + CTA inside 15 seconds.")
    
    # Always override any requested duration to 15s at render time
    if detected_duration and detected_duration > max_allowed:
        warnings.append(f"✅ Runtime will be automatically truncated to {max_allowed}s during video generation.")

    explicit_duration = _extract_explicit_duration_seconds(source_text)
    if explicit_duration is not None:
        candidates.append(("storyboard duration", explicit_duration))

    if not candidates:
        return []
    label, secs = max(candidates, key=lambda item: item[1])
    if secs <= _MAX_STORYBOARD_VIDEO_DURATION_S:
        return []
    return [
        "storyboard quality: "
        f"{label} {secs}s exceeds the current {_MAX_STORYBOARD_VIDEO_DURATION_S}s hard cap for a single storyboard/screenplay. "
        "Keep the full story arc, payoff, and CTA within 15 seconds or less until multi-shot stitching is supported."
    ]


def _storyboard_quality_warnings(text: str, *, is_video_blueprint: bool, expected_panels: int | None = None) -> list[str]:
    """Generic quality floor so CMO-authored storyboards are renderable artifacts, not summaries.

    This intentionally checks structure and production detail only; it does not
    hardcode story content, brand claims, products, or audience names.
    """
    raw = (text or "").strip()
    if not raw:
        return ["storyboard quality: missing storyboard body"]
    lowered = raw.lower()
    beat_count = _count_storyboard_beats(raw)

    warnings: list[str] = []
    if is_video_blueprint:
        generic_action_phrases = (
            "one immediate image that surfaces the audience tension without setup",
            "arriving as the answer to that tension",
            "simple branded cta frame anchored on",
        )
        if sum(1 for phrase in generic_action_phrases if phrase in lowered) >= 2:
            warnings.append(
                "storyboard quality: generic storyboard template placeholders remain; replace them with concrete scene-specific visual/action, camera, and asset details before approval"
            )
    if beat_count == 0:
        warnings.append("storyboard quality: missing ordered shot/panel structure")
    elif expected_panels is not None and expected_panels > 1 and beat_count < expected_panels:
        warnings.append(f"storyboard quality: only {beat_count} explicit shots/panels for requested count {expected_panels}")

    blocking_checks = {
        "audience/objective/offer context": any(token in lowered for token in ("audience", "objective", "goal", "offer", "cta", "call to action", "for ")),
        "visual action detail": any(token in lowered for token in ("visual", "action", "shows", "reveals", "enters", "presents", "holds", "walks", "sits", "looks", "cut to")),
        "camera/composition or motion detail": any(token in lowered for token in ("camera", "composition", "close", "wide", "medium", "over-the-shoulder", "pan", "tilt", "push", "pull", "motion", "angle", "frame")),
        "audio/script/caption detail": any(token in lowered for token in ("script", "audio", "voiceover", "dialogue", "caption", "on-screen", "text", "speaks", "says")),
    }
    for name, ok in blocking_checks.items():
        if not ok:
            warnings.append(f"storyboard quality: missing {name}")
    has_asset_detail = any(token in lowered for token in ("asset", "constraint", "must include", "must avoid", "brand", "logo", "no readable", "location", "wardrobe", "prop"))
    if not has_asset_detail:
        warnings.append("storyboard advisory: missing asset/constraint detail")
    return warnings


def is_blocking_quality_warning(warning: str) -> bool:
    return str(warning).startswith("storyboard quality:")


def validate_spec(spec: dict[str, Any]) -> tuple[bool, list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(spec.get("project"), dict):
        errors.append("missing project object")
    if not isinstance(spec.get("revision"), dict):
        warnings.append("missing revision object")
    if not isinstance(spec.get("global_visual_rules"), dict):
        warnings.append("missing global_visual_rules object")
    if not isinstance(spec.get("locked_elements"), dict):
        warnings.append("missing locked_elements object")
    source_text = str(spec.get("source_storyboard_text") or "")
    is_video_blueprint = spec.get("artifact_kind") == "video_production_blueprint"
    if is_video_blueprint:
        bp = spec.get("production_blueprint") if isinstance(spec.get("production_blueprint"), dict) else {}
        source_text = str(bp.get("source_text") or source_text or "")
        warnings.extend(_blueprint_text_warnings(source_text))
    warnings.extend(_storyboard_duration_warnings(spec, source_text))
    # Only enforce a count when the spec explicitly carries multiple parsed
    # shots from the author/request. Placeholder shots for a thin summary should
    # not become a hidden hardcoded panel requirement.
    expected_panels: int | None = None
    try:
        shots_hint = ((spec.get("acts") or [{}])[0] or {}).get("shots") if isinstance(spec.get("acts"), list) else None
        explicit_beats = _count_storyboard_beats(source_text)
        if isinstance(shots_hint, list) and explicit_beats > 1:
            expected_panels = len(shots_hint)
    except Exception:
        expected_panels = None
    warnings.extend(_storyboard_quality_warnings(source_text, is_video_blueprint=is_video_blueprint, expected_panels=expected_panels))
    acts = spec.get("acts")
    if not isinstance(acts, list) or not acts:
        errors.append("missing non-empty acts array")
    else:
        for ai, act in enumerate(acts, start=1):
            shots = act.get("shots") if isinstance(act, dict) else None
            if not isinstance(shots, list) or not shots:
                errors.append(f"act {ai} missing non-empty shots array")
                continue
            seen = set()
            for si, shot in enumerate(shots, start=1):
                if not isinstance(shot, dict):
                    errors.append(f"act {ai} shot {si} is not an object")
                    continue
                n = shot.get("shot_number")
                if n in seen:
                    warnings.append(f"act {ai} duplicate shot_number {n}")
                seen.add(n)
                for field in ("image_prompt", "composition", "action", "must_include", "must_avoid"):
                    if field not in shot:
                        warnings.append(f"act {ai} shot {n or si} missing {field}")
    return not errors, errors, warnings


def _jwt_account_id(token: str) -> str:
    try:
        payload = token.split(".")[1] + "=" * (-len(token.split(".")[1]) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload.encode()).decode())
        return str(data.get("https://api.openai.com/auth", {}).get("chatgpt_account_id") or "")
    except Exception:
        return ""


def _codex_text_model(model: str | None = None) -> str:
    raw = str(model or "").strip().lower()
    if raw.startswith("gpt-") and "image" not in raw:
        return raw
    return os.environ.get("STORYBOARD_CODEX_IMAGE_MODEL") or os.environ.get("OPENAI_CODEX_IMAGE_MODEL") or "gpt-5.5"


def _provider_auth_mode_from_brief(brief: dict[str, Any] | None = None) -> str:
    creds = (brief or {}).get("_channel_credentials", {}) if isinstance(brief, dict) else {}
    return str(creds.get("provider_api_key_auth_mode") or "").strip().lower() if isinstance(creds, dict) else ""


def _openai_base_url_from_brief(brief: dict[str, Any] | None = None) -> str | None:
    creds = (brief or {}).get("_channel_credentials", {}) if isinstance(brief, dict) else {}
    if not isinstance(creds, dict):
        return None
    raw = str(
        creds.get("openai_api_base_url")
        or creds.get("provider_api_base_url")
        or creds.get("provider_api_key_base_url")
        or os.environ.get("OPENAI_BASE_URL")
        or os.environ.get("OPENAI_API_BASE")
        or ""
    ).strip().rstrip("/")
    for suffix in ("/chat/completions", "/responses", "/images/edits", "/images/generations"):
        if raw.endswith(suffix):
            raw = raw[: -len(suffix)].rstrip("/")
    return raw or None


def get_openai_key(brief: dict[str, Any] | None = None) -> str:
    creds = (brief or {}).get("_channel_credentials", {}) if isinstance(brief, dict) else {}
    candidates = [
        creds.get("openai_api_key") if isinstance(creds, dict) else None,
        creds.get("platform_openai_key") if isinstance(creds, dict) else None,
        creds.get("provider_api_key") if isinstance(creds, dict) else None,
        os.environ.get("OPENAI_API_KEY"),
        os.environ.get("PLATFORM_OPENAI_KEY"),
    ]
    for key in candidates:
        if key and str(key).strip():
            return str(key).strip()
    raise RuntimeError("Missing OpenAI key. Configure OPENAI_API_KEY or PLATFORM_OPENAI_KEY for the storyboard plugin.")


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
            "No image generation provider configured for Storyboard. "
            "Set one in Admin → AI Providers."
        )
    if not api_key:
        raise ValueError(
            f"No API key found for provider '{provider}'. "
            "Configure it in Admin → AI Providers."
        )
    return provider, model, api_key


# ---------------------------------------------------------------------------
# Preflight gate (Postcraft pattern)
# ---------------------------------------------------------------------------

def _storyboard_preflight(brief: dict) -> list[str]:
    """Hard gate: no provider call without a valid spec and approved text/JSON."""
    missing: list[str] = []
    # Check for storyboard spec
    spec = brief.get("storyboard_spec") or brief.get("json_spec") or brief.get("spec")
    spec_path = str(brief.get("spec_path") or brief.get("storyboard_spec_path") or "").strip()
    has_spec = isinstance(spec, dict) or (isinstance(spec, str) and spec.strip().startswith("{")) or (spec_path and Path(spec_path).expanduser().exists())
    if not has_spec:
        missing.append("storyboard_spec")
    brand_kit = brief.get("brand_kit") if isinstance(brief.get("brand_kit"), dict) else {}
    brand_spec = brand_kit.get("brand_spec") if isinstance(brand_kit.get("brand_spec"), dict) else {}
    if not brand_spec and isinstance(brief.get("brand_spec"), dict):
        brand_spec = brief.get("brand_spec") or {}
    creds = brief.get("_channel_credentials") or {}
    drive_token = str(creds.get("google_drive_page_token") or creds.get("page_token") or creds.get("access_token") or "").strip()
    drive_root = str(creds.get("drive_root_folder_id") or brand_spec.get("drive_root_folder_id") or "").strip()
    logo_id = str(brand_spec.get("logo_drive_file_id") or "").strip()
    if not drive_token:
        missing.append("google_drive_credentials")
    if not drive_root:
        missing.append("google_drive_root_folder")
    if not logo_id:
        missing.append("official_logo_drive_file_id")
    # Check for approval gate on render (not on create)
    is_render = str(brief.get("capability") or brief.get("action") or "").lower() in {"storyboard.render", "render"}
    if is_render:
        approved = (
            brief.get("render_approved") is True
            or brief.get("approved_storyboard") is True
            or str(brief.get("approval_status") or "").lower() in {"approved", "json_approved", "render_approved"}
        )
        if not approved:
            missing.append("render_approval")
    return missing


def _preflight_block(missing: list[str], brief: dict) -> dict:
    checklist = {
        "storyboard_spec": {
            "fix": "Create a storyboard first using storyboard.create to produce an approved text/JSON artifact.",
            "href": "/workspace",
            "label": "Create Storyboard",
        },
        "render_approval": {
            "fix": "Review and approve the storyboard text/JSON before rendering images.",
            "href": "/workspace",
            "label": "Review Storyboard",
        },
        "google_drive_credentials": {
            "fix": "Connect Google Drive for this Brand so generated storyboard images can be saved before Stream review.",
            "href": "/admin/brands",
            "label": "Connect Google Drive",
        },
        "google_drive_root_folder": {
            "fix": "Select and validate the Brand Kit Google Drive folder for this Brand.",
            "href": "/admin/brands",
            "label": "Choose Drive Folder",
        },
        "official_logo_drive_file_id": {
            "fix": "Put an official logo/wordmark image in the Brand Kit Drive folder and validate it before image generation.",
            "href": "/admin/brands",
            "label": "Add Brand Logo",
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


# ---------------------------------------------------------------------------
# Thumbnail (Postcraft pattern)
# ---------------------------------------------------------------------------

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
    return "image/jpeg"


def _make_thumbnail(image_bytes: bytes, max_px: int = 480) -> tuple[str, str]:
    """Return (base64, mime_type) JPEG thumbnail for inline preview.

    JPEG at q=75 keeps previews under ~60KB regardless of source size,
    avoiding JSON truncation when the full image is already in Drive.
    """
    try:
        from PIL import Image as _PIL
        buf_in = io.BytesIO(image_bytes)
        img = _PIL.open(buf_in).convert("RGB")
        img.thumbnail((max_px, max_px), _PIL.LANCZOS)
        buf_out = io.BytesIO()
        img.save(buf_out, format="JPEG", quality=75, optimize=True)
        result_bytes = buf_out.getvalue()
        return base64.b64encode(result_bytes).decode(), _sniff_mime(result_bytes)
    except Exception:
        return "", "image/jpeg"


# ---------------------------------------------------------------------------
# Audit trail (Postcraft pattern)
# ---------------------------------------------------------------------------

def _write_audit(data: dict, label: str) -> None:
    """Write audit data to disk — non-blocking, never fails the pipeline."""
    try:
        _AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        path = _AUDIT_DIR / f"{label}_{int(time.time())}.json"
        path.write_text(json.dumps(data, indent=2, default=str))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Revision continuity (Postcraft pattern)
# ---------------------------------------------------------------------------

def _restore_from_prior(brief: dict) -> dict:
    """Recover brand context and approved spec from prior artifact blocks."""
    for key in ("original_artifact_block", "artifact_block", "artifact_data", "previous_artifact"):
        val = brief.get(key)
        if isinstance(val, dict):
            return val
    for key in ("artifact_blocks", "artifacts", "blocks"):
        val = brief.get(key)
        if isinstance(val, list) and val and isinstance(val[0], dict):
            return val[0]
    return {}


def download_url(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": "BOS-storyboard/1.0"})
    with urlopen(req, timeout=120) as r:
        return r.read()


def _image_response_to_bytes(response: Any) -> tuple[bytes, dict[str, Any]]:
    if isinstance(response, dict):
        item = response.get("data", [{}])[0]
        b64 = item.get("b64_json")
        url = item.get("url")
    else:
        item = response.data[0]
        b64 = getattr(item, "b64_json", None)
        url = getattr(item, "url", None)
    meta: dict[str, Any] = {}
    if b64:
        meta["response_kind"] = "b64_json"
        return base64.b64decode(b64), meta
    if url:
        meta["response_kind"] = "url"
        meta["url"] = url
        return download_url(url), meta
    raise RuntimeError(f"OpenAI image response had neither b64_json nor url: {item}")


def _write_optional_image(temp_dir: Path, name: str, b64_or_path: Any) -> Path | None:
    if not b64_or_path:
        return None
    # Attachment objects: {"vision_b64": "...", "mime_type": "...", ...}
    if isinstance(b64_or_path, dict):
        data = _decode_ref_image(b64_or_path)
        if data is None:
            return None
        out = temp_dir / name
        out.write_bytes(data)
        return out
    if isinstance(b64_or_path, str):
        value = b64_or_path.strip()
        if value.startswith("data:") and "," in value:
            value = value.split(",", 1)[1]
        # Only treat as a filesystem path if it looks like one (short, path-like).
        # Raw base64 strings are long and contain no path separators — trying
        # Path(...).exists() on them raises ENAMETOOLONG on the OS level.
        if len(value) <= 4096 and ("/" in value or "\\" in value or value.endswith((".png", ".jpg", ".jpeg", ".webp"))):
            p = Path(value).expanduser()
            if p.exists():
                return p
            if not p.is_absolute():
                candidate = PLUGIN_ROOT / p
                if candidate.exists():
                    return candidate
        try:
            raw = base64.b64decode(value)
        except Exception as exc:
            raise ValueError(f"{name} is neither an existing path nor valid base64") from exc
        out = temp_dir / name
        out.write_bytes(raw)
        return out
    return None


def _call_openai_generate(spec: dict[str, Any], prompt: str, brief: dict[str, Any], api_key: str, model: str, size: str, base_url: str | None = None) -> Any:
    from openai import OpenAI
    job = spec.get("job", {}) if isinstance(spec.get("job"), dict) else {}
    kwargs: dict[str, Any] = {
        "model": model or job.get("model") or brief.get("model") or DEFAULT_MODEL,
        "prompt": prompt,
        "size": size,
        "quality": brief.get("image_quality") or "medium",
        "n": 1,
    }
    # response_format is NOT a valid parameter for the Images API.
    # The API returns b64_json by default when no response_format is specified.
    client_kwargs: dict[str, Any] = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url
    client = OpenAI(**client_kwargs)
    return client.images.generate(**kwargs)


def _call_openai_edit(
    spec: dict[str, Any],
    prompt: str,
    images: list[Path],
    brief: dict[str, Any],
    api_key: str,
    model: str,
    size: str,
    mask: Path | None = None,
    base_url: str | None = None,
) -> Any:
    """Call images/edits via the OpenAI SDK.

    images: up to 4 — [source, ref1, ref2, ref3]. SDK handles multipart natively.
    """
    from openai import OpenAI
    job = spec.get("job", {}) if isinstance(spec.get("job"), dict) else {}
    kwargs: dict[str, Any] = {
        "model": model or job.get("model") or brief.get("model") or DEFAULT_MODEL,
        "prompt": prompt,
        "size": size,
        "quality": brief.get("image_quality") or "medium",
        "n": 1,
    }
    # response_format is NOT a valid parameter for the Images Edits API.
    # The API returns b64_json by default when no response_format is specified.
    client_kwargs: dict[str, Any] = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url
    client = OpenAI(**client_kwargs)
    with ExitStack() as stack:
        opened = [stack.enter_context(open(p, "rb")) for p in images]
        kwargs["image"] = opened if len(opened) > 1 else opened[0]
        if mask:
            kwargs["mask"] = stack.enter_context(open(mask, "rb"))
        return client.images.edit(**kwargs)


def _looks_like_image_payload(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    if text.startswith("data:image/"):
        return True
    if text.startswith(("http://", "https://")):
        return True
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=_-\n\r")
    return len(text) >= 8 and all(ch in allowed for ch in text)


def _codex_image_payload(value: object) -> str:
    """Extract image data or an image URL from Codex Responses envelopes."""
    if isinstance(value, str):
        return value.strip() if _looks_like_image_payload(value) else ""
    if isinstance(value, list):
        for child in reversed(value):
            found = _codex_image_payload(child)
            if found:
                return found
        return ""
    if not isinstance(value, dict):
        return ""

    for key in (
        "b64_json",
        "image_b64",
        "partial_image_b64",
        "image_data_b64",
        "base64",
        "url",
        "image_url",
        "download_url",
        "file_url",
        "result",
        "results",
        "image",
        "data",
        "content",
        "text",
        "output_text",
        "delta",
        "item",
        "output_item",
        "response",
        "output",
    ):
        candidate = value.get(key)
        if isinstance(candidate, dict) and key == "image_url":
            candidate = candidate.get("url")
        if isinstance(candidate, str) and candidate.strip().startswith(("{", "[")):
            try:
                candidate = json.loads(candidate)
            except Exception:
                pass
        found = _codex_image_payload(candidate)
        if found:
            return found

    for candidate in value.values():
        if isinstance(candidate, (dict, list)):
            found = _codex_image_payload(candidate)
            if found:
                return found
    return ""


def _decode_codex_image(payload: str) -> bytes:
    value = str(payload or "").strip()
    if value.startswith(("{", "[")):
        try:
            nested = _codex_image_payload(json.loads(value))
        except Exception:
            nested = ""
        if nested and nested != value:
            return _decode_codex_image(nested)
    if value.startswith(("http://", "https://")):
        dl = Request(value, headers={"User-Agent": _USER_AGENT})
        with urlopen(dl, timeout=120) as r:
            return r.read()
    if value.startswith("data:") and "," in value:
        value = value.split(",", 1)[1]
    return base64.b64decode(value, validate=False)


def _call_openai_codex_image_generation(
    prompt: str,
    brief: dict[str, Any],
    api_key: str,
    model: str,
    size: str,
    *,
    images: list[tuple[bytes, str, str]] | None = None,
    action: str = "auto",
) -> bytes:
    """Generate/edit through ChatGPT/Codex OAuth Responses image_generation."""
    content: list[dict[str, Any]] = [{"type": "input_text", "text": prompt}]
    for idx, (img, label, mime) in enumerate((images or [])[:4], start=1):
        content.append({"type": "input_text", "text": f"Reference image {idx}: {label}"})
        content.append({
            "type": "input_image",
            "image_url": f"data:{mime or 'image/png'};base64,{base64.b64encode(img).decode()}",
        })
    quality = str(brief.get("image_quality") or "medium")
    if quality not in {"low", "medium", "high", "auto"}:
        quality = "medium"
    tool: dict[str, Any] = {"type": "image_generation", "size": size, "quality": quality}
    if action in {"generate", "edit", "auto"}:
        tool["action"] = action
    body = {
        "model": _codex_text_model(model),
        "store": False,
        "stream": True,
        "input": [{"role": "user", "content": content}],
        "instructions": "Use the image_generation tool. Return the image only; do not answer with SVG, markdown, or text placeholders.",
        "text": {"verbosity": "low"},
        "include": ["reasoning.encrypted_content"],
        "tools": [tool],
        "tool_choice": {"type": "image_generation"},
        "parallel_tool_calls": False,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "chatgpt-account-id": _jwt_account_id(api_key),
        "originator": "pi",
        "OpenAI-Beta": "responses=experimental",
        "accept": "text/event-stream",
        "content-type": "application/json",
        "User-Agent": "pi (browser)",
    }
    req = Request(
        "https://chatgpt.com/backend-api/codex/responses",
        data=json.dumps(body).encode(),
        headers=headers,
        method="POST",
    )
    image_b64 = ""
    event_types: list[str] = []
    event_samples: list[dict[str, Any]] = []
    try:
        with urlopen(req, timeout=360) as r:
            for raw_line in r:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if line.startswith("data: "):
                    data_str = line[6:].strip()
                elif line.startswith("{"):
                    # Support Codex-compatible JSON-line responses as well as SSE.
                    data_str = line
                else:
                    continue
                if data_str == "[DONE]":
                    break
                try:
                    event = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                event_type = str(event.get("type") or "")
                if event_type and event_type not in event_types:
                    event_types.append(event_type)
                if len(event_samples) < 6:
                    sample: dict[str, Any] = {"type": event_type, "keys": sorted(list(event.keys()))[:12]}
                    item = event.get("item") if isinstance(event.get("item"), dict) else None
                    if item:
                        sample["item_type"] = item.get("type")
                        sample["item_keys"] = sorted(list(item.keys()))[:12]
                    response = event.get("response") if isinstance(event.get("response"), dict) else None
                    if response:
                        output = response.get("output")
                        if isinstance(output, list) and output:
                            sample["response_output_types"] = [
                                str(o.get("type") or type(o).__name__)
                                for o in output[:4]
                                if isinstance(o, dict)
                            ]
                    event_samples.append(sample)
                if event_type == "response.failed":
                    raise RuntimeError(json.dumps(event)[:1200])
                found = _codex_image_payload(event)
                if found:
                    image_b64 = found
    except HTTPError as exc:
        try:
            body_text = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body_text = ""
        raise RuntimeError(f"HTTP {exc.code} from OpenAI Codex image_generation: {body_text[:1200]}") from exc
    if not image_b64:
        seen = ", ".join(event_types[:12]) or "no recognized events"
        logger.warning("Storyboard Codex image_generation returned no image payload: events=%s samples=%s", seen, event_samples)
        raise RuntimeError(f"No image data in OpenAI Codex image_generation response (events: {seen})")
    try:
        return _decode_codex_image(image_b64)
    except (ValueError, base64.binascii.Error) as exc:
        logger.warning(
            "Storyboard Codex image_generation returned invalid image data: payload_prefix=%r events=%s samples=%s",
            image_b64[:160],
            event_types,
            event_samples,
        )
        raise RuntimeError("OpenAI Codex image_generation returned invalid image data") from exc


def render_storyboard(brief: dict[str, Any]) -> dict[str, Any]:
    """Render a storyboard image via gpt-image-2.

    Pipeline:
      1. Spec resolution (with revision continuity)
      2. Prompt construction
      3. Image generation (generate or edit with up to 4 images)
      4. Thumbnail (non-blocking)
      5. Audit trail (non-blocking)
    """
    start = time.perf_counter()
    pipeline_notes: list[str] = []

    # Credential resolution (Postcraft pattern)
    try:
        provider, model, api_key = _get_image_creds(brief)
        openai_base_url = _openai_base_url_from_brief(brief)
        openai_auth_mode = _provider_auth_mode_from_brief(brief)
    except ValueError:
        # Fall back to legacy OpenAI-only path
        provider = "openai"
        model = DEFAULT_MODEL
        api_key = get_openai_key(brief)
        openai_base_url = _openai_base_url_from_brief(brief)
        openai_auth_mode = _provider_auth_mode_from_brief(brief)
        pipeline_notes.append("using legacy OpenAI key (no channel credentials)")

    # Spec resolution with revision continuity (Postcraft pattern)
    spec = spec_from_brief(brief)
    ok, errors, warnings = validate_spec(spec)
    if not ok:
        raise ValueError("Invalid storyboard spec: " + "; ".join(errors))

    # Revision continuity: restore prior spec if this is a revision with sparse brief
    original_block = _restore_from_prior(brief)
    is_revision = bool(
        brief.get("revision_prompt")
        or brief.get("source_image")
        or brief.get("source_image_data_b64")
        or original_block
    )
    if is_revision and original_block:
        prior_spec = original_block.get("storyboard_spec") or original_block.get("spec")
        if isinstance(prior_spec, dict) and not spec.get("acts"):
            spec = prior_spec
            pipeline_notes.append("restored spec from prior artifact block")

    run_id = str(brief.get("run_id") or f"run_{int(time.time())}")
    title = str((spec.get("project") or {}).get("title") or brief.get("title") or "storyboard")
    version = str((spec.get("revision") or {}).get("variation_id") or brief.get("variation_id") or "v001")
    stem = f"{slugify(title)}_{slugify(version, 'v001')}_{slugify(run_id, 'run')}"[:200]
    out_dir = Path(str(brief.get("output_dir") or RUNS_ROOT)).expanduser()
    out_path = Path(str(brief.get("out") or brief.get("output_path") or out_dir / f"{stem}.png")).expanduser()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Resolve aspect ratio / explicit size to a provider-safe size.
    aspect_ratio = str((spec.get("project") or {}).get("aspect_ratio") or brief.get("aspect_ratio") or "16:9").strip()
    requested_size = (spec.get("job") or {}).get("size") or brief.get("size") or _SIZE_MAP.get(aspect_ratio, DEFAULT_SIZE)
    size = _normalize_requested_size(requested_size)

    with tempfile.TemporaryDirectory(prefix="storyboard_edit_") as td:
        temp_dir = Path(td)
        source = _write_optional_image(temp_dir, "source.png", brief.get("source_image") or brief.get("source_image_data_b64") or brief.get("source_image_path"))
        mask = _write_optional_image(temp_dir, "mask.png", brief.get("mask_image") or brief.get("mask_image_data_b64") or brief.get("mask_image_path"))

        # Brand refs: from brief first, then fall back to paths persisted in spec.brand_assets.
        raw_brand_refs: list[Any] = [r for r in (brief.get("reference_images") or brief.get("refs") or []) if r]
        if not raw_brand_refs:
            ba = spec.get("brand_assets") if isinstance(spec.get("brand_assets"), dict) else {}
            raw_brand_refs = [
                asset["path"] for asset in (ba.get("reference_images") or [])
                if isinstance(asset, dict) and asset.get("path") and Path(asset["path"]).exists()
            ]
        brand_refs: list[Path] = []
        brand_ref_labels: list[str] = []
        for idx, value in enumerate(raw_brand_refs[:3], start=1):
            ref = _write_optional_image(temp_dir, f"brand_ref_{idx}.png", value)
            if ref:
                brand_refs.append(ref)
                if isinstance(value, dict):
                    label = str(value.get("panel_label") or value.get("placement_role") or value.get("title") or f"brand reference {idx}")
                else:
                    label = f"brand reference {idx}"
                brand_ref_labels.append(label)

        revision_prompt = str(brief.get("revision_prompt") or "").strip() or None
        prompt = build_prompt(spec, has_source=bool(source), has_mask=bool(mask), has_brand_refs=bool(brand_refs), ref_count=len(brand_refs), revision_prompt=revision_prompt, brand_ref_labels=brand_ref_labels)

        # gpt-image-2 dispatch: edit (up to 4 images) or generate
        if source or brand_refs:
            images = ([source] if source else []) + brand_refs[:3]
            mode = "edit" if source and not brand_refs else ("edit_with_refs" if source else "generate_with_refs")
            if openai_auth_mode == "oauth":
                image_inputs: list[tuple[bytes, str, str]] = []
                for idx, image_path in enumerate(images, start=1):
                    label = "source storyboard image" if idx == 1 and source else f"brand reference {idx}"
                    image_inputs.append((Path(image_path).read_bytes(), label, "image/png"))
                image_bytes = _call_openai_codex_image_generation(
                    prompt, brief, api_key, model, size,
                    images=image_inputs,
                    action="edit" if source else "generate",
                )
                response_meta = {"response_kind": "codex_image_generation"}
            else:
                response = _call_openai_edit(spec, prompt, images, brief, api_key, model, size, mask=mask, base_url=openai_base_url)
                image_bytes, response_meta = _image_response_to_bytes(response)
        else:
            mode = "generate"
            if openai_auth_mode == "oauth":
                image_bytes = _call_openai_codex_image_generation(prompt, brief, api_key, model, size, action="generate")
                response_meta = {"response_kind": "codex_image_generation"}
            else:
                response = _call_openai_generate(spec, prompt, brief, api_key, model, size, base_url=openai_base_url)
                image_bytes, response_meta = _image_response_to_bytes(response)

    out_path.write_bytes(image_bytes)
    audit_stem = out_path.with_suffix("")
    write_json(audit_stem.with_suffix(".spec.json"), spec)
    audit_stem.with_suffix(".prompt.txt").write_text(prompt + "\n", encoding="utf-8")

    # Thumbnail (Postcraft pattern) — non-blocking
    thumb_b64, thumb_mime = _make_thumbnail(image_bytes)
    if not thumb_b64:
        pipeline_notes.append("Pillow unavailable — thumbnail omitted")

    # Audit trail (Postcraft pattern) — non-blocking
    _write_audit(
        {"title": title, "version": version, "mode": mode, "provider": provider, "model": model,
         "size": size, "byte_size": len(image_bytes), "latency_ms": round((time.perf_counter() - start) * 1000),
         "warnings": warnings, "pipeline_notes": pipeline_notes},
        f"storyboard_{slugify(title)}",
    )

    response_meta.update(
        {
            "output_path": str(out_path),
            "byte_size": len(image_bytes),
            "mode": mode,
            "model": model,
            "provider": provider,
            "size": size,
            "latency_ms": round((time.perf_counter() - start) * 1000),
            "warnings": warnings,
        }
    )
    write_json(audit_stem.with_suffix(".response.json"), response_meta)

    return {
        "status": "succeeded",
        "mode": mode,
        "spec": spec,
        "prompt": prompt,
        "image_bytes": image_bytes,
        "image_data_b64": base64.b64encode(image_bytes).decode("utf-8"),
        "thumb_b64": thumb_b64,
        "thumb_mime": thumb_mime,
        "mime_type": "image/png",
        "output_path": str(out_path),
        "spec_path": str(audit_stem.with_suffix(".spec.json")),
        "prompt_path": str(audit_stem.with_suffix(".prompt.txt")),
        "response_path": str(audit_stem.with_suffix(".response.json")),
        "byte_size": len(image_bytes),
        "provider": provider,
        "model": model,
        "size": size,
        "latency_ms": round((time.perf_counter() - start) * 1000),
        "validation_warnings": warnings,
        "pipeline_notes": pipeline_notes,
    }
