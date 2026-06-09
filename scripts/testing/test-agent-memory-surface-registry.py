#!/usr/bin/env python3
"""Validate the agent memory/state surface registry and promotion contract."""

from __future__ import annotations

import fnmatch
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "config" / "agent-memory-surface-registry.json"
STANDARD_DOC = ROOT / "docs" / "operations" / "agent-memory-state-standard.md"

REQUIRED_CATEGORIES = {
    "local_live_state",
    "portable_coordination_templates",
    "durable_collective_memory",
    "curated_prd_plan_prompt",
    "rag_database_facts",
    "raw_learning_feedback",
    "reference_only_archives",
}

REQUIRED_DOC_PHRASES = {
    "Local live state",
    "Durable collective memory",
    "RAG And Database Facts",
    "Reference-Only Surfaces",
    "Promotion Rule",
    "Agents must not write directly to AIDB or Qdrant",
}

REQUIRED_TRACKED_PATHS = {
    "config/agent-memory-surface-registry.json",
    "docs/operations/agent-memory-state-standard.md",
    "ai-stack/agent-memory/MEMORY.md",
    ".agent/memory/issues-backlog.md",
    ".agent/collaboration/README.md",
    ".agent/collaboration/HANDOFF.template.md",
    ".agent/collaboration/PENDING.template.json",
    ".agent/collaboration/RESUME.template.json",
    "docs/operations/agent-artifact-distribution-policy.md",
}


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(ROOT), *args],
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )


def tracked_files() -> set[str]:
    proc = git("ls-files")
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "git ls-files failed")
    return set(proc.stdout.splitlines())


def tracked_matches(tracked: set[str], pattern: str) -> list[str]:
    return sorted(path for path in tracked if fnmatch.fnmatch(path, pattern))


def require_mapping(value: Any, name: str, failures: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        failures.append(f"{name} must be an object")
        return {}
    return value


def main() -> int:
    failures: list[str] = []

    if not REGISTRY.exists():
        print(f"FAIL: missing registry {REGISTRY.relative_to(ROOT)}")
        return 1
    if not STANDARD_DOC.exists():
        print(f"FAIL: missing standard doc {STANDARD_DOC.relative_to(ROOT)}")
        return 1

    try:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"FAIL: registry JSON invalid: {exc}")
        return 1

    categories = require_mapping(registry.get("categories"), "categories", failures)
    missing_categories = sorted(REQUIRED_CATEGORIES - set(categories))
    if missing_categories:
        failures.append("registry missing categories: " + ", ".join(missing_categories))

    tracked = tracked_files()
    missing_tracked = sorted(path for path in REQUIRED_TRACKED_PATHS if path not in tracked and not (ROOT / path).exists())
    if missing_tracked:
        failures.append("required tracked/added files missing: " + ", ".join(missing_tracked))

    local_live = require_mapping(categories.get("local_live_state"), "local_live_state", failures)
    if local_live.get("tracking") != "ignored":
        failures.append("local_live_state.tracking must be ignored")
    local_forbidden = local_live.get("forbidden_tracked_patterns", [])
    if not isinstance(local_forbidden, list) or not local_forbidden:
        failures.append("local_live_state.forbidden_tracked_patterns must be a non-empty list")
    else:
        leaked = []
        for pattern in local_forbidden:
            if isinstance(pattern, str):
                leaked.extend(tracked_matches(tracked, pattern))
        if leaked:
            failures.append("local live-state files are tracked: " + ", ".join(sorted(set(leaked))))

    feedback = require_mapping(categories.get("raw_learning_feedback"), "raw_learning_feedback", failures)
    if feedback.get("authority") != "evidence-only":
        failures.append("raw_learning_feedback.authority must be evidence-only")
    for pattern in feedback.get("forbidden_tracked_patterns", []):
        if isinstance(pattern, str):
            matches = tracked_matches(tracked, pattern)
            if matches:
                failures.append("raw learning feedback files are tracked: " + ", ".join(matches))

    reference = require_mapping(categories.get("reference_only_archives"), "reference_only_archives", failures)
    if reference.get("authority") != "historical-reference":
        failures.append("reference_only_archives.authority must be historical-reference")
    reference_patterns = set(reference.get("allowed_patterns", []))
    for required_pattern in (".agents/planning/**", ".agents/summary/**"):
        if required_pattern not in reference_patterns:
            failures.append(f"reference_only_archives missing allowed pattern: {required_pattern}")

    rag = require_mapping(categories.get("rag_database_facts"), "rag_database_facts", failures)
    if rag.get("tracking") != "database":
        failures.append("rag_database_facts.tracking must be database")
    allowed = set(rag.get("allowed_patterns", []))
    if "coordinator:/memory/facts" not in allowed or "coordinator:/query" not in allowed:
        failures.append("rag_database_facts must require coordinator:/memory/facts and coordinator:/query")

    hot_limits = require_mapping(registry.get("hot_memory_limits"), "hot_memory_limits", failures)
    hot_path = hot_limits.get("path")
    max_lines = hot_limits.get("max_lines")
    if not isinstance(hot_path, str) or not isinstance(max_lines, int):
        failures.append("hot_memory_limits must define path and integer max_lines")
    else:
        hot_file = ROOT / hot_path
        if not hot_file.exists():
            failures.append(f"hot memory file missing: {hot_path}")
        else:
            line_count = len(hot_file.read_text(encoding="utf-8").splitlines())
            if line_count > max_lines:
                failures.append(f"{hot_path} has {line_count} lines, max is {max_lines}")

    doc = STANDARD_DOC.read_text(encoding="utf-8")
    for phrase in sorted(REQUIRED_DOC_PHRASES):
        if phrase not in doc:
            failures.append(f"standard doc missing phrase: {phrase}")
    for phrase in (".agents/planning/**", ".agents/summary/**", "Raw telemetry is not a fact"):
        if phrase not in doc:
            failures.append(f"standard doc missing reference-only/promotion phrase: {phrase}")

    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for pattern in (".agents/scratchpad/", ".agents/telemetry/*.jsonl", ".agent/collaboration/RESUME.json"):
        if pattern not in gitignore:
            failures.append(f".gitignore missing memory/state local pattern: {pattern}")

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1

    print("PASS: agent memory surface registry is enforced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
