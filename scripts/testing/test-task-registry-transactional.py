#!/run/current-system/sw/bin/python3
"""Transactional-write, CAS and cancel-escalation tests for scripts/ai/lib/task_registry.py."""
import importlib.util
import json
import multiprocessing
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts/ai/lib"))
_spec = importlib.util.spec_from_file_location("task_registry", REPO / "scripts/ai/lib/task_registry.py")
tr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tr)


def _mk(d: Path):
    return tr.TaskRegistry(d / "delegation", repo_root=d)


def _worker(args):
    d, wid, n = args
    r = _mk(Path(d))
    for i in range(n):
        r._locked_append(r.registry_file, json.dumps({"id": f"w{wid}-{i}", "status": "running"}))
        r._update_registry(f"w{wid}-{i}", {"touched": True})


class TransactionalWrites(unittest.TestCase):
    def test_concurrent_writers_no_lost_rows(self):
        with tempfile.TemporaryDirectory() as d:
            _mk(Path(d)).delegation_dir.mkdir(parents=True)
            with multiprocessing.Pool(4) as pool:
                pool.map(_worker, [(d, w, 15) for w in range(4)])
            rows = _mk(Path(d))._read_registry()
            self.assertEqual(len(rows), 60)
            self.assertEqual(len({r["id"] for r in rows}), 60)
            self.assertTrue(all(r.get("touched") for r in rows))

    def test_reader_never_sees_truncated_file(self):
        with tempfile.TemporaryDirectory() as d:
            r = _mk(Path(d))
            base = [json.dumps({"id": f"t{i}", "status": "running", "pad": "x" * 200}) for i in range(200)]
            r._locked_rewrite(r.registry_file, base)
            stop = threading.Event()
            bad = []

            def reader():
                while not stop.is_set():
                    try:
                        txt = r.registry_file.read_text()
                    except FileNotFoundError:
                        bad.append("missing")
                        continue
                    lines = [x for x in txt.split("\n") if x]
                    if len(lines) != 200 or not txt.endswith("\n"):
                        bad.append(len(lines))

            t = threading.Thread(target=reader)
            t.start()
            for _ in range(150):
                r._locked_rewrite(r.registry_file, base)
            stop.set()
            t.join()
            self.assertEqual(bad, [])

    def test_temp_symlink_not_followed(self):
        with tempfile.TemporaryDirectory() as d:
            r = _mk(Path(d))
            victim = Path(d) / "victim.txt"
            victim.write_text("keep")
            r.delegation_dir.mkdir(parents=True)
            # legacy fixed temp name planted as a symlink must be ignored entirely
            (r.delegation_dir / "registry.jsonl.tmp").symlink_to(victim)
            r.begin("sym-t1", "claude", "implementer", "writer", "code_generation", "file_output")
            self.assertEqual(victim.read_text(), "keep")
            # a symlink planted at the chosen temp path fails closed (O_EXCL|O_NOFOLLOW)
            target = r.delegation_dir / "x.json"
            orig = tr.os.open

            def planted(path, flags, *a, **k):
                if str(path).endswith(".tmp") and flags & os.O_EXCL:
                    os.symlink(victim, path)
                return orig(path, flags, *a, **k)

            tr.os.open = planted
            try:
                with self.assertRaises(OSError):
                    tr._atomic_write_bytes(target, b"pwned")
            finally:
                tr.os.open = orig
            self.assertEqual(victim.read_text(), "keep")


class CAS(unittest.TestCase):
    def setUp(self):
        self._d = tempfile.TemporaryDirectory()
        self.r = _mk(Path(self._d.name))
        self.r.begin("c1", "claude", "implementer", "writer", "code_generation", "file_output")

    def tearDown(self):
        self._d.cleanup()

    def test_missing_revision_rejected(self):
        with self.assertRaises(TypeError):
            self.r.transition_m2a("c1", "cancelled")
        with self.assertRaises(TypeError):
            self.r.attach_process("c1", 1234, 1)
        with self.assertRaisesRegex(tr.RegistryError, "expected_revision_required"):
            self.r.transition_m2a("c1", "cancelled", expected_revision=None)
        with self.assertRaisesRegex(tr.RegistryError, "expected_revision_required"):
            self.r.attach_process("c1", 1234, 1, None)

    def test_stale_rejected_and_fresh_accepted(self):
        rev = self.r.show_m2a("c1")["record_revision"]
        with self.assertRaisesRegex(tr.RegistryError, "stale_revision"):
            self.r.transition_m2a("c1", "cancelled", expected_revision=rev + 5)
        rec = self.r.transition_m2a("c1", "cancelled", expected_revision=rev)
        self.assertEqual(rec["record_revision"], rev + 1)
        with self.assertRaisesRegex(tr.RegistryError, "stale_revision"):
            self.r.transition_m2a("c1", "cancelled", expected_revision=rev)


class CancelEscalation(unittest.TestCase):
    def _reg_with_proc(self, d, script):
        r = _mk(Path(d))
        proc = subprocess.Popen(
            [sys.executable, "-c", script], start_new_session=True,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
        proc.stdout.readline()  # handler installed
        r._locked_append(r.registry_file, json.dumps({"id": "k1", "status": "running", "pid": proc.pid}))
        return r, proc

    def test_term_ignorer_gets_killed_then_cancelled(self):
        script = ("import signal,time\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
                  "print('ready',flush=True)\ntime.sleep(60)")
        with tempfile.TemporaryDirectory() as d:
            r, proc = self._reg_with_proc(d, script)
            seen = []
            orig = r._update_registry

            def spy(tid, upd):
                seen.append((upd, proc.poll()))
                return orig(tid, upd)

            r._update_registry = spy
            t0 = time.monotonic()
            self.assertEqual(r.cmd_cancel("k1", grace_s=0.5), 0)
            self.assertGreaterEqual(time.monotonic() - t0, 0.5)  # waited the grace
            proc.wait(timeout=5)
            self.assertEqual(proc.returncode, -signal.SIGKILL)
            self.assertEqual(r.get("k1")["status"], "cancelled")
            cancelled = [p for u, p in seen if u.get("status") == "cancelled"]
            self.assertTrue(cancelled and all(p is not None for p in cancelled))

    def test_cooperative_process_exits_on_term(self):
        script = "import time\nprint('ready',flush=True)\ntime.sleep(60)"
        with tempfile.TemporaryDirectory() as d:
            r, proc = self._reg_with_proc(d, script)
            t0 = time.monotonic()
            self.assertEqual(r.cmd_cancel("k1", grace_s=10), 0)
            self.assertLess(time.monotonic() - t0, 5)
            proc.wait(timeout=5)
            self.assertEqual(proc.returncode, -signal.SIGTERM)
            self.assertEqual(r.get("k1")["status"], "cancelled")

    def test_survivor_records_cancel_failed(self):
        with tempfile.TemporaryDirectory() as d:
            r = _mk(Path(d))
            r._locked_append(r.registry_file, json.dumps({"id": "k2", "status": "running", "pid": 424242}))
            r._group_alive = lambda pid, pgid: True
            orig = tr.os.kill
            tr.os.kill = lambda *a, **k: None
            try:
                rc = r.cmd_cancel("k2", grace_s=0.1)
            finally:
                tr.os.kill = orig
            self.assertEqual(rc, 1)
            e = r.get("k2")
            self.assertEqual(e["status"], "cancel-failed")
            self.assertIn("survived", e["cancel_detail"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
