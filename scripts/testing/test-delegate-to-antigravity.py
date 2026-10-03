#!/usr/bin/env python3
"""Unit tests for delegate-to-antigravity inbox bridge and delegation lifecycle."""

import importlib.machinery
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ai" / "delegate-to-antigravity"


def _load_module(repo_path: Path):
    loader = importlib.machinery.SourceFileLoader("delegate_to_antigravity", str(SCRIPT))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    mod._REPO = repo_path
    mod._DELEGATION_DIR = repo_path / ".agents" / "delegation"
    mod._OUTPUTS_DIR = mod._DELEGATION_DIR / "outputs"
    mod._REGISTRY = mod._DELEGATION_DIR / "registry.jsonl"
    loader.exec_module(mod)
    mod._REPO = repo_path
    mod._DELEGATION_DIR = repo_path / ".agents" / "delegation"
    mod._OUTPUTS_DIR = mod._DELEGATION_DIR / "outputs"
    mod._REGISTRY = mod._DELEGATION_DIR / "registry.jsonl"
    return mod


def _load_inbox(repo_path: Path):
    loader = importlib.machinery.SourceFileLoader(
        "test_antigravity_inbox", str(ROOT / "scripts" / "ai" / "aq-antigravity-inbox")
    )
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    mod.REPO = repo_path
    mod.INBOX = repo_path / ".agent" / "collaboration" / "antigravity-inbox"
    return mod


def test_inbox_bridge_dispatch_and_completion():
    with tempfile.TemporaryDirectory() as td:
        repo = Path(td)
        mod = _load_module(repo)
        mod._ensure_dirs()

        tid = "antigravity-20261002-120000-tst001"
        log_path = mod._OUTPUTS_DIR / f"{tid}.log"
        inbox_dir = repo / ".agent" / "collaboration" / "antigravity-inbox"
        receipts_dir = inbox_dir / "receipts"
        receipts_dir.mkdir(parents=True, exist_ok=True)

        prompt = "Diagnose RSI incident rsi-20261002-001."
        role = "reviewer"

        task_file = inbox_dir / f"{tid}.md"

        def simulate_worker():
            import time
            time.sleep(0.1)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text("Detailed diagnosis: root cause verified.\n", encoding="utf-8")
            inbox = _load_inbox(repo)
            assert inbox.main(["claim", task_file.name, "--actor", "ide-watch"]) == 0
            assert inbox.main([
                "complete", f".claimed-{tid}",
                "--output", f".agents/delegation/outputs/{tid}.log",
            ]) == 0

        import threading
        t = threading.Thread(target=simulate_worker)
        t.start()

        status, ti, to = mod._run_inbox(tid, prompt, role, timeout=5, log_path=log_path, print_to_stdout=False)
        t.join()

        assert status == "done", f"expected done, got {status}"
        assert task_file.exists() or (repo / ".agent" / "archive").exists(), "task file must be processed"
        log_content = log_path.read_text(encoding="utf-8")
        assert "[delegate-to-antigravity]" not in log_content, "output must remain strictly immutable"
        print("PASS: test_inbox_bridge_dispatch_and_completion")


def test_inbox_bridge_refuses_unisolated_implementation():
    with tempfile.TemporaryDirectory() as td:
        repo = Path(td)
        mod = _load_module(repo)
        mod._ensure_dirs()

        tid = "antigravity-20261002-120000-tst002"
        log_path = mod._OUTPUTS_DIR / f"{tid}.log"

        for imp_role in ("implement", "implementer"):
            status, ti, to = mod._run_inbox(tid, "code task", imp_role, timeout=5, log_path=log_path, print_to_stdout=False)
            assert status == "failed", f"expected failed for role {imp_role}, got {status}"
            assert log_path.exists()
            content = log_path.read_text(encoding="utf-8")
            assert "refusing editing dispatch" in content or "worktree isolation creation failed" in content
        print("PASS: test_inbox_bridge_refuses_unisolated_implementation")


