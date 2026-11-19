#!/usr/bin/env python3
"""Offline regression coverage for embedded knowledge-source fetch retries."""
import ast
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import MagicMock, mock_open, patch
import urllib.error
from email.message import Message
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/data/sync-knowledge-sources"
PROGRAM = SCRIPT.read_text().split("<<'PYEOF'\n")[-1].rsplit("\nPYEOF", 1)[0]
HELPERS = ast.Module(body=[node for node in ast.parse(PROGRAM).body
                          if isinstance(node, ast.FunctionDef) and node.name == "fetch_url"],
                     type_ignores=[])


class FetchTests(unittest.TestCase):
    def setUp(self):
        self.namespace = {"urllib": urllib,
                          "sys": sys, "time": __import__("time"), "fetch_max_retries": 3}
        exec(compile(HELPERS, str(SCRIPT), "exec"), self.namespace)
        self.response = MagicMock()
        self.response.__enter__.return_value.read.return_value = b"content"

    def fetch(self, effects, retries=3):
        self.namespace["fetch_max_retries"] = retries
        with patch("urllib.request.urlopen", side_effect=effects) as request, \
                patch("time.sleep") as sleep, contextlib.redirect_stderr(io.StringIO()):
            result = self.namespace["fetch_url"]("test-source")
        return result, request.call_count, sleep

    def test_transient_dns_recovers(self):
        result, calls, sleep = self.fetch([
            urllib.error.URLError("DNS"), urllib.error.URLError("DNS"), self.response])
        self.assertEqual((result, calls), ("content", 3))
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [1, 2])

    def test_outage_exhausts_retries(self):
        result, calls, sleep = self.fetch(urllib.error.URLError("DNS"))
        self.assertEqual((result, calls), (None, 4))
        self.assertEqual(sleep.call_count, 3)

    def test_http_and_timeout_policy(self):
        for error in [TimeoutError("timeout"),
                      urllib.error.HTTPError("test-source", 429, "busy", {}, None),
                      urllib.error.HTTPError("test-source", 503, "busy", {}, None)]:
            with self.subTest(error=error):
                self.assertEqual(self.fetch([error, self.response])[:2], ("content", 2))
        missing = urllib.error.HTTPError("test-source", 404, "missing", {}, None)
        result, calls, sleep = self.fetch(missing)
        self.assertEqual((result, calls, sleep.call_count), (None, 1, 0))

    def test_backoff_cap_and_no_retries(self):
        result, calls, sleep = self.fetch(TimeoutError("timeout"), retries=6)
        self.assertEqual((result, calls), (None, 7))
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [1, 2, 4, 8, 10, 10])
        self.assertEqual(self.fetch(TimeoutError("timeout"), retries=0)[:2], (None, 1))


class SourceIsolationTests(unittest.TestCase):
    def run_sources(self, source_types, fetch_effects, import_ok=True, dry_run=False, env=None):
        sources = [{"id": f"source-{i}", "type": kind, "url": f"source-{i}"}
                   for i, kind in enumerate(source_types)]
        yaml = types.ModuleType("yaml")
        yaml.safe_load = lambda _: {"sources": sources}
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'{"status":"ok"}'
        fetches = iter(fetch_effects)

        def urlopen(target, **kwargs):
            if isinstance(target, str):
                effect = next(fetches)
                if isinstance(effect, Exception):
                    raise effect
                fetched = MagicMock()
                fetched.__enter__.return_value.read.return_value = effect
                return fetched
            if not import_ok:
                raise urllib.error.URLError("import unavailable")
            return response

        output = io.StringIO()
        errors = io.StringIO()
        status_dir = tempfile.TemporaryDirectory(prefix="sync-status-")
        self.addCleanup(status_dir.cleanup)
        self.status_path = Path(status_dir.name) / "status.json"
        args = [str(SCRIPT), "sources", "", str(dry_run).lower(), "", "", "", "."]
        with patch.dict(sys.modules, {"yaml": yaml}), patch.object(sys, "argv", args), \
                patch.dict(os.environ, {"KNOWLEDGE_FETCH_MAX_RETRIES": "0",
                                        "AIDB_IMPORT_MAX_RETRIES": "0",
                                        "AIDB_IMPORT_DELAY_MS": "0",
                                        "KNOWLEDGE_SYNC_STATUS_FILE": str(self.status_path),
                                        **(env or {})}), \
                patch("builtins.open", mock_open()), patch("urllib.request.Request"), \
                patch("urllib.request.urlopen", side_effect=urlopen), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            with self.assertRaises(SystemExit) as exited:
                exec(compile(PROGRAM, str(SCRIPT), "exec"), {})
        self.stderr = errors.getvalue()
        return exited.exception.code, output.getvalue()

    def load_status(self):
        return json.loads(self.status_path.read_text())

    def test_mixed_sources_continue(self):
        code, output = self.run_sources(["github_repo", "url"],
                                        [urllib.error.URLError("DNS"), b"content"],
                                        env={"KNOWLEDGE_SYNC_DEGRADED_MAX_PCT": "60"})
        self.assertEqual(code, 0)
        self.assertIn("synced=1 skipped=0 fetch_failed=1", output)

    def test_total_outage_fails(self):
        code, output = self.run_sources(["github_repo", "url"],
                                        [urllib.error.URLError("DNS"), TimeoutError("timeout")])
        self.assertEqual(code, 1)
        self.assertIn("synced=0 skipped=0 fetch_failed=2", output)

    def test_import_failure_fails(self):
        code, output = self.run_sources(["url"], [b"content"], import_ok=False)
        self.assertEqual(code, 1)
        self.assertIn("synced=0 skipped=1 fetch_failed=0", output)

    def test_empty_and_dry_runs_succeed(self):
        self.assertEqual(self.run_sources([], [])[0], 0)
        code, output = self.run_sources(["github_repo", "url"], [], dry_run=True)
        self.assertEqual(code, 0)
        self.assertIn("synced=0 skipped=0 fetch_failed=0", output)


