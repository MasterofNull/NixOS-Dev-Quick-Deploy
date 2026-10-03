#!/usr/bin/env python3
"""Unit tests for delegate-to-antigravity inbox bridge and delegation lifecycle."""

import importlib.machinery
import importlib.util
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
        role = "implementer"

        # Mock out aq-antigravity-inbox call by not blocking
        # Simulate worker completing task after 0.2s in a background thread or pre-written
        task_file = inbox_dir / f"{tid}.md"

        # Write output and receipt right after starting
        def simulate_worker():
            import time
            time.sleep(0.1)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text("Detailed diagnosis: root cause verified.\n", encoding="utf-8")
            receipt_file = receipts_dir / f"{tid}.json"
            receipt_file.write_text(json.dumps({
                "task_id": tid,
                "records": [
                    {"type": "claim", "task_id": tid, "actor": "ide-watch"},
                    {"type": "completion", "task_id": tid, "ts": "2026-10-02T12:00:01Z"}
                ]
            }), encoding="utf-8")

        import threading
        t = threading.Thread(target=simulate_worker)
        t.start()

        status, ti, to = mod._run_inbox(tid, prompt, role, timeout=5, log_path=log_path, print_to_stdout=False)
        t.join()

        assert status == "done", f"expected done, got {status}"
        assert task_file.exists(), "task file must exist in inbox"
        content = task_file.read_text(encoding="utf-8")
        assert f"Output: .agents/delegation/outputs/{tid}.log" in content
        assert "Role: implementer" in content
        assert prompt in content

        log_content = log_path.read_text(encoding="utf-8")
        assert f"[delegate-to-antigravity] Task {tid} completed." in log_content
        print("PASS: test_inbox_bridge_dispatch_and_completion")


def test_inbox_bridge_timeout():
    with tempfile.TemporaryDirectory() as td:
        repo = Path(td)
        mod = _load_module(repo)
        mod._ensure_dirs()

        tid = "antigravity-20261002-120000-tst002"
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

        tid = "antigravity-20261002-120000-tst003"
        log_path = mod._OUTPUTS_DIR / f"{tid}.log"
        log_path.write_text("Output from antigravity task.\n", encoding="utf-8")

        mod._registry_append(tid, "implementer", "Test description", log_path)

        receipts_dir = repo / ".agent" / "collaboration" / "antigravity-inbox" / "receipts"
        receipts_dir.mkdir(parents=True, exist_ok=True)
        receipt_file = receipts_dir / f"{tid}.json"
        receipt_file.write_text(json.dumps({
            "task_id": tid,
            "records": [{"type": "completion", "task_id": tid}]
        }), encoding="utf-8")

        # Capture status
        import io
        buf = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf
        try:
            mod.cmd_status(tid)
        finally:
            sys.stdout = old_stdout

        status_text = buf.getvalue()
        assert "completed" in status_text

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
    test_inbox_bridge_timeout()
    test_cmd_status_and_check()
    print("ALL PASS: delegate-to-antigravity unit tests")


if __name__ == "__main__":
    main()
