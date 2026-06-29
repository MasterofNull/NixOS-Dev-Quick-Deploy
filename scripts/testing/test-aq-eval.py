#!/usr/bin/env python3
"""Focused tests for the repo-local aq-eval wrapper."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AQ_EVAL = ROOT / "scripts" / "ai" / "aq-eval"
SUITE_FILE = ROOT / "config" / "aq-eval-suites.json"
SCHEMA = ROOT / "config" / "schemas" / "aq-eval-suites.schema.json"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run_json(*args: str) -> dict:
    result = subprocess.run(
        [sys.executable, str(AQ_EVAL), "--json", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )
    assert_true(result.returncode == 0, result.stderr or result.stdout)
    return json.loads(result.stdout)


def main() -> int:
    suite_payload = json.loads(SUITE_FILE.read_text(encoding="utf-8"))
    json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert_true(suite_payload["policy"]["external_frameworks_enabled"] is False, "external frameworks must be disabled")
    assert_true(suite_payload["policy"]["activation_gate"] == "capability-intake", "activation gate must be capability-intake")

    validated = run_json("validate")
    assert_true(validated["status"] == "pass", "validate should pass")
    assert_true(validated["suite_count"] >= 2, "expected at least two suites")
    assert_true(validated["case_count"] >= 4, "expected static eval/red-team cases")

    listed = run_json("list")
    assert_true(listed["command_count"] >= 3, "expected local command checks")

    dry_run = run_json("run")
    assert_true(dry_run["mode"] == "dry-run", "run defaults to dry-run")
    assert_true(dry_run["status"] == "pass", "dry-run should pass")
    assert_true(all(cmd["status"] == "dry-run" for suite in dry_run["suites"] for cmd in suite["commands"]), "commands should not execute in dry-run")

    execute = run_json("run", "--suite", "agent-safety-redteam-static", "--execute")
    assert_true(execute["mode"] == "execute", "execute mode should be reported")
    assert_true(execute["status"] == "pass", "allowlisted command suite should pass")

    print("PASS: aq-eval validates, lists, dry-runs, and executes allowlisted local checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
