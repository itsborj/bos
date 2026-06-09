from __future__ import annotations

from types import SimpleNamespace

import pytest

from routers.runs import _extract_visual_constraints, _inject_campaign_brand_kit_style
from tests.test_media_image_local_renderer import _load_module_class


BRAND_KIT = """# Klaroha — Campaign Brand Kit
This Campaign Brand Kit is a long-lived onboarding artifact that defines the minimum practical brand, visual, voice, and component rules needed to generate consistent campaigns.

## 1. Campaign Brand Kit Overview
| Category | Description |
| --- | --- |
| Brand name | Klaroha |
| Primary product/service | Demand-Capture Infrastructure |
| Target audience | Fragmented high-value sellers |

## 2. Color Palette
| Token Name | Hex Value | Usage |
| --- | --- | --- |
| `color-primary` | #0B3D2E | Primary brand color, used for headlines and CTAs |
| `color-primary-dark` | #080B0D | Darker variant of primary color, used for backgrounds and overlays |
| `color-accent` | #826D40 | Warm accent color, used for highlights and emphasis |
| `bg-subtle` | #F5F1E8 | Subtle background color, used for card fills and textures |

## 3. Tone of Voice
* Voice summary: Clear, practical, and commercially grounded, with operator-focused and sales-aware language.
* Tone: Confident, direct, strategic, calm, and composed.
* Banned words or phrases: "Revolutionary," "magical," "effortless," and "10x."
* CTA language rules: Use direct language such as "Capture buyer intent" or "Qualify serious prospects."

## 4. Typography Basics
* `font-heading`: Manrope, a clean and modern sans-serif font.
* `font-body`: Inter, a clear and readable sans-serif font.
"""


def test_extract_visual_constraints_skips_overview_and_keeps_brand_rules() -> None:
    constraints = _extract_visual_constraints(BRAND_KIT)

    assert "#0B3D2E" in constraints
    assert "#826D40" in constraints
    assert "Manrope" in constraints
    assert "Inter" in constraints
    assert "Confident, direct, strategic" in constraints
    assert "Never generate fake text" in constraints
    assert "Campaign Brand Kit Overview" not in constraints
    assert "Primary product/service" not in constraints


@pytest.mark.asyncio
async def test_chat_injected_raw_brand_kit_is_converted_to_visual_constraints() -> None:
    brief = {
        "brand_name": "Klaroha",
        "product_name": "Demand-Capture Infrastructure",
        "campaign_brand_kit_excerpt": BRAND_KIT,
    }

    out = await _inject_campaign_brand_kit_style(brief, SimpleNamespace(id="ws"), None, None)

    assert out["campaign_brand_kit_excerpt"] == BRAND_KIT
    assert "brand_visual_constraints" in out
    assert "#0B3D2E" in out["brand_visual_constraints"]
    assert "Manrope" in out["brand_visual_constraints"]
    assert "Campaign Brand Kit Overview" not in out["brand_visual_constraints"]


def test_media_image_fallback_prompt_is_brand_locked_when_constraints_present() -> None:
    module = _load_module_class()()

    prompt = module._build_prompt({
        "brand_name": "Klaroha",
        "product_name": "Demand-Capture Infrastructure",
        "audience": "Fragmented high-value sellers",
        "brand_tone": "confident and calm",
        "brand_visual_constraints": _extract_visual_constraints(BRAND_KIT),
    })

    assert "brand-aligned" in prompt
    assert "not a generic stock" in prompt
    assert "Do not include readable text" in prompt
    assert "#0B3D2E" in prompt
    assert "Manrope" in prompt
    assert "Campaign Brand Kit Overview" not in prompt
