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

    route_hints = engine.rank(
        "help me choose local vs remote-coding vs remote-tool-calling for this agent task",
        max_hints=6,
        agent_type="codex",
    )
    route_ids = [item.id for item in route_hints]
    assert_true(
        "prompt_coaching_route_selection" in route_ids,
        "expected route-selection coaching hint for routing query",
    )

    continue_hints = engine.rank(
        "continue editor rescue: codium extension is failing and continue-local may be broken",
        max_hints=6,
        agent_type="continue",
    )
    continue_ids = [item.id for item in continue_hints]
    assert_true(
        "prompt_coaching_continue_rescue" in continue_ids,
        "expected Continue/editor troubleshooting coaching hint",
    )

    review_hints = engine.rank(
        "please do a patch review on this git diff and call out regressions first",
        max_hints=6,
        agent_type="codex",
    )
    review_ids = [item.id for item in review_hints]
    assert_true(
        "prompt_coaching_patch_review" in review_ids,
        "expected patch-review coaching hint",
    )

    research_hints = engine.rank(
        "research and summarize a source-bounded web dataset with retrieval evidence",
        max_hints=6,
        agent_type="continue",
    )
    research_ids = [item.id for item in research_hints]
    assert_true(
        "prompt_coaching_research_workflow" in research_ids,
        "expected research workflow coaching hint",
    )

    deploy_hints = engine.rank(
        "deploy this nixos service safely and include rollback plus live verification",
        max_hints=6,
        agent_type="codex",
    )
    deploy_ids = [item.id for item in deploy_hints]
    assert_true(
        "prompt_coaching_deploy_safe_ops" in deploy_ids,
        "expected deploy-safe ops coaching hint",
    )

    bugfix_hints = engine.rank(
        "debug this failing regression and produce a safe bugfix with explicit validation",
        max_hints=6,
        agent_type="codex",
    )
    bugfix_ids = [item.id for item in bugfix_hints]
    assert_true(
        "prompt_coaching_bugfix_safe" in bugfix_ids,
        "expected bugfix coaching hint",
    )

    hardening_hints = engine.rank(
        "harden this nixos service and preserve health checks plus rollback guidance",
        max_hints=6,
        agent_type="claude",
    )
    hardening_ids = [item.id for item in hardening_hints]
    assert_true(
        "prompt_coaching_service_hardening" in hardening_ids,
        "expected service-hardening coaching hint",
    )

    print("PASS: hints engine surfaces compact task-class coaching")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
