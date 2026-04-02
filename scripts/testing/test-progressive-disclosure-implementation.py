#!/usr/bin/env python3
"""Regression checks for progressive-disclosure implementation modules."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load_module(name: str, relative_path: str):
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def main() -> int:
    multi_tier = load_module(
        "progressive_multi_tier",
        "ai-stack/progressive-disclosure/multi_tier_loading.py",
    )
    lazy_context = load_module(
        "progressive_lazy_context",
        "ai-stack/progressive-disclosure/lazy_context.py",
    )
    relevance = load_module(
        "progressive_relevance",
        "ai-stack/progressive-disclosure/relevance_prediction.py",
    )

    with tempfile.TemporaryDirectory(prefix="progressive-disclosure-") as tmp_dir:
        repo = multi_tier.ContextRepository(Path(tmp_dir) / "context")
        selector = multi_tier.TierSelector()
        loader = multi_tier.MultiTierLoader(repo)
        learner = multi_tier.AdaptiveTierLearner()

        selection = selector.select_tier(
            "Implement a complete deployment troubleshooting workflow with rollback guidance",
            context_budget=1800,
        )
        assert_true(selection.selected_tier in multi_tier.ContextTier, "selector should return a valid tier")
        should_escalate, next_tier = selector.should_escalate(
            current_tier=multi_tier.ContextTier.BRIEF,
            query_satisfied=False,
            follow_up_questions=2,
        )
        should_deescalate, prev_tier = selector.should_deescalate(
            current_tier=multi_tier.ContextTier.DETAILED,
            query_satisfied=True,
            excess_context=0.7,
        )
        assert_true(should_escalate and next_tier is not None, "selector should escalate on unsatisfied follow-ups")
        assert_true(should_deescalate and prev_tier is not None, "selector should de-escalate when context was excessive")

        load_result = await loader.load_context(
            query="How do I debug deployment issues?",
            category="deployment",
            tier=multi_tier.ContextTier.STANDARD,
        )
        learner.record_outcome(
            query="How do I debug deployment issues?",
            tier_used=load_result.tier,
            success=True,
            tokens_used=load_result.total_tokens,
            response_quality=0.9,
        )
        recommended = learner.recommend_tier(query_length=7)
        assert_true(load_result.total_tokens > 0, "multi-tier loader should load non-empty context")
        assert_true(recommended in multi_tier.ContextTier, "adaptive learner should recommend a valid tier")

        graph = lazy_context.ContextDependencyGraph()
        graph.add_node(lazy_context.ContextNode("intro", "Intro", tokens=20))
        graph.add_node(lazy_context.ContextNode("setup", "Setup", {"intro"}, tokens=40))
        graph.add_node(lazy_context.ContextNode("config", "Config", {"setup"}, tokens=60))
        graph.add_node(lazy_context.ContextNode("errors", "Errors", {"config"}, tokens=80))
        loader2 = lazy_context.LazyContextLoader(graph)
        expander = lazy_context.IncrementalExpander(loader2)
        prefetcher = lazy_context.ContextPrefetcher(loader2)

        loaded = await loader2.load(["errors", "config", "setup", "intro"])
        expanded = await expander.expand_context(
            {"intro"},
            lambda node: node.tokens <= 80,
            max_expansions=2,
        )
        prefetcher.record_access("intro", "setup")
        prefetcher.record_access("intro", "config")
        prefetched = await prefetcher.prefetch("intro", max_prefetch=2)
        assert_true("errors" in loaded, "lazy loader should resolve dependencies and load requested nodes")
        assert_true(len(expanded) > 1, "incremental expansion should add dependent nodes")
        assert_true(len(prefetched) >= 1, "prefetcher should predict likely next nodes")

        predictor = relevance.RelevancePredictor()
        feedback = relevance.RelevanceFeedbackLoop(predictor)
        filterer = relevance.NegativeContextFilter(threshold=0.15)
        scores = predictor.predict_batch(
            "How do I fix deployment errors?",
            {
                "deploy": "Deployment guide with troubleshooting and rollback steps",
                "api": "API reference for unrelated endpoints",
                "security": "Security hardening for production rollouts",
            },
        )
        kept = filterer.filter(scores)
        for score in scores:
            feedback.record_feedback(
                query="How do I fix deployment errors?",
                context_id=score.context_id,
                predicted_score=score.score,
                actual_usefulness=0.85 if score.context_id == "deploy" else 0.2,
            )
        feedback.update_model()
        assert_true(scores[0].score >= scores[-1].score, "relevance predictor should rank contexts")
        assert_true(len(kept) >= 1, "negative filter should keep at least one context")
        assert_true(len(feedback.feedback) == len(scores), "feedback loop should record usefulness feedback")

    print("PASS: progressive-disclosure implementation primitives are operational")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
