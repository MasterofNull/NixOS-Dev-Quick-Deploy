#!/usr/bin/env python3
"""Mobility/sleep resilience tests: keep-awake decision, resume health gate, connection retry.

No real suspend, inhibitor, or dispatch. Stub HTTP servers on ephemeral ports.
"""
import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ai" / "lib"))
import conn_retry  # noqa: E402

_loader = importlib.machinery.SourceFileLoader("aq_keep_awake", str(ROOT / "scripts/ai/aq-keep-awake"))
_spec = importlib.util.spec_from_loader("aq_keep_awake", _loader)
ka = importlib.util.module_from_spec(_spec)
_loader.exec_module(ka)

GATE = ROOT / "scripts" / "ai" / "aq-llama-resume-gate"


def D(on=True, tasks=True, ac=True, bat=None, thr=40, temp=50.0, lim=90.0, lid=False, held=False):
    return ka.decide(on, tasks, ac, bat, thr, temp, lim, lid, held)


class KeepAwakeDecision(unittest.TestCase):
    def test_matrix(self):
        cases = [
            (dict(on=False), False, "mode off"),
            (dict(tasks=False), False, "no delegated"),
            (dict(ac=True), True, "guards ok"),
            (dict(ac=False, bat=39), False, "power guard"),
            (dict(ac=False, bat=40), True, "guards ok"),
            (dict(ac=False, bat=80), True, "guards ok"),
            (dict(ac=True, bat=5), True, "guards ok"),
            (dict(ac=None, bat=None), True, "guards ok"),
            (dict(ac=True, temp=90.0), True, "guards ok"),
            (dict(ac=True, temp=90.5), False, "thermal guard"),
            (dict(ac=False, bat=10, temp=95), False, "power guard"),
            (dict(ac=True, temp=None), True, "guards ok"),
        ]
        for kw, hold, reason in cases:
            d = D(**kw)
            self.assertEqual(d["hold"], hold, kw)
            self.assertIn(reason, d["reason"], kw)

    def test_suspend_on_release_with_lid_closed(self):
        # guard trips while holding and lid closed -> suspend
        d = D(ac=False, bat=20, lid=True, held=True)
        self.assertFalse(d["hold"]); self.assertTrue(d["suspend"])
        d = D(ac=True, temp=95, lid=True, held=True)
        self.assertTrue(d["suspend"])
        # task finished while lid closed and lock held -> suspend
        self.assertTrue(D(tasks=False, lid=True, held=True)["suspend"])
        # user turned keep-awake off while lid closed and lock held -> suspend
        self.assertTrue(D(on=False, lid=True, held=True)["suspend"])

    def test_no_suspend_otherwise(self):
        self.assertFalse(D(ac=False, bat=20, lid=False, held=True)["suspend"])  # lid open
        self.assertFalse(D(ac=False, bat=20, lid=True, held=False)["suspend"])  # not holding
        self.assertFalse(D(lid=True, held=True)["suspend"])                     # still holding

    def test_state_roundtrip_default_off(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["AQ_KEEP_AWAKE_STATE"] = str(Path(d) / "a" / "k.json")
            try:
                self.assertEqual(ka.load_state()["mode"], "off")
                self.assertEqual(ka.main(["on", "--threshold", "55"]), 0)
                st = ka.load_state()
                self.assertEqual((st["mode"], st["threshold"]), ("on", 55))
                ka.main(["off"])
                self.assertEqual(ka.load_state()["mode"], "off")
            finally:
                del os.environ["AQ_KEEP_AWAKE_STATE"]


def serve(handler_cls):
    srv = HTTPServer(("127.0.0.1", 0), handler_cls)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}"


class Healthy(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _ok(self):
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.end_headers(); self.wfile.write(b'{"status":"ok","choices":[]}')
    def do_GET(self): self._ok()
    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0))); self._ok()


class Unhealthy(Healthy):
    def do_GET(self):
        self.send_response(503); self.end_headers()


class ResumeGate(unittest.TestCase):
    def run_gate(self, handler):
        srv, url = serve(handler)
        with tempfile.TemporaryDirectory() as d:
            marker = Path(d) / "restarted"
            env = {"PATH": os.environ["PATH"], "LLAMA_BASE_URL": url, "RESUME_WAIT_S": "2",
                   "RESUME_POLL_S": "0.5", "RESUME_RESTART_CMD": f"touch {marker}"}
            r = subprocess.run(["bash", str(GATE)], env=env, capture_output=True, text=True, timeout=60)
            srv.shutdown()
            return r, marker.exists()

    def test_healthy_no_restart(self):
        r, restarted = self.run_gate(Healthy)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(restarted)
        self.assertIn("no restart", r.stdout)

    def test_unhealthy_restarts(self):
        r, restarted = self.run_gate(Unhealthy)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(restarted)


class DropFirst(Healthy):
    posts = 0
    def do_POST(self):
        type(self).posts += 1
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if type(self).posts == 1:
            self.close_connection = True
            self.connection.close()  # no response: "Remote end closed connection"
            return
        self._ok()


def make_runner(url, out):
    def run():
        try:
            req = urllib.request.Request(url + "/v1/chat/completions", data=b"{}", method="POST")
            with urllib.request.urlopen(req, timeout=5) as r:
                Path(out).write_text("answer " + r.read().decode())
            return True
        except Exception as e:
            Path(out).write_text(f"Error: {e}")
            return False
    return run


