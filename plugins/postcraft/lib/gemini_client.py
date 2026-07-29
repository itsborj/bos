"""Gemini REST helpers for Postcraft — stdlib only.

Supports:
  generate_image  — generateContent with optional inline reference images
  generate_image_text_only — same, no references
"""
from __future__ import annotations

import base64
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

_BASE = "https://generativelanguage.googleapis.com/v1beta"
_DEFAULT_MODEL = "gemini-2.5-flash-image"
_USER_AGENT = "BOS-Postcraft/1.1"

_IMAGEN_MODELS = {"imagen-4.0-generate-001", "imagen-4.0-fast-generate-001"}


def _http_post(url: str, payload: dict, timeout: int = 120) -> dict:
    data = json.dumps(payload).encode()
    req = Request(url, data=data, headers={"Content-Type": "application/json", "User-Agent": _USER_AGENT}, method="POST")
    try:
        with urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            body = "(unreadable)"
        raise RuntimeError(f"HTTP {e.code} from Gemini: {body}") from e


def _extract_image(data: dict) -> bytes:
    """Pull image bytes from a generateContent or predict response."""
    # generateContent response
    candidates = data.get("candidates") or []
    for candidate in candidates:
        for part in (candidate.get("content") or {}).get("parts") or []:
            if "inlineData" in part:
                return base64.b64decode(part["inlineData"]["data"])

    # imagen predict response
    predictions = data.get("predictions") or []
    for pred in predictions:
        img = pred.get("bytesBase64Encoded") or pred.get("b64")
        if img:
            return base64.b64decode(img)

    raise ValueError("Gemini returned no image in response")


def generate_image(
    api_key: str,
    prompt: str,
    model: str | None,
    size: str,
    ref_parts: list[dict] | None = None,
) -> bytes:
    """Generate a post image via Gemini.

    ref_parts: list of {b64, mime_type, label} dicts from vision intake.
    Gemini receives each asset as inline inlineData with a label text part.
    """
    m = (model or _DEFAULT_MODEL).strip()

    if m in _IMAGEN_MODELS:
        # Imagen 4 uses predict endpoint, no reference image support
        url = f"{_BASE}/models/{m}:predict?key={api_key}"
        payload = {
            "instances": [{"prompt": prompt}],
            "parameters": {"sampleCount": 1},
        }
        return _extract_image(_http_post(url, payload))

    # gemini-2.5-flash-image / gemini-2.5-pro-image — supports inline reference images
    parts: list[dict] = []
    for ref in (ref_parts or []):
        parts.append({"text": f"[{ref['label']}]"})
        parts.append({"inlineData": {"mimeType": ref["mime_type"], "data": ref["b64"]}})

    size_note = f" Output size: {size.replace('x', '×')} pixels." if size else ""
    parts.append({"text": (
        "Use the reference images above according to their labels when placing brand assets.\n\n"
        + prompt + size_note
    )})

    url = f"{_BASE}/models/{m}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]},
    }
    return _extract_image(_http_post(url, payload, timeout=120))


def generate_image_text_only(api_key: str, prompt: str, model: str | None, size: str) -> bytes:
    return generate_image(api_key, prompt, model, size, ref_parts=None)
