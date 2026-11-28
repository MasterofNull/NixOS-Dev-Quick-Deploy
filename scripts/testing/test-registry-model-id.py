#!/usr/bin/env python3
"""Delegation registry rows record the model that SERVED each run (model_id / model_source)."""
from __future__ import annotations

import http.server
import json
import os
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "scripts/ai/lib"
UPDATER = LIB / "registry-update.py"
QUOTA = "error: Individual quota reached. RESOURCE_EXHAUSTED (code 429)"


def rows(deleg: Path) -> list[dict]:
    path = deleg / "registry.jsonl"
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.deleg = self.dir / "deleg"
        self.deleg.mkdir()
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        self.env.update(AQ_DELEGATION_DIR=str(self.deleg), HOME=str(self.dir), CODEX_HOME=str(self.dir / "nocodex"))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def stub(self, name: str, body: str) -> Path:
        path = self.dir / name
        path.write_text(body)
        path.chmod(path.stat().st_mode | stat.S_IEXEC)
        return path

    def seed(self, task_id: str, **extra: object) -> None:
        row = {"id": task_id, "agent": "codex", "status": "running", "created": "2026-11-27T00:00:00Z", **extra}
        (self.deleg / "registry.jsonl").write_text(json.dumps(row) + "\n")

    def update(self, *args: str) -> None:
        r = subprocess.run([sys.executable, str(UPDATER), *args], capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)


class SharedWriter(_Base):
    def test_known_model_sets_id_effective_source_and_differing_requested(self) -> None:
        self.seed("t1", model_effective="unknown", model_requested="unknown")
        self.update("model", str(self.deleg / "registry.jsonl"), "t1", "gemini-4-hydrogen", "fallback", "gemini-4-argon")
        row = rows(self.deleg)[0]
        self.assertEqual(row["model_id"], "gemini-4-hydrogen")
        self.assertEqual(row["model_effective"], "gemini-4-hydrogen")
        self.assertEqual(row["model_source"], "fallback")
        self.assertEqual(row["model_requested"], "gemini-4-argon")

    def test_unknown_is_null_with_source_unknown_and_never_invented(self) -> None:
        self.seed("t1", model_effective="unknown")
        self.update("model", str(self.deleg / "registry.jsonl"), "t1", "", "whatever")
        row = rows(self.deleg)[0]
        self.assertIsNone(row["model_id"])
        self.assertEqual(row["model_source"], "unknown")
        self.assertEqual(row["model_effective"], "unknown")

    def test_requested_equal_to_served_is_not_rewritten(self) -> None:
        self.seed("t1", model_requested="x")
        self.update("model", str(self.deleg / "registry.jsonl"), "t1", "m", "cli_flag", "m")
        self.assertEqual(rows(self.deleg)[0]["model_requested"], "x")

    def test_existing_keys_survive(self) -> None:
        self.seed("t1", description="keep me", tokens_in=7)
        self.update("model", str(self.deleg / "registry.jsonl"), "t1", "m", "reported")
        row = rows(self.deleg)[0]
        self.assertEqual((row["description"], row["tokens_in"], row["status"]), ("keep me", 7, "running"))


class CodexWrapper(_Base):
    def run_codex(self, body: str, *args: str) -> dict:
        codex = self.stub("codex", body)
        env = dict(self.env, CODEX_BIN=str(codex))
        r = subprocess.run([str(ROOT / "scripts/ai/delegate-to-codex"), "--prompt", "hi", "--mode", "safe", "--wait", *args],
                           capture_output=True, text=True, timeout=90, env=env, cwd=self.dir)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return rows(self.deleg)[-1]

    def test_model_flag_is_recorded(self) -> None:
        row = self.run_codex("#!/bin/sh\necho done\n", "--model", "gpt-5-test")
        self.assertEqual(row["model_id"], "gpt-5-test")
        self.assertEqual(row["model_source"], "cli_flag")
        self.assertEqual(row["model_effective"], "gpt-5-test")

    def test_model_read_from_cli_output_header(self) -> None:
        row = self.run_codex("#!/bin/sh\necho 'model: gpt-5-from-header'\necho done\n")
        self.assertEqual(row["model_id"], "gpt-5-from-header")
        self.assertEqual(row["model_source"], "cli_output")

    def test_unknown_when_nothing_reports_a_model(self) -> None:
        row = self.run_codex("#!/bin/sh\necho done\n")
        self.assertIsNone(row["model_id"])
        self.assertEqual(row["model_source"], "unknown")


