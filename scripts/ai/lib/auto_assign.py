#!/usr/bin/env python3
"""auto_assign — infer role, band, task_class, and skill hints from the task itself.

Agents and callers should not need to be told which role, priority band,
tier task-class, or skills a task needs. This module derives all four from
the prompt (plus caller source), so `--role auto` / unset flags produce a
fully-assigned dispatch. Explicit values always win over inference.

Also fixes a latent gap: delegate-to-local's historical default role
"implement" is not a ROLE_SYSTEM_PROMPTS key, so the default path silently
received NO role injection. normalize_role() maps aliases to canonical
role-matrix names (docs/architecture/role-matrix.md).

Sub-agent non-orchestrator rule: inference NEVER assigns "orchestrator" —
delegated agents execute slices; orchestration is claimed explicitly.

Kill switch: AUTO_ASSIGN=0 disables inference (explicit/legacy values pass
through untouched).
"""

from __future__ import annotations

import os
import re
import subprocess

# Canonical roles (role-matrix SSOT projection) + accepted aliases.
_ROLE_ALIASES = {
    "implement": "implementer",
    "implementor": "implementer",
    "code": "implementer",
    "review": "reviewer",
    "critic": "reviewer",
    "architecture": "architect",
    "design": "architect",
    "plan": "architect",
    "orchestrate": "orchestrator",
}
_CANONICAL_ROLES = {"orchestrator", "architect", "implementer", "reviewer"}

# Ordered role heuristics — first match wins. Reviewer before architect so
# "review this design" lands reviewer; implementer is the fallback.
_ROLE_PATTERNS: list[tuple[str, str]] = [
    (r"\b(review|critique|verdict|pass/fail|assess|score|ratif|approve|reject|audit)\b", "reviewer"),
    (r"\b(architect|design doc|prd|trade-?off|architecture|roadmap|risk analysis|threat model)\b", "architect"),
    (r"\b(implement|fix|write|edit|refactor|add|create|build|patch|wire|migrate)\b", "implementer"),
]

# Band inference: caller source dominates; prompt only breaks ties.
_SOURCE_BANDS = {
    "aq-chat": "interactive",
    "interactive": "interactive",
    "cli": "interactive",
    "aq-loop": "background",
    "aq-loop-queue": "background",
    "eval": "background",
    "training": "background",
    "batch": "background",
    "queue": "background",
    "collab-round": "consensus",
    "round": "consensus",
    "review": "consensus",
}

# model_tier.TaskClass keyword map — first match wins; None lets the tier
# router fall to its own MID_RESIDENT default.
_TASK_CLASS_PATTERNS: list[tuple[str, str]] = [
    (r"\b(classify|categorize|label|tag)\b", "classification"),
    (r"\brepair(ing)? json|fix (the )?json|malformed json\b", "json_repair"),
    (r"\b(tool|json) schema (validat|check)", "tool_schema_validation"),
    (r"\b(consensus|vote|ratif|quorum)\b", "consensus_vote"),
    (r"\b(dissent|second opinion|red.?team)\b", "dissent_review"),
    (r"\b(critique|short review)\b", "short_critique"),
    (r"\b(grep|find (files?|paths?)|locate|search (the )?(code|repo))\b", "path_grep_summary"),
    (r"\b(diff|changed lines|delta)\b", "diff_analysis"),
    (r"\btriage|test failure|failing test|stack ?trace\b", "test_error_triage"),
    (r"\b(architecture|system design|multi.?hop design)\b", "architecture"),
    (r"\brefactor(ing)? (across|multiple|many)|multi.?file\b", "multi_file_refactor"),
    (r"\bplan\b", "single_file_plan"),
    (r"\b(edit|fix|patch) (one|a|the|single) file|single.?edit\b", "bounded_edit"),
]


def enabled() -> bool:
    return os.environ.get("AUTO_ASSIGN", "1") != "0"


def normalize_role(role: str | None) -> str | None:
    """Map role aliases to canonical role-matrix names; None/auto stay None."""
    if not role or role.lower() in ("auto", "none"):
        return None
    r = role.strip().lower()
    r = _ROLE_ALIASES.get(r, r)
    return r if r in _CANONICAL_ROLES else None


def resolve_role(explicit: str | None, prompt: str) -> str:
    """Explicit canonical role wins; otherwise infer from the prompt.

    Never returns orchestrator from inference (sub-agent rule).
    """
    normalized = normalize_role(explicit)
    if normalized:
        return normalized
    if not enabled():
        return "implementer"
    low = prompt.lower()
    for pattern, role in _ROLE_PATTERNS:
        if re.search(pattern, low):
            return role
    return "implementer"


def infer_band(source: str | None, prompt: str) -> str:
    """Return DISPATCH_BAND name (interactive|consensus|background).

    Explicit DISPATCH_BAND env always wins (checked by slot_queue itself);
    this covers callers that set neither.
    """
    if source:
        band = _SOURCE_BANDS.get(source.strip().lower())
        if band:
            return band
    low = prompt.lower()
    if re.search(r"\b(consensus|vote|ratif|review (the|this) (prd|plan|proposal))\b", low):
        return "consensus"
    if re.search(r"\b(nightly|batch|backlog|background|when idle)\b", low):
        return "background"
    return "consensus"


def infer_task_class(prompt: str) -> str | None:
    if not enabled():
        return None
    low = prompt.lower()
    for pattern, task_class in _TASK_CLASS_PATTERNS:
        if re.search(pattern, low):
            return task_class
    return None


def skill_hints(prompt: str, repo_root, max_n: int = 2, timeout_s: int = 8) -> list[str]:
    """Top skill names from aq-skill-suggest; fail-open to [] on any error.

    Injected into delegated prompts so sub-agents load the right skills
    without being told (skill-loading rule: pass names, not content).
    """
    if not enabled():
        return []
    try:
        out = subprocess.run(
            [str(repo_root / "scripts" / "ai" / "aq-skill-suggest"), prompt[:400]],
            capture_output=True, text=True, timeout=timeout_s, cwd=str(repo_root),
        ).stdout
        # aq-skill-suggest prints each ranked skill as a bare indented name line,
        # followed by indented "Tags:"/"Use:" detail lines.
        names = re.findall(r"^\s{2}([a-z0-9][a-z0-9_-]{2,40})\s*$", out, re.MULTILINE)
        seen: list[str] = []
        for n in names:
            if n not in seen and n not in ("usage", "error", "note"):
                seen.append(n)
        return seen[:max_n]
    except Exception:
        return []


def skill_hint_block(prompt: str, repo_root) -> str:
    """Formatted hint block for prompt injection ('' when no hints)."""
    hints = skill_hints(prompt, repo_root)
    if not hints:
        return ""
    return (
        "[Auto-suggested skills: " + ", ".join(hints)
        + " — load with: aq-skill-suggest --show <name>]"
    )
