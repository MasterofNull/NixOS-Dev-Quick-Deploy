#!/usr/bin/env python3
"""Unit tests for scripts/ai/aq-local-review (Slice 1 — local-embed-context DESIGN.md).

Runs WITHOUT a real local model or embed/Qdrant server: network/subprocess calls
are monkeypatched or pointed at dead ports. Covers:
  (a) chunk_text — line-aware, cap-respecting, full coverage, over-cap single line.
  (b) fail-open — embed()/cache_* return None/False/[] cleanly against a dead
      endpoint, and the end-to-end review still completes using in-memory
      findings when the cache never comes up (map_chunk/reduce_findings stubbed
      to avoid any real local-model call).
  (c) --dry-run — prints a chunk plan and makes ZERO network/subprocess calls.
"""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from unittest import mock

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))  # .../scripts/testing
REPO_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))  # .../ (repo root)
MODULE_PATH = os.path.join(REPO_ROOT, "scripts", "ai", "aq-local-review")

_loader = SourceFileLoader("aq_local_review", MODULE_PATH)
alr = _loader.load_module()  # noqa: N816 — module under test, hyphenated path


class ChunkTextTests(unittest.TestCase):
    """(a) chunk_text: line-aware, cap-respecting, full coverage, over-cap line."""

    def test_respects_cap_for_uniform_lines(self):
        line = "x" * 10 + "\n"  # 11 chars/line
        text = line * 9
        chunks = alr.chunk_text(text, cap=25)
        # 2 lines (22 chars) fit under cap=25; a 3rd would push to 33 > 25.
        for c in chunks[:-1]:
            self.assertLessEqual(len(c), 25)
        self.assertEqual("".join(chunks), text)

    def test_covers_all_input_exactly(self):
        text = "alpha\nbeta\ngamma\ndelta\nepsilon\n" * 5
        chunks = alr.chunk_text(text, cap=17)
        self.assertEqual("".join(chunks), text)

    def test_never_splits_mid_line(self):
        lines = [f"line-{i}-content\n" for i in range(20)]
        text = "".join(lines)
        chunks = alr.chunk_text(text, cap=40)
        # Every original line must appear WHOLE inside exactly one chunk.
        reconstructed_lines = []
        for c in chunks:
            reconstructed_lines.extend(c.splitlines(keepends=True))
        self.assertEqual(reconstructed_lines, lines)

    def test_single_over_cap_line_becomes_its_own_chunk(self):
        huge_line = "z" * 500 + "\n"
        text = "short1\n" + huge_line + "short2\n"
        chunks = alr.chunk_text(text, cap=50)
        self.assertEqual("".join(chunks), text)
        # The huge line must not be merged with a neighbor nor split.
        huge_chunk = [c for c in chunks if huge_line in c]
        self.assertEqual(len(huge_chunk), 1)
        self.assertEqual(huge_chunk[0], huge_line)

    def test_empty_input(self):
        self.assertEqual(alr.chunk_text("", cap=100), [""])

    def test_no_trailing_newline_last_line_preserved(self):
        text = "one\ntwo\nthree-no-trailing-newline"
        chunks = alr.chunk_text(text, cap=6)
        self.assertEqual("".join(chunks), text)


