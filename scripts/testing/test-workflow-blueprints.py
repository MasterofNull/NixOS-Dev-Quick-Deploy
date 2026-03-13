#!/usr/bin/env python3
"""Targeted checks for required workflow blueprint coverage."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BLUEPRINTS_PATH = ROOT / "config" / "workflow-blueprints.json"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    payload = json.loads(BLUEPRINTS_PATH.read_text(encoding="utf-8"))
    items = payload.get("blueprints") or []
    ids = {item.get("id") for item in items if isinstance(item, dict)}
    required = {
        "coding-bugfix-safe",
        "repo-refactor-guarded",
        "deploy-rollback-safe-ops",
        "continue-editor-rescue",
        "remote-reasoning-escalation",
        "prsi-pessimistic-recursive-improvement",
    }
    missing = sorted(required - ids)
    assert_true(not missing, f"missing required workflow blueprints: {', '.join(missing)}")
    print("PASS: workflow blueprints cover the required harness task families")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
