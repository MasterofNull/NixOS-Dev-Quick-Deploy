#!/usr/bin/env python3
"""
Phase 137/139 regression: RAGAS auto-scoring + faithfulness wired into handle_query.

Checks that http_server_impl.py fires eval_runner RAGAS calls at 20% sample
rate and faithfulness scoring (Qwen-as-judge, 10% sample when enabled).
No live server required — static analysis + unit mock.
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

    def test_phase139_faithfulness_wiring(self):
        """Static: Phase 139 faithfulness call must be present in _ragas_score."""
        src = (COORDINATOR / "http_server_impl.py").read_text(encoding="utf-8")
        self.assertIn("Phase 139", src, "Phase 139 faithfulness block missing")
        self.assertIn("score_faithfulness_async", src, "faithfulness call missing")

    def test_faithfulness_context_extraction(self):
        """Static: context string must be built from docs content/text/snippet fields."""
        src = (COORDINATOR / "http_server_impl.py").read_text(encoding="utf-8")
        self.assertIn('"content"', src)
        self.assertIn('"snippet"', src)

    def test_faithfulness_fn_callable(self):
        """eval_runner.score_faithfulness_async must be callable."""
        import eval_runner  # noqa: PLC0415
        self.assertTrue(callable(getattr(eval_runner, "score_faithfulness_async", None)))

    def test_faithfulness_fn_signature(self):
        """score_faithfulness_async takes (query, context, response)."""
        import inspect
        import eval_runner  # noqa: PLC0415
        sig = inspect.signature(eval_runner.score_faithfulness_async)
        self.assertIn("query", sig.parameters)
        self.assertIn("context", sig.parameters)
        self.assertIn("response", sig.parameters)

    def test_faithfulness_passed_to_record(self):
        """Static: faithfulness variable (fs) must be passed to record_query_metrics."""
        src = (COORDINATOR / "http_server_impl.py").read_text(encoding="utf-8")
        self.assertIn("faithfulness=fs", src, "faithfulness=fs not passed to record_query_metrics")

    def test_phase141_context_precision_payload_nested(self):
        """Unit (Phase 141): score_context_precision handles Qdrant payload-nested docs."""
        import eval_runner  # noqa: PLC0415
        docs = [
            {"collection": "c", "score": 2.1, "payload": {"solution": "fix: use payload-nested"}},
            {"collection": "c", "score": 1.5, "payload": {"content": "some content"}},
            {"collection": "c", "score": 0.5, "payload": {}},
        ]
        cp = eval_runner.score_context_precision(docs)
        self.assertAlmostEqual(cp, 2 / 3, places=3, msg="2/3 docs have non-empty payload content")

    def test_phase141_context_precision_top_level_still_works(self):
        """Unit (Phase 141): score_context_precision still handles top-level content field."""
        import eval_runner  # noqa: PLC0415
        docs = [{"content": "hello"}, {"text": "world"}, {"content": ""}]
        cp = eval_runner.score_context_precision(docs)
        self.assertAlmostEqual(cp, 2 / 3, places=3)

    def test_phase141_faithfulness_context_uses_payload(self):
        """Static (Phase 141): faithfulness _doc_ctx helper references payload field."""
        src = (COORDINATOR / "http_server_impl.py").read_text(encoding="utf-8")
        self.assertIn("Phase 139/141", src)
        self.assertIn('d.get("payload")', src)
        self.assertIn('p.get("solution")', src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
