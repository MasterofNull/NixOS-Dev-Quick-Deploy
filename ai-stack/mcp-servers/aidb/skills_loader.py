from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import yaml


def _normalize_tags(raw_tags) -> List[str]:
    if raw_tags is None:
        return []
    if isinstance(raw_tags, str):
        return [part.strip() for part in raw_tags.split(",") if part.strip()]
    if isinstance(raw_tags, (list, tuple, set)):
        return [str(item).strip() for item in raw_tags if str(item).strip()]
    return []


@dataclass
class ParsedSkill:
    slug: str
    name: str
    description: str
    version: Optional[str]
    tags: List[str]
    content: str
    metadata: Dict[str, object]
    source_path: str
    source_url: Optional[str] = None
    managed_by: str = "local"


def parse_skill_text(slug: str, text: str, source_path: str, *, source_url: Optional[str] = None, managed_by: str = "local") -> ParsedSkill:
    front_matter: Dict[str, object] = {}
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            try:
                front_matter = yaml.safe_load(parts[1]) or {}
            except yaml.YAMLError:
                front_matter = {}
            body = parts[2].lstrip("\n")

    tags = _normalize_tags(front_matter.get("tags"))
    return ParsedSkill(
        slug=slug,
        name=str(front_matter.get("name") or slug),
        description=str(front_matter.get("description") or ""),
        version=front_matter.get("version"),
        tags=tags,
        content=body.strip(),
        metadata=front_matter,
        source_path=source_path,
        source_url=source_url,
        managed_by=managed_by,
    )


def parse_skill_file(path: Path, repo_root: Path) -> ParsedSkill:
    text = path.read_text(encoding="utf-8")
    try:
        rel_path = str(path.relative_to(repo_root))
    except ValueError:
        rel_path = str(path)
    slug = path.parent.name
    return parse_skill_text(slug, text, rel_path)


def write_skill_file(skill: ParsedSkill, repo_root: Path) -> Path:
    target_dir = repo_root / ".agent" / "skills" / skill.slug
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / "SKILL.md"

    front_matter = skill.metadata.copy()
    front_matter.setdefault("name", skill.name)
    front_matter.setdefault("description", skill.description)
    front_matter.setdefault("version", skill.version or "1.0.0")
    front_matter.setdefault("tags", skill.tags)

    yaml_front = yaml.safe_dump(front_matter, sort_keys=False).strip()
    content = f"---\n{yaml_front}\n---\n\n{skill.content.strip()}\n"
    target_path.write_text(content, encoding="utf-8")
    return target_path
