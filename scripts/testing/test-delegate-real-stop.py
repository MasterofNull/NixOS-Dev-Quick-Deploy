#!/usr/bin/env python3
"""`aq-delegation-registry stop` and the console /kill really stop a task, safely.

Uses a fixture registry and throwaway child process groups only; never touches real tasks.
"""
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CLI = REPO / "scripts/ai/aq-delegation-registry"
CONSOLE = REPO / "scripts/ai/aq-subagent-interactive"
sys.path.insert(0, str(REPO / "scripts/ai/lib"))
import task_registry as tr  # noqa: E402

# Parent starts a child in the same (new) group, then both sleep.
TREE = ("import os,signal,subprocess,sys,time\n"
        "{ign}"
        "c=subprocess.Popen([sys.executable,'-c','import signal,time\\n{ign_c}print(1,flush=True)\\ntime.sleep(60)'],stdout=subprocess.PIPE)\n"
        "c.stdout.readline()\nprint(c.pid,flush=True)\ntime.sleep(60)\n")


def spawn(ignore_term=False):
    ign = "signal.signal(signal.SIGTERM,signal.SIG_IGN)\n" if ignore_term else ""
    ign_c = "signal.signal(signal.SIGTERM,signal.SIG_IGN)\\n" if ignore_term else ""
    p = subprocess.Popen([sys.executable, "-c", TREE.format(ign=ign, ign_c=ign_c)],
                         start_new_session=True, stdout=subprocess.PIPE, text=True)
    child = int(p.stdout.readline())
    return p, child


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    try:
        with open(f"/proc/{pid}/stat") as fh:
            return fh.read().rsplit(")", 1)[1].split()[0] != "Z"
    except OSError:
        return False


