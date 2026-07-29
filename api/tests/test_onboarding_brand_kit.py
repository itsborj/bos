from __future__ import annotations

from routers.onboarding import (
    _campaign_brand_kit_markdown,
    _campaign_seed_from_profile,
    _profile_json_from_profile,
    _profile_to_brief,
)


def test_onboarding_profile_json_keeps_brand_fields_without_foundation_payload() -> None:
    profile_json = _profile_json_from_profile({
        "brand_name": "Submitted Brand",
        "voice": "warm expert",
        "tone": "friendly",
        "values": ["trust", "speed"],
    })

    assert profile_json == {
        "voice": "warm expert",
        "tone": "friendly",
        "values": ["trust", "speed"],
    }


def test_onboarding_profile_persists_visual_identity() -> None:
    profile_json = _profile_json_from_profile({
        "voice": "warm expert",
        "tone": "friendly",
        "values": ["trust"],
        "visual_identity": {
            "colors": {"primary": "#123456"},
            "style": ["editorial", "human"],
            "typography": {"heading": "Manrope"},
            "avoid": ["neon", "fake logos"],
        },
    })

    assert profile_json["color_palette"] == {"primary": "#123456"}
    assert profile_json["visual_language"] == ["editorial", "human"]
    assert profile_json["typography"] == {"heading": "Manrope"}
    assert profile_json["negative_prompts"] == ["neon", "fake logos"]


def test_submitted_profile_is_flattened_for_brand_kit_brief() -> None:
    profile = {
        "brand_name": "Submitted Brand",
        "voice": "warm expert",
        "tone": "friendly",
        "values": ["trust", "speed"],
        "products": [
            {
                "name": "Profile Product",
                "tagline": "Proof from profile",
                "benefits": ["profile benefit", "less guesswork"],
            }
        ],
        "audiences": [
            {
                "name": "Profile Buyers",
                "demographics": "Operators who submitted the onboarding profile.",
                "pain_points": ["stale kits", "generic copy"],
            }
        ],
    }

    brief = _profile_to_brief(profile)

    assert brief["brand_name"] == "Submitted Brand"
    assert brief["voice"] == "warm expert"
    assert brief["tone"] == "friendly"
    assert brief["product_name"] == "Profile Product"
    assert brief["tagline"] == "Proof from profile"
    assert brief["key_benefit"] == "profile benefit"
    assert brief["audience"] == "Profile Buyers"
    assert brief["pain_points"] == ["stale kits", "generic copy"]


def test_onboarding_campaign_seed_extracts_live_campaign_from_profile() -> None:
    seed = _campaign_seed_from_profile(
        {
            "brand_name": "Submitted Brand",
            "products": [
                {
                    "name": "Profile Product",
                    "tagline": "Proof from profile",
                    "benefits": ["profile benefit", "less guesswork"],
                }
            ],
            "audiences": [
                {
                    "name": "Profile Buyers",
                    "demographics": "Operators who submitted the onboarding profile.",
                    "pain_points": ["stale kits", "generic copy"],
                }
            ],
        },
        brand_name="Submitted Brand",
    )

    assert seed["name"] == "Submitted Brand — Profile Product Campaign"
    assert seed["audience"] == "Profile Buyers"
    assert seed["message_angle"] == "Proof from profile"
    assert "Generate qualified demand for Profile Product among Profile Buyers." in seed["initial_intent"]
    assert "Core promise: Proof from profile." in seed["initial_intent"]
    assert seed["campaign_json"]["source"] == "onboarding.brand_profile"
    assert seed["campaign_json"]["business_objective"] == seed["initial_intent"]
    assert seed["campaign_json"]["product_name"] == "Profile Product"
    assert seed["campaign_json"]["audience_name"] == "Profile Buyers"


def test_brand_kit_markdown_uses_submitted_profile_fields() -> None:
    brief = _profile_to_brief({
        "brand_name": "Submitted Brand",
        "voice": "warm expert",
        "tone": "friendly",
        "values": ["trust", "speed"],
        "products": [{"name": "Profile Product", "tagline": "Proof from profile", "benefits": ["profile benefit"]}],
        "audiences": [{"name": "Profile Buyers", "pain_points": ["stale kits"]}],
    })

    markdown = _campaign_brand_kit_markdown(brief, "Fallback — Campaign Brand Kit")

    assert "# Submitted Brand — Brand Creative Brief" in markdown
    assert "**Core promise:** Proof from profile" in markdown
    assert "**Primary product/service:** Profile Product" in markdown
    assert "**Primary audience:** Profile Buyers" in markdown
    assert "warm expert" in markdown
    assert "Templates are optional" in markdown
    assert "Fallback" not in markdown


