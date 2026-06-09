#!/usr/bin/env python3
"""Validate tracked-vs-local policy for agent runtime artifacts."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

LOCAL_ONLY = {
    ".agent/collaboration/HANDOFF.md",
    ".agent/collaboration/PENDING.json",
    ".agent/collaboration/PULSE.log",
    ".agent/collaboration/RESUME.json",
    ".agent/comms/command.json",
    ".agent/comms/output.json",
    ".agent/comms/output.txt",
    ".agents/attention/ATTENTION.json",
    ".agents/attention/ATTENTION_ARCHIVE.jsonl",
    ".agents/delegation/registry.jsonl",
    ".agents/delegation/outputs/claude-arch-revamp-all-slices-done.md",
    ".agents/telemetry/hybrid-events.jsonl",
    ".agents/telemetry/routing-decisions.jsonl",
    "nix/hosts/hyperd/facts.nix",
    "nix/hosts/nixos/facts.nix",
    "nix/hosts/sbc-minimal/facts.nix",
}

REQUIRED_TRACKED = {
    ".agent/collaboration/README.md",
    ".agent/collaboration/HANDOFF.template.md",
    ".agent/collaboration/PENDING.template.json",
    ".agent/collaboration/RESUME.template.json",
    "docs/operations/agent-artifact-distribution-policy.md",
}

REQUIRED_IGNORE_PATTERNS = {
    ".agent/collaboration/HANDOFF.md",
    ".agent/collaboration/PENDING.json",
    ".agent/collaboration/PULSE.log",
    ".agent/collaboration/RESUME.json",
    ".agent/comms/command.json",
    ".agent/comms/output.json",
    ".agent/comms/output.txt",
    ".agents/attention/ATTENTION.json",
    ".agents/attention/ATTENTION_ARCHIVE.jsonl",
    ".agents/delegation/registry.jsonl",
    ".agents/telemetry/*.jsonl",
    "nix/hosts/*/facts.nix",
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
        raise RuntimeError(proc.stderr)
    return set(proc.stdout.splitlines())


def main() -> int:
    tracked = tracked_files()
    failures: list[str] = []

    still_tracked = sorted(LOCAL_ONLY & tracked)
    if still_tracked:
        failures.append("local-only artifacts still tracked: " + ", ".join(still_tracked))

    missing = sorted(REQUIRED_TRACKED - tracked)
    if missing:
        failures.append("required portable policy/template files not tracked: " + ", ".join(missing))

    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    missing_ignores = sorted(pattern for pattern in REQUIRED_IGNORE_PATTERNS if pattern not in gitignore)
    if missing_ignores:
        failures.append("missing .gitignore patterns: " + ", ".join(missing_ignores))

    policy = (ROOT / "docs" / "operations" / "agent-artifact-distribution-policy.md").read_text(encoding="utf-8")
    for phrase in ("Portable collective knowledge", "Local-Only Artifacts", "Promotion Rule"):
        if phrase not in policy:
            failures.append(f"policy missing section/phrase: {phrase}")

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1

    print("PASS: agent artifact distribution policy is enforced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
