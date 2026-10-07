#!/usr/bin/env python3
"""A hung delegate (and its descendant) is killed by the dispatcher and the row is not left running."""
import importlib.util
import os
import tempfile
import time
import unittest
from pathlib import Path

_INCIDENTS_TMP = tempfile.TemporaryDirectory(prefix="prsi-incidents-test-")
os.environ["PRSI_INCIDENTS_FILE"] = str(Path(_INCIDENTS_TMP.name) / "rsi-incidents.json")

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("prsi_hung", ROOT / "scripts/automation/prsi-orchestrator.py")
prsi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prsi)

FAKE = """#!/usr/bin/env python3
import os, subprocess, sys, time
# Descendant that ignores SIGTERM-free exit: sleeps far longer than any test timeout.
child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(300)"])
open(os.environ["FAKE_PIDFILE"], "w").write(str(child.pid))
time.sleep(300)
"""


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    # A killed-but-unreaped child shows as zombie; treat that as dead.
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] != "Z"
    except OSError:
        return False


class HungDelegate(unittest.TestCase):
    def test_timeout_kills_process_group_and_row_lands_stalled(self):
        with tempfile.TemporaryDirectory() as t:
            fake = Path(t) / "delegate-to-local"
            fake.write_text(FAKE)
            fake.chmod(0o755)
            pidfile = Path(t) / "child.pid"
            os.environ["FAKE_PIDFILE"] = str(pidfile)
            prsi.AI_SCRIPT_DIR = Path(t)
            prsi._RSI_DELEGATE_GRACE_S = 0.5
            row = {"id": "r1", "raw_action": {"incident_id": "abc123", "source": "rsi-incidents.json"}}
            started = time.monotonic()
            result, receipt = prsi._run_rsi_delegate(row, timeout_seconds=1, apply=False, lane="local")
            elapsed = time.monotonic() - started
            self.assertEqual(result, "rsi_stalled")
            self.assertEqual(receipt["reason"], "delegate_timeout")
            self.assertLess(elapsed, 20)
            child_pid = int(pidfile.read_text())
            deadline = time.monotonic() + 5
            while alive(child_pid) and time.monotonic() < deadline:
                time.sleep(0.1)
            self.assertFalse(alive(child_pid), "descendant of the hung delegate was leaked")

    def test_stale_running_rows_are_released(self):
        old = "2020-01-01T00:00:00Z"
        queue = {"actions": [{"id": "r", "status": "rsi_running", "execution": {"last_run_at": old},
                              "raw_action": {"source": "rsi-incidents.json", "reason": "rsi-incident-open"}}]}
        self.assertEqual(prsi._reconcile_stale_rsi_running(queue, 600), 1)
        row = queue["actions"][0]
        self.assertEqual((row["status"], row["execution"]["receipt"]["reason"]), ("rsi_failed", "stale_running"))


if __name__ == "__main__":
    unittest.main()
