#!/usr/bin/env python3
"""RSI convene rounds: trigger, budget, seat failure, time limit. Stubbed delegates, no network."""
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ai" / "lib"))
import rsi_convene as rc  # noqa: E402

REPLY = "design reply " + "x" * 260


def iso(days_ago=0):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


def inc(iid, **kw):
    base = {"id": iid, "status": "open", "severity": "medium", "count": 1, "first_seen": iso(1),
            "last_seen": iso(0), "path": "scripts/x.py", "root_fix": "", "error": "boom", "producer": "p"}
    base.update(kw)
    return base


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        t = Path(self.tmp.name)
        self.bin, self.log, self.state = t / "bin", t / "calls.log", t / "rsi-convene.json"
        self.bin.mkdir()
        self.env = {"RSI_CONVENE_DELEGATE_DIR": str(self.bin), "AQ_DELEGATION_DIR": str(t / "deleg"),
                    "RSI_CONVENE_SEAT_TIMEOUT": "5", "RSI_CONVENE": "1"}
        self._old = {k: os.environ.get(k) for k in self.env}
        os.environ.update(self.env)
        self.addCleanup(self.restore)
        self.stub("delegate-to-codex", f'echo "$@" >> {self.log}\n'
                  f'case "$*" in *--budget-check-only*) echo "review headroom: 250000"; exit 0;; esac\necho "{REPLY}"')
        self.stub("delegate-to-gemini", f'echo "$@" >> {self.log}\necho "{REPLY}"')
        self.stub("delegate-to-local", f'echo "$@" >> {self.log}\necho "{REPLY}"')

    def restore(self):
        for k, v in self._old.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)

    def stub(self, name, body):
        (self.bin / name).write_text("#!/usr/bin/env bash\n" + body + "\n")

    def tick(self, incidents):
        return rc.tick({i["id"]: i for i in incidents}, self.state)

    def st(self):
        return json.loads(self.state.read_text())

    def calls(self):
        return self.log.read_text() if self.log.exists() else ""


class Triggers(Base):
    def test_repeat_opens_exactly_one_round(self):
        out = self.tick([inc("a", count=3)])
        self.assertTrue(out["opened"])
        self.assertEqual(len(self.st()["rounds"]), 1)
        self.assertEqual(self.tick([inc("a", count=4)])["opened"], False)  # same incident: no second round
        self.assertEqual(len(self.st()["rounds"]), 1)

    def test_below_threshold_opens_none(self):
        self.assertFalse(self.tick([inc("a", count=2), inc("b", count=5, first_seen=iso(30))])["opened"])
        self.assertEqual(self.st()["rounds"], {})
        self.assertEqual(self.calls(), "")

    def test_high_severity_design_class(self):
        self.assertTrue(self.tick([inc("a", severity="high", root_fix="redesign the review authority boundary",
                                       path="scripts/ai/foo")])["opened"])
        self.assertFalse(self.tick([inc("b", severity="low", root_fix="design flaw")])["opened"])

    def test_gate_touching_fix(self):
        self.assertTrue(self.tick([inc("a", path="scripts/governance/tier0.d/check-x.sh")])["opened"])

    def test_second_trigger_queues(self):
        t = rc.load_state(self.state)
        t["rounds"]["r0"] = {"incident_id": "z", "status": "open", "opened": iso(0)}
        rc.save_state(t, self.state)
        out = self.tick([inc("a", count=3)])
        self.assertFalse(out["opened"])
        self.assertEqual([q["incident_id"] for q in self.st()["queue"]], ["a"])
        self.assertEqual(self.calls(), "")

    def test_one_round_per_tick_extra_queues(self):
        out = self.tick([inc("a", count=3), inc("b", count=3)])
        self.assertTrue(out["opened"])
        self.assertEqual(out["queued"], 1)

    def test_daily_limit_holds(self):
        t = rc.load_state(self.state)
        for n in ("r1", "r2"):
            t["rounds"][n] = {"incident_id": n, "status": "complete", "opened": iso(0)}
        rc.save_state(t, self.state)
        out = self.tick([inc("a", count=3)])
        self.assertFalse(out["opened"])
        self.assertEqual(out["queued"], 1)

    def test_kill_switch(self):
        os.environ["RSI_CONVENE"] = "0"
        self.assertEqual(self.tick([inc("a", count=3)]), {"enabled": False})
        self.assertFalse(self.state.exists())
        self.assertEqual(self.calls(), "")


