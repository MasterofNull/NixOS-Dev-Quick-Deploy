#!/usr/bin/env python3
"""Offline regression coverage for embedded knowledge-source fetch retries."""
import ast
import contextlib
import io
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import MagicMock, mock_open, patch
import urllib.error
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
    def run_sources(self, source_types, fetch_effects, import_ok=True, dry_run=False):
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
        args = [str(SCRIPT), "sources", "", str(dry_run).lower(), "", "", "", "."]
        with patch.dict(sys.modules, {"yaml": yaml}), patch.object(sys, "argv", args), \
                patch.dict(os.environ, {"KNOWLEDGE_FETCH_MAX_RETRIES": "0",
                                        "AIDB_IMPORT_MAX_RETRIES": "0",
                                        "AIDB_IMPORT_DELAY_MS": "0"}), \
                patch("builtins.open", mock_open()), patch("urllib.request.Request"), \
                patch("urllib.request.urlopen", side_effect=urlopen), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as exited:
                exec(compile(PROGRAM, str(SCRIPT), "exec"), {})
        return exited.exception.code, output.getvalue()

    def test_mixed_sources_continue(self):
        code, output = self.run_sources(["github_repo", "url"],
                                        [urllib.error.URLError("DNS"), b"content"])
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


if __name__ == "__main__":
    unittest.main()
