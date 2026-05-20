"""
knowledge/models.py — Shared data model types for the hints knowledge layer.

Extracted from hints_engine.py (Phase R3 decomposition).
Zero dependencies on other knowledge modules.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class Hint:
    """A ranked, actionable workflow hint surfaced to any agent or human."""

    id: str
    type: str  # "prompt_template" | "gap_topic" | "workflow_rule" | "tool_warning" | "runtime_signal" | "prompt_coaching"
    title: str
    score: float  # composite 0.0-1.0
    snippet: str  # actionable text: template excerpt, rule, etc.
    reason: str  # why this hint was surfaced
    tags: List[str] = field(default_factory=list)
    agent_hints: Dict[str, str] = field(default_factory=dict)
    # Per-agent delivery format overrides; keys: human/claude/codex/qwen/aider/continue