class Seats(Base):
    def test_down_seat_recorded_round_continues(self):
        self.stub("delegate-to-gemini", "exit 7")
        self.tick([inc("a", count=3)])
        rnd = next(iter(self.st()["rounds"].values()))
        self.assertEqual(rnd["seats"]["gemini"]["state"], "down")
        self.assertEqual(rnd["seats"]["codex"]["state"], "delivered")
        self.assertEqual(rnd["seats"]["local"]["state"], "delivered")

    def test_short_reply_is_short_not_down_and_not_delivered(self):
        self.stub("delegate-to-local", 'echo "' + "y" * 150 + '"')
        self.tick([inc("a", count=3)])
        rnd = next(iter(self.st()["rounds"].values()))
        seat = rnd["seats"]["local"]
        self.assertEqual(seat["state"], "short")
        self.assertIn("150 chars", seat["reason"])
        self.assertNotIn("local", rnd["delivered"])
        self.assertTrue(any(Path(self.tmp.name).rglob(seat["file"])))

    def test_empty_reply_is_down(self):
        self.stub("delegate-to-local", "exit 0")
        self.tick([inc("a", count=3)])
        rnd = next(iter(self.st()["rounds"].values()))
        self.assertEqual(rnd["seats"]["local"]["state"], "down")

    def test_hung_seat_killed_at_limit(self):
        os.environ["RSI_CONVENE_SEAT_TIMEOUT"] = "1"
        self.stub("delegate-to-gemini", "sleep 60")
        t0 = time.monotonic()
        self.tick([inc("a", count=3)])
        self.assertLess(time.monotonic() - t0, 20)
        rnd = next(iter(self.st()["rounds"].values()))
        self.assertIn("hard time limit", rnd["seats"]["gemini"]["reason"])

    def test_fewer_than_two_seats_incomplete(self):
        self.stub("delegate-to-gemini", "exit 1")
        self.stub("delegate-to-codex", "exit 3")
        self.tick([inc("a", count=3)])
        rnd = next(iter(self.st()["rounds"].values()))
        self.assertEqual(rnd["status"], "incomplete")
        self.assertIn("no consensus", rnd["note"])
        self.assertNotIn("consensus reached", json.dumps(rnd))

    def test_two_seats_complete(self):
        self.tick([inc("a", count=3)])
        self.assertEqual(next(iter(self.st()["rounds"].values()))["status"], "complete")

    def test_codex_budget_refusal_never_forces(self):
        self.stub("delegate-to-codex", f'echo "$@" >> {self.log}\ncase "$*" in *--budget-check-only*) exit 3;; esac\necho "{REPLY}"')
        self.tick([inc("a", count=3)])
        calls = self.calls()
        self.assertIn("--budget-check-only", calls)
        self.assertNotIn("--force-budget", calls)
        self.assertFalse([l for l in calls.splitlines() if "--mode safe" in l])  # no seat dispatch after refusal
        rnd = next(iter(self.st()["rounds"].values()))
        self.assertEqual(rnd["seats"]["codex"]["state"], "down")

    def test_gemini_names_flash_model_and_codex_checks_budget_first(self):
        self.tick([inc("a", count=3)])
        lines = self.calls().splitlines()
        self.assertTrue(any("--model gemini-3.8-flash-high" in l for l in lines))
        codex = [l for l in lines if re.search(r"--role review( |$)", l)]
        self.assertIn("--budget-check-only", codex[0])
        self.assertNotIn("--force-budget", self.calls())

    def test_round_is_design_only_artifact(self):
        self.tick([inc("a", count=3)])
        rnd = next(iter(self.st()["rounds"].values()))
        self.assertIn("rsi-rounds", rnd["output_dir"])
        self.assertTrue((Path(rnd["output_dir"]) / "codex.md").exists())
        for l in self.calls().splitlines():
            self.assertNotIn("--mode edit", l)
            self.assertNotIn("yolo", l)

    def test_local_scaffold_is_narrow_and_synchronous(self):
        self.tick([inc("a", count=3)])
        rnd = next(iter(self.st()["rounds"].values()))
        local = [l for l in self.calls().splitlines() if "--mode direct" in l]
        self.assertEqual(len(local), 1)
        # --wait with its own limit: a detached task would be reaped by the unit's control-group kill
        self.assertIn("--wait", local[0])
        self.assertRegex(local[0], r"--timeout \d+")
        self.assertIn("--max-tokens 300", local[0])
        self.assertIn("at most 5 short lines", (Path(rnd["output_dir"]) / "prompt-local.txt").read_text())
        self.assertEqual(rnd["seats"]["local"]["state"], "delivered")

    def test_low_codex_headroom_skips_seat_and_records_why(self):
        self.stub("delegate-to-codex", f'echo "$@" >> {self.log}\ncase "$*" in *--budget-check-only*) '
                  f'echo "review headroom: 59999"; exit 0;; esac\necho "{REPLY}"')
        self.tick([inc("a", count=3)])
        rnd = next(iter(self.st()["rounds"].values()))
        self.assertEqual(rnd["seats"]["codex"]["state"], "down")
        self.assertIn("59999 < 60000", rnd["seats"]["codex"]["reason"])
        self.assertFalse([l for l in self.calls().splitlines() if "--mode safe" in l])

    def test_unparseable_budget_output_skips_codex(self):
        self.stub("delegate-to-codex", f'echo "$@" >> {self.log}\necho "{REPLY}"')
        self.tick([inc("a", count=3)])
        rnd = next(iter(self.st()["rounds"].values()))
        self.assertEqual(rnd["seats"]["codex"]["state"], "down")
        self.assertIn("review headroom None", rnd["seats"]["codex"]["reason"])
        self.assertFalse([l for l in self.calls().splitlines() if "--mode safe" in l])

    def test_codex_runs_shared_no_worktree(self):
        self.tick([inc("a", count=3)])
        line = [l for l in self.calls().splitlines() if "--mode safe" in l][0]
        self.assertIn("--shared", line)

    def test_probe_runs_one_round_outside_budget(self):
        p = rc._probe_path(self.state)
        p.write_text("x")
        out = self.tick([])
        self.assertEqual(out["probe"], "complete")
        self.assertFalse(p.exists())
        self.assertEqual(rc._budget(self.st(), datetime.now(timezone.utc)), (0, 0))
        self.assertTrue(rc.summary(self.state)["last"]["probe"])


