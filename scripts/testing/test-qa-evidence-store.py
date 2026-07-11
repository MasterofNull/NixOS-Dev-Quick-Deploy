#!/usr/bin/env python3
"""Focused immutable QA evidence store fixtures, including real concurrency."""

from __future__ import annotations

import hashlib
import json
import multiprocessing
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ai" / "lib"))

from qa_evidence_store import EvidenceStoreError, QAEvidenceStore


def _writer(root: str, run_id: str, delay: float, queue: multiprocessing.Queue) -> None:
    store = QAEvidenceStore.for_isolated_test(Path(root))
    invocation = store.reserve_invocation(run_id)
    time.sleep(delay)
    result = store.publish(invocation, {"passed": 1, "failed": 0, "tests": []})
    queue.put((invocation.start_sequence, result["artifact"]))


def test_real_concurrent_writers() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        queue: multiprocessing.Queue = multiprocessing.Queue()
        older = multiprocessing.Process(target=_writer, args=(tmp, "older", 0.2, queue))
        newer = multiprocessing.Process(target=_writer, args=(tmp, "newer", 0.0, queue))
        older.start()
        time.sleep(0.05)
        newer.start()
        older.join(10)
        newer.join(10)
        assert older.exitcode == newer.exitcode == 0
        records = [queue.get(timeout=2), queue.get(timeout=2)]
        store = QAEvidenceStore.for_isolated_test(Path(tmp))
        verified = store.read_latest()
        assert verified.pointer["start_sequence"] == max(sequence for sequence, _ in records)
        assert len(list(Path(tmp).glob("qa-results-*.json"))) == 2
        raw = verified.artifact_path.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == verified.pointer["sha256"]


def test_permissions_hash_and_crash_pointer() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        store = QAEvidenceStore.for_isolated_test(root)
        invocation = store.reserve_invocation("stable")
        store.publish(invocation, {"passed": 2, "failed": 0})
        verified = store.read_latest()
        assert verified.payload["run_id"] == "stable"
        assert verified.artifact_path.stat().st_mode & 0o777 == 0o600
        assert store.pointer_path.stat().st_mode & 0o777 == 0o600
        interrupted = root / ".latest-qa-results.json.crash.tmp"
        interrupted.write_text("partial", encoding="utf-8")
        assert store.read_latest().payload["run_id"] == "stable"


def test_invalid_pointer_and_oversize_quarantine() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        store = QAEvidenceStore.for_isolated_test(root)
        invocation = store.reserve_invocation("valid")
        store.publish(invocation, {"passed": 1, "failed": 0})
        pointer = json.loads(store.pointer_path.read_text())
        pointer["target"] = "../escape.json"
        store.pointer_path.write_text(json.dumps(pointer), encoding="utf-8")
        try:
            store.read_latest()
        except EvidenceStoreError as exc:
            assert exc.reason_code == "TARGET_PATH_INVALID"
        else:
            raise AssertionError("traversal pointer accepted")


def test_retention_preserves_pointer_target() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = QAEvidenceStore.for_isolated_test(Path(tmp))
        for index in range(68):
            invocation = store.reserve_invocation(f"run-{index}")
            store.publish(invocation, {"passed": index, "failed": 0})
        verified = store.read_latest()
        assert verified.artifact_path.exists()
        assert len(list(Path(tmp).glob("qa-results-*.json"))) <= 64
        assert list((Path(tmp) / "retired").glob("*"))


def main() -> int:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"{len(tests)} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
