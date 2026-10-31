#!/usr/bin/env python3
"""Routing S1: local context preflight + normalized dispatch evidence."""
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "scripts" / "ai" / "lib"
DISPATCH = LIB / "local_preflight.py"
sys.path.insert(0, str(LIB))
import dispatch_evidence as de  # noqa: E402
from task_registry import TaskRegistry  # noqa: E402

N_CTX = 8000


class _Llama(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, obj):
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._send({"default_generation_settings": {"n_ctx": N_CTX}, "total_slots": 1})

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        content = json.loads(self.rfile.read(n))["content"]
        self._send({"tokens": list(range(len(content) // 4))})  # 4 bytes/token mock


def _run(url, prompt, max_tokens, tmp):
    return subprocess.run(
        [sys.executable, str(DISPATCH), "--task-id", "t1",
         "--output", f"{tmp}/o.log", "--mode", "direct", "--prompt", prompt,
         "--max-tokens", str(max_tokens), "--delegation-dir", tmp, "--llama-url", url],
        capture_output=True, text=True, timeout=60)


def _rows(tmp):
    p = Path(tmp) / "registry.jsonl"
    return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []


class PreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = HTTPServer(("127.0.0.1", 0), _Llama)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.srv.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def test_oversize_refused_before_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _run(self.url, "y" * 40000, 64, tmp)
            self.assertEqual(r.returncode, 3, r.stderr)
            ref = json.loads(r.stderr.strip().splitlines()[-1])
            self.assertTrue(ref["refused"])
            self.assertEqual((ref["method"], ref["limit"]), ("tokenize", N_CTX))
            self.assertIn("decompose_hint", ref)
            rows = _rows(tmp)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["status"], "failed")
            self.assertEqual(rows[0]["outcome"], "refused")
            self.assertEqual(rows[0]["preflight"]["verdict"], "refuse")
            self.assertEqual(json.loads((Path(tmp) / "o.log").read_text())["refused"], True)

    def test_output_allowance_counts_toward_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            # harness-assembled prompt fits alone; prompt + 7900 output does not
            r = _run(self.url, "short prompt", 7900, tmp)
            self.assertEqual(r.returncode, 3, r.stderr)

    def test_accepted_prompt_fits_total_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _run(self.url, "small task", 64, tmp)
            self.assertEqual(r.returncode, 0, r.stderr)
            pf = json.loads(r.stdout)["preflight"]
            self.assertEqual(pf["verdict"], "accept")
            self.assertLessEqual(pf["measured"], pf["limit"])
            self.assertEqual(pf["measured"], pf["prompt_tokens"] + 64)
            self.assertEqual(_rows(tmp), [])  # nothing registered, nothing launched

    def test_byte_guard_fallback_is_labeled(self):
        msgs = [{"role": "user", "content": "a" * 100}]
        pf = de.preflight(msgs, 10, "http://127.0.0.1:1", "direct")
        self.assertEqual(pf["method"], "byte_guard")
        self.assertEqual(pf["limit_source"], "config:local-model-config.yaml")
        self.assertIsInstance(pf["limit"], int)


class EvidenceTests(unittest.TestCase):
    def test_registry_fields_present_with_honest_unknowns(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg = TaskRegistry(Path(tmp))
            reg.append("id1", "desc", "out.log", "direct", "implementer")
            row = _rows(tmp)[0]
            for k in ("id", "agent", "role", "status", "output_file"):  # legacy readers
                self.assertIn(k, row)
            self.assertEqual(row["dispatch_id"], "id1")
            self.assertEqual((row["risk"], row["complexity"]), ("unknown", "unknown"))
            self.assertEqual(row["effort"], "n/a")
            self.assertEqual(row["effective_lane"], "local")
            self.assertIsNone(row["policy_version"])
            self.assertEqual(row["preflight"]["verdict"], "n/a")
            self.assertEqual(reg.list_all()[0]["id"], "id1")
            self.assertEqual(reg.monitor_payload()["dispatch_evidence"]["total"], 1)

    def test_existing_values_never_overwritten_and_legacy_rows_summarized(self):
        row = de.normalize_row({"id": "c1", "agent": "codex", "effort": "high", "model_effective": "o3"})
        self.assertEqual((row["effort"], row["model_effective"]), ("high", "o3"))
        s = de.summarize([row, {"id": "old", "agent": "gemini"}])
        self.assertEqual(s["without_normalized_evidence"], 1)
        self.assertEqual(s["by_source"]["unrecorded"], 1)


if __name__ == "__main__":
    unittest.main()