class QueueBound(Base):
    def seed(self, entries):
        t = rc.load_state(self.state)
        t["queue"] = entries
        rc.save_state(t, self.state)

    def q(self, iid, days_old=0):
        return {"incident_id": iid, "trigger": "repeat", "queued": iso(days_old)}

    def block_rounds(self):  # keep ticks from opening a round so only pruning is measured
        t = rc.load_state(self.state)
        t["rounds"]["open"] = {"incident_id": "z", "status": "open", "opened": iso(0)}
        rc.save_state(t, self.state)

    def test_queue_never_exceeds_cap_and_keeps_newest(self):
        self.block_rounds()
        ids = [f"i{n}" for n in range(40)]
        self.seed([self.q(i, days_old=2 - n / 100) for n, i in enumerate(ids)])
        out = self.tick([inc(i, count=3) for i in ids])
        qs = [q["incident_id"] for q in self.st()["queue"]]
        self.assertEqual(len(qs), rc.QUEUE_MAX)
        self.assertEqual(qs, ids[-rc.QUEUE_MAX:])
        self.assertEqual(self.st()["dropped"]["over-cap"], 30)
        self.assertEqual(out["queued"], rc.QUEUE_MAX)

    def test_old_entries_expire(self):
        self.block_rounds()
        self.seed([self.q("old", rc.QUEUE_TTL_DAYS + 1), self.q("fresh", 0)])
        self.tick([inc("old", count=3), inc("fresh", count=3)])
        self.assertEqual([q["incident_id"] for q in self.st()["queue"]], ["fresh"])
        self.assertEqual(self.st()["dropped"]["expired"], 1)

    def test_duplicate_incident_entries_collapse(self):
        self.block_rounds()
        self.seed([self.q("a"), self.q("a"), self.q("a")])
        self.tick([inc("a", count=3)])
        self.assertEqual([q["incident_id"] for q in self.st()["queue"]], ["a"])
        self.assertEqual(self.st()["dropped"]["duplicate"], 2)

    def test_resolved_incident_leaves_queue_but_unreadable_ledger_does_not_wipe_it(self):
        self.block_rounds()
        self.seed([self.q("gone"), self.q("closed"), self.q("live")])
        self.tick([inc("closed", count=3, status="closed"), inc("live", count=3)])
        self.assertEqual([q["incident_id"] for q in self.st()["queue"]], ["live"])
        self.seed([self.q("keep")])
        self.tick([])  # empty ledger = nothing known, never a reason to drop
        self.assertEqual([q["incident_id"] for q in self.st()["queue"]], ["keep"])

    def test_summary_reports_drops(self):
        self.block_rounds()
        self.seed([self.q("old", rc.QUEUE_TTL_DAYS + 1)])
        self.tick([inc("old", count=3)])
        self.assertEqual(rc.summary(self.state)["dropped"], {"expired": 1})