def NOT_FOUND():
    return urllib.error.HTTPError("u", 404, "missing", Message(), None)


class DegradedTests(SourceIsolationTests):
    """DEGRADED (minority of upstream failures) exits 0; FAILED exits 1. No network, stubbed fetch/import."""

    def many(self, total, failing):
        kinds = ["url"] * total
        effects = [NOT_FOUND() if i < failing else b"content"
                   for i in range(total)]
        return self.run_sources(kinds, effects)

    def test_all_ok_exits_zero_status_ok(self):
        code, _ = self.many(4, 0)
        self.assertEqual(code, 0)
        status = self.load_status()
        self.assertEqual((status["status"], status["failed_sources"]), ("ok", []))

    def test_minority_failure_is_degraded_exit_zero(self):
        code, output = self.many(513, 8)
        self.assertEqual(code, 0)
        self.assertIn("DEGRADED: 8 of 513", output)
        status = self.load_status()
        self.assertEqual((status["status"], status["failed_count"], status["synced"]), ("degraded", 8, 505))
        self.assertEqual(len(status["failed_sources"]), 8)
        self.assertEqual(status["failed_sources"][0]["reason"], "HTTP 404")
        self.assertEqual(self.stderr.count("WARN: source failed:"), 8)

    def test_above_threshold_fails(self):
        code, _ = self.many(4, 2)
        self.assertEqual(code, 1)
        self.assertEqual(self.load_status()["status"], "failed")

    def test_threshold_env_override(self):
        kinds = ["url"] * 4
        effects = [NOT_FOUND(), b"c", b"c", b"c"]
        self.assertEqual(self.run_sources(kinds, effects, env={"KNOWLEDGE_SYNC_DEGRADED_MAX_PCT": "10"})[0], 1)

    def test_zero_synced_fails(self):
        code, _ = self.many(2, 2)
        self.assertEqual(code, 1)
        self.assertEqual(self.load_status()["reason"], "no source synced")

    def test_import_connectivity_error_fails_even_when_minority(self):
        code, _ = self.run_sources(["url"], [b"content"], import_ok=False)
        self.assertEqual(code, 1)
        self.assertIn("AIDB", self.load_status()["failed_sources"][0]["reason"])

    def test_silent_github_source_reports_reason(self):
        # An empty 200 response used to be skipped with no reason; it must now be named.
        code, _ = self.run_sources(["github_repo", "url", "url", "url", "url"],
                                   [b"", b"c", b"c", b"c", b"c"])
        self.assertEqual(code, 0)
        failed = self.load_status()["failed_sources"]
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0]["type"], "github_repo")
        self.assertIn("empty response", failed[0]["reason"])
        self.assertIn("source failed: source-0", self.stderr)

    def test_dry_run_writes_no_status(self):
        self.run_sources(["url"], [], dry_run=True)
        self.assertFalse(self.status_path.exists())

    def test_github_raw_uses_default_branch(self):
        urls = []
        namespace: dict = {"fetch_url": lambda url: urls.append(url) or "x"}
        gh = [n for n in ast.parse(PROGRAM).body if isinstance(n, ast.FunctionDef) and n.name == "gh_raw"]
        exec(ast.unparse(gh[0]), namespace)
        namespace["gh_raw"]("mitre-attack/attack-stix-data", "README.md")
        self.assertIn("/HEAD/README.md", urls[0])


if __name__ == "__main__":
    unittest.main()
