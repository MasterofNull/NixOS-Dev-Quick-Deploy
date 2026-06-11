#!/usr/bin/env python3
"""Phase 154: verify cross-model workflow parity across agent instruction files."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Agent instruction files to check
AGENT_FILES = {
    ".agent/GEMINI.md": "GEMINI",
    ".agent/CODEX.md": "CODEX",
    ".agent/LOCAL-AGENT.md": "LOCAL-AGENT",
}

ROLE_MATRIX = "docs/architecture/role-matrix.md"

# Canonical roles required in role-matrix.md
CANONICAL_ROLES = ["orchestrator", "architect", "implementer", "reviewer"]

# Workflow canon reference patterns
WORKFLOW_CANON_PATTERNS = [
    "WORKFLOW-CANON",
    "ORIENT",
    "RESEARCH",
    "EXECUTE",
    "VALIDATE",
    "COMMIT",
]

# Sub-agent constraint patterns
SUB_AGENT_PATTERNS = [
    "sub-agents execute only assigned slices",
    "execute only assigned",
    "execute only the assigned slice",
    "You are NOT the orchestrator",
    "may not self-promote",
    "do not re-scope",
    "Do not re-scope",
]

# PRD gate patterns
PRD_GATE_PATTERNS = [
    "PRD GATE",
    "No coding without a written plan",
    "Never start coding",
    "never start coding",
    "no coding without",
]


def check_file_for_patterns(content: str, patterns: list[str]) -> bool:
    """Return True if any pattern is found in content."""
    return any(p in content for p in patterns)


def main() -> int:
    failures: list[str] = []
    total_checks = 0

    # -----------------------------------------------------------------------
    # Check 1: WORKFLOW-CANON reference in each agent file
    # -----------------------------------------------------------------------
    for rel_path, label in AGENT_FILES.items():
        total_checks += 1
        fpath = REPO_ROOT / rel_path
        if not fpath.exists():
            failures.append(f"FAIL: {rel_path} does not exist")
            continue
        content = fpath.read_text()
        if not check_file_for_patterns(content, WORKFLOW_CANON_PATTERNS):
            failures.append(f"FAIL: {rel_path} missing: workflow_canon_reference")

    # -----------------------------------------------------------------------
    # Check 2: All 4 canonical roles present in role-matrix.md
    # -----------------------------------------------------------------------
    total_checks += 1
    role_matrix_path = REPO_ROOT / ROLE_MATRIX
    if not role_matrix_path.exists():
        failures.append(f"FAIL: {ROLE_MATRIX} does not exist")
    else:
        role_content = role_matrix_path.read_text()
        missing_roles = [r for r in CANONICAL_ROLES if f"### {r}" not in role_content]
        if missing_roles:
            failures.append(
                f"FAIL: {ROLE_MATRIX} missing canonical roles: {', '.join(missing_roles)}"
            )

    # -----------------------------------------------------------------------
    # Check 3: Sub-agent constraint in each agent file
    # -----------------------------------------------------------------------
    for rel_path, label in AGENT_FILES.items():
        total_checks += 1
        fpath = REPO_ROOT / rel_path
        if not fpath.exists():
            # Already reported above
            continue
        content = fpath.read_text()
        if not check_file_for_patterns(content, SUB_AGENT_PATTERNS):
            failures.append(f"FAIL: {rel_path} missing: sub_agent_constraint")

    # -----------------------------------------------------------------------
    # Check 4: enable_thinking: false in LOCAL-AGENT.md (critical contract)
    # -----------------------------------------------------------------------
    total_checks += 1
    local_agent_path = REPO_ROOT / ".agent/LOCAL-AGENT.md"
    if not local_agent_path.exists():
        failures.append("FAIL: .agent/LOCAL-AGENT.md does not exist")
    else:
        la_content = local_agent_path.read_text()
        if "enable_thinking: false" not in la_content and "enable_thinking: False" not in la_content:
            failures.append(
                "FAIL: .agent/LOCAL-AGENT.md missing: enable_thinking: false (critical contract)"
            )

    # -----------------------------------------------------------------------
    # Check 5: PRD gate in each agent file
    # -----------------------------------------------------------------------
    for rel_path, label in AGENT_FILES.items():
        total_checks += 1
        fpath = REPO_ROOT / rel_path
        if not fpath.exists():
            continue
        content = fpath.read_text()
        if not check_file_for_patterns(content, PRD_GATE_PATTERNS):
            failures.append(f"FAIL: {rel_path} missing: prd_gate")

    # -----------------------------------------------------------------------
    # Report
    # -----------------------------------------------------------------------
    n_files = len(AGENT_FILES)
    if failures:
        for line in failures:
            print(line)
        return 1

    print(
        f"Test agentic workflow parity: PASSED ({total_checks} checks across {n_files} agent files + role matrix)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
