#!/usr/bin/env python3
"""Tests for scripts/ai/lib/work_ledger.py, scripts/ai/aq-ledger, the tier0 ledger check and the delegation
wrappers' ledger writes (all state in temp dirs; wrappers run from a throwaway copy of scripts/ai)."""
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "scripts/ai/lib"
CLI = REPO / "scripts/ai/aq-ledger"
TIER0_CHECK = REPO / "scripts/governance/tier0.d/check-work-ledger.sh"
sys.path.insert(0, str(LIB))

import work_ledger as wl  # noqa: E402


class LedgerCase(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="aq-work-ledger-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "delegation"
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop(wl.WINDOW_ENV, None)

    def add(self, event: str, dispatch_id: str = "d1", **kwargs):
        return wl.append_event(dispatch_id, event, delegation_dir=self.root, **kwargs)

    def init(self, dispatch_id: str = "d1", **kwargs):
        fields = {"lane": "codex", "role": "implementer", "task": "build it", **kwargs}
        return self.add("init", dispatch_id, **fields)

    def path(self, dispatch_id: str = "d1") -> Path:
        return wl.ledger_path(dispatch_id, self.root)

    def reduce(self, dispatch_id: str = "d1", **kwargs):
        return wl.reduce_ledger_file(self.path(dispatch_id), **kwargs)

    def lines(self, dispatch_id: str = "d1") -> list[bytes]:
        return self.path(dispatch_id).read_bytes().splitlines(keepends=True)


class LifecycleTest(LedgerCase):
    def test_full_lifecycle(self) -> None:
        self.init(model="m", parent="p", brief_path="b", worktree="w", branch="br", pr=7,
                  findings_path="f", resume_policy="auto", status="queued")
        queued = self.reduce()
        self.assertEqual((queued["status"], queued["auto_resume_allowed"]), ("queued", True))
        self.add("status", status="running")
        self.assertFalse(self.reduce()["auto_resume_allowed"])
        self.add("step", name="edit", status="running", artifact="a.diff")
        self.add("heartbeat", detail="still here")
        self.add("step", name="edit", status="done")
        self.add("step", name="test", status="skipped")
        self.add("status", status="done", reason="ok")
        got = self.reduce()
        expected = {"id": "d1", "lane": "codex", "model": "m", "role": "implementer", "parent": "p",
                    "task": "build it", "brief_path": "b", "worktree": "w", "branch": "br", "pr": 7,
                    "findings_path": "f", "resume_policy": "auto", "status": "done", "status_reason": "ok",
                    "torn_tail": False, "stale_heartbeat": False, "auto_resume_allowed": False,
                    "warnings": [], "event_count": 7, "path": str(self.path()),
                    "boot_id": wl.read_boot_id(), "pid": os.getpid(),
                    "pid_start_ticks": wl.read_pid_start_ticks(os.getpid())}
        self.assertEqual({k: got[k] for k in expected}, expected)
        self.assertEqual([(s["name"], s["status"], s["artifact"]) for s in got["steps"]],
                         [("edit", "done", "a.diff"), ("test", "skipped", None)])
        self.assertEqual(got["last_heartbeat"], json.loads(self.lines()[-1])["at"])

    def test_record_envelope_and_single_line(self) -> None:
        record = self.init(task="line one\nline two \u2028 caf\u00e9")
        self.assertEqual(record["schema"], 1)
        self.assertRegex(record["at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertIsInstance(record["pid_start_ticks"], int)
        self.assertEqual(self.path().read_bytes().count(b"\n"), 1)
        self.assertEqual(self.reduce()["task"], "line one\nline two \u2028 caf\u00e9")
        self.assertEqual(self.reduce()["resume_policy"], "confirm")

    def test_overrides_and_missing_pid(self) -> None:
        record = self.init(boot_id="boot-x", pid=999_999_999)
        self.assertEqual((record["boot_id"], record["pid"], record["pid_start_ticks"]),
                         ("boot-x", 999_999_999, None))

    def test_modes(self) -> None:
        old = os.umask(0)
        try:
            self.init()
        finally:
            os.umask(old)
        self.assertEqual(stat.S_IMODE(self.path().parent.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(self.path().stat().st_mode), 0o600)

    def test_env_delegation_dir_is_default(self) -> None:
        os.environ["AQ_DELEGATION_DIR"] = str(self.root)
        self.assertEqual(wl.ledger_dir(), self.root / "ledger")

    def test_default_dir_without_git(self) -> None:
        os.environ.pop("AQ_DELEGATION_DIR", None)
        os.environ["AQ_ALLOW_VOLATILE_DIR"] = "1"
        with mock.patch("subprocess.run", side_effect=OSError("no git")), mock.patch("sys.stderr"):
            self.assertEqual(wl.ledger_dir(), REPO / ".agents/delegation/ledger")

    def test_invalid_ids_rejected(self) -> None:
        for bad in ("", "../escape", "a/b", "..", "a..b", ".hidden", "-x", "a\n", "a\x00", "a b", "x" * 129):
            with self.subTest(bad=bad), self.assertRaises(wl.LedgerError):
                self.init(bad)
        self.assertFalse(self.root.exists())
        self.init("x" * 128)

    def test_writer_refusals(self) -> None:
        with self.assertRaises(wl.LedgerError):
            self.add("heartbeat")
        self.assertFalse(self.root.exists())
        for bad in ({"task": ""}, {"status": "done"}, {"pr": "7"}, {"resume_policy": "x"}):
            with self.subTest(bad=bad), self.assertRaises(wl.LedgerError):
                self.init(**bad)
        self.assertFalse(self.root.exists())
        self.init()
        before = self.path().read_bytes()
        cases: tuple[tuple[str, dict[str, Any]], ...] = (
            ("init", {"lane": "l", "role": "r", "task": "t"}),
            ("step", {"name": "s", "status": "bogus"}),
            ("status", {"status": "bogus"}),
            ("heartbeat", {"nope": 1}),
            ("bogus", {}),
        )
        for event, fields in cases:
            with self.subTest(event=event), self.assertRaises(wl.LedgerError):
                wl.append_event("d1", event, delegation_dir=self.root, **fields)
        self.assertEqual(self.path().read_bytes(), before)

    def test_symlinked_entry_refused(self) -> None:
        self.init()
        target = self.root / "target"
        target.write_text("keep")
        self.path("link").symlink_to(target)
        with self.assertRaises(OSError):
            self.add("heartbeat", "link")
        self.assertEqual(self.reduce("link")["status"], "needs-attention")
        self.assertEqual(target.read_text(), "keep")


class ProjectionTest(LedgerCase):
    def test_prior_boot_running_is_interrupted(self) -> None:
        self.init(boot_id="old", resume_policy="auto")
        got = self.reduce(current_boot_id="new")
        self.assertEqual((got["status"], got["interrupted_reason"]), ("interrupted", "prior-boot"))
        self.assertTrue(got["auto_resume_allowed"])
        self.assertFalse(got["stale_heartbeat"])
        self.assertEqual(self.reduce(current_boot_id="old")["status"], "running")

    def test_prior_boot_leaves_other_states(self) -> None:
        for index, status in enumerate(s for s in wl.STATUSES if s != "running"):
            dispatch_id = f"s{index}"
            self.init(dispatch_id, boot_id="old")
            self.add("status", dispatch_id, status=status, boot_id="old")
            with self.subTest(status=status):
                self.assertEqual(self.reduce(dispatch_id, current_boot_id="new")["status"], status)

    def test_last_event_boot_id_decides(self) -> None:
        self.init(boot_id="old")
        self.add("heartbeat", boot_id="new")
        self.assertEqual(self.reduce(current_boot_id="new")["status"], "running")

    def test_stale_window(self) -> None:
        self.init()
        later = datetime.now(timezone.utc) + timedelta(seconds=120)
        self.assertFalse(self.reduce(now=later)["stale_heartbeat"])
        self.assertTrue(self.reduce(now=later + timedelta(seconds=1800))["stale_heartbeat"])
        os.environ[wl.WINDOW_ENV] = "60"
        self.assertTrue(self.reduce(now=later)["stale_heartbeat"])
        os.environ[wl.WINDOW_ENV] = "600"
        self.assertFalse(self.reduce(now=later)["stale_heartbeat"])
        self.add("status", status="done")
        self.assertFalse(self.reduce(now=later + timedelta(days=1))["stale_heartbeat"])

    def test_invalid_window_rejected(self) -> None:
        for bad in ("", "0", "-5", "abc", "1.5"):
            os.environ[wl.WINDOW_ENV] = bad
            with self.subTest(bad=bad), self.assertRaises(wl.LedgerError):
                wl.heartbeat_window_s()


class TornAndCorruptTest(LedgerCase):
    def build(self) -> None:
        self.init(boot_id="old", resume_policy="auto")
        self.add("step", name="one", status="done", boot_id="old")
        self.add("step", name="two", status="done", boot_id="old")

    def test_torn_tail_preserves_done_steps(self) -> None:
        self.build()
        self.add("step", name="three", status="done", boot_id="old")
        data = self.path().read_bytes()
        last = self.lines()[-1]
        for cut in (1, len(last) // 2, len(last) - 1):
            with self.subTest(kept_bytes=cut):
                self.path().write_bytes(data[:-len(last)] + last[:cut])
                got = self.reduce(current_boot_id="new")
                self.assertTrue(got["torn_tail"])
                self.assertIn("torn tail", " ".join(got["warnings"]))
                self.assertEqual((got["status"], got["event_count"]), ("interrupted", 3))
                self.assertEqual([(s["name"], s["status"]) for s in got["steps"]],
                                 [("one", "done"), ("two", "done")])
                self.assertTrue(got["auto_resume_allowed"])

    def test_terminated_garbage_final_line_is_torn(self) -> None:
        self.build()
        with self.path().open("ab") as handle:
            handle.write(b"\x00\x00{garbage\n")
        got = self.reduce(current_boot_id="old")
        self.assertEqual((got["torn_tail"], got["status"], got["event_count"]), (True, "running", 3))

    def test_append_after_torn_tail_stays_clean(self) -> None:
        for fragment in (b'{"schema":1,"event":"st', b"{garbage\n"):
            dispatch_id = f"d{len(fragment)}"
            self.init(dispatch_id)
            self.add("step", dispatch_id, name="one", status="done")
            with self.path(dispatch_id).open("ab") as handle:
                handle.write(fragment)
            self.add("status", dispatch_id, status="interrupted", reason="reconcile")
            got = self.reduce(dispatch_id)
            self.assertEqual((got["status"], got["torn_tail"], got["event_count"]), ("interrupted", False, 3))
            self.assertEqual(got["interrupted_reason"], "reconcile")
            self.assertEqual([(s["name"], s["status"]) for s in got["steps"]], [("one", "done")])
            side = Path(f"{self.path(dispatch_id)}.torn")
            self.assertEqual(side.read_bytes().rstrip(b"\n"), fragment.rstrip(b"\n"))
            self.assertEqual(stat.S_IMODE(side.stat().st_mode), 0o600)
            self.assertIn("quarantined", " ".join(got["warnings"]))

    def test_torn_init_needs_attention_and_can_be_reinitialised(self) -> None:
        self.init()
        self.path().write_bytes(self.path().read_bytes()[:20])
        got = self.reduce()
        self.assertEqual((got["status"], got["torn_tail"]), ("needs-attention", True))
        self.init()
        self.assertEqual(self.reduce()["status"], "running")

    def assert_refused_untouched(self, event: str, dispatch_id: str = "d1", **fields: Any) -> None:
        path = self.path(dispatch_id)
        path.chmod(0o640)
        before = (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_mode)
        with self.assertRaises(wl.LedgerError):
            self.add(event, dispatch_id, **fields)
        self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_mode), before)
        self.assertFalse(Path(f"{path}.torn").exists())

    def test_refused_init_leaves_torn_entry_untouched(self) -> None:
        self.init()
        with self.path().open("ab") as handle:
            handle.write(b'{"schema":1,"event":"st')
        self.assert_refused_untouched("init", lane="l", role="r", task="t")

    def test_refused_event_leaves_torn_only_file_untouched(self) -> None:
        self.init()
        for fragment in (b'{"schema":1,', b"{garbage\n"):
            self.path().write_bytes(fragment)
            for event, fields in (("heartbeat", {}), ("status", {"status": "done"}),
                                  ("step", {"name": "s", "status": "done"})):
                with self.subTest(event=event, fragment=fragment):
                    self.assert_refused_untouched(event, **fields)

    def assert_fails_closed(self, line_number: int) -> dict:
        got = self.reduce(current_boot_id="new")
        self.assertEqual(got["status"], "needs-attention")
        self.assertFalse(got["auto_resume_allowed"])
        self.assertTrue(any(w.startswith(f"line {line_number}:") for w in got["warnings"]), got["warnings"])
        return got

    def test_mid_file_corruption_fails_closed(self) -> None:
        self.build()
        original = self.lines()
        valid = json.loads(original[1])
        cases = {
            "bad json": b"{not json\n",
            "blank": b"\n",
            "not object": b"[1]\n",
            "bad schema": json.dumps({**valid, "schema": 2}).encode() + b"\n",
            "bad status": json.dumps({**valid, "status": "maybe"}).encode() + b"\n",
            "bad time": json.dumps({**valid, "at": "yesterday"}).encode() + b"\n",
            "unhashable event": json.dumps({**valid, "event": []}).encode() + b"\n",
            "missing field": json.dumps({k: v for k, v in valid.items() if k != "boot_id"}).encode() + b"\n",
            "duplicate init": original[0],
        }
        for name, bad in cases.items():
            with self.subTest(name):
                self.path().write_bytes(original[0] + bad + original[2])
                got = self.assert_fails_closed(2)
                self.assertFalse(got["torn_tail"])
        self.add("status", status="done")
        self.assert_fails_closed(2)

    def test_complete_final_line_with_bad_schema_fails_closed(self) -> None:
        self.build()
        with self.path().open("ab") as handle:
            handle.write(b'{"schema":1}\n')
        self.assertFalse(self.assert_fails_closed(4)["torn_tail"])

    def test_missing_or_foreign_init_fails_closed(self) -> None:
        self.build()
        original = self.lines()
        self.path().write_bytes(b"".join(original[1:]))
        self.assert_fails_closed(1)
        self.path("other").write_bytes(original[0])
        self.assertEqual(self.reduce("other")["status"], "needs-attention")
        self.path("empty").touch()
        self.assertIn("no valid init event", self.reduce("empty")["warnings"])


class ConcurrencyTest(LedgerCase):
    def test_concurrent_appends(self) -> None:
        self.init()
        code = ("import sys; sys.path.insert(0, sys.argv[1]); import work_ledger as wl\n"
                "for i in range(40):\n"
                "    wl.append_event('d1', 'step', delegation_dir=sys.argv[2], "
                "name=f'{sys.argv[3]}-{i}', status='done', artifact=sys.argv[3] * 20000)\n")
        procs = [subprocess.Popen([sys.executable, "-c", code, str(LIB), str(self.root), str(n)])
                 for n in range(8)]
        for proc in procs:
            self.assertEqual(proc.wait(timeout=90), 0)
        for line in self.lines():
            self.assertTrue(line.endswith(b"\n"))
            self.assertIsNone(wl.validate_record(json.loads(line)))
        got = self.reduce()
        self.assertEqual((got["event_count"], len(got["steps"]), got["warnings"]), (321, 320, []))
        self.assertFalse(Path(f"{self.path()}.torn").exists())


class CliTest(LedgerCase):
    def run_cli(self, *args: str, rc: int = 0, env: dict[str, str] | None = None):
        result = subprocess.run([str(CLI), *args], capture_output=True, text=True, timeout=60,
                                env={**os.environ, "AQ_USAGE_TELEMETRY": "0", **(env or {})})
        self.assertEqual(result.returncode, rc, f"{args}: {result.stdout}{result.stderr}")
        return result

    def cli(self, command: str, *args: str, **kwargs):
        return self.run_cli(command, "--delegation-dir", str(self.root), *args, **kwargs)

    def test_executable(self) -> None:
        self.assertTrue(os.access(CLI, os.X_OK))

    def test_end_to_end(self) -> None:
        self.cli("init", "--id", "c1", "--lane", "claude", "--role", "reviewer", "--task", "review",
                 "--model", "m", "--parent", "p", "--brief-path", "b", "--worktree", "w", "--branch", "br",
                 "--pr", "12", "--findings-path", "f", "--resume-policy", "auto", "--status", "queued")
        self.cli("status", "--id", "c1", "--status", "running", "--reason", "start")
        self.cli("step", "--id", "c1", "--name", "read", "--status", "done", "--artifact", "out.md")
        self.cli("heartbeat", "--id", "c1", "--detail", "alive")
        shown = json.loads(self.cli("show", "c1", "--json").stdout)
        self.assertEqual((shown["status"], shown["pr"], shown["event_count"], shown["resume_policy"]),
                         ("running", 12, 4, "auto"))
        self.assertEqual(shown["steps"][0]["artifact"], "out.md")
        self.assertIn("status: running", self.cli("show", "c1").stdout)
        listed = json.loads(self.cli("list", "--unfinished", "--json").stdout)
        self.assertEqual([e["id"] for e in listed], ["c1"])
        self.assertTrue(json.loads(self.cli("check", "--json").stdout)["ok"])
        self.cli("status", "--id", "c1", "--status", "done")
        self.assertEqual(json.loads(self.cli("list", "--unfinished", "--json").stdout), [])
        self.assertEqual(len(json.loads(self.cli("list", "--json").stdout)), 1)
        self.assertIn("c1  done", self.cli("list").stdout)

    def test_global_delegation_dir_flag(self) -> None:
        base = ("--delegation-dir", str(self.root))
        self.run_cli(*base, "init", "--id", "g", "--lane", "l", "--role", "r", "--task", "t")
        self.assertEqual(json.loads(self.run_cli(*base, "show", "g", "--json").stdout)["id"], "g")

    def test_errors(self) -> None:
        for bad in ("../escape", "a/b"):
            result = self.cli("init", "--id", bad, "--lane", "l", "--role", "r", "--task", "t", rc=2)
            self.assertIn("invalid dispatch id", result.stderr)
        self.cli("show", "missing", rc=2)
        self.cli("heartbeat", "--id", "missing", rc=2)
        self.cli("status", "--id", "x", "--status", "bogus", rc=2)
        self.assertFalse(self.root.exists())

    def test_check_empty(self) -> None:
        self.assertEqual(json.loads(self.cli("check", "--json").stdout)["checked"], 0)
        self.assertFalse(self.root.exists())
        (self.root / "ledger").mkdir(parents=True)
        self.cli("check")

    def test_invalid_window_rejected_without_ledger_dir(self) -> None:
        os.environ[wl.WINDOW_ENV] = "zero"
        with self.assertRaises(wl.LedgerError):
            wl.list_entries(self.root)
        for command in ("check", "list"):
            self.assertIn(wl.WINDOW_ENV, self.cli(command, rc=2).stderr)
        self.assertFalse(self.root.exists())

    def test_worker_pid(self) -> None:
        worker = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        self.addCleanup(worker.wait)
        self.addCleanup(worker.kill)
        ticks = wl.read_pid_start_ticks(worker.pid)
        self.assertIsNotNone(ticks)
        pid = ("--pid", str(worker.pid))
        self.cli("init", "--id", "p", "--lane", "l", "--role", "r", "--task", "t", *pid)
        self.cli("step", "--id", "p", "--name", "s", "--status", "done", *pid)
        self.cli("heartbeat", "--id", "p", *pid)
        self.cli("status", "--id", "p", "--status", "done", *pid)
        records = [json.loads(line) for line in self.lines("p")]
        self.assertEqual([(r["pid"], r["pid_start_ticks"]) for r in records], [(worker.pid, ticks)] * 4)
        before = self.path("p").read_bytes()
        for bad in ("0", "-1", "abc", "1.5", ""):
            with self.subTest(pid=bad):
                self.cli("heartbeat", "--id", "p", f"--pid={bad}", rc=2)
        self.assertEqual(self.path("p").read_bytes(), before)

    def test_check_stale(self) -> None:
        self.init("stale")
        record = json.loads(self.path("stale").read_bytes())
        record["at"] = (datetime.now(timezone.utc) - timedelta(seconds=300)).strftime(wl.TIME_FORMAT)
        self.path("stale").write_text(json.dumps(record) + "\n")
        self.cli("check", env={wl.WINDOW_ENV: "3600"})
        env = {wl.WINDOW_ENV: "60"}
        report = json.loads(self.cli("check", "--json", rc=1, env=env).stdout)
        self.assertEqual([(p["id"], p["stale_heartbeat"]) for p in report["problems"]], [("stale", True)])
        self.assertIn("WARN", self.cli("check", "--warn-only", env=env).stdout)
        self.cli("check", rc=2, env={wl.WINDOW_ENV: "zero"})

    def test_check_corrupt(self) -> None:
        self.init("bad")
        with self.path("bad").open("ab") as handle:
            handle.write(b"junk\n")
        self.cli("check")  # a torn tail alone is tolerated
        with self.path("bad").open("ab") as handle:
            handle.write(b"junk\n")
        self.assertIn("FAIL", self.cli("check", rc=1).stdout)
        self.assertFalse(json.loads(self.cli("check", "--json", "--warn-only").stdout)["ok"])


class Tier0CheckTest(LedgerCase):
    def check(self, rc: int = 0, env: dict[str, str] | None = None) -> str:
        result = subprocess.run(
            ["bash", str(TIER0_CHECK), "--pre-commit"], capture_output=True, text=True, timeout=60,
            env={**os.environ, "AQ_USAGE_TELEMETRY": "0", "AQ_DELEGATION_DIR": str(self.root), **(env or {})})
        self.assertEqual(result.returncode, rc, result.stdout + result.stderr)
        return result.stdout

    def test_executable(self) -> None:
        self.assertTrue(os.access(TIER0_CHECK, os.X_OK))

    def test_empty_and_valid_pass(self) -> None:
        self.assertEqual(self.check().strip(), "[tier0.d/check-work-ledger] PASS (0 entries)")
        self.assertFalse(self.root.exists())
        self.init()
        self.assertIn("PASS (1 entries)", self.check())

    def test_stale_heartbeat_warns_and_passes(self) -> None:
        self.init("old")
        record = json.loads(self.path("old").read_bytes())
        record["at"] = (datetime.now(timezone.utc) - timedelta(seconds=300)).strftime(wl.TIME_FORMAT)
        self.path("old").write_text(json.dumps(record) + "\n")
        out = self.check(env={wl.WINDOW_ENV: "60"})
        self.assertIn("WARN: stale heartbeat: old", out)
        self.assertIn("PASS (1 entries)", out)

    def test_mid_file_corruption_fails(self) -> None:
        self.init("bad")
        original = self.path("bad").read_bytes()
        self.path("bad").write_bytes(original + b"junk\n" + original)
        out = self.check(rc=1)
        self.assertIn("FAIL: needs-attention: bad", out)
        self.assertNotIn("PASS", out)

    def test_unrunnable_check_fails(self) -> None:
        self.assertIn("FAIL", self.check(rc=1, env={wl.WINDOW_ENV: "zero"}))


class WrapperLedgerTest(unittest.TestCase):
    """Real wrappers, stub providers: every dispatch writes one entry that ends done or failed."""

    PROMPT = "-dash $(touch PWNED) `touch PWNED2` \"q\" 'q'\nsecond line " + "x" * 200

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="aq-ledger-wrapper-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        shutil.copytree(REPO / "scripts/ai", self.root / "scripts/ai", symlinks=True,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        (self.root / "config").mkdir()
        shutil.copy2(REPO / "config/remote-lane-egress.json", self.root / "config")
        self.delegation = self.root / ".agents/delegation"
        (self.delegation / "outputs").mkdir(parents=True)
        self.stub = self.script("stub-provider", 'printf "stub-ok\\n"\nexit "${STUB_RC:-0}"\n')
        # delegate-to-local has no provider binary: intercept its preflight and dispatcher.
        self.script("bin/python3", '''case "$1" in
  */local_preflight.py) exit 0 ;;
  */dispatch.py)
    while [ "$#" -gt 0 ]; do
      case "$1" in --task-id) task="$2" ;; --output) output="$2" ;; esac
      shift
    done
    printf "stub-ok\\n" > "$output"
    printf '{"id":"%s","status":"done"}\\n' "$task" >> "$AQ_DELEGATION_DIR/registry.jsonl"
    exit "${STUB_RC:-0}" ;;
esac
exec "$REAL_PYTHON" "$@"
''')
        drop = ("GIT_", "DELEGATE_", "AQ_")
        self.env = {
            **{k: v for k, v in os.environ.items() if not k.startswith(drop)},
            "PATH": f"{self.root / 'bin'}:{os.environ['PATH']}", "REAL_PYTHON": sys.executable,
            "HOME": str(self.root), "AQ_DELEGATION_DIR": str(self.delegation), "AQ_ALLOW_VOLATILE_DIR": "1",
            "AQ_USAGE_TELEMETRY": "0", "HYBRID_COORDINATOR_URL": "http://127.0.0.1:9", "A2A_BUDGET_BYPASS": "1",
            "DELEGATE_CODEX_IGNORE_COOLDOWN": "1", "CODEX_BIN": str(self.stub), "GEMINI_BIN": str(self.stub),
            "CLAUDE_BIN": str(self.stub),
        }

    def script(self, name: str, body: str) -> Path:
        path = self.root / name
        path.parent.mkdir(exist_ok=True)
        path.write_text("#!/bin/sh\n" + body)
        path.chmod(0o755)
        return path

    ARGS: dict[str, tuple[str, ...]] = {
        "codex": ("--shared",), "gemini": (), "claude": (),
        "local": ("--mode", "hybrid", "--no-consult", "--ignore-power-gate"),
    }

    def dispatch(self, lane: str, *extra: str, **env: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(self.root / f"scripts/ai/delegate-to-{lane}"), *self.ARGS[lane], *extra],
            cwd=self.root, env={**self.env, **env}, capture_output=True, text=True, timeout=60)

    def entry(self) -> dict[str, Any]:
        """Wait for the single entry to end and for background workers to finish writing."""
        deadline = time.monotonic() + 60
        entries: list[dict[str, Any]] = []
        registry = self.delegation / "registry.jsonl"
        while time.monotonic() < deadline:
            entries = wl.list_entries(self.delegation)
            rows = [json.loads(x) for x in registry.read_text().splitlines()] if registry.exists() else []
            if (entries and entries[0]["status"] in wl.TERMINAL_STATUSES
                    and rows and rows[-1]["status"] != "running"):
                break
            time.sleep(0.1)
        self.assertEqual(len(entries), 1, entries)
        return entries[0]

    def assert_lifecycle(self, lane: str, wait: bool, rc: int) -> None:
        shutil.rmtree(self.delegation / "ledger", ignore_errors=True)
        (self.delegation / "registry.jsonl").unlink(missing_ok=True)
        extra = ("--prompt", self.PROMPT, *(("--wait",) if wait else ()))
        result = self.dispatch(lane, *extra, STUB_RC=str(rc))
        if rc == 0 or not wait:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        got = self.entry()
        expected = "done" if rc == 0 else "failed"
        self.assertEqual((got["status"], got["lane"], got["resume_policy"], got["warnings"]),
                         (expected, lane, "confirm", []), result.stdout + result.stderr)
        self.assertTrue(got["role"])
        self.assertTrue(got["task"].startswith("-dash $(touch PWNED)"), got["task"])
        self.assertNotIn("\n", got["task"])
        self.assertLessEqual(len(got["task"]), 120)
        records = [json.loads(x) for x in Path(got["path"]).read_bytes().splitlines()]
        self.assertEqual((records[0]["event"], records[0]["status"]), ("init", "running"))
        self.assertEqual([r["status"] for r in records if r["event"] == "status"], [expected])
        self.assertEqual(list(self.root.rglob("PWNED*")), [])

    def test_blocking_and_background_lifecycles(self) -> None:
        for lane in self.ARGS:
            for wait in (True, False):
                for rc in (0, 3):
                    with self.subTest(lane=lane, wait=wait, rc=rc):
                        self.assert_lifecycle(lane, wait, rc)

    def test_brief_path_worktree_and_handback(self) -> None:
        git_env = {k: v for k, v in self.env.items() if not k.startswith("GIT_")}
        for args in (("init", "-q"), ("add", "scripts", "config"),
                     ("-c", "user.name=f", "-c", "user.email=f@example.invalid", "commit", "-qm", "base")):
            subprocess.run(["git", "-C", str(self.root), *args], env=git_env, check=True, capture_output=True)
        brief = self.root / "brief.md"
        brief.write_text("do the slice\n")
        self.ARGS = {**type(self).ARGS, "codex": ()}
        identity = {"GIT_AUTHOR_NAME": "f", "GIT_AUTHOR_EMAIL": "f@example.invalid",
                    "GIT_COMMITTER_NAME": "f", "GIT_COMMITTER_EMAIL": "f@example.invalid"}
        result = self.dispatch("codex", "--prompt-file", str(brief), **identity)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        got = self.entry()
        self.assertEqual((got["status"], got["brief_path"], got["branch"]),
                         ("done", str(brief), f"delegate/{got['id']}"), got)
        self.assertEqual(got["worktree"], str(self.delegation / "worktrees" / got["id"]))

        # A failed handback overrides the provider's success.
        shutil.rmtree(self.delegation / "ledger")
        (self.delegation / "registry.jsonl").unlink()
        self.script(".git/hooks/pre-commit", "exit 44\n")
        self.stub = self.script("stub-provider", 'printf "change\\n" > child.txt\n')
        self.dispatch("codex", "--prompt-file", str(brief), "--wait", **identity)
        got = self.entry()
        self.assertEqual((got["status"], got["status_reason"]), ("failed", "worktree_handback_failed"))

    def test_ledger_failure_never_breaks_a_delegation(self) -> None:
        (self.root / "scripts/ai/aq-ledger").write_text("raise SystemExit(2)\n")
        for lane in self.ARGS:
            for wait in (True, False):
                with self.subTest(lane=lane, wait=wait):
                    registry = self.delegation / "registry.jsonl"
                    registry.unlink(missing_ok=True)
                    result = self.dispatch(lane, "--prompt", "hi", *(("--wait",) if wait else ()))
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    deadline = time.monotonic() + 60
                    status = "running"
                    while status == "running" and time.monotonic() < deadline:
                        time.sleep(0.1)
                        lines = registry.read_text().splitlines() if registry.exists() else []
                        if lines:
                            status = json.loads(lines[-1])["status"]
                    self.assertEqual(status, "done")
        self.assertFalse((self.delegation / "ledger").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
