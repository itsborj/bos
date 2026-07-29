"""OpenAI REST helpers for Postcraft — stdlib only, no openai package.

Three operations:
  1. vision_intake   — classify a single brand asset (chat/completions with vision)
  2. generate_image  — call images/edits with composite reference sheet (multipart)
  3. analyze_output  — gpt-4o-mini breakdown of the generated image
"""
from __future__ import annotations

import base64
import json
import logging
import os
from urllib.error import HTTPError
from urllib.request import Request, urlopen


class ScopeError(RuntimeError):
    """Raised when the API key lacks the required OpenAI scope for image generation."""


def _raise_http(exc: HTTPError) -> None:
    """Re-raise HTTPError with the response body included for easier debugging."""
    try:
        body = exc.read().decode("utf-8", errors="replace")
    except Exception:
        body = "(unreadable)"
    if exc.code == 401 and "api.model.images.request" in body:
        raise ScopeError(f"HTTP {exc.code} from OpenAI: {body}") from exc
    if "billing_hard_limit_reached" in body:
        raise RuntimeError(
            f"HTTP {exc.code} from OpenAI Image API: {body}\n"
            "This response comes from the OpenAI credential selected for image generation. "
            "Reconnect OpenAI in Admin → AI Providers or choose another image backend."
        ) from exc
    raise RuntimeError(f"HTTP {exc.code} from OpenAI: {body}") from exc


_DEFAULT_API_ROOT = "https://api.openai.com/v1"
_USER_AGENT = "BOS-Postcraft/1.0"
_IMAGE_TIMEOUT = int(os.getenv("POSTCRAFT_OPENAI_IMAGE_TIMEOUT", "360"))
_DOWNLOAD_TIMEOUT = int(os.getenv("POSTCRAFT_OPENAI_DOWNLOAD_TIMEOUT", "120"))
logger = logging.getLogger("bos.postcraft.openai_client")


def _api_root(base_url: str | None = None) -> str:
    """Return the OpenAI REST root used by CMO Brain's API-key path.

    CMO Brain stores the canonical provider root in the channel credential packet
    as `openai_api_base_url`/`provider_api_base_url`. Env vars remain a dev-only
    escape hatch for OpenAI-compatible test gateways.
    """
    raw = (base_url or os.getenv("OPENAI_BASE_URL") or os.getenv("OPENAI_API_BASE") or _DEFAULT_API_ROOT).strip().rstrip("/")
    for suffix in ("/chat/completions", "/responses", "/images/edits", "/images/generations"):
        if raw.endswith(suffix):
            raw = raw[: -len(suffix)].rstrip("/")
    return raw or _DEFAULT_API_ROOT


def _endpoint(path: str, base_url: str | None = None) -> str:
    return f"{_api_root(base_url)}/{path.lstrip('/')}"


def _jwt_account_id(token: str) -> str:
    try:
        payload = token.split(".")[1] + "=" * (-len(token.split(".")[1]) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload.encode()).decode())
        return str(data.get("https://api.openai.com/auth", {}).get("chatgpt_account_id") or "")
    except Exception:
        return ""


def _codex_text_model(model: str | None = None) -> str:
    # The Responses image_generation hosted tool runs under a text-capable model;
    # GPT Image model IDs are configured on BOS plugins but are not valid as the
    # main `model` field for the Codex/Responses endpoint.
    raw = str(model or "").strip().lower()
    if raw.startswith("gpt-") and "image" not in raw:
        return raw
    return os.getenv("POSTCRAFT_CODEX_IMAGE_MODEL") or os.getenv("OPENAI_CODEX_IMAGE_MODEL") or "gpt-5.5"


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
        with urlopen(dl, timeout=_DOWNLOAD_TIMEOUT) as r:
            return r.read()
    if value.startswith("data:") and "," in value:
        value = value.split(",", 1)[1]
    return base64.b64decode(value, validate=False)


