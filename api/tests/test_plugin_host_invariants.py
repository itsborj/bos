"""
T012 / T023 — Plugin host invariant tests.

T012: Empty external plugin root → zero plugin capabilities, no startup crash.
T023: One broken plugin does not prevent a valid plugin from loading.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
import plugin_loader as pl
import registry as reg


@pytest.fixture(autouse=True)
def reset_plugin_loader_state():
    """Clear plugin loader and registry scan state before and after each test.

    The registry's _scanned flag is reset too so that the next test that calls
    list_all() / get_module() triggers a fresh scan and repopulates
    _module_to_plugin.  Without this, tests that run after the invariant tests
    see an empty _module_to_plugin even though the registry thinks it has
    already scanned (because _scanned remained True).
    """
    def _clear():
        pl._loaded.clear()
        pl._error_states.clear()
        pl._module_to_plugin.clear()
        pl._connection_to_plugin.clear()
        pl._EXTERNAL_PLUGIN_ROOT = None
        pl._scanned = False
        # Reset the registry so subsequent tests get a fresh scan with fully
        # populated _module_to_plugin / _loaded state.
        reg._scanned = False
        reg._registry.clear()

    _clear()
    yield
    _clear()


def _minimal_channel_json(plugin_id: str) -> dict:
    return {
        "plugin_id": plugin_id,
        "name": f"Test {plugin_id}",
        "version": "1.0.0",
        "klaroha_version": ">=0.0.0",
        "capability_ids": [],
        "credential_slots": [],
    }


def test_required_plugin_vars_ignores_optional_platform_fallbacks():
    manifest = pl.ChannelPluginManifest(**{
        **_minimal_channel_json("test.optional"),
        "credential_slots": [
            {"key": "provider_api_key", "type": "backend_provider_api_key", "module": "postcraft.render"},
            {"key": "platform_openai_key", "type": "platform_var", "var": "PLATFORM_OPENAI_KEY", "optional": True},
            {"key": "google_drive_page_token", "type": "social_token", "platform": "google_drive"},
        ],
    })

    assert pl.required_plugin_vars(manifest) == []


def test_media_plugin_manifests_mark_legacy_provider_env_slots_optional():
    root = Path(__file__).resolve().parents[2] / "plugins"
    for rel, expected_var in [
        ("postcraft/channel.json", "PLATFORM_OPENAI_KEY"),
        ("storyboard/channel.json", "PLATFORM_OPENAI_KEY"),
        ("previs-motion/channel.json", "BYTEPLUS_API_KEY"),
    ]:
        data = json.loads((root / rel).read_text(encoding="utf-8"))
        slot = next(s for s in data["credential_slots"] if s.get("type") == "platform_var" and s.get("var") == expected_var)
        assert slot.get("optional") is True


# ── T012 ─────────────────────────────────────────────────────────────────────

def test_t012_empty_root_returns_no_plugin_states():
    """T012: Empty external root directory → _scan_root returns [] (no crash)."""
    with tempfile.TemporaryDirectory() as tmp:
        states = pl._scan_root(Path(tmp), source="external")
    assert states == []


def test_t012_empty_root_leaves_no_error_states():
    """T012: Empty root → no error_states recorded."""
    with tempfile.TemporaryDirectory() as tmp:
        pl._scan_root(Path(tmp), source="external")
    assert pl._error_states == {}


def test_t012_dirs_without_channel_json_are_silently_skipped():
    """T012: Directories without channel.json are silently skipped, not quarantined."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "not_a_plugin").mkdir()
        (root / "also_not_a_plugin").mkdir()
        (root / "also_not_a_plugin" / "README.md").write_text("not a plugin")
        states = pl._scan_root(root, source="external")
    assert states == []
    assert pl._error_states == {}


# ── T023 ─────────────────────────────────────────────────────────────────────

def test_t023_broken_json_does_not_hide_valid_plugin():
    """T023: Plugin with invalid JSON in channel.json doesn't prevent a valid sibling from loading."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        valid_dir = root / "valid_plugin"
        valid_dir.mkdir()
        (valid_dir / "channel.json").write_text(json.dumps(_minimal_channel_json("test.valid")))

        broken_dir = root / "broken_plugin"
        broken_dir.mkdir()
        (broken_dir / "channel.json").write_text("{ this is not valid json }")

        states = pl._scan_root(root, source="external")

    loaded_ids = [s.manifest.plugin_id for s in states]
    assert "test.valid" in loaded_ids
    assert "test.valid" not in pl._error_states


def test_t023_invalid_manifest_schema_does_not_hide_valid_plugin():
    """T023: Plugin with schema-invalid channel.json (missing required fields) is quarantined; valid sibling loads."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        valid_dir = root / "valid_plugin"
        valid_dir.mkdir()
        (valid_dir / "channel.json").write_text(json.dumps(_minimal_channel_json("test.valid2")))

        invalid_dir = root / "invalid_schema_plugin"
        invalid_dir.mkdir()
        (invalid_dir / "channel.json").write_text(json.dumps({
            "plugin_id": "test.bad_schema",
            # missing required fields: name, version, klaroha_version
        }))

        states = pl._scan_root(root, source="external")

    loaded_ids = [s.manifest.plugin_id for s in states]
    assert "test.valid2" in loaded_ids
    assert "test.valid2" not in pl._error_states


def test_t023_two_plugins_same_id_second_is_quarantined_not_first():
    """T023: Duplicate plugin_id quarantines the second, not the first; no crash."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        for name in ("plugin_a", "plugin_b"):
            d = root / name
            d.mkdir()
            (d / "channel.json").write_text(json.dumps(_minimal_channel_json("test.duplicate")))

        states = pl._scan_root(root, source="external")

    assert len(states) == 1
    assert states[0].manifest.plugin_id == "test.duplicate"
    assert "test.duplicate" in pl._error_states
    assert "duplicate_plugin_id" in pl._error_states["test.duplicate"]["reason"]


def test_scan_plugins_is_idempotent_after_activation_lookup(monkeypatch):
    """Regression: CMO loads active plugin IDs before building tools.

    That calls scan_plugins() before registry._scan() calls it again. The second
    call must return the already-loaded states, not quarantine them as duplicate
    plugin IDs and hide CMO capabilities like Storyboard.
    """
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        plugin_dir = root / "storyboard"
        plugin_dir.mkdir()
        (plugin_dir / "channel.json").write_text(json.dumps({
            **_minimal_channel_json("channel.storyboard"),
            "capability_ids": ["storyboard.render"],
        }))

        monkeypatch.setenv("EXTERNAL_PLUGINS_DIR", str(root))
        monkeypatch.setattr(pl, "_LOAD_INTERNAL_PLUGINS", False)
        first = pl.scan_plugins()
        second = pl.scan_plugins()

    assert [s.manifest.plugin_id for s in first] == ["channel.storyboard"]
    assert [s.manifest.plugin_id for s in second] == ["channel.storyboard"]
    assert pl._error_states == {}
    assert pl._module_to_plugin["storyboard.render"] == "channel.storyboard"
