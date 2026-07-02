#!/usr/bin/env python3
"""Unit tests for Phase A complexity -> lane routing decision.

Verifies _complexity_preferred_lane() in isolation: heavy complexities route
remote (scale natively off-box), bounded/unknown stay local (single-slot APU we
control). Extracts the pure helper without importing the coordinator package.
"""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_MC = _REPO / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "extensions" / "model_coordinator.py"


def _load():
    src = _MC.read_text()
    # Pull the flag/frozenset/helper block (module-level, no package imports).
    marker = "_COMPLEXITY_LANE_ROUTING = os.environ"
    start = src.index(marker)
    end = src.index("@dataclass\nclass RoutingDecision")
    snippet = "import os\n" + src[start:end]
    ns: dict = {}
    exec(compile(snippet, str(_MC), "exec"), ns)
    return ns["_complexity_preferred_lane"]


def main() -> int:
    f = _load()
    fails = []

    def check(name, got, want):
        if got != want:
            fails.append(f"{name}: got {got!r} want {want!r}")

    # Heavy -> remote
    for c in ("complex", "critical", "architecture", "COMPLEX", "Critical"):
        check(f"heavy_{c}", f(c), "remote")

    # Bounded -> local
    for c in ("trivial", "simple", "medium"):
        check(f"bounded_{c}", f(c), "local")

    # Unknown / empty -> local (safe default)
    check("unknown", f("banana"), "local")
    check("empty", f(""), "local")

    if fails:
        print("FAIL: complexity lane routing")
        for x in fails:
            print("  " + x)
        return 1
    print("ok complexity->lane routing (10 cases)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
