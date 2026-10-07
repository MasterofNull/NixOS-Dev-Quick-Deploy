#!/usr/bin/env python3
"""rsi_gate: bound approvals, atomic leases, daily run budget, and dispatch integration. Offline."""
import importlib.util
import json
import multiprocessing
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

_INCIDENTS_TMP = tempfile.TemporaryDirectory(prefix="prsi-incidents-test-")
os.environ["PRSI_INCIDENTS_FILE"] = str(Path(_INCIDENTS_TMP.name) / "rsi-incidents.json")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/ai/lib"))
import rsi_gate as gate

INC = {"id": "inc1", "producer": "p", "path": "x", "authority": "a", "error": "boom"}
T0 = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def _claimer(store, start, out, n):
    start.wait()
    out.put(gate.claim("row1", f"w{n}", 60, store=Path(store)))


def _reserver(state, start, out):
    start.wait()
    out.put(gate.reserve_daily_run(Path(state), 2, today="2026-10-01")[0])


class ApprovalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Path(self.tmp.name)

    def chk(self, inc=INC, scope="diagnose", now=T0 + timedelta(seconds=10), **kw):
        return gate.check(inc, scope, store=self.store, now=now, **kw)

    def test_valid_expired_mismatch_scope_authority(self):
        self.assertEqual(self.chk(), (False, "no_approval"))
        gate.bind(INC, "diagnose", 60, "owner", store=self.store, now=T0)
        self.assertEqual(self.chk(), (True, "ok"))
        self.assertEqual(self.chk(now=T0 + timedelta(seconds=61)), (False, "approval_expired"))
        self.assertEqual(self.chk(inc={**INC, "error": "different"}), (False, "approval_subject_mismatch"))
        self.assertEqual(self.chk(scope="apply"), (False, "approval_scope_insufficient"))
        self.assertEqual(self.chk(authorities=("someone",)), (False, "approver_not_authorized"))
        gate.bind(INC, "apply", 60, "owner", store=self.store, now=T0)
        self.assertEqual(self.chk(scope="diagnose"), (True, "ok"))  # apply covers diagnose

    def test_bind_validation_and_corrupt_store_fails_closed(self):
        for bad in (dict(scope="nope", ttl_s=60, by="o"), dict(scope="apply", ttl_s=0, by="o"),
                    dict(scope="apply", ttl_s=10**9, by="o"), dict(scope="apply", ttl_s=60, by=" ")):
            with self.assertRaises(ValueError):
                gate.bind(INC, store=self.store, **bad)
        (self.store / "rsi-approvals.json").write_text("{not json")
        self.assertEqual(self.chk(), (False, "approval_store_corrupt"))


class LeaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Path(self.tmp.name)

    def test_concurrent_claim_once(self):
        ctx = multiprocessing.get_context("fork")
        start, out = ctx.Event(), ctx.Queue()
        procs = [ctx.Process(target=_claimer, args=(str(self.store), start, out, n)) for n in range(6)]
        for p in procs: p.start()
        start.set()
        for p in procs: p.join(10)
        results = [out.get(timeout=5) for _ in procs]
        self.assertEqual(results.count(True), 1)

    def test_expiry_reclaim_and_release_owner_check(self):
        self.assertTrue(gate.claim("r", "a", 60, store=self.store, now=T0))
        self.assertFalse(gate.claim("r", "b", 60, store=self.store, now=T0 + timedelta(seconds=30)))
        gate.release("r", "b", store=self.store)  # not the owner: no effect
        self.assertFalse(gate.claim("r", "b", 60, store=self.store, now=T0 + timedelta(seconds=30)))
        self.assertTrue(gate.claim("r", "b", 60, store=self.store, now=T0 + timedelta(seconds=61)))
        gate.release("r", "b", store=self.store)
        self.assertTrue(gate.claim("r", "c", 60, store=self.store, now=T0))

    def test_crash_recovery_dead_pid_reclaims_immediately(self):
        child = subprocess.Popen([sys.executable, "-c", "pass"])
        child.wait()
        self.assertTrue(gate.claim("r", "crashed", 3600, store=self.store, pid=child.pid))
        # Lease is far from expiry but its owner process is gone (crash): reclaimable now.
        self.assertTrue(gate.claim("r", "restarted", 3600, store=self.store))
        self.assertFalse(gate.claim("r", "third", 3600, store=self.store))  # live owner (this pid)


class BudgetTests(unittest.TestCase):
    def test_cap_is_shared_and_atomic_across_processes(self):
        with tempfile.TemporaryDirectory() as t:
            state = Path(t) / "state.json"
            state.write_text(json.dumps({"date": "2026-10-01", "remote_tokens_used": 5}))
            ctx = multiprocessing.get_context("fork")
            start, out = ctx.Event(), ctx.Queue()
            procs = [ctx.Process(target=_reserver, args=(str(state), start, out)) for _ in range(6)]
            for p in procs: p.start()
            start.set()
            for p in procs: p.join(10)
            self.assertEqual([out.get(timeout=5) for _ in procs].count(True), 2)
            data = json.loads(state.read_text())
            self.assertEqual((data["rsi_runs_today"], data["remote_tokens_used"]), (2, 5))  # PRSI keys preserved

    def test_zero_cap_blocks_and_new_day_resets(self):
        with tempfile.TemporaryDirectory() as t:
            state = Path(t) / "s.json"
            self.assertEqual(gate.reserve_daily_run(state, 0, today="2026-10-01"), (False, 0))
            self.assertEqual(gate.reserve_daily_run(state, 1, today="2026-10-01"), (True, 1))
            self.assertEqual(gate.reserve_daily_run(state, 1, today="2026-10-01"), (False, 1))
            self.assertEqual(gate.reserve_daily_run(state, 1, today="2026-10-02"), (True, 1))


class DispatchFilterTests(unittest.TestCase):
    def test_filter_blocks_unbound_and_passes_bound(self):
        spec = importlib.util.spec_from_file_location("prsi_gate_test", ROOT / "scripts/automation/prsi-orchestrator.py")
        prsi = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(prsi)
        with tempfile.TemporaryDirectory() as t:
            ledger = Path(t) / "rsi-incidents.json"
            ledger.write_text(json.dumps({"version": 1, "incidents": {"inc1": INC, "inc2": {**INC, "id": "inc2"}}}))
            prsi._RSI_INCIDENTS = ledger
            gate.bind(INC, "diagnose", 600, "owner", store=Path(t))
            rows = [{"id": "r1", "raw_action": {"incident_id": "inc1"}},
                    {"id": "r2", "raw_action": {"incident_id": "inc2"}},
                    {"id": "r3", "raw_action": {"incident_id": "gone"}}]
            allowed, skips = prsi._rsi_gate_filter(rows, {}, apply=False)
            self.assertEqual([r["id"] for r in allowed], ["r1"])
            self.assertEqual(skips, {"skipped_no_approval": 1, "skipped_no_incident": 1})
            self.assertEqual(rows[1]["execution"]["result"], "skipped_no_approval")
            _, skips = prsi._rsi_gate_filter(rows[:1], {}, apply=True)  # diagnose binding can't apply
            self.assertEqual(skips, {"skipped_approval_scope_insufficient": 1})


if __name__ == "__main__":
    unittest.main()
