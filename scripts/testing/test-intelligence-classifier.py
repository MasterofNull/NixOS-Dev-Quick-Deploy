#!/usr/bin/env python3
"""scripts/testing/test-intelligence-classifier.py

Unit tests for Hype vs. Facts vs. Signal classification contract and schema.
"""

from __future__ import annotations
import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "config" / "schemas" / "intelligence-classification.schema.json"
PROMPT_PATH = REPO_ROOT / "prompts" / "intelligence" / "hype-facts-signal.prompt.txt"

CANONICAL_LABELS = ("hype", "facts", "signal")

GOLDEN_EXAMPLES = [
    {
        "item_id": "test-hype-01",
        "source": "https://twitter.com/example/status/123",
        "title": "New stealth AGI framework replaces all software engineers with zero setup",
        "category": "hype",
        "confidence": 0.99,
        "rationale": "Unsubstantiated marketing claim with no repo, no ablation study, and no reproducible proof.",
        "reproducible_evidence": False,
        "recommended_action": "DISCARD",
        "target_rag_collection": None,
    },
    {
        "item_id": "test-fact-01",
        "source": "https://github.com/ggml-org/llama.cpp/releases/tag/b3820",
        "title": "llama.cpp release b3820 adds support for GBNF grammar whitespace trimming",
        "category": "facts",
        "confidence": 0.95,
        "rationale": "Verified upstream release with commit hash, changelog, and measurable parser behavior.",
        "reproducible_evidence": True,
        "recommended_action": "LOG_MAINTENANCE",
        "target_rag_collection": None,
    },
    {
        "item_id": "test-signal-01",
        "source": "https://arxiv.org/abs/2402.xxxx",
        "title": "Process Reward Models with Step-Level Value Verification in Multi-Agent Code Generation",
        "category": "signal",
        "confidence": 0.98,
        "rationale": "Demonstrates a +14% pass@1 improvement on SWE-bench using deterministic step-level verification gates.",
        "reproducible_evidence": True,
        "recommended_action": "SEED_RAG",
        "target_rag_collection": "best-practices",
    },
]


class TestIntelligenceClassifier(unittest.TestCase):
    def test_schema_exists_and_valid(self):
        self.assertTrue(SCHEMA_PATH.is_file(), f"Schema missing: {SCHEMA_PATH}")
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(schema.get("title"), "IntelligenceClassification")
        self.assertIn("category", schema.get("required", []))

    def test_prompt_template_exists(self):
        self.assertTrue(PROMPT_PATH.is_file(), f"Prompt missing: {PROMPT_PATH}")
        content = PROMPT_PATH.read_text(encoding="utf-8")
        for label in CANONICAL_LABELS:
            self.assertIn(f'"{label}"', content)

    def test_labels_match_live_consumer(self):
        # aq-durable-sweeper reads classification["category"] and counts these exact lowercase labels.
        sweeper = (REPO_ROOT / "scripts" / "ai" / "aq-durable-sweeper").read_text(encoding="utf-8")
        for label in CANONICAL_LABELS:
            self.assertIn(f'category == "{label}"', sweeper)
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(set(schema["properties"]["category"]["enum"]), set(CANONICAL_LABELS))

    def test_golden_examples_conformance(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        allowed_classes = set(schema["properties"]["category"]["enum"])
        allowed_actions = set(schema["properties"]["recommended_action"]["enum"])

        for ex in GOLDEN_EXAMPLES:
            self.assertIn(ex["category"], allowed_classes)
            self.assertIn(ex["recommended_action"], allowed_actions)
            self.assertTrue(0.0 <= ex["confidence"] <= 1.0)
            self.assertIsInstance(ex["reproducible_evidence"], bool)
            self.assertIsInstance(ex["rationale"], str)
            self.assertGreater(len(ex["rationale"]), 10)


if __name__ == "__main__":
    unittest.main()