def test_service_brand_creative_brief_has_no_b2b_or_cross_brand_bleed() -> None:
    brief = _profile_to_brief({
        "brand_name": "Golden Gate Memorial",
        "voice": "warm, calm, respectful, and emotionally intelligent",
        "tone": "empathetic",
        "values": ["dignity", "preparedness", "family"],
        "products": [{"name": "Memorial Garden and Columbarium", "tagline": "Plan today", "benefits": ["Dignified resting place"]}],
        "audiences": [{"name": "Filipino Family Protector", "pain_points": ["Leaving family unprepared"]}],
    })

    markdown = _campaign_brand_kit_markdown(brief, "Fallback — Campaign Brand Kit")

    assert "No explicit palette supplied" in markdown
    assert "Book a Memorial demo" not in markdown
    assert "Start a pilot" not in markdown
    assert "Sales Ready" not in markdown
    assert "Racing Green" not in markdown
    assert "Obsidian" not in markdown


def test_brand_kit_markdown_preserves_visual_rules_from_brand_document() -> None:
    brief = _profile_to_brief({
        "brand_name": "Klaroha",
        "voice": "clear, practical, commercially grounded",
        "tone": "authoritative",
        "values": ["clarity", "precision", "restraint"],
        "products": [{"name": "Klaroha Demand-Capture Infrastructure", "tagline": "Turn buyer intent into qualified conversations"}],
        "audiences": [{"name": "Fragmented High-Value Sellers", "pain_points": ["slow replies"]}],
    })
    brief["document_text"] = """
    Racing Green #0b3d2e
    Forest #4b7c54
    Sage #9cbd77
    Amber #fcc167
    Coral #ef8250
    Crimson #de425b
    Highlight #fffe9c
    Pure White #FFFFFF
    Ivory #F5F1E8
    Obsidian #080B0D
    Display / Headline: Manrope. Body / UI / Data: Inter.
    Maximum corner radius: 2px. Default for all components: 0px.
    Dark foreground on light background. Light foreground on dark background.
    """

    markdown = _campaign_brand_kit_markdown(brief, "Fallback — Campaign Brand Kit")

    assert "`#0b3d2e`" in markdown
    assert "`#ef8250`" in markdown
    assert "`#080b0d`" in markdown
    assert "`#1F4E5F`" not in markdown
    assert "Manrope" in markdown
    assert "Templates are optional" in markdown


def test_generic_palette_document_does_not_receive_klaroha_defaults() -> None:
    brief = _profile_to_brief({
        "brand_name": "Different Brand",
        "voice": "focused expert",
        "tone": "professional",
        "values": ["trust", "speed"],
        "products": [{"name": "Different Product", "tagline": "A sharper operating layer"}],
        "audiences": [{"name": "Operations Leaders", "pain_points": ["manual reporting"]}],
    })
    brief["document_text"] = """
    Color Palette
    Primary color #112233
    Secondary color #445566
    Accent color #778899
    """

    markdown = _campaign_brand_kit_markdown(brief, "Fallback — Campaign Brand Kit")

    assert "`#112233`" in markdown
    assert "`#445566`" in markdown
    assert "`#778899`" in markdown
    assert "`#0b3d2e`" not in markdown
    assert "`#ef8250`" not in markdown


def test_common_color_names_do_not_trigger_klaroha_palette() -> None:
    brief = _profile_to_brief({
        "brand_name": "AmberOps",
        "voice": "precise operator",
        "tone": "professional",
        "values": ["trust", "speed"],
        "products": [{"name": "AmberOps Platform", "tagline": "Operations without drift"}],
        "audiences": [{"name": "Operations Leaders", "pain_points": ["handoff drift"]}],
    })
    brief["document_text"] = """
    Brand Colors
    Primary color #112233
    Amber accent #ffbf00
    Typography: Inter for all text.
    """

    markdown = _campaign_brand_kit_markdown(brief, "Fallback — Campaign Brand Kit")

    assert "`#112233`" in markdown
    assert "`#ffbf00`" in markdown
    assert "`#0b3d2e`" not in markdown
    assert "`#ef8250`" not in markdown
    assert "Inter for all text" in markdown
    assert "Manrope" not in markdown
