#!/usr/bin/env python3
"""Tests for brief_caps: parser, validator (WARN->FAIL schedule), cap tiers, measurement record."""
import datetime as dt
import http.server
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ai" / "lib"))
import brief_caps as bc  # noqa: E402

GOOD = """slice_objective: x
checks:
  command: python3 scripts/testing/test-x.py
  end_state: exit 0
caps:
  tier: small
  stop_condition: halt
"""
BEFORE = dt.date(2026, 11, 18)
AFTER = dt.date(2026, 12, 2)


class Parse(unittest.TestCase):
    def test_blocks(self):
        b = bc.parse_brief(GOOD)
        self.assertEqual(b["checks"]["command"], "python3 scripts/testing/test-x.py")
        self.assertEqual(b["caps"]["tier"], "small")

    def test_legacy_aliases(self):
        b = bc.parse_brief("check_command: pytest\ntoken_budget: 9000\nturn_cap: 3\n")
        self.assertEqual(b["checks"]["command"], "pytest")
        r = bc.resolve_caps(b["caps"])
        self.assertEqual((r["input_tokens"], r["max_turns"]), (9000, 3))


class LegacyBudget(unittest.TestCase):
    def test_nonpositive_or_bad_token_budget_rejected(self):
        for v in ("0", "-5", "abc"):
            with self.assertRaises(ValueError):
                bc.resolve_caps({"token_budget": v})


