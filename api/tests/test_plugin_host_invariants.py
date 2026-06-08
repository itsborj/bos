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


@pytest.fixture(autouse=True)
def reset_plugin_loader_state():
    """Clear all module-level plugin loader state before and after each test."""
    def _clear():
        pl._loaded.clear()
        pl._error_states.clear()
        pl._module_to_plugin.clear()
        pl._connection_to_plugin.clear()
        pl._EXTERNAL_PLUGIN_ROOT = None

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
