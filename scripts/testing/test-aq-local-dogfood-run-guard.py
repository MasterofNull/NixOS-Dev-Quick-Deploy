#!/usr/bin/env python3
"""Regression checks for dogfood CLI and shared-worktree isolation."""

from __future__ import annotations

import importlib.util
import subprocess
from importlib.machinery import SourceFileLoader
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts" / "ai" / "aq-local-dogfood-run"


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    loader = SourceFileLoader("aq_local_dogfood_run", str(RUNNER))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    check(spec is not None and spec.loader is not None, "runner import spec unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    owned, foreign = module.classify_task_changes(
        {"owned.py", "orchestrator.py", ".agents/delegation/dogfood-ledger.jsonl"},
        set(),
        "owned.py",
    )
    check(owned == ["owned.py"], f"declared change classification drifted: {owned}")
    check(foreign == ["orchestrator.py"], f"foreign change was not isolated: {foreign}")

    targeted_prompt = module.build_prompt({
        "backlog_item": "test", "file": "scripts/ai/aq-role-route",
        "target_symbol": "_matches_exclude", "target_read_range": [270, 279],
    })
    check("exactly one bounded read_file call" in targeted_prompt,
          "valid target metadata must request one bounded read")
    check("`scripts/ai/aq-role-route`, lines 270-279" in targeted_prompt,
          "valid target range did not render exactly")
    check("`_matches_exclude`" in targeted_prompt,
          "valid target symbol did not render exactly")

    generic_prompt = module.build_prompt({"backlog_item": "test", "file": "owned.py"})
    check("No exact front-loaded code or exact line-range read is promised" in generic_prompt,
          "missing target metadata must retain the truthful generic instruction")
    check("FRONT-LOADED above" not in generic_prompt,
          "generic prompt must not claim an unspecified exact frontload")
    check("DECLARED SINGLE-FILE SCOPE: owned.py" in generic_prompt,
          "targeting must not alter declared single-file scope")
    check("Do NOT git add / commit / push" in generic_prompt,
          "targeting must not weaken the no-commit instruction")

    with TemporaryDirectory(prefix="aq-dogfood-guard-") as tmp:
        module.LEDGER = Path(tmp) / "ledger.jsonl"
        with patch.object(module, "tracked_mods", return_value=set()), patch.object(
                module.subprocess, "run", side_effect=AssertionError("dispatch must not run")):
            blocked = module.run_task(
                {"task": "blocked", "backlog_item": "test", "file": "owned.py"},
                {"owned.py"},
            )
        check(blocked["status"] == "blocked-preexisting",
              "pre-dirty declared file must stop before dispatch")

        with patch.object(module, "tracked_mods", return_value=set()), patch.object(
                module.subprocess, "run", side_effect=AssertionError("dispatch must not run")):
            malformed = module.run_task(
                {"task": "malformed", "backlog_item": "test", "file": "clean.py",
                 "target_symbol": "safe_symbol", "target_read_range": [279, 270]},
                set(),
            )
        check(malformed["status"] == "blocked-invalid-target-metadata",
              "malformed target range must fail closed before dispatch")

    source = RUNNER.read_text()
    check('"target_symbol": "_matches_exclude", "target_read_range": [270, 279]' in source,
          "dogfood-01 must retain exact target metadata in source")

    help_run = subprocess.run(
        [str(RUNNER), "--help"], cwd=ROOT, text=True, capture_output=True, timeout=5,
    )
    check(help_run.returncode == 0 and "Usage:" in help_run.stdout,
          "--help must exit without starting the queue")
    unknown = subprocess.run(
        [str(RUNNER), "--not-a-real-option"], cwd=ROOT, text=True, capture_output=True, timeout=5,
    )
    check(unknown.returncode == 2, "unknown options must fail before starting the queue")
    print("PASS: dogfood runner guardrails, target metadata, and prompt honesty hold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
