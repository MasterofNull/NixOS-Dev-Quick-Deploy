#!/usr/bin/env python3
"""Focused regression checks for semantic compression primitives."""

from __future__ import annotations

import asyncio
import importlib.util
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "ai-stack" / "efficiency" / "semantic_compression.py"


def load_module():
    spec = importlib.util.spec_from_file_location("semantic_compression", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Unable to load module from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


SAMPLE_TEXT = """
# Error Recovery Runbook

Critical: Restore the coordinator before touching downstream workers.

The first recovery step is to inspect the failing unit, confirm whether the
problem is local configuration drift or a remote provider outage, and capture
the exact error text for the incident log.

Important: If the service is restarting in a loop, gather recent journal lines
and current unit properties before attempting a rebuild.

Additional background information explains the historical architecture and
includes examples, references, and optional cleanup notes that can be trimmed
when context is tight.

Warning: Do not rotate secrets unless the failure path shows exposure or auth
breakage. Secret churn during a routing outage will usually compound recovery.

The final section documents optional examples and reference snippets for future
training material, but those details are not necessary for the first response.
""".strip()

LONG_TEXT = "\n\n".join(
    [
        (
            "Critical recovery guidance requires inspecting the failing unit, "
            "capturing the precise error output, preserving recent journal lines, "
            "and verifying whether the outage is caused by local configuration drift, "
            "provider instability, or secret-path breakage before attempting a rebuild. "
            "This section also explains the expected validation commands, rollback guardrails, "
            "and the reasons operator discipline matters during service recovery."
        )
        for _ in range(6)
    ]
)


async def test_compression_and_stats(module) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        compressor = module.SemanticCompressor(output_dir=Path(tmpdir))
        compressed, metadata = await compressor.compress(
            LONG_TEXT,
            target_tokens=180,
            query="switchboard restart failure and service recovery",
        )

        assert_true(metadata["original_tokens"] > metadata["final_tokens"], "compression should reduce token count")
        assert_true(metadata["chunks_kept"] >= 1, "compression plan should retain at least one chunk")
        assert_true("Critical recovery guidance" in compressed, "compressed output should retain important guidance")

        stats = compressor.get_stats()
        assert_true(stats["compressions"] == 1, "compressor should track compression count")
        assert_true(stats["total_tokens_saved"] > 0, "compressor should track tokens saved")


def test_dynamic_prompt_generation(module) -> None:
    generator = module.DynamicPromptGenerator()

    simple_prompt, simple_meta = generator.generate("Fix typo in README")
    complex_prompt, complex_meta = generator.generate(
        "Implement a new authentication service with OAuth2 integration",
        context="Existing API gateway and session middleware are already deployed.",
        requirements="Support token refresh and provider fallback.",
    )
    expert_prompt, expert_meta = generator.generate(
        "Design a scalable distributed architecture for secure multi-region failover",
        context="The system handles AI coordinator traffic and remote tool routing.",
        constraints="Keep cost growth bounded and maintain strict auth.",
        criteria="Recovery within minutes under regional outages.",
    )

    assert_true(simple_meta["complexity"] == "simple", "simple tasks should stay compact")
    assert_true(complex_meta["complexity"] == "complex", "implementation tasks should classify as complex")
    assert_true(expert_meta["complexity"] == "expert", "architecture tasks should classify as expert")
    assert_true(len(expert_prompt) > len(simple_prompt), "higher-complexity prompts should expand structure")


def test_ab_testing_flow(module) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tester = module.PromptABTester(output_dir=Path(tmpdir), min_trials=6, confidence_threshold=0.80)
        variant_a = tester.create_variant("concise", "Keep the answer short and precise.")
        variant_b = tester.create_variant("detailed", "Explain each step, risk, and validation command in depth.")
        test_id = tester.create_test("concise-vs-detailed", variant_a, variant_b)

        for idx in range(3):
            chosen = tester.get_variant_to_test(test_id)
            assert_true(chosen in {variant_a.variant_id, variant_b.variant_id}, "allocator should return a known variant id")
            tester.record_result(test_id, chosen, success=True if idx != 1 else False)

        for _ in range(3):
            tester.record_result(test_id, variant_a.variant_id, success=True)
            tester.record_result(test_id, variant_b.variant_id, success=False)

        result = tester.evaluate_test(test_id)
        assert_true(result is not None, "test evaluation should return a result object")
        assert_true("Confidence:" in result.summary, "evaluation summary should expose confidence")
        assert_true(result.variant_a.trials > 0 and result.variant_b.trials > 0, "both variants should accumulate trials")


async def main() -> int:
    module = load_module()
    await test_compression_and_stats(module)
    test_dynamic_prompt_generation(module)
    test_ab_testing_flow(module)
    print("PASS: semantic compression primitives are operational")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
