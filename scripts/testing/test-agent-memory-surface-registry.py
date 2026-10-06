#!/usr/bin/env python3
"""Compatibility wrapper and validator for the agent memory surface registry."""

from __future__ import annotations

import fnmatch
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
CANONICAL_HOT_MEMORY_PATH = "ai-stack/agent-memory/MEMORY.md"

ACTIVE_MEMORY_REFERENCE_PATHS = [
    "AGENTS.md",
    "README.md",
    ".agent/SKILL_INDEX.md",
    ".agent/WORKFLOW-CANON.md",
    ".agent/GEMINI.md",
    ".agent/skills/context-efficiency/SKILL.md",
    ".agent/skills/provider-request-error-recovery/SKILL.md",
    ".agent/skills/strict-json-output-contract/SKILL.md",
    ".agent/skills/system-dev/SKILL.md",
]

REQUIRED_CATEGORIES = [
    "local_live_state",
    "portable_coordination_templates",
    "durable_collective_memory",
    "curated_prd_plan_prompt",
    "rag_database_facts",
    "raw_learning_feedback",
    "reference_only_archives",
]

REQUIRED_MEMORY_DOC_PHRASES = [
    "Local live state",
    "Durable collective memory",
    "RAG And Database Facts",
    "Reference-Only Surfaces",
    "Promotion Rule",
    "Agents must not write directly to AIDB or Qdrant",
    ".agents/planning/**",
    ".agents/summary/**",
    "Raw telemetry is not a fact",
]

REQUIRED_TRACKED_MEMORY_PATHS = [
    "config/agent-memory-surface-registry.json",
    "docs/operations/agent-memory-state-standard.md",
    CANONICAL_HOT_MEMORY_PATH,
    ".agent/memory/issues-backlog.md",
    ".agent/collaboration/README.md",
    ".agent/collaboration/HANDOFF.template.md",
    ".agent/collaboration/PENDING.template.json",
    ".agent/collaboration/RESUME.template.json",
    "docs/operations/agent-artifact-distribution-policy.md",
]


def tracked_files(root: Path, failures: list[str]) -> set[str]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "ls-files"],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            return set(proc.stdout.splitlines())
        failures.append(f"git ls-files failed: {proc.stderr.strip()}")
        return set()
    except Exception as err:
        failures.append(f"failed to run git ls-files: {err}")
        return set()


def read_required(root: Path, relative: str, failures: list[str]) -> str:
    path = root / relative
    try:
        return path.read_text(encoding="utf-8")
    except Exception as err:
        failures.append(f"missing or unreadable {relative}: {err}")
        return ""


def validate_memory_surface_py(root: Path) -> list[str]:
    failures: list[str] = []
    registry_text = read_required(root, "config/agent-memory-surface-registry.json", failures)
    standard_doc = read_required(root, "docs/operations/agent-memory-state-standard.md", failures)
    gitignore = read_required(root, ".gitignore", failures)
    tracked = tracked_files(root, failures)

    try:
        registry = json.loads(registry_text) if registry_text else {}
    except Exception as exc:
        failures.append(f"config/agent-memory-surface-registry.json invalid JSON: {exc}")
        registry = {}

    for category in REQUIRED_CATEGORIES:
        if f'"{category}"' not in registry_text:
            failures.append(f"registry missing category: {category}")

    for path in REQUIRED_TRACKED_MEMORY_PATHS:
        if path not in tracked and not (root / path).exists():
            failures.append(f"required tracked/added file missing: {path}")

    for phrase in REQUIRED_MEMORY_DOC_PHRASES:
        if phrase not in standard_doc:
            failures.append(f"standard doc missing phrase: {phrase}")

    for pattern in [
        ".agents/scratchpad/",
        ".agents/telemetry/*.jsonl",
        ".agent/collaboration/RESUME.json",
    ]:
        if pattern not in gitignore:
            failures.append(f".gitignore missing memory/state local pattern: {pattern}")

    if '"path": "ai-stack/agent-memory/MEMORY.md"' not in registry_text:
        failures.append("hot_memory_limits must point to canonical hot memory path")

    hot_file = root / CANONICAL_HOT_MEMORY_PATH
    try:
        hot_text = hot_file.read_text(encoding="utf-8")
        if len(hot_text.splitlines()) > 200:
            failures.append(f"{CANONICAL_HOT_MEMORY_PATH} exceeds 200 lines")
    except Exception as err:
        failures.append(f"hot memory file missing or unreadable: {CANONICAL_HOT_MEMORY_PATH}: {err}")

    forbidden_patterns: list[str] = []
    if isinstance(registry, dict):
        for val in registry.get("categories", {}).values():
            if isinstance(val, dict) and "forbidden_tracked_patterns" in val:
                pats = val.get("forbidden_tracked_patterns")
                if isinstance(pats, list):
                    forbidden_patterns.extend(pats)

    if not forbidden_patterns:
        failures.append("registry must define forbidden_tracked_patterns")
    for pattern in forbidden_patterns:
        for path in tracked:
            if fnmatch.fnmatch(path, pattern):
                failures.append(f"forbidden local/raw state path is tracked: {path} (pattern {pattern})")

    for path in ACTIVE_MEMORY_REFERENCE_PATHS:
        text = read_required(root, path, failures)
        if "MEMORY.md" in text and CANONICAL_HOT_MEMORY_PATH not in text:
            failures.append(f"{path} references MEMORY.md without canonical path {CANONICAL_HOT_MEMORY_PATH}")
        if "`memory/MEMORY.md`" in text or ".agent/memory/MEMORY.md" in text:
            failures.append(f"{path} references a stale hot-memory path")

    return failures


def main() -> int:
    # 1. If precompiled binary exists, use it
    for candidate in [
        ROOT / "target" / "release" / "harness-contracts",
        ROOT / "target" / "debug" / "harness-contracts",
    ]:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            proc = subprocess.run(
                [
                    str(candidate),
                    "memory-surface",
                    "--root",
                    str(ROOT),
                ],
                cwd=ROOT,
                check=False,
            )
            return proc.returncode

    # 2. If FORCE_CARGO_VALIDATOR is explicitly set to 1, use cargo
    if os.environ.get("FORCE_CARGO_VALIDATOR") == "1":
        proc = subprocess.run(
            [
                "cargo",
                "run",
                "--quiet",
                "-p",
                "harness-contracts",
                "--",
                "memory-surface",
                "--root",
                str(ROOT),
            ],
            cwd=ROOT,
            check=False,
        )
        return proc.returncode

    # 3. Otherwise, run the fast native Python validator directly (0.04s, prevents CI timeouts)
    failures = validate_memory_surface_py(ROOT)
    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print("PASS: agent memory surface registry is enforced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
