#!/usr/bin/env python3
"""harness_qa/main.py — CLI entry point for the AI Stack QA framework.

Drop-in replacement for scripts/ai/aq-qa (bash).

Usage:
  python3 scripts/testing/harness_qa/main.py 0
  python3 scripts/testing/harness_qa/main.py 0 --json
  python3 scripts/testing/harness_qa/main.py all --layer 4 --causality
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

# Allow direct execution (python3 main.py) as well as package import (python3 -m harness_qa.main)
if __package__ is None or __package__ == "":
    _pkg_parent = Path(__file__).resolve().parent.parent
    if str(_pkg_parent) not in sys.path:
        sys.path.insert(0, str(_pkg_parent))
    # Explicitly set package context for relative imports
    import importlib
    import importlib.util
    _spec = importlib.util.spec_from_file_location(
        "harness_qa.main", __file__, submodule_search_locations=[]
    )
    __package__ = "harness_qa"

# Ensure repo root is on sys.path so dashboard/backend imports work if needed
_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent.parent.parent

# Load service-endpoints.sh into environment if not already set
def _source_endpoints() -> None:
    endpoints = _REPO_ROOT / "config" / "service-endpoints.sh"
    if not endpoints.exists():
        return
    # Only set vars that are not already in the environment
    import subprocess
    result = subprocess.run(
        ["bash", "-c", f"source {endpoints} && env"],
        capture_output=True, text=True, cwd=str(_REPO_ROOT),
    )
    for line in result.stdout.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            if k.isidentifier() and k not in os.environ:
                os.environ[k] = v


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="aq-qa",
        description="AI Stack QA phase runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Phases:
  0    pre-flight smoke (services, ports, inference, editor, front-door)
  1    infrastructure (redis, postgres, qdrant, aidb, hybrid-coordinator)
  2    runtime/package/confinement diagnostics
  3    AppArmor/confinement diagnostics
  4    context engineering (aq-hints, switchboard trimming, policy files)
  5    security hardening (SSRF, prompt injection, network isolation)
  6    monitoring (Prometheus, tool audit log, aq-report, MCP integrity)
  7    self-improvement (aq-prompt-eval, registry, query gaps)
  8    E2E workflows (hints, /query, weekly report timer)
  9    optimisation targets (llama health, Redis cache, embeddings)
  10   regression (git hooks, verifier self-check, no failed units)
  54   Phase 54 agentic-first elevation
  55   Phase 55 temporal memory / crystalline distillation
  56   Phase 56 harness integration loop
  57   Phase 57 hardware capability matrix + ROCm
  58   Phase 58 universal validation framework
  59   Phase 59 consensus arbiter
  all  Run all phases
""",
    )
    parser.add_argument(
        "phase",
        nargs="?",
        default="help",
        help="Phase number or 'all'",
    )
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON output")
    parser.add_argument("--sudo", action="store_true", help="Enable checks requiring sudo")
    parser.add_argument("--layer", type=int, default=0, metavar="N", help="Run only layer N checks")
    parser.add_argument("--causality", action="store_true", help="Include dependency layers (L1..LN)")
    return parser.parse_args(argv)


def _run_phase(phase_id: str, ctx) -> list:
    from .phases import get_phase_map
    pm = get_phase_map()
    runner = pm.get(phase_id)
    if runner is None:
        print(f"aq-qa: unknown phase '{phase_id}'", file=sys.stderr)
        sys.exit(2)
    results = runner(ctx)
    for r in results:
        r.phase = phase_id
    return results


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    # Backward compat: strip optional "phase" prefix from phase arg
    if argv and argv[0].startswith("phase") and argv[0][5:].isdigit():
        argv[0] = argv[0][5:]

    ns = _parse_args(argv)
    phase = ns.phase.lstrip("phase")

    if phase in ("help", ""):
        # Re-parse to trigger help
        _parse_args(["--help"])
        return 0

    _source_endpoints()

    from .core.context import RunContext
    from .core.result import ResultSet
    from .reporters.console import ConsoleReporter
    from .reporters.json_out import JsonReporter
    from .phases import ALL_PHASES

    ctx = RunContext(
        repo_root=_REPO_ROOT,
        layer_filter=ns.layer,
        causality_mode=ns.causality,
        use_sudo=ns.sudo,
        aq_report_json=os.environ.get("AQ_QA_AQ_REPORT_JSON", ""),
        skip_report_checks=os.environ.get("AQ_QA_SKIP_REPORT_BACKED_CHECKS", "0") == "1",
        query_timeout_s=int(os.environ.get("AQ_QA_QUERY_TIMEOUT_SECONDS", "45")),
        port_retry_attempts=int(os.environ.get("AQ_QA_PORT_RETRY_ATTEMPTS", "4")),
        port_retry_delay_s=float(os.environ.get("AQ_QA_PORT_RETRY_DELAY_SECONDS", "1")),
    )

    start = time.monotonic()

    if phase == "all":
        all_results = []
        for p in ALL_PHASES:
            all_results.extend(_run_phase(p, ctx))
        phase_label = "all"
    else:
        all_results = _run_phase(phase, ctx)
        phase_label = phase

    duration = int(time.monotonic() - start)

    rs = ResultSet(
        phase=phase_label,
        results=all_results,
        duration_s=duration,
        layer_filter=ns.layer,
        causality_mode=ns.causality,
    )

    if ns.json:
        JsonReporter().render(rs)
    else:
        ConsoleReporter().render(rs)

    return 1 if rs.failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
