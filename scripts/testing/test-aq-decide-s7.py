#!/usr/bin/env python3
"""Unit tests for DEC-S7: T2 small LLM tier evaluation harness."""

import sys
import unittest
import tempfile
from pathlib import Path

# Add scripts/ai/lib to path
sys.path.insert(0, str(Path(__file__).parent.parent / "ai" / "lib"))
from aq_decide import evaluate_t2_candidate


class TestAqDecideT2(unittest.TestCase):
    def test_t2_candidate_defaults(self):
        res = evaluate_t2_candidate(model_name="qwen3-0.6b")
        self.assertEqual(res["candidate"], "qwen3-0.6b")
        self.assertEqual(res["param_count_b"], 0.6)
        self.assertTrue(res["within_param_limit"])
        self.assertIn("est_page_cache_mb", res)

    def test_t2_candidate_param_ceiling(self):
        res_7b = evaluate_t2_candidate(model_name="qwen3-7b", max_param_limit_b=4.0)
        self.assertEqual(res_7b["param_count_b"], 4.0)
        self.assertTrue(res_7b["within_param_limit"])

        # Exceeds custom limit
        res_exceeded = evaluate_t2_candidate(model_name="qwen3-7b", max_param_limit_b=2.0)
        self.assertFalse(res_exceeded["within_param_limit"])

    def test_t2_candidate_with_weights_fixture(self):
        with tempfile.NamedTemporaryFile(suffix=".gguf") as tmp:
            tmp.write(b"GGUF" + b"\x00" * 1024 * 1024)  # 1MB simulated weights
            tmp.flush()

            res = evaluate_t2_candidate(
                model_name="qwen3-1.7b",
                weights_path=tmp.name,
                max_param_limit_b=4.0,
            )
            self.assertTrue(res["model_present"])
            self.assertTrue(res["within_param_limit"])
            self.assertEqual(res["param_count_b"], 1.7)
            self.assertGreater(res["size_mb"], 0.9)
            self.assertEqual(res["evaluation_verdict"], "READY")
            self.assertTrue(res["constrained_logprob_ready"])


if __name__ == "__main__":
    unittest.main()
