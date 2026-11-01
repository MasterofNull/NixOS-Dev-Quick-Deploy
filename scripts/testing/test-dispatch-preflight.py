#!/usr/bin/env python3
"""Routing S1: local context preflight + normalized dispatch evidence."""
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# Hermetic: no live context assembler / embedded-assist calls in either path.
os.environ["AQ_CONTEXT_ASSEMBLER"] = "0"
os.environ["SWITCHBOARD_URL"] = "http://127.0.0.1:1"

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "scripts" / "ai" / "lib"
DISPATCH = LIB / "local_preflight.py"
sys.path.insert(0, str(LIB))
import dispatch_evidence as de  # noqa: E402
from task_registry import TaskRegistry  # noqa: E402

N_CTX = 8000


class _Llama(BaseHTTPRequestHandler):
    seen: list = []  # (path, body) for every POST

    def log_message(self, *a):
        pass

    def _send(self, obj):
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    no_ctx = False

    def do_GET(self):
        if self.path.startswith("/slots"):
            return self._send([{"is_processing": False}])
        if _Llama.no_ctx:
            return self._send({})
        if self.path.startswith("/slots"):
            return self._send([{"is_processing": False}])
        self._send({"default_generation_settings": {"n_ctx": N_CTX}, "total_slots": 1})

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n))
        _Llama.seen.append((self.path, body))
        if self.path == "/apply-template":
            # chat template adds 10 chars of framing per message
            return self._send({"prompt": "".join("<|im_start|>" + str(m.get("content")) for m in body["messages"])})
        if self.path == "/tokenize":
            return self._send({"tokens": list(range(len(body["content"]) // 4))})  # 4 bytes/token mock
        # /v1/chat/completions: minimal SSE stream
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        self.wfile.write(b'data: {"choices":[{"delta":{"content":"ok"}}]}\n\ndata: [DONE]\n\n')


def _run(url, prompt, max_tokens, tmp, mode="direct", env=None):
    return subprocess.run(
        [sys.executable, str(DISPATCH), "--task-id", "t1",
         "--output", f"{tmp}/o.log", "--mode", mode, "--prompt", prompt,
         "--max-tokens", str(max_tokens), "--delegation-dir", tmp, "--llama-url", url],
        capture_output=True, text=True, timeout=60, env=env)


class _Switchboard(BaseHTTPRequestHandler):
    """embedded-assist stand-in: every call returns DIFFERENT content."""
    calls = 0

    def log_message(self, *a):
        pass

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        _Switchboard.calls += 1
        chunk = {"choices": [{"delta": {"content": f"ASSIST-CALL-{_Switchboard.calls}"}}]}
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        self.wfile.write(f"data: {json.dumps(chunk)}\n\ndata: [DONE]\n\n".encode())


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
            self.assertEqual((ref["method"], ref["limit"]), ("apply_template+tokenize", N_CTX))
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
            self.assertTrue(Path(f"{tmp}/o.log.preflight.json").is_file())

    def test_agent_mode_measures_agent_request_with_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run(
                [sys.executable, str(DISPATCH), "--task-id", "ta", "--output", f"{tmp}/a.log",
                 "--mode", "agent", "--prompt", "tiny", "--max-tokens", "64",
                 "--delegation-dir", tmp, "--llama-url", self.url],
                capture_output=True, text=True, timeout=120)
            # Agent system prompt (lists tools) dwarfs a direct "tiny" request, but a
            # small agent request must still fit an 8k window (schemas are not re-counted).
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            pf = json.loads(r.stdout)["preflight"]
            self.assertEqual(pf["mode"], "agent")
            self.assertGreater(pf["prompt_tokens"], 1000)
            self.assertEqual(pf["verdict"], "accept")

    def test_byte_fallback_is_labeled_guaranteed_upper_bound(self):
        text = "\u00e9" * 100  # 2 bytes per char; real tokens can never exceed bytes
        payload = {"messages": [{"role": "user", "content": text}], "_tool_schemas": [{"name": "t"}]}
        pf = de.preflight(payload, 10, "http://127.0.0.1:1", "agent")
        self.assertEqual(pf["method"], "byte_upper_bound")
        self.assertGreaterEqual(pf["prompt_tokens"], len(json.dumps(payload["messages"], ensure_ascii=False).encode()))
        self.assertEqual(pf["limit_source"], "config:local-model-config.yaml")
        self.assertIsInstance(pf["limit"], int)

    def test_small_agent_request_accepted_in_8192_window(self):
        payload = {"messages": [{"role": "user", "content": "Say hi."}],
                   "_tool_schemas": [{"name": "t", "description": "d" * 21000}],
                   "grammar": "root ::= " + "x" * 5000}
        pf = de.preflight(payload, 800, self.url, "agent")
        self.assertEqual(pf["method"], "apply_template+tokenize")
        self.assertEqual(pf["verdict"], "accept", pf)
        self.assertLess(pf["prompt_tokens"], 100)

    def test_tool_schemas_count_in_byte_fallback(self):
        base = {"messages": [{"role": "user", "content": "hi"}]}
        big = dict(base, _tool_schemas=[{"name": "t", "description": "d" * 4000}])
        a = de.preflight(base, 0, "http://127.0.0.1:1", "agent")["prompt_tokens"]
        b = de.preflight(big, 0, "http://127.0.0.1:1", "agent")["prompt_tokens"]
        self.assertGreaterEqual(b - a, 4000)


def _wrapper(url, tmp, prompt, extra=(), pf_exit=None, mode="direct", extra_env=None):
    """Run the real delegate-to-local with a python3 shim: dispatch/conn_retry
    launches touch a sentinel instead of running."""
    bin_dir = Path(tmp) / "bin"
    bin_dir.mkdir(exist_ok=True)
    sentinel = Path(tmp) / "LAUNCHED"
    shim = bin_dir / "python3"
    shim.write_text(f"""#!/bin/sh
case "$*" in
  *--record-error*) ;;
  *local_preflight.py*) {'exit ' + str(pf_exit) if pf_exit else ':'} ;;
esac
case "$*" in
  *conn_retry.py*|*dispatch.py*delegate*) echo launched > {sentinel}; echo ok > "$OUT_FOR_SENTINEL"; exit 0 ;;
esac
exec {sys.executable} "$@"
""")
    shim.chmod(0o755)
    out = Path(tmp) / "outputs" / "x.log"
    env = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}", AQ_DELEGATION_DIR=tmp,
               LLAMA_PORT=url.rsplit(":", 1)[1], AQ_NO_CONSULT="1", OUT_FOR_SENTINEL=str(out), **(extra_env or {}))
    r = subprocess.run(
        [str(REPO / "scripts" / "ai" / "delegate-to-local"), "--mode", mode, "--wait",
         "--prompt", prompt, *extra],
        capture_output=True, text=True, timeout=120, env=env, cwd=tmp)
    return r, sentinel


class WrapperLaunchBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = HTTPServer(("127.0.0.1", 0), _Llama)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.srv.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def test_oversize_refused_and_not_launched(self):
        with tempfile.TemporaryDirectory() as tmp:
            r, sentinel = _wrapper(self.url, tmp, "y" * 40000, ["--max-tokens", "64"])
            self.assertEqual(r.returncode, 3, r.stderr)
            self.assertFalse(sentinel.exists(), "oversize task must not launch")
            rows = _rows(tmp)
            self.assertEqual([x["outcome"] for x in rows], ["refused"])
            self.assertEqual(rows[0]["preflight"]["verdict"], "refuse")

    def test_missing_context_limit_blocks_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            _Llama.no_ctx = True
            self.addCleanup(setattr, _Llama, "no_ctx", False)
            r, sentinel = _wrapper(self.url, tmp, "small task", ["--max-tokens", "64"],
                                   extra_env={"AQ_LOCAL_MODEL_CONFIG": f"{tmp}/missing.yaml"})
            self.assertEqual(r.returncode, 3, r.stderr)
            self.assertFalse(sentinel.exists(), "no-limit task must not launch")
            self.assertEqual(_rows(tmp)[0]["terminal_reason"], "preflight_no_limit")

    def test_hybrid_launches_with_not_measured_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            r, sentinel = _wrapper(self.url, tmp, "small task", ["--max-tokens", "64"], mode="hybrid")
            self.assertTrue(sentinel.exists(), r.stdout + r.stderr)
            saved = json.loads(next((Path(tmp) / "outputs").glob("*.preflight.json")).read_text())
            self.assertEqual(saved["preflight"]["verdict"], "not_measured")

    def test_preflight_crash_blocks_launch_and_is_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            r, sentinel = _wrapper(self.url, tmp, "small task", ["--max-tokens", "64"], pf_exit=7)
            self.assertEqual(r.returncode, 4, r.stderr)
            self.assertFalse(sentinel.exists(), "unmeasured task must not launch")
            rows = _rows(tmp)
            self.assertEqual(len(rows), 1)
            self.assertEqual((rows[0]["status"], rows[0]["outcome"]), ("failed", "refused"))
            self.assertEqual(rows[0]["terminal_reason"], "preflight_error")

    def test_preflight_bad_args_blocks_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            r, sentinel = _wrapper(self.url, tmp, "small task", ["--max-tokens", "notanumber"])
            self.assertNotEqual(r.returncode, 0, r.stderr)
            self.assertFalse(sentinel.exists())

    def test_accepted_job_launches_and_records_preflight_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            r, sentinel = _wrapper(self.url, tmp, "small task", ["--max-tokens", "64"])
            self.assertTrue(sentinel.exists(), r.stdout + r.stderr)
            side = list((Path(tmp) / "outputs").glob("*.preflight.json"))
            self.assertEqual(len(side), 1)
            saved = json.loads(side[0].read_text())
            self.assertEqual(saved["preflight"]["verdict"], "accept")
            # the registry row the launched job would write picks the evidence up
            out = str(side[0])[: -len(".preflight.json")]
            reg = TaskRegistry(Path(tmp))
            reg.append(saved["task_id"], "d", out, "direct", "implementer")
            row = _rows(tmp)[-1]
            self.assertEqual(row["preflight"]["verdict"], "accept")
            self.assertEqual(row["preflight"]["limit"], N_CTX)
            self.assertEqual(row["preflight"]["method"], "apply_template+tokenize")

    def test_launch_uses_the_measured_prompt_not_a_second_assembly(self):
        sw = HTTPServer(("127.0.0.1", 0), _Switchboard)
        threading.Thread(target=sw.serve_forever, daemon=True).start()
        self.addCleanup(sw.shutdown)
        env = dict(os.environ, SWITCHBOARD_URL=f"http://127.0.0.1:{sw.server_port}")
        with tempfile.TemporaryDirectory() as tmp:
            _Switchboard.calls = 0
            _Llama.seen.clear()
            r = _run(self.url, "parity prompt", 64, tmp, env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(_Switchboard.calls, 1)
            measured = [b for p, b in _Llama.seen if p == "/apply-template"][-1]["messages"]
            self.assertIn("ASSIST-CALL-1", json.dumps(measured))
            _Llama.seen.clear()
            deleg = Path(tmp) / "root" / ".agents" / "delegation"
            deleg.mkdir(parents=True)
            d = subprocess.run(
                [sys.executable, str(LIB / "dispatch_measured.py"), "delegate", "--task-id", "t1",
                 "--output", f"{tmp}/o.log", "--mode", "direct", "--role", "auto",
                 "--prompt", "parity prompt", "--timeout", "30", "--max-tokens", "64",
                 "--assembled-file", f"{tmp}/o.log.assembled.json",
                 "--delegation-dir", str(deleg), "--llama-url", self.url,
                 "--hybrid-url", "http://127.0.0.1:1", "--ralph-url", "http://127.0.0.1:1"],
                capture_output=True, text=True, timeout=60, env=env)
            sent = [b for p, b in _Llama.seen if p == "/v1/chat/completions"]
            self.assertTrue(sent, d.stdout + d.stderr)
            self.assertEqual(_Switchboard.calls, 1, "launch must not re-run embedded-assist")
            self.assertNotIn("ASSIST-CALL-2", json.dumps(sent[-1]))
            self.assertEqual(sent[-1]["messages"], measured)

    def test_launch_refuses_when_assembled_prompt_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            _Llama.seen.clear()
            deleg = Path(tmp) / "root" / ".agents" / "delegation"
            deleg.mkdir(parents=True)
            d = subprocess.run(
                [sys.executable, str(LIB / "dispatch_measured.py"), "delegate", "--task-id", "t1",
                 "--output", f"{tmp}/o.log", "--mode", "direct", "--prompt", "p", "--max-tokens", "64",
                 "--assembled-file", f"{tmp}/nope.json", "--delegation-dir", str(deleg),
                 "--llama-url", self.url, "--hybrid-url", "http://127.0.0.1:1",
                 "--ralph-url", "http://127.0.0.1:1"], capture_output=True, text=True, timeout=60)
            self.assertNotEqual(d.returncode, 0)
            self.assertFalse([1 for p, _ in _Llama.seen if p == "/v1/chat/completions"])

    def test_hybrid_and_ralph_are_never_accepted(self):
        for mode in ("hybrid", "ralph"):
            with tempfile.TemporaryDirectory() as tmp:
                r = _run(self.url, "small task", 64, tmp, mode=mode)
                self.assertEqual(r.returncode, 0, r.stderr)
                pf = json.loads(r.stdout)["preflight"]
                self.assertEqual(pf["verdict"], "not_measured")
                self.assertNotEqual(pf["verdict"], "accept")
                self.assertEqual(pf["limitation"], de.NOT_MEASURED_LIMITATION)
                row = de.normalize_row({"id": "t1", "output_file": f"{tmp}/o.log"})
                self.assertEqual(row["preflight"]["verdict"], "not_measured")
                self.assertEqual(row["preflight"]["limitation"], de.NOT_MEASURED_LIMITATION)
                self.assertFalse(Path(f"{tmp}/o.log.assembled.json").exists())

    def test_no_context_limit_refuses_before_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            _Llama.no_ctx = True
            self.addCleanup(setattr, _Llama, "no_ctx", False)
            pf = de.preflight({"messages": [{"role": "user", "content": "x"}]}, 8, self.url, "direct")
            r = _run(self.url, "small task", 64, tmp,
                     env=dict(os.environ, AQ_LOCAL_MODEL_CONFIG=f"{tmp}/missing.yaml"))
            self.assertEqual(r.returncode, 3, r.stderr)
            rows = _rows(tmp)
            self.assertEqual(rows[0]["terminal_reason"], "preflight_no_limit")
            self.assertEqual(rows[0]["outcome"], "refused")


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