class UnitSetting(unittest.TestCase):
    def systemctl(self, body):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        f = Path(d.name) / "systemctl"
        f.write_text("#!/bin/sh\n" + body + "\n")
        f.chmod(0o755)
        old = os.environ.get("PATH")
        os.environ["PATH"] = f"{d.name}:{old}"
        self.addCleanup(os.environ.__setitem__, "PATH", old)

    def test_reads_the_units_environment_not_the_callers(self):
        old = os.environ.pop("RSI_CONVENE", None)  # caller env has no RSI_CONVENE: the old code said False
        self.addCleanup(lambda: old is None or os.environ.__setitem__("RSI_CONVENE", old))
        self.systemctl('echo "Environment=FOO=1 RSI_CONVENE=1 AQ_DELEGATION_DIR=/x y"; echo LoadState=loaded')
        self.assertIs(rc.unit_setting(), True)
        self.assertIs(rc.summary(Path("/nonexistent/x.json"))["enabled"], True)

    def test_unit_without_the_variable_is_off_and_zero_is_off(self):
        self.systemctl('echo "Environment=FOO=1"; echo LoadState=loaded')
        self.assertIs(rc.unit_setting(), False)
        self.systemctl('echo "Environment=RSI_CONVENE=0"; echo LoadState=loaded')
        self.assertIs(rc.unit_setting(), False)

    def test_unreadable_unit_is_unknown(self):
        self.systemctl("exit 1")
        self.assertIsNone(rc.unit_setting())
        self.systemctl('echo "Environment="; echo LoadState=not-found')  # absent unit: rc 0 but not loaded
        self.assertIsNone(rc.unit_setting())
        old = os.environ["PATH"]
        os.environ["PATH"] = "/nonexistent"
        try:
            self.assertIsNone(rc.unit_setting())
        finally:
            os.environ["PATH"] = old


class Activation(unittest.TestCase):
    def test_code_default_is_off(self):
        old = os.environ.pop("RSI_CONVENE", None)
        try:
            self.assertFalse(rc.enabled())
            os.environ["RSI_CONVENE"] = "1"
            self.assertTrue(rc.enabled())
        finally:
            os.environ.pop("RSI_CONVENE", None)
            if old is not None:
                os.environ["RSI_CONVENE"] = old

    def test_nix_unit_declares_what_the_seats_need(self):
        nix = (ROOT / "nix" / "modules" / "roles" / "ai-stack.nix").read_text()
        i = nix.index("systemd.services.ai-prsi-rsi-dispatch = {")
        unit = nix[i:nix.index("systemd.paths.ai-prsi-rsi-dispatch", i)]
        self.assertIn('"RSI_CONVENE=1"', unit)
        self.assertRegex(unit, r"path = \[[^\]]*pkgs\.nodejs")
        self.assertRegex(unit, r'users\.users\.\$\{cfg\.primaryUser\}\.home\}/\.gemini"')
        self.assertRegex(unit, r'users\.users\.\$\{cfg\.primaryUser\}\.home\}/\.codex"')
        self.assertIn("AQ_DELEGATION_DIR=", unit)
        self.assertIn('"ANTIGRAVITY_DISABLE_EMBEDDED_RIPGREP=1"', unit)  # gemini seat: no writes under read-only ~/.local/bin
        self.assertRegex(unit, r"path = \[[^\]]*pkgs\.ripgrep")
        mem = int(re.search(r'MemoryMax = "(\d+)G"', unit).group(1))
        self.assertGreaterEqual(mem, 2)
        # repair 2400s + local seat limit must fit the unit timeout
        self.assertGreaterEqual(int(re.search(r'TimeoutSec = "(\d+)"', unit).group(1)), 2400 + rc.LOCAL_SEAT_TIMEOUT)

    def test_manifest_defers_until_rebuild(self):
        feats = json.loads((ROOT / "config" / "activation-manifest.json").read_text())["features"]
        (f,) = [x for x in feats if x["entrypoint"].endswith("rsi_convene.py")]
        self.assertRegex(f["deferral"]["date"], r"^2026-")
        self.assertIn("rebuild", f["deferral"]["reason"])


class NoAntigravity(unittest.TestCase):
    def test_no_antigravity_path(self):
        src = (ROOT / "scripts" / "ai" / "lib" / "rsi_convene.py").read_text()
        code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
        # the only permitted mention is the module docstring stating the lane is retired
        code = re.sub(r'""".*?"""', "", code, count=1, flags=re.S)
        self.assertNotRegex(code.lower(), r"antigravity")
        self.assertNotIn("--force-budget", code)


class Wiring(unittest.TestCase):
    def test_live_caller_and_status_surface(self):
        orch = (ROOT / "scripts" / "automation" / "prsi-orchestrator.py").read_text()
        self.assertIn("rsi_convene.tick(", orch)
        self.assertRegex(orch, r"args\.func is cmd_rsi_dispatch:\s+_convene_tick\(\)")
        self.assertIn("rsi_convene.summary()", (ROOT / "scripts" / "ai" / "aq-rsi").read_text())


if __name__ == "__main__":
    unittest.main()
