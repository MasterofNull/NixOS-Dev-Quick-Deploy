#!/usr/bin/env python3
"""
Test that PRSI action queue path is consistent across all scripts and Nix.

The canonical path is /var/lib/nixos-ai-stack/optimizer/prsi/action-queue.json.
This test statically extracts the default queue path from all relevant sources
and verifies they are identical and correct.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"

CANONICAL_PATH = "/var/lib/nixos-ai-stack/optimizer/prsi/action-queue.json"
CANONICAL_NIX_PATH = "${mutableOptimizerDir}/prsi/action-queue.json"

# Files to check and their extraction patterns
FILES_TO_CHECK = {
    SCRIPTS_DIR / "ai" / "aq-rsi": r'PRSI_ACTION_QUEUE_PATH",\s*"([^"]+)"',
    SCRIPTS_DIR / "ai" / "aq-rsi-pending": r'PRSI_ACTION_QUEUE_PATH",\s*"([^"]+)"',
    SCRIPTS_DIR / "automation" / "prsi-orchestrator.py": r'PRSI_ACTION_QUEUE_PATH",\s*"([^"]+)"',
    SCRIPTS_DIR / "ai" / "aq-prsi-review": r'PRSI_ACTION_QUEUE_PATH",\s*"([^"]+)"',
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


def main():
    """Run all consistency checks."""
    all_passed = True
    extracted_paths = {}

    # Extract defaults from each file
    for file_path, pattern in FILES_TO_CHECK.items():
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

        if extracted != CANONICAL_PATH:
            print(
                f"FAIL: {file_path} has path {extracted}, expected {CANONICAL_PATH}",
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

    # Check Nix file
    if not NIX_FILE.exists():
        print(f"FAIL: {NIX_FILE} not found", file=sys.stderr)
        all_passed = False
    elif not check_nix_file(NIX_FILE):
        print(
            f"FAIL: {NIX_FILE} does not contain {CANONICAL_NIX_PATH}",
            file=sys.stderr,
        )
        all_passed = False

    # Summary
    if all_passed:
        print(f"PASS: all PRSI queue paths point to {CANONICAL_PATH}")
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
