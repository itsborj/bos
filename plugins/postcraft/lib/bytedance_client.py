"""BytePlus/ModelArk REST helpers for Postcraft — stdlib only, text-to-image only.

BytePlus Seedream does not support reference-sheet editing; prompt-only generation is used.
"""
from __future__ import annotations

import base64
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

_ARK_URL = "https://ark.ap-southeast.bytepluses.com/api/v3/images/generations"
_DEFAULT_MODEL = "seedream-4-5-251128"
_USER_AGENT = "BOS-Postcraft/1.1"

_SIZE_MAP = {
    "1024x1024": "1920x1920",
    "1024x1536": "1920x1920",
    "1536x1024": "1920x1920",
}


def generate_image(api_key: str, prompt: str, model: str | None, size: str) -> bytes:
    m = (model or _DEFAULT_MODEL).strip()
    ark_size = _SIZE_MAP.get(size, "1024x1024")

    payload = json.dumps({
        "model": m,
        "prompt": prompt,
        "n": 1,
        "size": ark_size,
        "response_format": "b64_json",
    }).encode()

    req = Request(
        _ARK_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": _USER_AGENT,
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=120) as r:
            result = json.loads(r.read())
    except HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            body = "(unreadable)"
        raise RuntimeError(f"HTTP {e.code} from BytePlus: {body}") from e

    item = result["data"][0]
    if item.get("b64_json"):
        return base64.b64decode(item["b64_json"])
    if item.get("url"):
        dl = Request(item["url"], headers={"User-Agent": _USER_AGENT})
        with urlopen(dl, timeout=60) as r:
            return r.read()
    raise RuntimeError("No image data in BytePlus response")
