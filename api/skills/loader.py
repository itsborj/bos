from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, List, Dict, Tuple, Optional

from typing import Optional
from pydantic import BaseModel, Field

SkillScope = Literal[
    "workspace",
    "module",
    "onboarding",
    "campaign",
    "product",
    "audience",
    "workflow",
    "atomic_task",
    "atomic_workflow",
    "diagnostic",
    "knowledge",
]
IntentType = Literal["discussion", "generation", "revision", "approval", "onboarding", "diagnostic"]


class SkillManifest(BaseModel):
    id: str
    name: str
    description: str
    scope: SkillScope
    status: str = "active"
    version: str = "0.1.0"
    allowed_from_chat: bool = False
    module_id: Optional[str] = None
    related_modules: List[str] = Field(default_factory=list)
    requires_intent: List[IntentType] = Field(default_factory=list)
    triggers: List[str] = Field(default_factory=list)
    excluded_triggers: List[str] = Field(default_factory=list)
    memory_slots: List[str] = Field(default_factory=list)
    resources: List[str] = Field(default_factory=list)
    available_resources: List[str] = Field(default_factory=list)
    related_skills: Dict[str, str] = Field(default_factory=dict)
    required_context: List[str] = Field(default_factory=list)
    output_contract: List[str] = Field(default_factory=list)
    quality_gates: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    path: str


class Skill(SkillManifest):
    body: str


_SKILLS_ROOT = Path(__file__).resolve().parent.parent / "capabilities"
_extra_skill_roots: list[Path] = []
_skill_file_map: dict[str, Path] = {}


def register_skill_root(root: str) -> None:
    """Register a plugin capability root for skill discovery. Called by registry._scan()."""
    p = Path(root)
    if p not in _extra_skill_roots:
        _extra_skill_roots.append(p)
        _skill_file_map.clear()
        list_skill_manifests.cache_clear()
        get_skill.cache_clear()


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if value in {"null", "~", ""}:
        return None
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    return value.strip('"\'')


def _available_resources_for(skill_file: Path) -> List[str]:
    skill_dir = skill_file.parent
    resources: List[str] = []
    for child in sorted(skill_dir.rglob("*")):
        if not child.is_file() or child.name == "SKILL.md" or "__pycache__" in child.parts:
            continue
        resources.append(str(child.relative_to(skill_dir)))
    return resources


def _skill_id_from_path(path: Path, root: Path) -> str:
    rel_dir = path.parent.relative_to(root)
    return ".".join(rel_dir.parts)


def _normalize_frontmatter(data: dict[str, Any], path: Path, root: Path) -> dict[str, Any]:
    data = dict(data)
    data.setdefault("id", _skill_id_from_path(path, root))
    data.setdefault("scope", "atomic_workflow")
    data.setdefault("status", "active")
    data.setdefault("version", "0.1.0")
    data.setdefault("allowed_from_chat", False)
    data["path"] = str(path.relative_to(root))
    data["available_resources"] = _available_resources_for(path)
    if data.get("module_id") and not data.get("related_modules"):
        data["related_modules"] = [data["module_id"]]
    rs = data.get("related_skills")
    if isinstance(rs, list):
        data["related_skills"] = {sid: "" for sid in rs if isinstance(sid, str)}
    metadata = data.get("metadata")
    if isinstance(metadata, dict) and metadata.get("version") and not data.get("version"):
        data["version"] = str(metadata["version"])
    return data


def _parse_frontmatter(raw: str) -> tuple[dict[str, Any], str]:

    """Parse the small YAML subset used by BOS SKILL.md frontmatter.

    Supports top-level scalars, top-level string lists, and one-level maps.
    This avoids adding a YAML dependency while still accepting common Agent
    Skills metadata such as `metadata.version` and `related_skills`.
    """
    text = raw.lstrip()
    if not text.startswith("---\n"):
        raise ValueError("SKILL.md must start with YAML frontmatter")

    end = text.find("\n---", 4)
    if end == -1:
        raise ValueError("SKILL.md frontmatter is not closed")

    header = text[4:end]
    body = text[end + 4 :].lstrip("\n")
    data: dict[str, Any] = {}
    current_key: Optional[str] = None

    for line in header.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line.startswith((" ", "\t")) and current_key and ":" in stripped and not stripped.startswith("-"):
            if not isinstance(data.get(current_key), dict):
                data[current_key] = {}
            subkey, subvalue = stripped.split(":", 1)
            data[current_key][subkey.strip()] = _parse_scalar(subvalue.strip())
            continue
        if stripped.startswith("-"):
            if current_key is None:
                raise ValueError(f"List item without key: {line}")
            if current_key not in data:
                data[current_key] = []
            elif not isinstance(data.get(current_key), list):
                raise ValueError(f"Cannot add list item to non-list key: {current_key}")
            data[current_key].append(_parse_scalar(stripped[1:].strip()))
            continue
        if ":" not in line:
            raise ValueError(f"Invalid frontmatter line: {line}")
        key, value = line.split(":", 1)
        current_key = key.strip()
        if value.strip():
            data[current_key] = _parse_scalar(value)
        # Don't set empty list here; let the '-' handler create lists when needed

    return data, body


@lru_cache(maxsize=1)
def list_skill_manifests() -> tuple[SkillManifest, ...]:
    _skill_file_map.clear()
    manifests: list[SkillManifest] = []
    for root in [_SKILLS_ROOT] + list(_extra_skill_roots):
        for path in sorted(root.glob("**/SKILL.md")):
            try:
                data, _body = _parse_frontmatter(path.read_text())
            except Exception:
                continue
            data = _normalize_frontmatter(data, path, root)
            try:
                manifest = SkillManifest.model_validate(data)
            except Exception:
                continue
            if manifest.status != "active":
                continue
            _skill_file_map[manifest.id] = path
            manifests.append(manifest)
    return tuple(manifests)


@lru_cache(maxsize=128)
def get_skill(skill_id: str) -> Optional[Skill]:
    for manifest in list_skill_manifests():
        if manifest.id != skill_id:
            continue
        path = _skill_file_map.get(manifest.id)
        if path is None:
            return None
        try:
            data, body = _parse_frontmatter(path.read_text())
        except Exception:
            return None
        skill_root = _SKILLS_ROOT
        for r in _extra_skill_roots:
            try:
                path.relative_to(r)
                skill_root = r
                break
            except ValueError:
                pass
        data = _normalize_frontmatter(data, path, skill_root)
        data["body"] = body
        return Skill.model_validate(data)
    return None


def format_activated_skill(skill: Skill) -> str:
    """Return protected, structured skill context for prompt assembly/tracing."""
    resource_lines = "\n".join(f"- {resource}" for resource in skill.available_resources) or "- none"
    related_lines = "\n".join(f"- {sid}: {reason}" for sid, reason in skill.related_skills.items()) or "- none"
    return f"""<activated_skill id=\"{skill.id}\" name=\"{skill.name}\" version=\"{skill.version}\" path=\"{skill.path}\">
<instructions>
{skill.body.strip()}
</instructions>
<available_resources>
{resource_lines}
</available_resources>
<related_skills>
{related_lines}
</related_skills>
</activated_skill>"""


def clear_skill_cache() -> None:
    _skill_file_map.clear()
    list_skill_manifests.cache_clear()
    get_skill.cache_clear()