class DelegateGate(unittest.TestCase):
    """delegate-to-local must block on validator failure and pass an absolute brief path."""
    def _run(self, text, env_extra=None):
        import subprocess
        d = tempfile.mkdtemp()
        Path(d, "brief.md").write_text(text)
        env = dict(os.environ, **(env_extra or {}))
        return subprocess.run([str(ROOT / "scripts/ai/delegate-to-local"), "--prompt-file", "brief.md"],
                              cwd=d, env=env, capture_output=True, text=True)

    def test_invalid_caps_block(self):
        r = self._run("checks:\n  command: x\n  end_state: y\ncaps:\n  token_budget: 0\n")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("failed validation", r.stderr + r.stdout)

    def test_missing_checks_blocks_after_deadline(self):
        r = self._run("caps:\n  tier: small\n", {"AQ_BRIEF_CHECKS_FAIL_FROM": "2000-01-01"})
        self.assertIn("failed validation", r.stderr + r.stdout)

    def test_slice_objective_without_checks_blocks_after_deadline(self):
        r = self._run("slice_objective: build x\n", {"AQ_BRIEF_CHECKS_FAIL_FROM": "2000-01-01"})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("failed validation", r.stderr + r.stdout)

    def test_script_resolves_prompt_file_absolute(self):
        src = (ROOT / "scripts/ai/delegate-to-local").read_text()
        self.assertLess(src.index('PROMPT_FILE="$(cd "$(dirname "$PROMPT_FILE")"'),
                        src.index('export AQ_BRIEF_FILE'))

    def test_is_slice_brief_classification(self):
        self.assertTrue(bc.is_slice_brief(GOOD))
        self.assertTrue(bc.is_slice_brief("slice_objective: build x\n"))
        self.assertTrue(bc.is_slice_brief("caps:\n  tier: small\n"))
        self.assertTrue(bc.is_slice_brief("check_command: pytest\n"))
        self.assertFalse(bc.is_slice_brief("Summarize the diff in one sentence.\n"))
        self.assertFalse(bc.is_slice_brief(
            "Reviewing chunk 1 of 2 of SKILL.md for this question: any bug?\n\n"
            "--- CHUNK ---\ncaps:\n  tier: small\n--- END CHUNK ---\n\n"
            "Report ONLY findings about THIS chunk.\n"
        ))
        self.assertFalse(bc.is_slice_brief("Notes:\n```yaml\ncaps:\n  tier: small\n```\n"))

    def test_ordinary_prompt_file_allowed_on_enforcement_date(self):
        seen_bodies = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/health":
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b'{"status":"ok"}')
                elif self.path == "/props":
                    body = json.dumps({"default_generation_settings": {"n_ctx": 32768}}).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(body)
                elif self.path == "/slots":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'[{"id":0,"is_processing":false}]')
                else:
                    self.send_response(404)
                    self.end_headers()

            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                seen_bodies.append(json.loads(self.rfile.read(length)))
                if self.path == "/v1/chat/completions":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.end_headers()
                    self.wfile.write(
                        b'data: {"choices":[{"delta":{"content":"NO FINDINGS"}}]}\n\n'
                        b'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n'
                        b'data: [DONE]\n\n'
                    )
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, *args):
                return

        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        try:
            with tempfile.TemporaryDirectory() as td:
                deleg_dir = Path(td) / "sub" / "delegation"
                prompt_path = Path(td) / "map.prompt.txt"
                prompt_path.write_text(
                    "Reviewing chunk 1 of 1 of foo.py for this question: bugs?\n\n"
                    "--- CHUNK ---\nprint('hi')\n--- END CHUNK ---\n\n"
                    "Report ONLY findings about THIS chunk.\n",
                    encoding="utf-8",
                )
                env = dict(os.environ)
                env.update({
                    "AQ_BRIEF_CHECKS_FAIL_FROM": "2000-01-01",
                    "AQ_DELEGATION_DIR": str(deleg_dir),
                    "LLAMA_PORT": str(srv.server_port),
                    "AQ_CONTEXT_ASSEMBLER": "0",
                    "AQ_CONTEXT_PACKET": "0",
                    "AQ_LOCAL_POWER_GATE": "0",
                    "AQ_NO_CONSULT": "1",
                    "SLOT_QUEUE": "0",
                    "SWITCHBOARD_URL": "http://127.0.0.1:1",
                    "HYBRID_PORT": "1",
                })
                r = subprocess.run(
                    [
                        str(ROOT / "scripts/ai/delegate-to-local"),
                        "--mode", "direct",
                        "--wait",
                        "--no-consult",
                        "--ignore-power-gate",
                        "--prompt-file", str(prompt_path),
                    ],
                    cwd=td,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                self.assertEqual(r.returncode, 0, f"stderr={r.stderr}\nstdout={r.stdout}")
                self.assertIn("NO FINDINGS", r.stdout)
                self.assertNotIn("failed validation", r.stderr + r.stdout)
                self.assertFalse((deleg_dir / bc.LOG).exists())
                self.assertTrue(seen_bodies)
        finally:
            srv.shutdown()
            srv.server_close()


class Validate(unittest.TestCase):
    def test_valid(self):
        r = bc.validate(GOOD, BEFORE)
        self.assertEqual((r["errors"], r["warnings"]), ([], []))

    def test_missing_checks_warns_before_checkpoint(self):
        r = bc.validate("caps:\n  tier: small\n", BEFORE)
        self.assertEqual(r["errors"], [])
        self.assertTrue(any("checks.command" in w and "2026-12-02" in w for w in r["warnings"]))

    def test_missing_checks_fails_from_checkpoint(self):
        r = bc.validate("caps:\n  tier: small\n", AFTER)
        self.assertTrue(any("checks.command" in e for e in r["errors"]))

    def test_bad_tier_and_numbers_fail(self):
        self.assertTrue(bc.validate(GOOD.replace("small", "huge"), BEFORE)["errors"])
        self.assertTrue(bc.validate(GOOD + "  output_tokens: abc\n", BEFORE)["errors"])
        self.assertTrue(bc.validate(GOOD + "  max_turns: 0\n", BEFORE)["errors"])

    def test_missing_caps_warns_and_defaults(self):
        r = bc.validate("checks:\n  command: x\n  end_state: y\n", BEFORE)
        self.assertTrue(any("caps" in w for w in r["warnings"]))
        self.assertEqual(r["caps"]["tier"], "medium")


class Tiers(unittest.TestCase):
    def test_tier_values(self):
        for tier, i, o in (("small", 2000, 500), ("medium", 12000, 4000), ("large", 24000, 8000)):
            r = bc.resolve_caps({"tier": tier})
            self.assertEqual((r["input_tokens"], r["output_tokens"]), (i, o))

    def test_default_and_override(self):
        self.assertEqual(bc.resolve_caps({})["tier"], "medium")
        self.assertEqual(bc.resolve_caps({"tier": "small", "output_tokens": "900"})["output_tokens"], 900)
        self.assertEqual(bc.resolve_caps({})["stop_condition"], bc.DEFAULT_STOP)


class Configurable(unittest.TestCase):
    ENV = ("AQ_BRIEF_TIERS_FILE", "AQ_BRIEF_LANE_CTX", "AQ_BRIEF_LANE_MODEL", "AQ_BRIEF_CHECKS_FAIL_FROM")

    def setUp(self):
        self._saved = {k: os.environ.pop(k, None) for k in self.ENV}

    def tearDown(self):
        for k, v in self._saved.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v

    def test_tiers_file_override(self):
        with tempfile.TemporaryDirectory(dir=str(ROOT / ".agents")) as td:
            f = Path(td) / "tiers.json"
            f.write_text(json.dumps({"default_tier": "tiny", "tiers": {
                "tiny": {"input_tokens": 300, "output_tokens": 100, "max_turns": 2}}}))
            os.environ["AQ_BRIEF_TIERS_FILE"] = str(f)
            r = bc.resolve_caps({})
            self.assertEqual((r["tier"], r["input_tokens"], r["output_tokens"], r["max_turns"]),
                             ("tiny", 300, 100, 2))
            self.assertTrue(bc.validate("caps:\n  tier: small\n", BEFORE)["errors"])  # not in this file

    def test_unreadable_tiers_file_falls_back_to_builtin(self):
        os.environ["AQ_BRIEF_TIERS_FILE"] = "/nonexistent/tiers.json"
        self.assertEqual(bc.resolve_caps({"tier": "large"})["input_tokens"], 24000)

    def test_lane_ctx_clamps_tier_caps_not_explicit_values(self):
        os.environ["AQ_BRIEF_LANE_CTX"] = "8192"
        r = bc.resolve_caps({"tier": "large"})
        self.assertEqual((r["input_tokens"], r["output_tokens"]), (4096, 2048))
        self.assertEqual(r["over_lane_budget"], [])
        r = bc.resolve_caps({"tier": "large", "output_tokens": "6000"})
        self.assertEqual(r["output_tokens"], 6000)
        self.assertEqual(r["over_lane_budget"], ["output_tokens"])

    def test_lane_model_from_coordinator_config(self):
        os.environ["AQ_BRIEF_LANE_MODEL"] = "llama-cpp-local"
        n = bc.lane_context()
        self.assertIsInstance(n, int)
        self.assertLessEqual(bc.resolve_caps({"tier": "large"})["input_tokens"], n // 2)
        os.environ["AQ_BRIEF_LANE_MODEL"] = "no-such-model"
        self.assertIsNone(bc.lane_context())

    def test_checks_fail_from_env(self):
        os.environ["AQ_BRIEF_CHECKS_FAIL_FROM"] = "2027-06-01"
        self.assertEqual(bc.validate("caps:\n  tier: small\n", AFTER)["errors"], [])
        self.assertTrue(bc.validate("caps:\n  tier: small\n", dt.date(2027, 6, 1))["errors"])
        os.environ["AQ_BRIEF_CHECKS_FAIL_FROM"] = "never"
        r = bc.validate("caps:\n  tier: small\n", dt.date(2099, 1, 1))
        self.assertEqual(r["errors"], [])
        self.assertTrue(r["warnings"])


class Measure(unittest.TestCase):
    def test_record_from_registry_and_timing(self):
        with tempfile.TemporaryDirectory(dir=str(ROOT / ".agents")) as td:
            d = Path(td)
            out = d / "outputs" / "t1.log"
            out.parent.mkdir()
            (d / "registry.jsonl").write_text(json.dumps(
                {"id": "t1", "output_file": str(out), "tokens_in": 1500, "tokens_out": 900}) + "\n")
            Path(str(out) + ".timing.json").write_text(json.dumps({"request_elapsed_seconds": 12.5}))
            rec = bc.measure(d, "t1", GOOD, lane="local-direct", turns=2, now="2026-11-18T00:00:00Z")
            self.assertEqual(rec["caps"], {"input_tokens": 2000, "output_tokens": 500, "max_turns": 4})
            self.assertEqual(rec["within_caps"], {"input_tokens": True, "output_tokens": False, "turns": True})
            self.assertEqual(rec["elapsed_seconds"], 12.5)
            line = json.loads((d / bc.LOG).read_text().splitlines()[0])
            self.assertEqual(line, rec)
            s = bc.summarize([line])
            self.assertEqual((s["runs"], s["over_cap"]["output_tokens"]), (1, 1))

    def test_unknown_actuals_are_null_not_zero(self):
        with tempfile.TemporaryDirectory(dir=str(ROOT / ".agents")) as td:
            rec = bc.measure(Path(td), "nope", "caps:\n  tier: large\n")
            self.assertEqual(rec["actual"], {"input_tokens": None, "output_tokens": None, "turns": None})
            self.assertEqual(rec["within_caps"]["input_tokens"], None)
            self.assertFalse(rec["checks_declared"])
            self.assertEqual(bc.summarize([rec])["unknown"]["input_tokens"], 1)


class AgentCapWiring(unittest.TestCase):
    """AgentRunner must pass config.max_tokens to aq-agent-loop and reach generation."""

    def test_agent_runner_cap_reaches_llama_generation(self):
        lib_dir = str(ROOT / "scripts/ai/lib")
        if lib_dir not in sys.path:
            sys.path.insert(0, lib_dir)
        spec = importlib.util.spec_from_file_location("dispatch_test_agent_cap", ROOT / "scripts/ai/lib/dispatch.py")
        dispatch = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(dispatch)

        seen_payloads = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(404)
                self.end_headers()

            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                seen_payloads.append(json.loads(self.rfile.read(length)))
                if self.path == "/v1/chat/completions":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.end_headers()
                    self.wfile.write(
                        b'data: {"choices":[{"delta":{"content":"COMPLETED: capped answer"}}]}\n\n'
                        b'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n'
                        b'data: {"choices":[],"usage":{"prompt_tokens":12,"completion_tokens":4,"total_tokens":16}}\n\n'
                        b'data: [DONE]\n\n'
                    )
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, *args):
                return

        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        saved = {k: os.environ.get(k) for k in (
            "SWITCHBOARD_URL", "LLAMA_MAX_TOKENS", "AQ_AGENT_RUN_EVENTS_PATH",
            "AQ_AGENT_HYBRID_EVENTS_PATH", "AQ_LOCAL_SKILL_PROJECTION",
        )}
        try:
            with tempfile.TemporaryDirectory() as td:
                os.environ["SWITCHBOARD_URL"] = f"http://127.0.0.1:{srv.server_port}"
                os.environ["LLAMA_MAX_TOKENS"] = "999"
                os.environ["AQ_AGENT_RUN_EVENTS_PATH"] = str(Path(td) / "events.jsonl")
                os.environ["AQ_AGENT_HYBRID_EVENTS_PATH"] = str(Path(td) / "hybrid.jsonl")
                os.environ["AQ_LOCAL_SKILL_PROJECTION"] = "0"
                out_file = Path(td) / "agent.log"
                config = dispatch.TaskConfig(
                    mode="agent",
                    role="implementer",
                    timeout_secs=30,
                    max_tokens=222,
                    llama_url=f"http://127.0.0.1:{srv.server_port}",
                    hybrid_url="http://127.0.0.1:1",
                    ralph_url="http://127.0.0.1:1",
                    task_type="agent",
                )
                ok = dispatch.AgentRunner(ROOT / "scripts/ai").run(config, "Reply with OK.", out_file, max_calls=1)
                self.assertTrue(ok, out_file.read_text(encoding="utf-8") if out_file.exists() else "no output")
                self.assertTrue(seen_payloads, "no /v1/chat/completions request reached generation")
                self.assertEqual(seen_payloads[0].get("max_tokens"), 222)
        finally:
            srv.shutdown()
            srv.server_close()
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


class MissingUsage(unittest.TestCase):
    """A stream returning content without usage must record null, not 0 or chunk count."""

    def test_direct_stream_without_usage_records_null_not_in_budget(self):
        lib_dir = str(ROOT / "scripts/ai/lib")
        if lib_dir not in sys.path:
            sys.path.insert(0, lib_dir)
        spec = importlib.util.spec_from_file_location("dispatch_test_missing_usage", ROOT / "scripts/ai/lib/dispatch.py")
        dispatch = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(dispatch)

        class _Socket:
            def settimeout(self, timeout):
                return None

        class _Response:
            def __init__(self, lines):
                self.lines = lines
                self.fp = type("FP", (), {"raw": type("Raw", (), {"_sock": _Socket()})()})()

            def __enter__(self):
                return self

            def __exit__(self, *unused):
                return False

            def __iter__(self):
                return iter(self.lines)

        chunks = [
            b'data: {"choices":[{"delta":{"content":"hello "}}]}\n',
            b'data: {"choices":[{"delta":{"content":"world"}}]}\n',
            b'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n',
            b'data: [DONE]\n',
        ]
        orig_urlopen = dispatch.urllib.request.urlopen
        orig_wait = dispatch.wait_for_slot
        orig_queue = dispatch._slot_queue
        orig_emit = dispatch._emit_training_event
        orig_service = dispatch._wait_for_service
        orig_asm = dispatch._apply_context_assembler
        orig_prefetch = dispatch._embedded_assist_prefetch
        orig_brief = os.environ.get("AQ_BRIEF_FILE")
        try:
            dispatch.urllib.request.urlopen = lambda *a, **k: _Response(chunks)
            dispatch.wait_for_slot = lambda *a: None
            dispatch._slot_queue = None
            dispatch._emit_training_event = lambda *a: None
            dispatch._wait_for_service = lambda *a: True
            dispatch._apply_context_assembler = lambda p, *a: p
            dispatch._embedded_assist_prefetch = lambda *a: ""

            with tempfile.TemporaryDirectory() as td:
                d = Path(td) / "a" / "b" / "delegation"
                out_direct = d / "outputs" / "direct-only.log"
                out_direct.parent.mkdir(parents=True)
                cfg = dispatch.TaskConfig(
                    mode="direct",
                    role="implementer",
                    timeout_secs=5,
                    max_tokens=500,
                    llama_url="http://127.0.0.1:1",
                    hybrid_url="http://127.0.0.1:1",
                    ralph_url="http://127.0.0.1:1",
                    task_type="code",
                )
                self.assertTrue(dispatch.DirectRunner().run(cfg, "prompt", out_direct, "t-direct"))
                sidecar = json.loads(Path(str(out_direct) + ".usage.json").read_text(encoding="utf-8"))
                self.assertIsNone(sidecar["tokens_in"])
                self.assertIsNone(sidecar["tokens_out"])
                self.assertEqual(sidecar["finish_reason"], "stop")

                brief_path = d / "brief.md"
                brief_path.write_text(GOOD, encoding="utf-8")
                os.environ["AQ_BRIEF_FILE"] = str(brief_path)
                reg = dispatch.TaskRegistry(d)
                out_task = d / "outputs" / "t-no-usage.log"
                self.assertTrue(dispatch.dispatch_task(cfg, "prompt", "t-no-usage", out_task, reg, ROOT / "scripts/ai"))
                row = reg.get("t-no-usage")
                self.assertIsNone(row["tokens_in"])
                self.assertIsNone(row["tokens_out"])
                line = json.loads((d / bc.LOG).read_text(encoding="utf-8").splitlines()[0])
                self.assertEqual(line["actual"], {"input_tokens": None, "output_tokens": None, "turns": None})
                self.assertEqual(line["within_caps"], {"input_tokens": None, "output_tokens": None, "turns": None})
                summary = bc.summarize([line])
                self.assertEqual(summary["unknown"], {"input_tokens": 1, "output_tokens": 1, "turns": 1})
        finally:
            dispatch.urllib.request.urlopen = orig_urlopen
            dispatch.wait_for_slot = orig_wait
            dispatch._slot_queue = orig_queue
            dispatch._emit_training_event = orig_emit
            dispatch._wait_for_service = orig_service
            dispatch._apply_context_assembler = orig_asm
            dispatch._embedded_assist_prefetch = orig_prefetch
            if orig_brief is None:
                os.environ.pop("AQ_BRIEF_FILE", None)
            else:
                os.environ["AQ_BRIEF_FILE"] = orig_brief


if __name__ == "__main__":
    unittest.main()