def generate_image_codex(
    prompt: str,
    access_token: str,
    *,
    model: str = "gpt-5.5",
    size: str = "1024x1024",
    quality: str = "high",
    images: list[tuple[bytes, str, str]] | None = None,
    action: str = "auto",
) -> bytes:
    """Generate/edit via the Codex OAuth Responses `image_generation` tool.

    This is the ChatGPT/Codex auth path. It intentionally does not call the
    public `/v1/images/*` endpoints, which reject Codex OAuth with missing
    `api.model.images.request` scope.
    """
    content: list[dict] = [{"type": "input_text", "text": prompt}]
    for idx, (img, label, mime) in enumerate((images or [])[:4], start=1):
        b64 = base64.b64encode(img).decode()
        content.append({"type": "input_text", "text": f"Reference image {idx}: {label}"})
        content.append({"type": "input_image", "image_url": f"data:{mime or 'image/png'};base64,{b64}"})

    tool: dict = {"type": "image_generation", "size": size or "1024x1024", "quality": quality or "high"}
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
        "Authorization": f"Bearer {access_token}",
        "chatgpt-account-id": _jwt_account_id(access_token),
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
    event_samples: list[dict[str, object]] = []
    try:
        with urlopen(req, timeout=_IMAGE_TIMEOUT) as r:
            for raw_line in r:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if line.startswith("data: "):
                    data_str = line[6:].strip()
                elif line.startswith("{"):
                    # Some Codex-compatible gateways return JSON lines even
                    # when stream=true instead of SSE envelopes.
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
                    sample = {"type": event_type, "keys": sorted(list(event.keys()))[:12]}
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
    except HTTPError as e:
        _raise_http(e)
    if not image_b64:
        seen = ", ".join(event_types[:12]) or "no recognized events"
        logger.warning("Postcraft Codex image_generation returned no image payload: events=%s samples=%s", seen, event_samples)
        raise RuntimeError(f"No image data in OpenAI Codex image_generation response (events: {seen})")
    try:
        return _decode_codex_image(image_b64)
    except (ValueError, base64.binascii.Error) as exc:
        logger.warning(
            "Postcraft Codex image_generation returned invalid image data: payload_prefix=%r events=%s samples=%s",
            image_b64[:160],
            event_types,
            event_samples,
        )
        raise RuntimeError("OpenAI Codex image_generation returned invalid image data") from exc


def _chat(messages: list, api_key: str, model: str = "gpt-4o-mini", max_tokens: int = 300, base_url: str | None = None) -> str:
    payload = json.dumps({"model": model, "messages": messages, "max_tokens": max_tokens}).encode()
    req = Request(
        _endpoint("chat/completions", base_url),
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": _USER_AGENT,
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=60) as r:
            return json.loads(r.read())["choices"][0]["message"]["content"] or ""
    except HTTPError as e:
        _raise_http(e)


def vision_intake(image_b64: str, mime: str, title: str, api_key: str, base_url: str | None = None) -> dict:
    """Run vision classification on one brand asset.

    Returns a dict with:
      asset_type: logo | mascot | property_photo | portrait | product | background | unknown
      subject:    plain-English description of what the image shows
      panel_label: ALL-CAPS instruction for the composite panel label
      placement_role: logo | hero_image | portrait | background | accent | unknown
    """
    if image_b64.startswith("data:"):
        data_url = image_b64
    else:
        data_url = f"data:{mime};base64,{image_b64}"

    prompt = (
        f'You are a brand asset classifier for a social media post generator.\n'
        f'The attached image is titled "{title}".\n\n'
        "Classify this image and respond with ONLY valid JSON — no markdown, no explanation:\n"
        "{\n"
        '  "asset_type": "<logo|mascot|property_photo|portrait|product|background|unknown>",\n'
        '  "subject": "<one sentence describing what is shown>",\n'
        '  "panel_label": "<ALL CAPS label — what this asset is and where to place it in a social post>",\n'
        '  "placement_role": "<logo|hero_image|portrait|background|accent|unknown>"\n'
        "}\n\n"
        "panel_label examples:\n"
        '  "BRAND LOGO — place at top center of design"\n'
        '  "HERO PROPERTY PHOTO — fill right-side hero panel, curved gold border on left edge"\n'
        '  "AGENT PORTRAIT — place subject on right side with face in upper third"\n'
        '  "MASCOT CHARACTER — place lower right, full body visible"\n'
        "Be specific about where this asset should go in a premium social media post."
    )

    messages = [{
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": data_url, "detail": "low"}},
            {"type": "text", "text": prompt},
        ],
    }]

    try:
        raw = _chat(messages, api_key, model="gpt-4o-mini", max_tokens=300, base_url=base_url)
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(raw[start:end])
    except Exception:
        pass

    return {
        "asset_type": "unknown",
        "subject": title,
        "panel_label": f"{title.upper()} — use as brand asset",
        "placement_role": "unknown",
    }