def test_inbox_bridge_rejects_corrupted_or_mismatched_receipt():
    with tempfile.TemporaryDirectory() as td:
        repo = Path(td)
        mod = _load_module(repo)
        mod._ensure_dirs()

        tid = "antigravity-20261002-120000-tst003"
        log_path = mod._OUTPUTS_DIR / f"{tid}.log"
        inbox_dir = repo / ".agent" / "collaboration" / "antigravity-inbox"
        receipts_dir = inbox_dir / "receipts"
        receipts_dir.mkdir(parents=True, exist_ok=True)

        # Write fake receipt with wrong task_id and wrong records
        receipt_file = receipts_dir / f"{tid}.json"
        receipt_file.write_text(json.dumps({
            "task_id": "wrong-task",
            "records": [{"type": "completion", "task_id": "wrong-task"}]
        }), encoding="utf-8")

        status, ti, to = mod._run_inbox(tid, "prompt", "reviewer", timeout=1, log_path=log_path, print_to_stdout=False)
        assert status == "failed", f"expected failed on mismatched receipt, got {status}"
        print("PASS: test_inbox_bridge_rejects_corrupted_or_mismatched_receipt")


def test_inbox_bridge_timeout():
    with tempfile.TemporaryDirectory() as td:
        repo = Path(td)
        mod = _load_module(repo)
        mod._ensure_dirs()

        tid = "antigravity-20261002-120000-tst004"
        log_path = mod._OUTPUTS_DIR / f"{tid}.log"

        status, ti, to = mod._run_inbox(tid, "short prompt", "reviewer", timeout=1, log_path=log_path, print_to_stdout=False)
        assert status == "timeout", f"expected timeout, got {status}"
        assert log_path.exists()
        assert "timed out after 1s" in log_path.read_text(encoding="utf-8")
        print("PASS: test_inbox_bridge_timeout")


def test_cmd_status_and_check():
    with tempfile.TemporaryDirectory() as td:
        repo = Path(td)
        mod = _load_module(repo)
        mod._ensure_dirs()

        tid = "antigravity-20261002-120000-tst005"
        log_path = mod._OUTPUTS_DIR / f"{tid}.log"
        log_path.write_text("Output from antigravity task.\n", encoding="utf-8")
        mod._registry_append(tid, "reviewer", "Test description", log_path)

        inbox_dir = repo / ".agent" / "collaboration" / "antigravity-inbox"
        task_file = inbox_dir / f"{tid}.md"
        task_file.parent.mkdir(parents=True, exist_ok=True)
        task_file.write_text(f"# Task\nOutput: .agents/delegation/outputs/{tid}.log\nRole: reviewer\n\nprompt\n", encoding="utf-8")

        inbox = _load_inbox(repo)
        assert inbox.main(["claim", task_file.name, "--actor", "ide-watch"]) == 0
        assert inbox.main([
            "complete", f".claimed-{tid}",
            "--output", f".agents/delegation/outputs/{tid}.log",
        ]) == 0

        # Capture status with valid supervisor receipt
        buf = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf
        try:
            mod.cmd_status(tid)
        finally:
            sys.stdout = old_stdout

        status_text = buf.getvalue()
        assert '"status": "completed"' in status_text

        # Capture check
        buf_check = io.StringIO()
        sys.stdout = buf_check
        try:
            mod.cmd_check(tid)
        finally:
            sys.stdout = old_stdout

        check_text = buf_check.getvalue()
        assert "Output from antigravity task." in check_text
        print("PASS: test_cmd_status_and_check")


def main():
    test_inbox_bridge_dispatch_and_completion()
    test_inbox_bridge_refuses_unisolated_implementation()
    test_inbox_bridge_rejects_corrupted_or_mismatched_receipt()
    test_inbox_bridge_timeout()
    test_cmd_status_and_check()
    print("ALL PASS: delegate-to-antigravity unit tests")


if __name__ == "__main__":
    main()
