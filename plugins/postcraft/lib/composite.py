"""Build a labeled composite reference sheet from N image assets.

gpt-image-2 via images.edit accepts exactly one source image.
This module composites multiple brand assets (logo, mascot, property photo, etc.)
into a single horizontal reference sheet with labeled panels so the model can
distinguish and correctly place each asset.

Proven technique from json-imagen prototype (v5.png, v6.png).
"""
from __future__ import annotations

import io
from typing import Sequence


def build_composite(assets: Sequence[tuple[bytes, str, str]], panel_size: int = 1024) -> bytes:
    """Composite assets into a horizontal reference sheet.

    Args:
        assets: List of (image_bytes, label, mime_type).
                Label is drawn into the panel so the model reads it.
        panel_size: Width/height of each panel in pixels.

    Returns:
        PNG bytes of the composite sheet.
    """
    from PIL import Image, ImageDraw, ImageFont

    n = len(assets)
    if n == 0:
        raise ValueError("No assets to composite")

    # Revisions can carry several operator-supplied references. A single
    # horizontal strip becomes too wide and may be downsampled badly by image
    # providers, so use a compact contact-sheet grid while keeping each panel
    # labeled. Existing one/two image cases still render naturally.
    cols = min(3, n)
    rows = (n + cols - 1) // cols
    sheet_w = panel_size * cols
    sheet_h = panel_size * rows
    sheet = Image.new("RGBA", (sheet_w, sheet_h), (30, 27, 24, 255))

    for i, (img_bytes, label, _mime) in enumerate(assets):
        img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")

        pad = 40
        max_w = panel_size - pad * 2
        max_h = panel_size - 90
        img.thumbnail((max_w, max_h), Image.LANCZOS)

        bg = Image.new("RGBA", (panel_size, panel_size), (30, 27, 24, 255))
        x = (panel_size - img.width) // 2
        y = (panel_size - img.height) // 2 + 20
        bg.paste(img, (x, y), img)

        draw = ImageDraw.Draw(bg)
        try:
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24
            )
        except Exception:
            font = ImageFont.load_default()
        safe_label = str(label or f"REFERENCE {i + 1}")[:96]
        draw.text((panel_size // 2, 16), safe_label, fill="#C79A42", font=font, anchor="mt")

        col = i % cols
        row = i // cols
        sheet.paste(bg, (col * panel_size, row * panel_size))

    buf = io.BytesIO()
    sheet.save(buf, format="PNG")
    return buf.getvalue()
