#!/usr/bin/env python3
"""Single-use claim semantics for aq-approve / attention_queue
(defect attention-approval-pre-effect-fence-and-actor-auth-gap).

Real attention_queue against a temp ATTENTION_QUEUE_DIR; the executor handler
is replaced with a counting stub (the effect), never a mocked queue.
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AI_DIR = REPO_ROOT / "scripts" / "ai"
TMP = tempfile.mkdtemp(prefix="aq-approve-su-")
os.environ["ATTENTION_QUEUE_DIR"] = TMP
os.environ["ATTENTION_MIRROR_PATH"] = str(Path(TMP) / "mirror.json")
sys.path.insert(0, str(AI_DIR))
sys.path.insert(0, str(AI_DIR / "lib"))

import attention_queue as AQ  # noqa: E402

loader = importlib.machinery.SourceFileLoader("aq_approve_mod", str(AI_DIR / "aq-approve"))
spec = importlib.util.spec_from_loader("aq_approve_mod", loader)
APPROVE = importlib.util.module_from_spec(spec)
loader.exec_module(APPROVE)


def check(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _push(title: str, executor: str = "stub") -> str:
    aid = AQ.push("test", "high", "human_gate", title, "d", "a", executor=executor)
    check(bool(aid), "push failed")
    return aid


def _archive() -> list:
    p = Path(TMP) / "ATTENTION_ARCHIVE.jsonl"
    return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []


def _install(handler):
    APPROVE._EXECUTOR_TABLE["stub"] = handler


def test_concurrent_approvals_execute_once():
    aid = _push("concurrent")
    calls = []
    lock = threading.Lock()

    def handler(alert):
        time.sleep(0.2)  # widen the race window
        with lock:
            calls.append(1)
        return True

    _install(handler)
    rcs = []
    threads = [threading.Thread(target=lambda: rcs.append(APPROVE.main([aid]))) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    check(len(calls) == 1, f"effect ran {len(calls)} times, expected 1")
    rec = [a for a in _archive() if a["id"] == aid]
    check(len(rec) == 1 and rec[0]["status"] == "approved", f"archive: {rec}")


def test_approve_after_reject_does_nothing():
    aid = _push("rejected")
    check(AQ.resolve(aid, "rejected", resolved_by="tester"), "reject failed")
    calls = []
    _install(lambda a: calls.append(1) or True)
    APPROVE.main([aid])
    check(not calls, "effect ran after reject")


def test_approve_after_expiry_does_nothing():
    aid = _push("expired")
    qf = Path(TMP) / "ATTENTION.json"
    d = json.loads(qf.read_text())
    for a in d["alerts"]:
        if a["id"] == aid:
            a["expires_at"] = "2000-01-01T00:00:00Z"
    qf.write_text(json.dumps(d))
    calls = []
    _install(lambda a: calls.append(1) or True)
    APPROVE.main([aid])
    check(not calls, "effect ran after expiry")


def test_executor_failure_is_terminal_failed():
    aid = _push("failing")
    calls = []

    def handler(alert):
        calls.append(1)
        raise RuntimeError("boom")

    _install(handler)
    check(APPROVE.main([aid]) == 1, "failure should return 1")
    rec = [a for a in _archive() if a["id"] == aid]
    check(rec and rec[0]["status"] == "failed" and "boom" in rec[0].get("error", ""), f"{rec}")
    APPROVE.main([aid])
    check(len(calls) == 1, "failed executor was silently re-run")


def test_actor_recorded():
    aid = _push("actor")
    _install(lambda a: True)
    APPROVE.main(["--actor", "ci-bot", aid])
    rec = [a for a in _archive() if a["id"] == aid][0]
    check(rec["resolved_by"] != "human" and rec["resolved_by"].endswith(":ci-bot"), rec["resolved_by"])
    check(rec["claimed_by"] == rec["resolved_by"], "claimed_by mismatch")
    aid2 = _push("actor2")
    APPROVE.main([aid2])
    rec2 = [a for a in _archive() if a["id"] == aid2][0]
    check(rec2["resolved_by"] not in ("human", ""), rec2["resolved_by"])


def main() -> int:
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except Exception as exc:  # noqa: BLE001
                failed += 1
                print(f"FAIL {name}: {exc}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