class FailOpenTests(unittest.TestCase):
    """(b) embed()/cache_* fail open against an unreachable endpoint."""

    DEAD_URL = "http://127.0.0.1:1"  # port 1 — reserved, nothing listens, fast refusal

    def setUp(self):
        self._env_patch = mock.patch.dict(
            os.environ,
            {"AI_STACK_EMBED_ENDPOINT": self.DEAD_URL, "QDRANT_URL": self.DEAD_URL},
        )
        self._env_patch.start()

    def tearDown(self):
        self._env_patch.stop()

    def test_embed_returns_none_on_dead_endpoint(self):
        self.assertIsNone(alr.embed("some finding text", timeout=2.0))

    def test_cache_create_returns_false_on_dead_endpoint(self):
        self.assertFalse(alr.cache_create("local-review-test", 8, timeout=2.0))

    def test_cache_upsert_returns_false_on_dead_endpoint(self):
        self.assertFalse(alr.cache_upsert("local-review-test", 1, [0.1, 0.2], {"a": 1}, timeout=2.0))

    def test_cache_search_returns_none_on_dead_endpoint(self):
        self.assertIsNone(alr.cache_search("local-review-test", [0.1, 0.2], 5, timeout=2.0))

    def test_cache_delete_does_not_raise_on_dead_endpoint(self):
        alr.cache_delete("local-review-test", timeout=2.0)  # must not raise

    def test_review_proceeds_with_in_memory_findings_when_cache_dead(self):
        """End-to-end: cache never comes up (dead ports) but the review still
        completes using in-memory findings — map_chunk/reduce_findings are
        stubbed so no real local-model call happens."""
        captured_reduce_findings = {}

        def fake_map_chunk(target, i, n, question, chunk, timeout):
            return f"finding-for-chunk-{i}"

        def fake_reduce_findings(question, findings, timeout):
            captured_reduce_findings["findings"] = list(findings)
            captured_reduce_findings["question"] = question
            return "STUB VERDICT"

        text = ("relevant line about the topic\n" * 3 + "filler\n" * 3) * 4
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as tf:
            tf.write(text)
            target_path = tf.name
        try:
            with mock.patch.object(alr, "map_chunk", side_effect=fake_map_chunk), \
                 mock.patch.object(alr, "reduce_findings", side_effect=fake_reduce_findings):
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    rc = alr.main([
                        "--target", target_path,
                        "--question", "does this cover the topic?",
                        "--chunk-chars", "40",
                        "--timeout", "5",
                    ])
                self.assertEqual(rc, 0)
                self.assertIn("STUB VERDICT", stdout.getvalue())
                # Cache never came up (dead ports) -> reduce must see ALL
                # per-chunk findings, not a top-K subset from a live cache.
                chunks = alr.chunk_text(text, 40)
                self.assertEqual(len(captured_reduce_findings["findings"]), len(chunks))
                for i in range(1, len(chunks) + 1):
                    self.assertIn(f"finding-for-chunk-{i}", captured_reduce_findings["findings"])
        finally:
            os.unlink(target_path)


class DryRunTests(unittest.TestCase):
    """(c) --dry-run prints a chunk plan and makes ZERO network/subprocess calls."""

    def test_dry_run_makes_no_subprocess_or_network_calls(self):
        text = "one\ntwo\nthree\nfour\nfive\n" * 10
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as tf:
            tf.write(text)
            target_path = tf.name

        def boom(*a, **kw):
            raise AssertionError("subprocess.run must NOT be called during --dry-run")

        def boom_requests(*a, **kw):
            raise AssertionError("no network call must happen during --dry-run")

        try:
            with mock.patch("subprocess.run", side_effect=boom), \
                 mock.patch.object(alr.requests, "post", side_effect=boom_requests), \
                 mock.patch.object(alr.requests, "put", side_effect=boom_requests), \
                 mock.patch.object(alr.requests, "delete", side_effect=boom_requests):
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    rc = alr.main([
                        "--target", target_path,
                        "--question", "any question",
                        "--chunk-chars", "12",
                        "--dry-run",
                    ])
                out = stdout.getvalue()
                self.assertEqual(rc, 0)
                self.assertIn("dry-run", out)
                self.assertIn("chunk 1/", out)
        finally:
            os.unlink(target_path)

    def test_dry_run_json_reports_full_chunk_plan(self):
        text = "alpha\nbeta\ngamma\ndelta\n" * 5
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as tf:
            tf.write(text)
            target_path = tf.name

        def boom(*a, **kw):
            raise AssertionError("no subprocess/network call must happen during --dry-run --json")

        try:
            with mock.patch("subprocess.run", side_effect=boom), \
                 mock.patch.object(alr.requests, "post", side_effect=boom):
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    rc = alr.main([
                        "--target", target_path,
                        "--question", "any question",
                        "--chunk-chars", "15",
                        "--dry-run", "--json",
                    ])
                payload = json.loads(stdout.getvalue())
                self.assertEqual(rc, 0)
                self.assertTrue(payload["dry_run"])
                expected_chunks = alr.chunk_text(text, 15)
                self.assertEqual(payload["chunk_count"], len(expected_chunks))
                self.assertEqual(len(payload["chunks"]), len(expected_chunks))
                for entry in payload["chunks"]:
                    self.assertIn("prompt", entry)
                    self.assertIn("CHUNK", entry["prompt"])
        finally:
            os.unlink(target_path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
