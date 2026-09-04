#!/usr/bin/env python3
"""Hermetic regressions for aq-local-dogfood-run collision containment."""
from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace


REPO = Path(__file__).resolve().parents[2]
RUNNER = REPO / "scripts/ai/aq-local-dogfood-run"
loader = importlib.machinery.SourceFileLoader("aq_local_dogfood_collision_test", str(RUNNER))
spec = importlib.util.spec_from_loader(loader.name, loader)
dogfood = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dogfood)


def test_foreign_change_survives_collision() -> None:
    """No collision-era path is checked out when an active task collides."""
    with tempfile.TemporaryDirectory() as tmpdir:
        temp = Path(tmpdir)
        foreign = temp / "foreign.md"
        foreign.write_text("human work: preserve exactly\n")
        canonical_ledger = dogfood.LEDGER
        canonical_ledger_before = canonical_ledger.read_bytes() if canonical_ledger.exists() else None
        originals = {
            "REPO": dogfood.REPO,
            "DIFFDIR": dogfood.DIFFDIR,
            "LEDGER": dogfood.LEDGER,
            "tracked_mods": dogfood.tracked_mods,
            "git": dogfood.git,
            "registered_task_status": dogfood.registered_task_status,
            "cancel_registered_task": dogfood.cancel_registered_task,
            "subprocess_run": dogfood.subprocess.run,
            "monotonic": dogfood.time.monotonic,
            "sleep": dogfood.time.sleep,
        }
        try:
            dogfood.REPO = temp
            dogfood.DIFFDIR = temp / "diffs"
            dogfood.DIFFDIR.mkdir()
            dogfood.LEDGER = temp / "dogfood-ledger.jsonl"
            changes = iter([
                set(),  # pre-dispatch: clean relative to baseline
                {"owned.py", "foreign.md"},  # active task collision
                {"owned.py", "foreign.md"},  # capture collision state
                {"owned.py", "foreign.md"},  # capture declared target diff
            ])
            dogfood.tracked_mods = lambda: next(changes)
            git_calls: list[tuple[str, ...]] = []

            def fake_git(*args: str, check: bool = False) -> str:
                git_calls.append(args)
                if args[:2] == ("diff", "--"):
                    return "diff --git a/owned.py b/owned.py\n"
                return ""

            dogfood.git = fake_git
            dogfood.subprocess.run = lambda *args, **kwargs: SimpleNamespace(
                stdout="local-test-task\n", stderr="", returncode=0
            )
            dogfood.registered_task_status = lambda task_id: {"status": "running"}
            cancelled: list[str] = []
            dogfood.cancel_registered_task = lambda task_id: cancelled.append(task_id) or True
            dogfood.time.monotonic = lambda: 0.0
            dogfood.time.sleep = lambda _: None

            result = dogfood.run_task(
                {"task": "collision-test", "backlog_item": "test", "file": "owned.py"}, set()
            )

            assert result["status"] == "scope-collision"
            assert result["halt_run"] is True
            assert cancelled == ["local-test-task"]
            assert foreign.read_text() == "human work: preserve exactly\n"
            checkouts = [call for call in git_calls if call and call[0] == "checkout"]
            assert checkouts == [], checkouts
            if canonical_ledger_before is None:
                assert not canonical_ledger.exists()
            else:
                assert canonical_ledger.read_bytes() == canonical_ledger_before
        finally:
            dogfood.REPO = originals["REPO"]
            dogfood.DIFFDIR = originals["DIFFDIR"]
            dogfood.LEDGER = originals["LEDGER"]
            dogfood.tracked_mods = originals["tracked_mods"]
            dogfood.git = originals["git"]
            dogfood.registered_task_status = originals["registered_task_status"]
            dogfood.cancel_registered_task = originals["cancel_registered_task"]
            dogfood.subprocess.run = originals["subprocess_run"]
            dogfood.time.monotonic = originals["monotonic"]
            dogfood.time.sleep = originals["sleep"]


def test_main_halts_before_subsequent_dispatch() -> None:
    """A collision result stops queue processing and retries immediately."""
    with tempfile.TemporaryDirectory() as tmpdir:
        temp = Path(tmpdir)
        queue = temp / "queue.json"
        queue.write_text(json.dumps({"queue": [
            {"task": "queue-first", "backlog_item": "first", "file": "first.py"},
            {"task": "queue-second", "backlog_item": "second", "file": "second.py"},
        ]}))
        originals = {
            "QUEUE": dogfood.QUEUE,
            "DIFFDIR": dogfood.DIFFDIR,
            "wait_for_gate": dogfood.wait_for_gate,
            "tracked_mods": dogfood.tracked_mods,
            "run_task": dogfood.run_task,
            "write_summary": dogfood.write_summary,
            "ledger": dogfood.ledger,
        }
        try:
            dogfood.QUEUE = queue
            dogfood.DIFFDIR = temp / "diffs"
            dogfood.wait_for_gate = lambda: True
            dogfood.tracked_mods = lambda: set()
            dogfood.write_summary = lambda *args, **kwargs: None
            dogfood.ledger = lambda row: None
            calls: list[str] = []

            def fake_run(task: dict, baseline: set) -> dict:
                calls.append(task["task"])
                return {
                    "task": task["task"], "backlog_item": task["backlog_item"],
                    "edit_landed": False, "elapsed_s": 0.0, "diff_path": "",
                    "status": "scope-collision", "halt_run": task["task"] == "queue-first",
                }

            dogfood.run_task = fake_run
            assert dogfood.main() == 1
            assert calls == ["dogfood-01", "queue-first"], calls
        finally:
            dogfood.QUEUE = originals["QUEUE"]
            dogfood.DIFFDIR = originals["DIFFDIR"]
            dogfood.wait_for_gate = originals["wait_for_gate"]
            dogfood.tracked_mods = originals["tracked_mods"]
            dogfood.run_task = originals["run_task"]
            dogfood.write_summary = originals["write_summary"]
            dogfood.ledger = originals["ledger"]


if __name__ == "__main__":
    test_foreign_change_survives_collision()
    print("PASS foreign tracked changes survive collision cleanup")
    test_main_halts_before_subsequent_dispatch()
    print("PASS collision terminates run before subsequent task dispatch")
