#!/usr/bin/env python3
"""Targeted checks for compact task-class prompt coaching."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("AI_STRICT_ENV", "false")
sys.path.insert(0, str(ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator"))

from hints_engine import HintsEngine  # noqa: E402


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    engine = HintsEngine()

    def prompt_hint_ids(query: str, agent_type: str) -> list[str]:
        return [item.id for item in engine._hints_from_prompt_coaching(query, query.lower().split(), agent_type)]

    route_ids = prompt_hint_ids(
        "help me choose local vs remote-coding vs remote-tool-calling for this agent task",
        "codex",
    )
    assert_true(
        "prompt_coaching_route_selection" in route_ids,
        "expected route-selection coaching hint for routing query",
    )

    continue_ids = prompt_hint_ids(
        "continue editor rescue: codium extension is failing and continue-local may be broken",
        "continue",
    )
    assert_true(
        "prompt_coaching_continue_rescue" in continue_ids,
        "expected Continue/editor troubleshooting coaching hint",
    )

    review_ids = prompt_hint_ids(
        "please do a patch review on this git diff and call out regressions first",
        "codex",
    )
    assert_true(
        "prompt_coaching_patch_review" in review_ids,
        "expected patch-review coaching hint",
    )

    research_ids = prompt_hint_ids(
        "research and summarize a source-bounded web dataset with retrieval evidence",
        "continue",
    )
    assert_true(
        "prompt_coaching_research_workflow" in research_ids,
        "expected research workflow coaching hint",
    )

    deploy_ids = prompt_hint_ids(
        "deploy this nixos service safely and include rollback plus live verification",
        "codex",
    )
    assert_true(
        "prompt_coaching_deploy_safe_ops" in deploy_ids,
        "expected deploy-safe ops coaching hint",
    )

    bugfix_ids = prompt_hint_ids(
        "debug this failing regression and produce a safe bugfix with explicit validation",
        "codex",
    )
    assert_true(
        "prompt_coaching_bugfix_safe" in bugfix_ids,
        "expected bugfix coaching hint",
    )

    hardening_ids = prompt_hint_ids(
        "harden this nixos service and preserve health checks plus rollback guidance",
        "claude",
    )
    assert_true(
        "prompt_coaching_service_hardening" in hardening_ids,
        "expected service-hardening coaching hint",
    )

    prsi_ids = prompt_hint_ids(
        "run one pessimistic self-improvement PRSI cycle with rollback and validation gates",
        "codex",
    )
    assert_true(
        "prompt_coaching_prsi_loop" in prsi_ids,
        "expected PRSI coaching hint",
    )

    skill_ids = prompt_hint_ids(
        "sync this approved agentskill source into the shared skill registry and expose it to local agents",
        "codex",
    )
    assert_true(
        "prompt_coaching_skill_registry" in skill_ids,
        "expected skill-registry coaching hint",
    )

    delegation_ids = prompt_hint_ids(
        "delegate this bounded task through the coordinator and keep sub-agent fan-out disabled",
        "codex",
    )
    assert_true(
        "prompt_coaching_delegation_contract" in delegation_ids,
        "expected delegation-contract coaching hint",
    )

    print("PASS: hints engine surfaces compact task-class coaching")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
