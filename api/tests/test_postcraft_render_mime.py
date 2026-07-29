import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path("/external_plugins/postcraft/capabilities/postcraft/render/module.py")
if not PLUGIN_ROOT.exists():
    PLUGIN_ROOT = ROOT / "plugins/postcraft/capabilities/postcraft/render/module.py"
spec = importlib.util.spec_from_file_location("postcraft_render_module", PLUGIN_ROOT)
assert spec and spec.loader
render = importlib.util.module_from_spec(spec)
spec.loader.exec_module(render)


def test_full_image_mime_is_sniffed_separately_from_jpeg_thumbnail():
    assert render._sniff_mime(b"\x89PNG\r\n\x1a\nrest") == "image/png"
    assert render._sniff_mime(b"\xff\xd8\xffrest") == "image/jpeg"


def test_operator_reference_is_preserved_ahead_of_optional_brand_refs_on_initial_render():
    refs = [
        {"title": "Brand Logo", "drive_file_id": "logo", "placement_role": "logo", "panel_label": "OFFICIAL BRAND LOGO", "_auto_injected": True},
        {"title": "Brand Ref 1", "drive_file_id": "brand-1", "_auto_injected": True},
        {"title": "Brand Ref 2", "drive_file_id": "brand-2", "_auto_injected": True},
        {"title": "Brand Ref 3", "drive_file_id": "brand-3", "_auto_injected": True},
        {"title": "Ginto-profile.png", "drive_file_id": "ginto", "source": "google_drive"},
    ]
    selected, notes = render._select_reference_images(refs, False)
    ids = [r.get("drive_file_id") for r in selected]
    assert ids == ["logo", "ginto", "brand-1", "brand-2"]
    assert any("operator references" in note for note in notes)