class Base(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.reg = Path(self.d.name) / "registry.jsonl"
        self.procs = []

    def tearDown(self):
        for p in self.procs:
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except OSError:
                pass
            p.wait()
        self.d.cleanup()

    def row(self, tid, proc=None, **kw):
        r = {"id": tid, "status": "running", "agent": "gemini", "pid": proc.pid if proc else None}
        if proc is not None:
            r["pid_start_time"] = tr.proc_start_time(proc.pid)
        r.update(kw)
        with open(self.reg, "a") as fh:
            fh.write(json.dumps(r) + "\n")

    def start(self, **kw):
        p, child = spawn(**kw)
        self.procs.append(p)
        return p, child

    def stop(self, tid, *extra):
        return subprocess.run([sys.executable, str(CLI), "--registry", str(self.reg), "stop", tid, *extra],
                              capture_output=True, text=True)

    def get(self, tid):
        for line in self.reg.read_text().splitlines():
            e = json.loads(line)
            if e["id"] == tid:
                return e


class RealStop(Base):
    def test_running_group_stopped_row_updated(self):
        p, child = self.start()
        self.row("t1", p)
        r = self.stop("t1", "--reason", "hung 96 min", "--by", "owner", "--grace", "5")
        self.assertEqual(r.returncode, 0, r.stderr)
        p.wait(timeout=5)
        time.sleep(0.2)
        self.assertFalse(alive(child), "child in the task's group must be gone")
        e = self.get("t1")
        self.assertEqual(e["status"], "cancelled")
        self.assertEqual((e["stopped_by"], e["stop_reason"]), ("owner", "hung 96 min"))
        self.assertIn("stopped_at", e)
        self.assertIn("stopped (SIGTERM to process group", r.stdout)

    def test_term_ignorer_gets_sigkill(self):
        p, child = self.start(ignore_term=True)
        self.row("t2", p)
        r = self.stop("t2", "--grace", "0.5")
        self.assertEqual(r.returncode, 0, r.stderr)
        p.wait(timeout=5)
        self.assertEqual(p.returncode, -signal.SIGKILL)
        time.sleep(0.2)
        self.assertFalse(alive(child))
        self.assertIn("SIGKILL", self.get("t2")["stop_detail"])

    def test_reused_pid_refused(self):
        p, child = self.start()
        self.row("t3", p)
        # Row recorded a different start time: the pid now belongs to something else.
        lines = [json.loads(x) for x in self.reg.read_text().splitlines()]
        lines[0]["pid_start_time"] += 12345
        self.reg.write_text("".join(json.dumps(x) + "\n" for x in lines))
        r = self.stop("t3", "--grace", "0.2")
        self.assertEqual(r.returncode, 2)
        self.assertIn("REFUSED", r.stderr)
        self.assertIn("reused", r.stderr)
        self.assertTrue(alive(p.pid) and alive(child), "must not signal an unproven process")
        self.assertEqual(self.get("t3")["status"], "running")

    def test_unmarked_row_needs_task_id_in_cmdline(self):
        p, _ = self.start()
        self.row("old-task-9", p)
        e = [json.loads(x) for x in self.reg.read_text().splitlines()]
        del e[0]["pid_start_time"]
        self.reg.write_text(json.dumps(e[0]) + "\n")
        r = self.stop("old-task-9", "--grace", "0.2")
        self.assertEqual(r.returncode, 2)
        self.assertIn("cannot prove", r.stderr)
        self.assertTrue(alive(p.pid))

    def test_terminal_row_is_noop(self):
        p, child = self.start()
        self.row("t4", p, status="done")
        r = self.stop("t4")
        self.assertEqual(r.returncode, 0)
        self.assertIn("already done", r.stdout)
        self.assertTrue(alive(p.pid) and alive(child))
        self.assertEqual(self.get("t4")["status"], "done")

    def test_unknown_task_and_gone_process(self):
        self.row("t5", None)
        self.assertEqual(self.stop("nope").returncode, 3)
        self.assertEqual(self.stop("t5").returncode, 2)  # no pid recorded: refuse, do not guess
        p, _ = self.start()
        self.row("t6", p)
        os.killpg(p.pid, signal.SIGKILL)
        p.wait()
        time.sleep(0.2)
        r = self.stop("t6")
        self.assertEqual(r.returncode, 0)
        self.assertIn("already gone", r.stdout)
        self.assertEqual(self.get("t6")["status"], "cancelled")

    def test_never_signals_callers_group(self):
        # Task process lives in OUR process group: only the pid is signalled, never killpg(own group).
        p = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(60)", "t7"])
        self.procs.append(type("P", (), {"pid": p.pid, "wait": lambda s: p.wait()})())
        self.row("t7", p)
        calls = []
        real = tr.os.killpg
        tr.os.killpg = lambda *a: calls.append(a)
        try:
            reg = tr.TaskRegistry(self.reg.parent, repo_root=self.reg.parent)
            rc = reg.cmd_cancel("t7", grace_s=2)
        finally:
            tr.os.killpg = real
        self.assertEqual(rc, 0)
        self.assertEqual(calls, [])
        p.wait(timeout=5)


class LaunchMarker(Base):
    def test_registry_update_pid_records_start_time(self):
        self.row("m1", None)
        p, _ = self.start()
        subprocess.run([sys.executable, str(REPO / "scripts/ai/lib/registry-update.py"), "set",
                        str(self.reg), "m1", "pid", str(p.pid)], check=True)
        e = self.get("m1")
        self.assertEqual((e["pid"], e["pid_start_time"]), (p.pid, tr.proc_start_time(p.pid)))

    def test_background_wrappers_launch_in_own_session(self):
        for lane in ("gemini", "codex", "claude"):
            src = (REPO / f"scripts/ai/delegate-to-{lane}").read_text()
            self.assertIn('setsid nohup "${AQ_INHIBIT_PREFIX[@]}" bash', src, lane)
        self.assertIn('registry-update.py" set "$REGISTRY" "$id" pid',
                      (REPO / "scripts/ai/delegate-to-claude").read_text())
        self.assertIn("setsid", (REPO / "scripts/ai/delegate-to-local").read_text())


class ConsoleKill(Base):
    def _console(self):
        import importlib.machinery
        import importlib.util
        try:
            loader = importlib.machinery.SourceFileLoader("aq_sub_inter", str(CONSOLE))
            spec = importlib.util.spec_from_loader("aq_sub_inter", loader)
            mod = importlib.util.module_from_spec(spec)
            loader.exec_module(mod)
            return mod
        except ImportError as exc:
            self.skipTest(f"console deps missing: {exc}")

    def test_kill_calls_real_stop_and_prints_truth(self):
        mod = self._console()
        p, child = self.start()
        self.row("k1", p)
        out = []
        mod.REGISTRY_FILE = self.reg
        mod.console.print = lambda *a, **k: out.append(" ".join(str(x) for x in a))
        mod.InteractiveSubagentConsole().stop_task("k1")
        p.wait(timeout=15)
        self.assertFalse(alive(child))
        self.assertIn("stopped (SIGTERM", out[-1])
        # Failure is stated, not hidden.
        out.clear()
        mod.InteractiveSubagentConsole().stop_task("missing")
        self.assertIn("Stop NOT completed", out[-1])
        self.assertIn("exit 3", out[-1])

    def test_cancel_stays_queue_only(self):
        mod = self._console()
        src = CONSOLE.read_text()
        self.assertIn('text.lstrip("/") == "kill"', src)
        self.assertIn("cancel=True", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
