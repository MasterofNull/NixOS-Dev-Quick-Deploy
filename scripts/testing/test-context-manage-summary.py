#!/usr/bin/env python3
"""Integration regression for aq-context-manage summary."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "scripts" / "ai" / "aq-context-manage"


def _run(*args: str) -> dict:
    result = subprocess.run(
        ["python3", str(TOOL), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = str(Path(tmpdir) / "temporal_facts.json")
        task = "resume local agent workflow"

        _run(
            "checkpoint",
            "--task",
            task,
            "--decision",
            "use bounded validation gates",
            "--next-step",
            "run aq-qa before deeper edits",
            "--fact",
            "embedded-assist is the compact helper lane",
            "--memory-storage",
            storage,
            "--json",
        )

        payload = _run(
            "summary",
            "--task",
            task,
            "--memory-storage",
            storage,
            "--json",
        )

    assert_true(payload["task"] == task, "summary should preserve task")
    assert_true(any("Latest checkpoint event:" in line for line in payload["summary_lines"]), "summary should include latest event")
    assert_true(any("use bounded validation gates" in item["content"] for item in payload["decisions"]), "summary should surface checkpoint decisions")
    assert_true(any("run aq-qa before deeper edits" in item["content"] for item in payload["next_steps"]), "summary should surface next steps")
    assert_true(payload["context_assist_profiles"] == ["embedded-assist"], "summary should surface embedded-assist as the compact helper lane")
    assert_true(
        payload["resume_commands"][0].startswith(f'aq-context-manage summary --task "{task}"'),
        "summary should emit itself as the first compact resume command",
    )

    print("PASS: aq-context-manage summary builds compact checkpoint resumes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
