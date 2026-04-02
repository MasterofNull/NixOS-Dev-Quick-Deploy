#!/usr/bin/env python3
"""Regression checks for advanced hybrid-coordinator implementation primitives."""

from __future__ import annotations

import asyncio
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
    with tempfile.TemporaryDirectory(prefix="advanced-features-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        os.environ["ADVANCED_FEATURES_STATE"] = str(tmp_path / "state")
        os.environ["AI_STRICT_ENV"] = "false"
        for subdir in ("offloading", "efficiency", "capability-gap", "learning"):
            (tmp_path / "state" / subdir).mkdir(parents=True, exist_ok=True)
        sys.path.insert(0, str(HYBRID_DIR))
        sys.path.insert(0, str(MCP_ROOT))

        advanced = load_module("advanced_features_test", HYBRID_DIR / "advanced_features.py")

        pool = advanced.get_agent_pool()
        pool.record_request("mistral-7b-free", success=True, latency_ms=800, quality_score=0.82)
        pool.record_request("gemma-7b-free", success=False, latency_ms=1800, quality_score=0.25)
        pool.record_request("mistral-small-paid", success=True, latency_ms=900, quality_score=0.78)

        quality_profiles = await advanced.get_agent_quality_profiles()
        assert_true(len(quality_profiles["profiles"]) >= 3, "agent pool should expose quality profiles")
        failover = await advanced.select_failover_remote_agent(min_composite_score=0.7)
        assert_true(failover["selected"], "failover selection should find a fallback agent")
        benchmarks = await advanced.get_agent_benchmarks()
        assert_true(benchmarks["best_agent"] is not None, "benchmarks should report a best agent")

        long_prompt = (
            "Please provide a very detailed explanation of the implementation strategy. "
            "Please provide a very detailed explanation of the implementation strategy. "
            "The service must preserve API compatibility and should mention any error conditions. "
            "The service must preserve API compatibility and should mention any error conditions. "
            "```python\nprint('keep code')\n```"
        )
        compressed = await advanced.compress_prompt(long_prompt, strategy="stopword_removal")
        semantic = await advanced.semantic_compress_prompt(long_prompt, max_sentences=2)
        assert_true(compressed["tokens_saved"] > 0, "basic compression should save tokens")
        assert_true("keep code" in semantic["compressed_text"], "semantic compression should preserve code blocks")

        optimized = await advanced.optimize_prompt_template(
            task_type="implementation",
            task="build a readiness check",
            context="Focus on repo-only validation",
        )
        dynamic = await advanced.generate_dynamic_prompt(
            "debug repeated failure in routing path",
            context="Recent runs failed in delegated execution",
        )
        variant_result = await advanced.record_prompt_variant_outcome(
            task_type=optimized["task_type"],
            variant_id=optimized["variant_id"],
            score=0.9,
        )
        ab_stats = await advanced.get_prompt_ab_stats()
        assert_true("prompt" in optimized, "template optimizer should generate a prompt")
        assert_true(dynamic["task_type"] == "debugging", "dynamic prompt generation should infer task type")
        assert_true(variant_result["uses"] >= 1, "A/B stats should record outcomes")
        assert_true("implementation" in ab_stats["variants"], "A/B stats should include implementation variants")

        pattern_analysis = await advanced.analyze_failure_patterns(
            query="run the missing tool against the repo",
            response="The required tool is not available and the workflow failed to complete.",
            error_message="tool not available",
            user_feedback={"negative": True, "score": -1},
        )
        gap = await advanced.detect_capability_gap(
            query="run the missing tool against the repo",
            response="The required tool is not available and the workflow failed to complete.",
            outcome="failure",
            error_message="tool not available",
            user_feedback={"negative": True, "score": -1},
        )
        assert_true(pattern_analysis["gap_type"] == "tool_missing", "failure analysis should classify tool gaps")
        assert_true(gap["gap_detected"], "gap detection should persist failed interactions")
        gap_stats = await advanced.get_capability_gap_stats()
        assert_true(gap_stats["total_gaps"] >= 1, "gap stats should include persisted detections")

        readiness = await advanced.get_advanced_features_readiness()
        phase6 = readiness["readiness"]["phase_6_offloading"]
        phase7 = readiness["readiness"]["phase_7_efficiency"]
        phase9 = readiness["readiness"]["phase_9_capability_gap"]
        assert_true(phase6["status"] == "implementation_exists", "readiness should mark repo-only implementation state")
        assert_true(phase7["ab_variants"] >= 1, "readiness should report prompt A/B variants")
        assert_true(phase9["failure_patterns"] >= 1, "readiness should report failure-pattern coverage")

    print("PASS: advanced feature implementation primitives are operational")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
