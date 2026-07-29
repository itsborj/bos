from types import SimpleNamespace
from uuid import uuid4

from services.brand_kit import _merge_brand_row_into_brand_kit


def test_merge_brand_row_into_brand_kit_builds_minimal_postcraft_scaffold():
    brand = SimpleNamespace(
        id=uuid4(),
        name="Klaroha",
        brand_json={
            "tone": "authoritative",
            "voice": "clear and practical",
            "values": ["clarity", "precision"],
        },
    )

    result = _merge_brand_row_into_brand_kit({}, brand)

    assert result["brand_id"] == str(brand.id)
    assert result["brand_name"] == "Klaroha"
    assert result["name"] == "Klaroha"
    assert result["tone"] == "authoritative"
    assert result["voice"] == "clear and practical"
    assert result["values"] == ["clarity", "precision"]
    assert result["visual_tone"] == "authoritative"
