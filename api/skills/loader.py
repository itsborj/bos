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
    "reasoning",
    "strategy",
    "creative",
    "media",
]
IntentType = Literal[
    "discussion",
    "generation",
    "revision",
    "approval",
    "onboarding",
    "diagnostic",
    "action",
    "publish",
]


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
    inherits: List[str] = Field(default_factory=list)
    depends_on: List[str] = Field(default_factory=list)
    required_upstream: List[str] = Field(default_factory=list)
    outputs: List[str] = Field(default_factory=list)
    input_minimum: Optional[str] = None
    load_policy: Optional[str] = None
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
    if value == "[]":
        return []
    if value == "{}":
        return {}
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    return value.strip('"\'')


def _coerce_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return [str(value).strip()] if str(value).strip() else []


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
    for list_key in (
        "related_modules",
        "requires_intent",
        "triggers",
        "excluded_triggers",
        "memory_slots",
        "resources",
        "output_contract",
        "quality_gates",
        "inherits",
        "depends_on",
        "required_upstream",
        "outputs",
    ):
        data[list_key] = _coerce_string_list(data.get(list_key))
    rs = data.get("related_skills")
    if isinstance(rs, list):
        data["related_skills"] = {sid: "" for sid in rs if isinstance(sid, str)}
    metadata = data.get("metadata")
    if isinstance(metadata, dict) and metadata.get("version") and not data.get("version"):
        data["version"] = str(metadata["version"])
    return data


def _parse_frontmatter(raw: str) -> tuple[dict[str, Any], str]:

    """Parse SKILL.md frontmatter.

    Prefer real YAML when available so folded descriptions, inline lists, and
    nested metadata stay valid. Fall back to the legacy permissive parser for
    older skill files that contain unquoted values YAML rejects (for example
    list items beginning with @).
    """
    text = raw.lstrip()
    if not text.startswith("---\n"):
        raise ValueError("SKILL.md must start with YAML frontmatter")

    end = text.find("\n---", 4)
    if end == -1:
        raise ValueError("SKILL.md frontmatter is not closed")

    header = text[4:end]
    body = text[end + 4 :].lstrip("\n")

    try:
        import yaml  # type: ignore
        parsed = yaml.safe_load(header) or {}
        if isinstance(parsed, dict):
            return parsed, body
    except Exception:
        pass

    data: dict[str, Any] = {}
    current_key: Optional[str] = None
    lines = header.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        if line.startswith((" ", "\t")):
            # Nested content is consumed by the top-level key handlers below.
            i += 1
            continue
        if ":" not in line:
            raise ValueError(f"Invalid frontmatter line: {line}")

        key, value = line.split(":", 1)
        current_key = key.strip()
        raw_value = value.strip()

        if raw_value in {">", "|"}:
            block_lines: list[str] = []
            i += 1
            while i < len(lines) and (not lines[i].strip() or lines[i].startswith((" ", "\t"))):
                block_lines.append(lines[i].strip())
                i += 1
            if raw_value == ">":
                data[current_key] = " ".join(part for part in block_lines if part)
            else:
                data[current_key] = "\n".join(block_lines).strip()
            continue

        if raw_value:
            data[current_key] = _parse_scalar(raw_value)
            i += 1
            continue

        # Empty top-level key: consume a top-level list or one-level mapping.
        nested: list[str] = []
        i += 1
        while i < len(lines) and (not lines[i].strip() or lines[i].startswith((" ", "\t"))):
            if lines[i].strip():
                nested.append(lines[i])
            i += 1

        if not nested:
            continue

        first = nested[0].strip()
        if first.startswith("-"):
            data[current_key] = [_parse_scalar(n.strip()[1:].strip()) for n in nested if n.strip().startswith("-")]
            continue

        mapping: dict[str, Any] = {}
        j = 0
        while j < len(nested):
            entry = nested[j]
            entry_stripped = entry.strip()
            if not entry_stripped or entry_stripped.startswith("#"):
                j += 1
                continue
            if ":" not in entry_stripped:
                j += 1
                continue
            subkey, subvalue = entry_stripped.split(":", 1)
            subkey = subkey.strip()
            subvalue = subvalue.strip()
            if subvalue:
                mapping[subkey] = _parse_scalar(subvalue)
                j += 1
                continue
            child_items: list[Any] = []
            j += 1
            while j < len(nested) and nested[j].startswith(("    ", "\t\t")):
                child = nested[j].strip()
                if child.startswith("-"):
                    child_items.append(_parse_scalar(child[1:].strip()))
                j += 1
            mapping[subkey] = child_items if child_items else None
        data[current_key] = mapping

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
    inherits_lines = "\n".join(f"- {item}" for item in skill.inherits) or "- none"
    depends_lines = "\n".join(f"- {item}" for item in skill.depends_on) or "- none"
    upstream_lines = "\n".join(f"- {item}" for item in skill.required_upstream) or "- none"
    outputs_lines = "\n".join(f"- {item}" for item in skill.outputs) or "- none"
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
<skill_dependencies>
<inherits>
{inherits_lines}
</inherits>
<depends_on>
{depends_lines}
</depends_on>
<required_upstream>
{upstream_lines}
</required_upstream>
<outputs>
{outputs_lines}
</outputs>
</skill_dependencies>
</activated_skill>"""


def clear_skill_cache() -> None:
    _skill_file_map.clear()
    list_skill_manifests.cache_clear()
    get_skill.cache_clear()
