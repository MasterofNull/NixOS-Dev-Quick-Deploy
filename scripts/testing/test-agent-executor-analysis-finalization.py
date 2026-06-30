#!/usr/bin/env python3
"""Verify analysis-only local-agent observation loops force final synthesis."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXECUTOR = ROOT / "ai-stack" / "local-agents" / "agent_executor.py"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    text = EXECUTOR.read_text(encoding="utf-8")
    require("_is_analysis_only_task" in text, "analysis-only task classifier missing")
    require("FINALIZE NOW. Do not call another tool" in text, "analysis tasks must force final synthesis")
    require("Start with 'COMPLETED:'" in text, "forced synthesis must require completion marker")
    require("task_type=task.task_type" in text, "forced synthesis must preserve task profile")
    require("asking\n            # them to \"act\"" in text, "root-cause comment missing")
    print("PASS: analysis-only observation stall forces final synthesis")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