class ConnectionRetry(unittest.TestCase):
    def test_retry_once_on_dropped_connection(self):
        DropFirst.posts = 0
        srv, url = serve(DropFirst)
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "o.txt"
            rec = []
            ok = conn_retry.run_with_connection_retry(make_runner(url, out), out, url, rec.append, 5, 0.2)
            srv.shutdown()
            self.assertTrue(ok)
            self.assertEqual(DropFirst.posts, 2)
            self.assertEqual(rec[0]["retried"], True)
            self.assertIn("retry_reason", rec[0])
            self.assertTrue(out.read_text().startswith("answer"))

    def test_no_retry_on_other_error(self):
        calls = []
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "o.txt"
            def run():
                calls.append(1); out.write_text("HTTP 400: bad request"); return False
            rec = []
            ok = conn_retry.run_with_connection_retry(run, out, "http://127.0.0.1:9", rec.append, 1, 0.1)
            self.assertFalse(ok); self.assertEqual(len(calls), 1); self.assertEqual(rec, [])

    def test_retry_gives_up_when_unhealthy(self):
        calls = []
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "o.txt"
            def run():
                calls.append(1); out.write_text("Error: [Errno 111] Connection refused"); return False
            rec = []
            ok = conn_retry.run_with_connection_retry(run, out, "http://127.0.0.1:9", rec.append, 0.5, 0.1)
            self.assertFalse(ok); self.assertEqual(len(calls), 1)
            self.assertFalse(rec[0]["retried"])

    def test_delegate_to_local_wired_and_dispatch_untouched(self):
        text = (ROOT / "scripts/ai/delegate-to-local").read_text()
        self.assertIn('conn_retry.py', text)
        self.assertNotIn("conn_retry", (ROOT / "scripts/ai/lib/dispatch.py").read_text())

    def test_cli_retries_command_once(self):
        """CLI path: first run drops the connection; rerun under <id>-r1 succeeds.
        No registry row is removed; the original id resolves to the retry's outcome."""
        DropFirst.posts = 0
        srv, url = serve(DropFirst)
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "o.txt"
            deleg = Path(d) / "deleg"
            deleg.mkdir()
            reg = deleg / "registry.jsonl"
            worker = Path(d) / "w.py"
            worker.write_text(
                "import sys, json, urllib.request, pathlib\n"
                "a = sys.argv[1:]; i = a.index('--task-id'); tid = a[i+1]; u, o, reg = a[:i] + a[i+2:]\n"
                "row = {'id': tid, 'status': 'running', 'output_file': o}\n"
                "ok = True\n"
                "try:\n"
                "    urllib.request.urlopen(urllib.request.Request(u + '/v1/chat/completions', data=b'{}', method='POST'), timeout=5)\n"
                "    pathlib.Path(o).write_text('answer')\n"
                "except Exception as e:\n"
                "    ok = False; pathlib.Path(o).write_text(f'Error: {e}')\n"
                "row['status'] = 'done' if ok else 'failed'\n"
                "open(reg, 'a').write(json.dumps(row) + '\\n')\n"
                "sys.exit(0 if ok else 1)\n")
            r = subprocess.run([sys.executable, str(ROOT / "scripts/ai/lib/conn_retry.py"),
                                "--task-id", "T1", "--output", str(out), "--llama-url", url,
                                "--delegation-dir", str(deleg), "--wait-s", "5", "--",
                                sys.executable, str(worker), "--task-id", "T1", url, str(out), str(reg)],
                               capture_output=True, text=True, timeout=60,
                               env={**os.environ, "PYTHONPATH": str(ROOT / "scripts/ai/lib")})
            srv.shutdown()
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(DropFirst.posts, 2)
            self.assertEqual(out.read_text(), "answer")
            meta = json.loads(Path(str(out) + ".retry.json").read_text())
            self.assertTrue(meta["retried"])
            self.assertEqual(meta["retry_task_id"], "T1-r1")
            self.assertTrue(meta["retry_reason"])
            rows = {x["id"]: x for x in map(json.loads, reg.read_text().splitlines())}
            self.assertEqual(set(rows), {"T1", "T1-r1"})          # no row removed
            self.assertEqual(len(reg.read_text().splitlines()), 2)
            self.assertEqual(rows["T1-r1"]["status"], "done")
            self.assertEqual(rows["T1-r1"]["retry_of"], "T1")
            self.assertEqual(rows["T1"]["status"], "done")        # original id resolves to retry outcome
            self.assertEqual(rows["T1"]["first_attempt_status"], "failed_retried")
            self.assertEqual(rows["T1"]["retried_as"], "T1-r1")
            self.assertTrue(rows["T1"]["retried"])
    def test_cli_no_retry_on_other_error(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "o.txt"
            deleg = Path(d) / "deleg"; deleg.mkdir()
            cnt = Path(d) / "cnt"
            worker = Path(d) / "w.py"
            worker.write_text("import sys,pathlib\n"
                              f"open({str(cnt)!r},'a').write('x')\n"
                              "pathlib.Path(sys.argv[1]).write_text('HTTP 400: bad'); sys.exit(1)\n")
            r = subprocess.run([sys.executable, str(ROOT / "scripts/ai/lib/conn_retry.py"),
                                "--task-id", "T2", "--output", str(out), "--llama-url", "http://127.0.0.1:9",
                                "--delegation-dir", str(deleg), "--wait-s", "1", "--",
                                sys.executable, str(worker), str(out)],
                               capture_output=True, text=True, timeout=60,
                               env={**os.environ, "PYTHONPATH": str(ROOT / "scripts/ai/lib")})
            self.assertEqual(r.returncode, 1)
            self.assertEqual(cnt.read_text(), "x")
            self.assertFalse(Path(str(out) + ".retry.json").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