def generate_image(composite_bytes: bytes, prompt: str, api_key: str, model: str = "gpt-image-2", size: str = "1024x1024", quality: str = "high", base_url: str | None = None) -> bytes:
    """Generate a branded post image via images/edits with the composite reference sheet."""
    boundary = "----PostcraftBoundary7a3f9c"
    body = bytearray()

    def field(name: str, value: str):
        body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode())

    def file_field(name: str, filename: str, content: bytes, mime: str):
        body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"; filename=\"{filename}\"\r\nContent-Type: {mime}\r\n\r\n".encode())
        body.extend(content)
        body.extend(b"\r\n")

    field("model", model)
    field("prompt", prompt)
    field("n", "1")
    field("size", size)
    if quality:
        field("quality", quality)
    file_field("image", "reference_sheet.png", composite_bytes, "image/png")
    body.extend(f"--{boundary}--\r\n".encode())

    req = Request(
        _endpoint("images/edits", base_url),
        data=bytes(body),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": _USER_AGENT,
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=_IMAGE_TIMEOUT) as r:
            result = json.loads(r.read())
    except HTTPError as e:
        _raise_http(e)

    item = result["data"][0]
    if item.get("b64_json"):
        return base64.b64decode(item["b64_json"])
    if item.get("url"):
        dl = Request(item["url"], headers={"User-Agent": _USER_AGENT})
        with urlopen(dl, timeout=_DOWNLOAD_TIMEOUT) as r:
            return r.read()
    raise RuntimeError("No image data in OpenAI images/edits response")


def generate_image_text_only(prompt: str, api_key: str, model: str = "gpt-image-2", size: str = "1024x1024", quality: str = "high", base_url: str | None = None) -> bytes:
    """Text-to-image fallback when no reference images are available."""
    payload_obj = {
        "model": model,
        "prompt": prompt,
        "n": 1,
        "size": size,
    }
    if quality:
        payload_obj["quality"] = quality
    payload = json.dumps(payload_obj).encode()
    req = Request(
        _endpoint("images/generations", base_url),
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": _USER_AGENT,
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=_IMAGE_TIMEOUT) as r:
            result = json.loads(r.read())
    except HTTPError as e:
        _raise_http(e)

    item = result["data"][0]
    if item.get("b64_json"):
        return base64.b64decode(item["b64_json"])
    if item.get("url"):
        dl = Request(item["url"], headers={"User-Agent": _USER_AGENT})
        with urlopen(dl, timeout=_DOWNLOAD_TIMEOUT) as r:
            return r.read()
    raise RuntimeError("No image data in OpenAI images/generations response")


def analyze_output(image_bytes: bytes, brief_summary: str, api_key: str, base_url: str | None = None) -> dict:
    """Vision analysis of the generated post image."""
    b64 = base64.b64encode(image_bytes).decode()
    data_url = f"data:image/png;base64,{b64}"

    prompt = (
        "Analyze this generated social media post image. Output ONLY valid JSON:\n"
        "{\n"
        '  "detected_elements": ["list every visual element you can see"],\n'
        '  "colors": ["dominant colors as hex or names"],\n'
        '  "layout": "description of composition and layout",\n'
        '  "typography": "fonts observed: styles, sizes, positioning",\n'
        '  "brand_assets_placed": ["which brand assets are visible and where"],\n'
        '  "copy_visible": ["all text visible in the image"],\n'
        '  "quality_flags": ["any issues: clipping, distortion, unreadable text, etc."],\n'
        '  "overall_assessment": "brief quality verdict"\n'
        "}\n\n"
        f"Expected brief: {brief_summary[:800]}"
    )

    messages = [{
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": data_url, "detail": "low"}},
            {"type": "text", "text": prompt},
        ],
    }]

    try:
        raw = _chat(messages, api_key, model="gpt-4o-mini", max_tokens=1000, base_url=base_url)
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(raw[start:end])
    except Exception:
        pass

    return {}
