#!/usr/bin/env python3
"""PRSI queue single-writer contract: fail-closed load, atomic save, serialized RMW."""
import argparse
import importlib.util
import json
import multiprocessing
import os
import sys
import tempfile
import threading
import time
import types
from pathlib import Path

_INCIDENTS_TMP = tempfile.TemporaryDirectory(prefix="prsi-incidents-test-")
os.environ["PRSI_INCIDENTS_FILE"] = str(Path(_INCIDENTS_TMP.name) / "rsi-incidents.json")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ai" / "lib"))
import prsi_queue  # noqa: E402


def _load_orchestrator():
    spec = importlib.util.spec_from_file_location("prsi_orch", ROOT / "scripts/automation/prsi-orchestrator.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _worker(path, n, tag):
    p = Path(path)
    for i in range(n):
        with prsi_queue.locked(p):
            q = prsi_queue.load(p)
            q["actions"].append({"id": f"{tag}-{i}", "status": "pending_approval"})
            prsi_queue.save(q, p)


def main() -> int:
    failures = []

    def check(name, cond):
        print(("PASS" if cond else "FAIL") + f": {name}")
        if not cond:
            failures.append(name)

    with tempfile.TemporaryDirectory() as tmp:
        qp = Path(tmp) / "action-queue.json"
        os.environ["PRSI_ACTION_QUEUE_PATH"] = str(qp)
        check("queue_path honors env", prsi_queue.queue_path() == qp)

        # (b) schema preserved, mode preserved
        qp.write_text(json.dumps({"updated_at": None, "actions": [{"id": "seed", "status": "approved"}],
                                  "meta": {"k": 1}}))
        os.chmod(qp, 0o640)
        q = prsi_queue.load()
        prsi_queue.save(q)
        data = json.loads(qp.read_text())
        check("save keeps dict schema", isinstance(data, dict) and data["actions"][0]["id"] == "seed"
              and data["meta"] == {"k": 1} and data["updated_at"])
        check("save preserves file mode", (qp.stat().st_mode & 0o777) == 0o640)

        os.environ["PRSI_STATE_PATH"] = str(Path(tmp) / "state.json")
        os.environ["PRSI_ACTIONS_LOG_PATH"] = str(Path(tmp) / "actions.jsonl")
        orch = _load_orchestrator()
        events = []
        orch._log_event = events.append
        raw = {"type": "maintenance", "action": "noop", "reason": "t", "safe": True}

        def seed(rows):
            qp.write_text(json.dumps({"updated_at": None, "meta": {}, "actions": rows}))

        def fake_run_with(mutate):
            def fake_run(argv, **kw):
                mutate()
                return types.SimpleNamespace(returncode=0, stdout=json.dumps({"applied": []}), stderr="")
            return fake_run

        def run_execute(mutate):
            orch.subprocess.run = fake_run_with(mutate)
            orch.cmd_execute(argparse.Namespace(limit=1, dry_run=False))
            return {r["id"]: r for r in json.loads(qp.read_text())["actions"]}

        def row(i, status="approved"):
            return {"id": i, "status": status, "risk": "low", "raw_action": dict(raw), "approval": {}, "seen_count": 1}

        # (a) reject during unlocked execute phase: stays rejected + merge_conflict logged
        seed([row("ex1")])
        events.clear()
        rows = run_execute(lambda: orch._set_approval("ex1", "reject", "owner", "no"))
        check("reject during execute stays rejected", rows["ex1"]["status"] == "rejected"
              and rows["ex1"]["approval"].get("by") == "owner")
        check("merge_conflict logged", any(e.get("event") == "merge_conflict" and e.get("id") == "ex1" for e in events))

        # (b) verify during execute + verify during dispatch merge
        seed([row("ex1"), row("other", "executed")])
        t0 = time.time()
        rows = run_execute(lambda: orch._set_verifier("other", "tester", "n"))
        check("verify during execute survives; execute result lands",
              rows["other"]["approval"].get("verifier_by") == "tester"
              and rows["ex1"]["execution"]["result"] == "optimizer_noop" and time.time() - t0 < 10)
        seed([row("d1", "rsi_pending")])
        snap = orch._load_queue()
        r = snap["actions"][0]
        orch._set_verifier("d1", "tester", "n")
        r["status"] = "rsi_running"
        r["rsi_attempts"] = 1
        conflicts = orch._merge_save(snap, [r], orch._RSI_OWNED_FIELDS, {"d1": "rsi_pending"})
        fr = json.loads(qp.read_text())["actions"][0]
        check("dispatch merge keeps verifier_by and lands status/attempts",
              not conflicts and fr["approval"].get("verifier_by") == "tester"
              and fr["status"] == "rsi_running" and fr["rsi_attempts"] == 1)
        r["status"] = "rsi_failed"
        conflicts = orch._merge_save(snap, [r], orch._RSI_OWNED_FIELDS, {"d1": "rsi_pending"})
        check("dispatch merge conflicts when status no longer expected",
              conflicts == ["d1"] and json.loads(qp.read_text())["actions"][0]["status"] == "rsi_running")

        # (c) sync-style seen_count bump during execute survives
        def bump():
            with prsi_queue.locked(qp):
                q = prsi_queue.load(qp)
                q["actions"][0]["seen_count"] = 7
                q["actions"][0]["raw_action"]["reason"] = "bumped"
                prsi_queue.save(q, qp)

        seed([row("ex1")])
        rows = run_execute(bump)
        check("sync bump during execute survives",
              rows["ex1"]["seen_count"] == 7 and rows["ex1"]["raw_action"]["reason"] == "bumped"
              and rows["ex1"]["execution"]["result"] == "optimizer_noop")

        # (c) concurrent writers, no lost update
        qp.write_text(json.dumps({"updated_at": None, "actions": [], "meta": {}}))
        procs = [multiprocessing.Process(target=_worker, args=(str(qp), 25, t)) for t in ("a", "b", "c")]
        for p in procs:
            p.start()
        for p in procs:
            p.join()
        data = json.loads(qp.read_text())
        check("concurrent locked writers lose no updates", len(data["actions"]) == 75
              and all(p.exitcode == 0 for p in procs))

        # (d) malformed -> RuntimeError, untouched
        for bad in ("{not json", json.dumps([{"id": "x"}]), json.dumps({"actions": {}})):
            qp.write_text(bad)
            try:
                prsi_queue.load()
                ok = False
            except RuntimeError:
                ok = True
            check(f"malformed {bad[:12]!r} fails closed and file untouched", ok and qp.read_text() == bad)

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
