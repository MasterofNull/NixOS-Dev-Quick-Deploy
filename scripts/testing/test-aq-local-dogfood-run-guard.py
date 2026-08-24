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

    with TemporaryDirectory(prefix="aq-dogfood-guard-") as tmp:
        module.LEDGER = Path(tmp) / "ledger.jsonl"
        with patch.object(module.subprocess, "run", side_effect=AssertionError("dispatch must not run")):
            blocked = module.run_task(
                {"task": "blocked", "backlog_item": "test", "file": "owned.py"},
                {"owned.py"},
            )
        check(blocked["status"] == "blocked-preexisting",
              "pre-dirty declared file must stop before dispatch")

    help_run = subprocess.run(
        [str(RUNNER), "--help"], cwd=ROOT, text=True, capture_output=True, timeout=5,
    )
    check(help_run.returncode == 0 and "Usage:" in help_run.stdout,
          "--help must exit without starting the queue")
    unknown = subprocess.run(
        [str(RUNNER), "--not-a-real-option"], cwd=ROOT, text=True, capture_output=True, timeout=5,
    )
    check(unknown.returncode == 2, "unknown options must fail before starting the queue")
    print("PASS: dogfood runner help is inert and foreign worktree changes are never owned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
