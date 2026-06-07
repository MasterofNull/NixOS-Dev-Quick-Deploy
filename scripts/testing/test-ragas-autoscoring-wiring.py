#!/usr/bin/env python3
"""
Phase 137 regression: RAGAS auto-scoring wired into handle_query.

Checks that http_server_impl.py fires eval_runner RAGAS calls at 20% sample
rate just before the trace commit. No live server required — static analysis +
unit mock.
"""
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call

REPO_ROOT = Path(__file__).resolve().parents[2]
COORDINATOR = REPO_ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator"
sys.path.insert(0, str(COORDINATOR))


class TestRagasAutoscoringWiring(unittest.TestCase):

    def test_phase137_block_present_in_source(self):
        """Static: Phase 137 comment and fire-and-forget block must exist."""
        src = (COORDINATOR / "http_server_impl.py").read_text(encoding="utf-8")
        self.assertIn("Phase 137", src, "Phase 137 RAGAS auto-scoring block missing")
        self.assertIn("_ragas_score", src, "_ragas_score coroutine missing")
        self.assertIn("score_answer_relevance", src, "answer_relevance call missing")
        self.assertIn("score_context_precision", src, "context_precision call missing")
        self.assertIn("record_query_metrics", src, "record_query_metrics call missing")

    def test_sample_rate_is_20pct(self):
        """Static: sample gate must be < 0.20."""
        src = (COORDINATOR / "http_server_impl.py").read_text(encoding="utf-8")
        self.assertIn("< 0.20", src, "20% sample gate not found")

    def test_result_docs_extraction_pattern(self):
        """Static: result["results"] extraction using all three result key variants."""
        src = (COORDINATOR / "http_server_impl.py").read_text(encoding="utf-8")
        self.assertIn("combined_results", src)
        self.assertIn("semantic_results", src)
        self.assertIn("keyword_results", src)

    def test_compile_clean(self):
        """http_server_impl.py must compile without errors."""
        import py_compile
        try:
            py_compile.compile(str(COORDINATOR / "http_server_impl.py"), doraise=True)
        except py_compile.PyCompileError as exc:
            self.fail(f"Compile error: {exc}")

    def test_ragas_score_fn_callable(self):
        """eval_runner module must expose score_answer_relevance and record_query_metrics."""
        import eval_runner  # noqa: PLC0415
        self.assertTrue(callable(getattr(eval_runner, "score_answer_relevance", None)))
        self.assertTrue(callable(getattr(eval_runner, "score_context_precision", None)))
        self.assertTrue(callable(getattr(eval_runner, "record_query_metrics", None)))

    def test_ragas_score_fn_signatures(self):
        """score_answer_relevance takes (query, response); score_context_precision takes (docs)."""
        import inspect
        import eval_runner  # noqa: PLC0415
        ar_sig = inspect.signature(eval_runner.score_answer_relevance)
        self.assertIn("query", ar_sig.parameters)
        self.assertIn("response", ar_sig.parameters)
        cp_sig = inspect.signature(eval_runner.score_context_precision)
        self.assertIn("retrieved_docs", cp_sig.parameters)


if __name__ == "__main__":
    unittest.main(verbosity=2)
