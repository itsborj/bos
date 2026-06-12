from __future__ import annotations

from routers.onboarding import _campaign_brand_kit_markdown, _profile_to_brief


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

    assert "# Submitted Brand — Campaign Brand Kit" in markdown
    assert "| Core promise | Proof from profile |" in markdown
    assert "| Primary product/service | Profile Product |" in markdown
    assert "| Target audience | Profile Buyers |" in markdown
    assert "warm expert" in markdown
    assert "stale kits" in markdown
    assert "Fallback" not in markdown
