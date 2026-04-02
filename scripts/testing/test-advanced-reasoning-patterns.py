#!/usr/bin/env python3
"""Focused regression coverage for advanced reasoning pattern primitives."""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATTERN_DIR = ROOT / "ai-stack" / "agentic-patterns"


def load_module(name: str):
    module_path = PATTERN_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    import sys
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


async def test_self_consistency() -> None:
    module = load_module("self_consistency")
    agent = module.SelfConsistencyAgent(
        sampler=lambda prompt, index: module.ConsistencyCandidate(
            answer="continue" if index < 3 else "retry",
            rationale=f"sample-{index}",
            confidence=0.9 if index == 0 else 0.6,
        ),
        samples=5,
    )
    result = await agent.solve("choose best lane")
    assert result.selected_answer == "continue"
    assert result.support_count == 3
    assert result.agreement_ratio == 0.6


async def test_plan_and_solve() -> None:
    module = load_module("plan_and_solve")

    async def planner(objective: str):
        return [
            {"description": f"analyze {objective}", "expected_output": "analysis"},
            {"description": "implement fix", "expected_output": "patch"},
        ]

    async def executor(step, context):
        return {
            "step": step.description,
            "previous_steps": len(context["completed_steps"]),
        }

    result = await module.PlanAndSolveAgent(planner=planner, executor=executor).solve("freeze issue")
    assert len(result.plan) == 2
    assert result.step_outputs[1]["output"]["previous_steps"] == 1
    assert result.final_answer["step"] == "implement fix"


async def test_chain_of_verification() -> None:
    module = load_module("chain_of_verification")

    async def verifier(claim: str):
        verdict = "pass" if "healthy" in claim else "fail"
        return module.VerificationCheck(claim=claim, verdict=verdict, evidence="checked")

    result = await module.ChainOfVerificationAgent(
        answer_generator=lambda prompt: "The service is healthy. The deployment is risky.",
        verifier=verifier,
    ).solve("verify deployment state")
    assert result.passed is False
    assert len(result.checks) == 2
    assert "Unverified claims" in result.verified_answer


async def test_debate_pattern() -> None:
    module = load_module("debate_pattern")

    async def debater(prompt: str, position: str):
        return {
            "debater_id": f"{position}-agent",
            "position": position,
            "argument": f"{position}: {prompt}",
        }

    async def judge(prompt: str, turns):
        return {
            "judgment": f"Reviewed {len(turns)} turns for {prompt}",
            "winning_position": turns[0].position,
        }

    agent = module.DebateAgent(
        debaters=[debater, debater],
        positions=["pro", "con"],
        judge=judge,
    )
    result = await agent.solve("switch to Continue only")
    assert len(result.turns) == 2
    assert result.winning_position == "pro"
    assert "Reviewed 2 turns" in result.judgment


def main() -> int:
    asyncio.run(test_self_consistency())
    asyncio.run(test_plan_and_solve())
    asyncio.run(test_chain_of_verification())
    asyncio.run(test_debate_pattern())
    print("PASS: advanced reasoning patterns are operational")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
