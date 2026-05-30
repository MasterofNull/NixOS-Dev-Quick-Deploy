"""
drop_spec.py — Phase 85 Drop Zone schema validation.
Parses and validates *.drop.yaml files before dispatch.
"""
from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import yaml

# Injection patterns rejected in prompt/objective fields (OWASP agentic injection guard)
_INJECTION_PATTERNS = re.compile(r"\$\(|`|&&|\|\|(?!\s)|;\s*\w")

_VALID_ROLES = {"implementer", "architect", "reviewer", "orchestrator"}
_VALID_MODES = {"auto", "agent", "hybrid", "direct"}
_MAX_TTL_S = 86400  # 24h cap — no zombie locks
_MAX_PROMPT_LEN = 8192

# mode: agent dispatches to aq-agent-loop which has run_shell_command capability.
# Blocked by default — requires DROP_ALLOW_AGENT=true env var to enable.
# This prevents semantic prompt injection from triggering code execution.
_AGENT_MODE_BLOCKED = os.environ.get("DROP_ALLOW_AGENT", "").lower() not in ("1", "true", "yes")

# Semantic content policy — phrases that, if present in a prompt, indicate
# destructive intent regardless of shell metacharacter absence.
_DESTRUCTIVE_PATTERNS = re.compile(
    r"(?:"
    r"\brm\s+-[rf]+"           # rm -rf / rm -fr / rm -r / rm -f
    r"|\bgit\s+reset\s+--hard"
    r"|\bgit\s+push\s+--force"
    r"|\bdrop\s+table\b"
    r"|\btruncate\s+table\b"
    r"|\bdelete\s+from\b"
    r"|\bmkfs\."
    r"|\bdd\s+if="
    r"|\bchmod\s+-R\s+777\b"
    r"|\bsudo\s+rm\b"
    r"|\bshred\s+-[uz]"
    r")",
    re.IGNORECASE,
)


class DropSpecError(ValueError):
    """Raised when a drop file fails schema validation."""


@dataclass
class DropSpec:
    objective: str
    prompt: str
    role: str = "implementer"
    mode: str = "auto"
    priority: int = 5
    ttl_s: int = 3600
    tags: List[str] = field(default_factory=list)
    # Set by loader, not from YAML
    source_file: Optional[Path] = field(default=None, repr=False)
    drop_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @classmethod
    def from_file(cls, path: Path) -> "DropSpec":
        try:
            raw = yaml.safe_load(path.read_text())
        except yaml.YAMLError as exc:
            raise DropSpecError(f"YAML parse error in {path.name}: {exc}") from exc

        if not isinstance(raw, dict):
            raise DropSpecError(f"{path.name}: top-level must be a YAML mapping")

        spec = cls(
            objective=_require_str(raw, "objective", path),
            prompt=_require_str(raw, "prompt", path),
            role=str(raw.get("role", "implementer")).strip().lower(),
            mode=str(raw.get("mode", "auto")).strip().lower(),
            priority=int(raw.get("priority", 5)),
            ttl_s=int(raw.get("ttl_s", 3600)),
            tags=list(raw.get("tags", [])),
            source_file=path,
        )
        spec._validate()
        return spec

    def _validate(self) -> None:
        for field_name, value in [("objective", self.objective), ("prompt", self.prompt)]:
            if _INJECTION_PATTERNS.search(value):
                raise DropSpecError(
                    f"Injection pattern detected in '{field_name}' field — drop rejected"
                )
            if _DESTRUCTIVE_PATTERNS.search(value):
                raise DropSpecError(
                    f"Destructive command pattern detected in '{field_name}' field — drop rejected"
                )
            if len(value) > _MAX_PROMPT_LEN:
                raise DropSpecError(
                    f"'{field_name}' exceeds {_MAX_PROMPT_LEN} chars ({len(value)})"
                )
        if not self.objective.strip():
            raise DropSpecError("'objective' must not be empty")
        if not self.prompt.strip():
            raise DropSpecError("'prompt' must not be empty")
        if self.role not in _VALID_ROLES:
            raise DropSpecError(f"'role' must be one of {sorted(_VALID_ROLES)}, got {self.role!r}")
        if self.mode not in _VALID_MODES:
            raise DropSpecError(f"'mode' must be one of {sorted(_VALID_MODES)}, got {self.mode!r}")
        # Block agent mode unless explicitly opted in (run_shell_command capability)
        if self.mode == "agent" and _AGENT_MODE_BLOCKED:
            raise DropSpecError(
                "mode: agent is disabled by default (shell execution capability). "
                "Set DROP_ALLOW_AGENT=true to enable."
            )
        if not (1 <= self.priority <= 10):
            raise DropSpecError(f"'priority' must be 1–10, got {self.priority}")
        if not (60 <= self.ttl_s <= _MAX_TTL_S):
            raise DropSpecError(f"'ttl_s' must be 60–{_MAX_TTL_S}, got {self.ttl_s}")


def _require_str(raw: dict, key: str, path: Path) -> str:
    val = raw.get(key)
    if not isinstance(val, str):
        raise DropSpecError(f"{path.name}: required string field '{key}' missing or not a string")
    return val.strip()