class GeminiWrapper(_Base):
    def run_gemini(self, argon: str, hydrogen: str, *args: str) -> dict:
        log = self.dir / "calls"
        gem = self.stub("gemini", f"""#!/usr/bin/env python3
import sys
a = sys.argv[1:]
m = a[a.index("--model") + 1] if "--model" in a else ""
mode = {{"": {argon!r}, "gemini-4-argon": {argon!r}, "gemini-4-hydrogen": {hydrogen!r}}}.get(m, "ok")
if mode == "quota":
    print({QUOTA!r}); sys.exit(1)
print("OK " * 200)
""")
        env = dict(self.env, GEMINI_BIN=str(gem))
        subprocess.run([str(ROOT / "scripts/ai/delegate-to-gemini"), "--prompt", "hi", "--wait", *args],
                       capture_output=True, text=True, timeout=90, env=env, cwd=self.dir)
        del log
        return rows(self.deleg)[-1]

    def test_fallback_records_served_model_and_requested(self) -> None:
        row = self.run_gemini("quota", "ok")
        self.assertEqual(row["model_id"], "gemini-4-hydrogen")
        self.assertEqual(row["model_source"], "fallback")
        self.assertEqual(row["model_requested"], "gemini-4-argon")
        self.assertEqual(row["model_effective"], "gemini-4-hydrogen")

    def test_pinned_model_is_recorded(self) -> None:
        row = self.run_gemini("ok", "ok", "--model", "gemini-4-neon-high")
        self.assertEqual(row["model_id"], "gemini-4-neon-high")
        self.assertEqual(row["model_source"], "cli_flag")

    def test_cli_default_success_is_unknown_not_invented(self) -> None:
        row = self.run_gemini("ok", "ok")
        self.assertIsNone(row["model_id"])
        self.assertEqual(row["model_source"], "unknown")

    def test_both_exhausted_serves_nothing(self) -> None:
        row = self.run_gemini("quota", "quota")
        self.assertIsNone(row["model_id"])
        self.assertEqual(row["model_source"], "unknown")
        self.assertEqual(row["model_requested"], "gemini-4-argon")


class ClaudeWrapper(_Base):
    def test_resolved_tier_model_is_recorded_and_default_is_unknown(self) -> None:
        sys.path.insert(0, str(ROOT / "scripts/testing"))
        import importlib.util
        spec = importlib.util.spec_from_file_location("claude_routing", ROOT / "scripts/testing/test-delegate-claude-model-routing.py")
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        case = mod.ClaudeModelRoutingTest("test_flagship_resolves_and_is_recorded")
        case.setUp()
        try:
            r = case.run_wrapper("--wait", "--model-tier", "flagship", "--role", "plan", "--prompt", "x")
            self.assertEqual(r.returncode, 0, r.stderr)
            row = case.registry()[-1]
            self.assertEqual((row["model_id"], row["model_source"]), ("claude-fable-5-1", "cli_flag"))
            r = case.run_wrapper("--wait", "--role", "review", "--prompt", "y")
            self.assertEqual(r.returncode, 0, r.stderr)
            row = case.registry()[-1]
            self.assertIsNone(row["model_id"])
            self.assertEqual(row["model_source"], "unknown")
        finally:
            case.tearDown()


class _SSE(http.server.BaseHTTPRequestHandler):
    model = "Qwen3.6-35B-test"

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass

    def do_GET(self) -> None:
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"{}")

    def do_POST(self) -> None:
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        base = {"model": self.model} if self.model else {}
        for ch in (
            {**base, "choices": [{"delta": {"content": "hello"}}]},
            {**base, "choices": [{"delta": {}, "finish_reason": "stop"}]},
            {**base, "choices": [], "usage": {"prompt_tokens": 3, "completion_tokens": 1}},
        ):
            self.wfile.write(b"data: " + json.dumps(ch).encode() + b"\n\n")
        self.wfile.write(b"data: [DONE]\n\n")


class LocalDispatch(_Base):
    def dispatch(self, model: str | None) -> dict:
        sys.path.insert(0, str(LIB))
        import dispatch as d  # type: ignore
        from task_config import TaskConfig  # type: ignore
        from task_registry import TaskRegistry  # type: ignore

        handler = type("H", (_SSE,), {"model": model})
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{srv.server_address[1]}"
        cfg = TaskConfig(mode="direct", role="implementer", max_tokens=64, timeout_secs=20, llama_url=url,
                         hybrid_url=url, ralph_url=url, task_type="code")
        reg = TaskRegistry(self.deleg)
        out = self.deleg / "out.log"
        try:
            with mock.patch.object(d, "wait_for_slot", lambda *a, **k: None), \
                 mock.patch.object(d, "_slot_queue", None), \
                 mock.patch.object(d, "_wait_for_service", lambda *a, **k: True), \
                 mock.patch.object(d, "_apply_context_assembler", lambda p, *a, **k: p), \
                 mock.patch.object(d, "_embedded_assist_prefetch", lambda *a, **k: ""):
                ok = d.dispatch_task(cfg, "say hello", "local-t1", out, reg, ROOT / "scripts/ai")
        finally:
            srv.shutdown()
        self.assertTrue(ok)
        return rows(self.deleg)[-1]

    def test_llama_reported_model_is_recorded(self) -> None:
        row = self.dispatch("Qwen3.6-35B-test")
        self.assertEqual(row["model_id"], "Qwen3.6-35B-test")
        self.assertEqual(row["model_source"], "llama_response")

    def test_unreported_model_is_null_unknown(self) -> None:
        row = self.dispatch(None)
        self.assertIsNone(row["model_id"])
        self.assertEqual(row["model_source"], "unknown")


class BaselineEligibility(unittest.TestCase):
    def test_model_id_counts_as_known(self) -> None:
        sys.path.insert(0, str(LIB))
        import aq_baseline  # type: ignore
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        ts = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        data = "\n".join(json.dumps(r) for r in (
            {"id": "a", "agent": "codex", "created": ts, "model_id": "m", "model_effective": "unknown"},
            {"id": "b", "agent": "codex", "created": ts, "model_id": None, "model_effective": "unknown"},
        )).encode()
        row = aq_baseline._model_known_row(data, (now - timedelta(days=1), now + timedelta(days=1)), None)
        self.assertEqual((row["numerator"], row["denominator"]), (1, 2))


if __name__ == "__main__":
    unittest.main(verbosity=2)
