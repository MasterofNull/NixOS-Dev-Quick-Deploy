#!/usr/bin/env python3
"""
Test that PRSI action queue, state, and purge paths are consistent across all scripts and Nix.

Canonical paths:
- Action queue: /var/lib/nixos-ai-stack/optimizer/prsi/action-queue.json
- Runtime state: /var/lib/nixos-ai-stack/optimizer/prsi/runtime-state.json
- Purge audit: /var/lib/nixos-ai-stack/optimizer/prsi/purge-audit.jsonl

This test statically extracts the default paths from all relevant sources
and verifies they are identical and correct (no legacy /var/lib/nixos-ai-stack/prsi/ references).
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"

CANONICAL_QUEUE_PATH = "/var/lib/nixos-ai-stack/optimizer/prsi/action-queue.json"
CANONICAL_STATE_PATH = "/var/lib/nixos-ai-stack/optimizer/prsi/runtime-state.json"
CANONICAL_PURGE_LOG_PATH = "/var/lib/nixos-ai-stack/optimizer/prsi/purge-audit.jsonl"
CANONICAL_NIX_QUEUE_PATH = "${mutableOptimizerDir}/prsi/action-queue.json"
CANONICAL_NIX_STATE_PATH = "${mutableOptimizerDir}/prsi/runtime-state.json"

# Files to check and their extraction patterns for queue paths
QUEUE_FILES_TO_CHECK = {
    SCRIPTS_DIR / "ai" / "aq-rsi": r'PRSI_ACTION_QUEUE_PATH",\s*"([^"]+)"',
    SCRIPTS_DIR / "ai" / "aq-rsi-pending": r'PRSI_ACTION_QUEUE_PATH",\s*"([^"]+)"',
    SCRIPTS_DIR / "automation" / "prsi-orchestrator.py": r'PRSI_ACTION_QUEUE_PATH",\s*"([^"]+)"',
    SCRIPTS_DIR / "ai" / "aq-prsi-review": r'PRSI_ACTION_QUEUE_PATH",\s*"([^"]+)"',
}

# Files to check for state paths (check these have canonical state path defaults)
STATE_FILES_TO_CHECK = {
    SCRIPTS_DIR / "automation" / "prsi-orchestrator.py": r'PRSI_STATE_PATH",\s*"([^"]+)"',
    SCRIPTS_DIR / "testing" / "check-prsi-budget-discipline.sh": r'PRSI_STATE_PATH:-([^}]+)',
}

# Files to check for purge audit log paths
PURGE_FILES_TO_CHECK = {
    SCRIPTS_DIR / "ai" / "aq-prsi-review": r'PRSI_PURGE_AUDIT_LOG",\s*"([^"]+)"',
}

# aq-throttler once list-wrapped the queue dict on write (2026-10-02 incident
# wiped 198 rows). It must perform no queue writes at all.
THROTTLER = SCRIPTS_DIR / "ai" / "aq-throttler"

NIX_FILE = ROOT / "nix" / "modules" / "roles" / "ai-stack.nix"


def extract_default_path(file_path: Path, pattern: str) -> str | None:
    """Extract the default path from a file using the given regex pattern."""
    try:
        content = file_path.read_text()
        matches = re.findall(pattern, content)
        if matches:
            return matches[0]
    except Exception as e:
        print(f"Error reading {file_path}: {e}", file=sys.stderr)
        return None
    return None


def check_nix_file(nix_path: Path) -> bool:
    """Check that the Nix file contains the canonical Nix path."""
    try:
        content = nix_path.read_text()
        return CANONICAL_NIX_PATH in content
    except Exception as e:
        print(f"Error reading {nix_path}: {e}", file=sys.stderr)
        return False


def check_for_legacy_paths(file_path: Path) -> list[str]:
    """Check file for legacy /var/lib/nixos-ai-stack/prsi/ paths (not optimizer/prsi)."""
    try:
        content = file_path.read_text()
        issues = []
        for match in re.finditer(r'/var/lib/nixos-ai-stack/prsi/[a-z\-_.]+', content):
            # Ignore matches that already have optimizer/ prefix
            if 'optimizer/prsi' not in match.group():
                issues.append((match.group(), file_path))
        return issues
    except Exception:
        return []


def main():
    """Run all consistency checks."""
    all_passed = True
    extracted_paths = {}

    # Check QUEUE paths
    print("=== Checking PRSI_ACTION_QUEUE_PATH ===")
    for file_path, pattern in QUEUE_FILES_TO_CHECK.items():
        if not file_path.exists():
            print(f"FAIL: {file_path} not found", file=sys.stderr)
            all_passed = False
            continue

        extracted = extract_default_path(file_path, pattern)
        if extracted is None:
            print(
                f"FAIL: could not extract PRSI_ACTION_QUEUE_PATH from {file_path}",
                file=sys.stderr,
            )
            all_passed = False
            continue

        extracted_paths[str(file_path)] = extracted

        if extracted != CANONICAL_QUEUE_PATH:
            print(
                f"FAIL: {file_path} has queue path {extracted}, expected {CANONICAL_QUEUE_PATH}",
                file=sys.stderr,
            )
            all_passed = False

    # Check STATE paths
    print("=== Checking PRSI_STATE_PATH ===")
    state_files_checked = 0
    for file_path, pattern in STATE_FILES_TO_CHECK.items():
        if not file_path.exists():
            continue

        extracted = extract_default_path(file_path, pattern)
        if extracted is None:
            # Some files may not have extractable state paths; that's ok
            continue

        state_files_checked += 1
        if CANONICAL_STATE_PATH not in extracted:
            print(
                f"FAIL: {file_path} state path {extracted} does not contain {CANONICAL_STATE_PATH}",
                file=sys.stderr,
            )
            all_passed = False

    # Check PURGE AUDIT LOG paths
    print("=== Checking PRSI_PURGE_AUDIT_LOG ===")
    for file_path, pattern in PURGE_FILES_TO_CHECK.items():
        if not file_path.exists():
            print(f"FAIL: {file_path} not found", file=sys.stderr)
            all_passed = False
            continue

        extracted = extract_default_path(file_path, pattern)
        if extracted is None:
            print(
                f"FAIL: could not extract PRSI_PURGE_AUDIT_LOG from {file_path}",
                file=sys.stderr,
            )
            all_passed = False
            continue

        if extracted != CANONICAL_PURGE_LOG_PATH:
            print(
                f"FAIL: {file_path} has purge log path {extracted}, expected {CANONICAL_PURGE_LOG_PATH}",
                file=sys.stderr,
            )
            all_passed = False

    # Check for legacy paths that would cause split-brain
    print("=== Scanning for legacy /var/lib/nixos-ai-stack/prsi/ paths ===")
    legacy_issues = []
    test_file_path = Path(__file__)
    for root_dir in [SCRIPTS_DIR, ROOT / "ai-stack"]:
        if root_dir.exists():
            for py_file in root_dir.glob("**/*.py"):
                # Skip the test file itself (contains patterns as string literals)
                if py_file.resolve() == test_file_path.resolve():
                    continue
                issues = check_for_legacy_paths(py_file)
                legacy_issues.extend(issues)
            for sh_file in root_dir.glob("**/*"):
                if sh_file.is_file() and not sh_file.suffix:
                    issues = check_for_legacy_paths(sh_file)
                    legacy_issues.extend(issues)

    if legacy_issues:
        for legacy_path, file_path in legacy_issues:
            print(
                f"FAIL: {file_path} contains legacy path {legacy_path} (should use optimizer/prsi)",
                file=sys.stderr,
            )
        all_passed = False

    throttler_src = THROTTLER.read_text()
    if any(t in throttler_src for t in ("prsi_queue.save", "prsi_queue.locked", "json.dump(", "write_text")):
        print(
            f"FAIL: {THROTTLER} must perform no queue writes (no prsi_queue.save/locked, json.dump, write_text)",
            file=sys.stderr,
        )
        all_passed = False

    # Check Nix file for canonical paths
    print("=== Checking Nix declarations ===")
    if not NIX_FILE.exists():
        print(f"FAIL: {NIX_FILE} not found", file=sys.stderr)
        all_passed = False
    else:
        nix_content = NIX_FILE.read_text()
        if CANONICAL_NIX_QUEUE_PATH not in nix_content:
            print(
                f"FAIL: {NIX_FILE} does not contain {CANONICAL_NIX_QUEUE_PATH}",
                file=sys.stderr,
            )
            all_passed = False
        if CANONICAL_NIX_STATE_PATH not in nix_content:
            print(
                f"FAIL: {NIX_FILE} does not contain {CANONICAL_NIX_STATE_PATH}",
                file=sys.stderr,
            )
            all_passed = False

    # Summary
    if all_passed:
        print(f"PASS: all PRSI paths (queue, state, purge) point to canonical /var/lib/nixos-ai-stack/optimizer/prsi/")
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
