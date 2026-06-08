from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from typing import Dict, Type

from module_base import ModuleBase

_registry: Dict[str, Type[ModuleBase]] = {}
_scanned = False


def _scan() -> None:
    global _scanned

    # First-party capabilities
    cap_dir = Path(os.path.dirname(os.path.abspath(__file__))) / "capabilities"
    for path in sorted(cap_dir.rglob("module.py")):
        if "__pycache__" in path.parts:
            continue
        _load_file(str(path), cap_dir, prefix="bos_mod")

    # Third-party plugins — scan manifests, register template roots, load modules
    from plugin_loader import quarantine_plugin, register_plugin_module, scan_plugins
    from module_base import register_template_root
    from skills.loader import collect_skill_parse_errors, register_skill_root
    for state in scan_plugins():
        cap_root = state.capabilities_path
        loaded_ids: list[str] = []
        failed_path: str | None = None
        for path in sorted(cap_root.rglob("module.py")):
            if "__pycache__" in path.parts:
                continue
            ok, ids = _load_file(str(path), cap_root, prefix="bos_ext")
            loaded_ids.extend(ids)
            if not ok:
                failed_path = str(path)
                break
        if failed_path:
            for module_id in loaded_ids:
                _registry.pop(module_id, None)
            quarantine_plugin(state.manifest.plugin_id, f"import_failed: {failed_path}")
            continue
        conflict = next((reason for module_id in loaded_ids if (reason := register_plugin_module(state.manifest.plugin_id, module_id))), None)
        if conflict:
            for module_id in loaded_ids:
                _registry.pop(module_id, None)
            quarantine_plugin(state.manifest.plugin_id, conflict)
            continue
        skill_errors = collect_skill_parse_errors(str(cap_root))
        if skill_errors:
            for module_id in loaded_ids:
                _registry.pop(module_id, None)
            quarantine_plugin(state.manifest.plugin_id, "skill_parse_failed: " + "; ".join(skill_errors[:3]))
            continue
        register_template_root(str(cap_root))
        register_skill_root(str(cap_root))

    _scanned = True


def _load_file(path: str, root_dir: Path | None = None, prefix: str = "bos_mod") -> tuple[bool, list[str]]:
    if root_dir is None:
        root_dir = Path(os.path.dirname(os.path.abspath(__file__))) / "capabilities"
    rel = Path(path).relative_to(root_dir)
    module_name = prefix + "_" + "_".join(rel.with_suffix("").parts)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        return False, []
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:
        import logging
        logging.getLogger("bos.registry").warning("Failed to load module %s: %s", path, exc)
        return False, []
    registered_ids: list[str] = []
    for name in dir(mod):
        obj = getattr(mod, name)
        if not isinstance(obj, type):
            continue
        if not issubclass(obj, ModuleBase):
            continue
        if obj is ModuleBase:
            continue
        # Support both 'id' (old interface) and 'module_id' (new SDK interface).
        # If both are set, 'id' takes precedence.
        canon_id = getattr(obj, "id", None) or getattr(obj, "module_id", None)
        if not canon_id:
            continue
        # Normalize: ensure obj.id is set so downstream code that reads cls.id works.
        if not getattr(obj, "id", None):
            obj.id = canon_id  # type: ignore[attr-defined]
        if prefix == "bos_ext" and canon_id in _registry:
            return False, registered_ids
        _registry[canon_id] = obj
        registered_ids.append(canon_id)
        for legacy_id in getattr(obj, "legacy_ids", []):
            _registry.setdefault(legacy_id, obj)
            registered_ids.append(legacy_id)
    return True, registered_ids


def _ensure() -> None:
    if not _scanned:
        _scan()


def get_module(module_id: str) -> Type[ModuleBase] | None:
    _ensure()
    return _registry.get(module_id)


def list_by_vertical(vertical: str) -> list[dict]:
    _ensure()
    seen_ids: set[str] = set()
    modules: list[dict] = []
    for cls in _registry.values():
        if cls.vertical != vertical or cls.id in seen_ids:
            continue
        seen_ids.add(cls.id)
        modules.append(cls().module_info())
    return modules


def list_verticals() -> list[dict]:
    _ensure()
    counts: Dict[str, int] = {}
    for cls in _registry.values():
        counts[cls.vertical] = counts.get(cls.vertical, 0) + 1
    return [{"vertical": v, "module_count": c} for v, c in sorted(counts.items())]


def list_all() -> list[dict]:
    _ensure()
    seen_ids: set[str] = set()
    modules: list[dict] = []
    for cls in _registry.values():
        if cls.id in seen_ids:
            continue
        seen_ids.add(cls.id)
        modules.append(cls().module_info())
    return modules
