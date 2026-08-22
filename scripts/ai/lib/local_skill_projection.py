"""Bounded, fail-closed projection of selected local-agent skills.

This module is the only subprocess seam: it invokes the existing read-only
``aq-skill-auto --agent local --json --test`` selector.  It never executes a
selected skill, activates a capability, or exposes the skills catalogue.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence


_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_MAX_SKILLS = 2
_MAX_SKILL_CHARS = 900
_MAX_PROMPT_CHARS = 2_000
_SELECTOR_TIMEOUT_S = 8


@dataclass(frozen=True)
class SkillProjection:
    """Typed result suitable for an untrusted-prompt boundary."""

    status: str
    skill_names: tuple[str, ...]
    prompt: str
    reason: str | None = None


def _degraded(reason: str) -> SkillProjection:
    return SkillProjection(
        status="degraded",
        skill_names=(),
        prompt=(
            "\n\n[LOCAL SKILL PROJECTION: unavailable — do not claim selected skill "
            "guidance was applied. Continue under the existing behavioral contract only.]"
        ),
        reason=reason,
    )


def select_local_skills(
    task: str,
    *,
    repo_root: Path | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> SkillProjection:
    """Select at most two verified skills and project only bounded instructions.

    Selector or source failures deliberately return a visible typed-degraded result;
    callers must not silently substitute a catalogue dump or inferred skill content.
    """
    root = (repo_root or Path(__file__).resolve().parents[3]).resolve()
    selector = root / "scripts" / "ai" / "aq-skill-auto"
    if not isinstance(task, str) or not task.strip() or not selector.is_file():
        return _degraded("invalid-task-or-selector-unavailable")
    try:
        result = runner(
            [str(selector), task[:4_000], "--agent", "local", "--json"],
            cwd=str(root), text=True, capture_output=True, timeout=_SELECTOR_TIMEOUT_S,
            check=False,
        )
        if result.returncode != 0:
            return _degraded("selector-nonzero")
        payload = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError, TypeError, ValueError):
        return _degraded("selector-unreadable")
    if not isinstance(payload, dict) or payload.get("status") != "ok":
        return _degraded("selector-invalid-payload")
    names = payload.get("reference_skills")
    if not isinstance(names, list) or len(names) > _MAX_SKILLS:
        return _degraded("selector-invalid-skill-count")
    selected: list[tuple[str, str]] = []
    skills_root = (root / ".agent" / "skills").resolve()
    for name in names:
        if not isinstance(name, str) or not _NAME_RE.fullmatch(name):
            return _degraded("selector-invalid-skill-name")
        skill_file = (skills_root / name / "SKILL.md").resolve()
        if skills_root not in skill_file.parents or not skill_file.is_file():
            return _degraded("selected-skill-unreadable")
        try:
            content = skill_file.read_text(encoding="utf-8")[:_MAX_SKILL_CHARS].strip()
        except (OSError, UnicodeError):
            return _degraded("selected-skill-unreadable")
        if not content:
            return _degraded("selected-skill-empty")
        selected.append((name, content))
    if not selected:
        return SkillProjection(status="selected", skill_names=(), prompt="", reason=None)
    blocks = ["\n\n[SELECTED LOCAL SKILLS — bounded relevant instructions]"]
    for name, content in selected:
        blocks.append(f"\n<{name}>\n{content}\n</{name}>")
    prompt = "".join(blocks)
    if len(prompt) > _MAX_PROMPT_CHARS:
        return _degraded("projection-budget-exceeded")
    return SkillProjection(status="selected", skill_names=tuple(name for name, _ in selected), prompt=prompt)
