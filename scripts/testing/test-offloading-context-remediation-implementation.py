#!/usr/bin/env python3
"""Regression checks for 6.3, 7.2, and 9.2 implementation primitives."""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HYBRID_DIR = ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator"
MCP_ROOT = ROOT / "ai-stack" / "mcp-servers"


def load_module(name: str, path: Path):
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
    with tempfile.TemporaryDirectory(prefix="phase-6-7-9-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        os.environ["QUALITY_ASSURANCE_STATE"] = str(tmp_path / "quality")
        os.environ["GAP_REMEDIATION_STATE"] = str(tmp_path / "remediation")
        os.environ["ADVANCED_FEATURES_STATE"] = str(tmp_path / "advanced")
        os.environ["AI_STRICT_ENV"] = "false"
        for base in ("quality", "remediation", "advanced/offloading", "advanced/efficiency", "advanced/capability-gap"):
            (tmp_path / base).mkdir(parents=True, exist_ok=True)

        sys.path.insert(0, str(HYBRID_DIR))
        sys.path.insert(0, str(MCP_ROOT))
        sys.path.insert(0, str(ROOT / "ai-stack" / "capability-gap"))

        quality_assurance = load_module(
            "phase_quality_assurance",
            ROOT / "ai-stack" / "offloading" / "quality_assurance.py",
        )
        context_management = load_module(
            "phase_context_management",
            ROOT / "ai-stack" / "efficiency" / "context_management.py",
        )
        gap_detection = importlib.import_module("gap_detection")
        gap_remediation = load_module(
            "phase_gap_remediation",
            ROOT / "ai-stack" / "capability-gap" / "gap_remediation.py",
        )
        advanced = load_module(
            "phase_advanced_features_extra",
            HYBRID_DIR / "advanced_features.py",
        )

        fallback_manager = quality_assurance.LocalFallbackManager(tmp_path / "quality")
        fallback_manager.record_remote_failure(
            query="debug remote timeout in bounded workflow",
            agent_id="remote-1",
            reason="timeout from remote provider",
            quality_score=0.2,
        )
        fallback_manager.record_remote_failure(
            query="debug remote timeout in bounded workflow",
            agent_id="remote-1",
            reason="provider unavailable",
            quality_score=0.25,
        )
        fallback = fallback_manager.recommend_fallback(
            query="debug remote timeout in bounded workflow",
            failed_agent_id="remote-1",
        )
        assert_true(fallback["fallback_to_local"], "quality assurance should recommend local fallback after repeated remote failures")

        chunks = [
            context_management.ContextChunk("a", "Critical deployment error requires rollback action", 12, source="error"),
            context_management.ContextChunk("b", "General reference documentation for old API behavior", 14, source="docs"),
            context_management.ContextChunk("c", "Warning: authentication issue in production rollout", 11, source="warning"),
        ]
        pruner = context_management.ContextPruner()
        kept, pruned = pruner.prune(chunks, max_tokens=24, query="deployment authentication rollback")
        summarizer = context_management.HierarchicalSummarizer()
        summary = summarizer.summarize(
            "Critical rollout error occurred. The system must rollback safely. Additional detail explains the operator workflow.",
            target_tokens=12,
        )
        scorer = context_management.RelevanceScorer()
        windows = context_management.SlidingWindowManager(window_size=10).create_windows(
            "One two three four five. Six seven eight nine ten. Eleven twelve thirteen fourteen fifteen. Sixteen seventeen eighteen nineteen twenty.",
            overlap=2,
        )
        reuser = context_management.ContextReuser()
        reuser.cache_context("deployment rollback", "cached deployment rollback context")
        reused = reuser.get_cached_context("deployment rollback")
        assert_true(len(kept) > 0 and len(pruned) > 0, "context pruner should keep high-value chunks and prune the rest")
        assert_true(summary.levels >= 1, "hierarchical summarizer should compress long context")
        assert_true(scorer.score_context("authentication rollback", chunks[2].content) > 0, "relevance scorer should detect related context")
        assert_true(len(windows) >= 2, "sliding window manager should split long documents")
        assert_true(reused is not None, "context reuser should serve similar cached context")

        gap = gap_detection.CapabilityGap(
            gap_id="gap-1",
            gap_type=gap_detection.GapType.KNOWLEDGE,
            severity=gap_detection.GapSeverity.MEDIUM,
            description="Missing knowledge about staged deployment verification",
        )
        orchestrator = gap_remediation.RemediationOrchestrator(tmp_path / "remediation")
        remediation = await orchestrator.execute_plan(
            gap,
            topic="staged_deployment_verification",
            examples=[{"steps": ["collect signals", "compare thresholds", "decide next action"]}],
        )
        assert_true(remediation.success, "remediation orchestrator should produce a knowledge artifact")
        assert_true(remediation.validation_passed, "remediation result should validate created artifacts")

        await advanced.record_remote_failure(
            query="retry bounded local workflow",
            response="provider timeout",
            reason="timeout from upstream provider",
            agent_id="remote-x",
            quality_score=0.1,
        )
        await advanced.record_remote_failure(
            query="retry bounded local workflow",
            response="provider unavailable",
            reason="provider unavailable",
            agent_id="remote-x",
            quality_score=0.1,
        )
        advanced_fallback = await advanced.recommend_local_fallback(
            query="retry bounded local workflow",
            failed_agent_id="remote-x",
        )
        summarized = await advanced.summarize_long_context(
            "Critical issue happened. The operator must review logs. A safe rollback should follow once the threshold is crossed.",
            target_tokens=10,
        )
        relevance = await advanced.score_context_relevance(
            "rollback threshold",
            "A rollback should happen once the threshold is crossed.",
        )
        reusable_cache = await advanced.cache_reusable_context("rollback threshold", "reused context block")
        reusable_hit = await advanced.get_reusable_context("rollback threshold")
        imported = await advanced.import_gap_knowledge(
            topic="deployment thresholds",
            reason="Missing deployment threshold knowledge",
            source_urls=["https://example.invalid/deploy-thresholds"],
        )
        synthesized = await advanced.synthesize_gap_skill(
            skill_name="deployment_verification",
            examples=[{"steps": ["collect metrics", "check error budget", "approve rollout"]}],
            reason="Need reusable deployment verification skill",
        )
        extracted = await advanced.extract_gap_pattern(
            pattern_name="safe_rollout_pattern",
            instances=[{"phase": "verify", "action": "check metrics"}, {"phase": "rollback", "action": "restore stable version"}],
            reason="Need generalized rollout remediation pattern",
        )
        assert_true(advanced_fallback["fallback_to_local"], "advanced feature bridge should recommend local fallback")
        assert_true(summarized["summary_tokens"] <= summarized["original_tokens"], "advanced summarizer should reduce or preserve token count")
        assert_true(relevance["score"] > 0, "advanced relevance scorer should score matching context")
        assert_true(reusable_cache["stored"] and reusable_hit["hit"], "advanced bridge should cache and reuse context")
        assert_true(imported["validation_passed"], "knowledge import bridge should create a valid artifact")
        assert_true(synthesized["validation_passed"], "skill synthesis bridge should create a valid artifact")
        assert_true(extracted["validation_passed"], "pattern extraction bridge should create a valid artifact")

    print("PASS: offloading, context management, and remediation implementation primitives are operational")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
