#!/usr/bin/env python3
"""Targeted checks for route-selection and Continue/editor prompt coaching."""

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

    print("PASS: hints engine surfaces route-selection and Continue/editor coaching")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
