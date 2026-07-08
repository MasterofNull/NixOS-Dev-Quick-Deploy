#!/usr/bin/env python3
"""Integration regression for aq-context-manage summary."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "scripts" / "ai" / "aq-context-manage"


def _run(*args: str, env: dict[str, str] | None = None) -> dict:
    merged_env = os.environ.copy()
    merged_env["AQ_CONTEXT_MANAGE_SKIP_CLM"] = "1"
    if env:
        merged_env.update(env)
    result = subprocess.run(
        ["python3", str(TOOL), *args],
        cwd=ROOT,
        env=merged_env,
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

        clm_status_file = Path(tmpdir) / "clm-status.json"
        clm_status_file.write_text(
            json.dumps(
                {
                    "pressure_pct": 101.5,
                    "thermal_tier": "critical",
                    "compaction_suspended": True,
                    "thresholds": {"hot_pressure_pct": 85.0},
                }
            ),
            encoding="utf-8",
        )
        check_payload = _run(
            "check",
            "--json",
            env={
                "AQ_CONTEXT_MANAGE_SKIP_CLM": "0",
                "AQ_CONTEXT_MANAGE_CLM_STATUS_FILE": str(clm_status_file),
            },
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
    assert_true(check_payload["should_trigger"] is True, "high live CLM pressure should trigger context action")
    assert_true("CLM hot pressure" in check_payload["reason"], "check reason should name live CLM pressure")
    assert_true(check_payload["clm_status"]["thermal_tier"] == "critical", "check should include live CLM details")

    print("PASS: aq-context-manage summary builds compact checkpoint resumes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
