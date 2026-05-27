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

# Add scripts/ai/lib to sys.path for LocalModelClient (must be after _REPO_ROOT is defined)
_ai_lib = _REPO_ROOT / "scripts" / "ai" / "lib"
if str(_ai_lib) not in sys.path:
    sys.path.insert(0, str(_ai_lib))
try:
    from model_client import LocalModelClient
except ImportError:
    # Handle kebab-case rename policy
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("model_client", str(_ai_lib / "model-client.py"))
        model_client = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(model_client)
        LocalModelClient = model_client.LocalModelClient
    except Exception:
        LocalModelClient = None

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
    parser.add_argument("--machine", action="store_true", help="Minimalist, machine-friendly text output")
    parser.add_argument("--sudo", action="store_true", help="Enable checks requiring sudo")
    parser.add_argument("--layer", type=int, default=0, metavar="N", help="Run only layer N checks")
    parser.add_argument("--causality", action="store_true", help="Include dependency layers (L1..LN)")
    parser.add_argument("--remediate", action="store_true", help="Auto-diagnose failures using local model")
    parser.add_argument(
        "--queue-to-ralph", action="store_true",
        help="Submit each failing check as a ralph-wiggum improvement task (POST /tasks)",
    )
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


def auto_remediate(rs: ResultSet) -> None:
    """Use the local model to diagnose failures and suggest remediations."""
    if not LocalModelClient:
        print("\n[aq-qa] Error: LocalModelClient not available for remediation.", file=sys.stderr)
        return
    
    import json as _json
    failures = [r for r in rs.results if r.status.name == "FAIL"]
    if not failures:
        return
    
    print("\n[aq-qa] Initiating auto-diagnosis for failures using local model...", file=sys.stderr)
    
    client = LocalModelClient()
    
    failure_data = []
    for f in failures:
        failure_data.append({
            "id": f.id,
            "layer": f.layer,
            "description": f.description,
            "reason": f.reason,
        })
    
    prompt = (
        "You are the AI Stack SRE. The following QA checks have FAILED. "
        "Diagnose the likely root cause for each failure and provide a specific, "
        "actionable remediation command or step.\n\n"
        f"Failed Checks: {_json.dumps(failure_data, indent=2)}\n\n"
        "Diagnosis & Remediation:"
    )
    
    messages = [{"role": "user", "content": prompt}]
    response = client.chat(messages)
    
    if "choices" in response:
        print("\n" + "=" * 80)
        print("  AUTO-DIAGNOSIS & REMEDIATION")
        print("=" * 80)
        print(response["choices"][0]["message"]["content"])
        print("=" * 80 + "\n")
    else:
        print(f"\n[aq-qa] Error during diagnosis: {response.get('error', 'unknown error')}", file=sys.stderr)


def _submit_failures_to_ralph(rs) -> None:
    """Submit each failing aq-qa check as a ralph-wiggum improvement task.

    Reads the API key from /run/secrets/aidb_api_key (same credential ralph-wiggum
    uses internally) or falls back to the RALPH_API_KEY env var.
    """
    import json as _json
    import urllib.request
    import urllib.error

    failures = [r for r in rs.results if r.status.name == "FAIL"]
    if not failures:
        return

    # Resolve auth key — ralph-wiggum uses aidb_api_key per mcp-servers.nix wiring
    api_key = ""
    try:
        api_key = Path("/run/secrets/aidb_api_key").read_text().strip()
    except OSError:
        api_key = os.environ.get("RALPH_API_KEY", "")

    ralph_url = os.environ.get("RALPH_URL", "http://127.0.0.1:8004")

    submitted = 0
    errors = []
    for f in failures:
        prompt = (
            f"AQ-QA Phase {rs.phase} check {f.id} FAILED.\n"
            f"Description: {f.description}\n"
            f"Reason: {f.reason or 'no detail'}\n\n"
            "Diagnose the root cause and provide a specific remediation step or "
            "nixos-rebuild / service restart command to fix this failure."
        )
        payload = _json.dumps({
            "prompt": prompt,
            "backend": "aider",
            "max_iterations": 2,
            "metadata": {
                "source": "aq-qa",
                "phase": rs.phase,
                "check_id": f.id,
                "layer": f.layer,
            },
        }).encode()
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        req = urllib.request.Request(
            f"{ralph_url}/tasks", data=payload, headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = _json.loads(resp.read())
                task_id = body.get("task_id", "?")
                print(
                    f"[aq-qa] ralph task queued for {f.id}: {task_id[:12]}…",
                    file=sys.stderr,
                )
                submitted += 1
        except urllib.error.HTTPError as exc:
            errors.append(f"{f.id}: HTTP {exc.code}")
        except Exception as exc:
            errors.append(f"{f.id}: {exc}")

    if submitted:
        print(
            f"[aq-qa] {submitted}/{len(failures)} failure(s) queued to ralph-wiggum for remediation.",
            file=sys.stderr,
        )
    if errors:
        print(f"[aq-qa] ralph submission errors: {'; '.join(errors)}", file=sys.stderr)


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
        ConsoleReporter().render(rs, machine_mode=ns.machine)

    # Persist latest results for auto-remediation
    try:
        latest_json = _REPO_ROOT / "data" / "hybrid" / "telemetry" / "latest-qa-results.json"
        latest_json.parent.mkdir(parents=True, exist_ok=True)
        import json as _json
        # Extract logic from JsonReporter to get the dict
        layers: dict[str, list] = {}
        tests = []
        for r in rs.results:
            item = {
                "layer": r.layer, "id": r.id, "status": r.status.value,
                "description": f"{r.description} ({r.reason})" if r.reason else r.description,
            }
            tests.append(item)
            layers.setdefault(str(r.layer), []).append(item)
        output = {
            "phase": rs.phase, "passed": rs.passed, "failed": rs.failed,
            "skipped": rs.skipped, "duration_s": rs.duration_s,
            "tests": tests,
        }
        latest_json.write_text(_json.dumps(output, indent=2), encoding="utf-8")
    except Exception:
        pass

    if rs.failed > 0 and ns.remediate:
        auto_remediate(rs)

    if rs.failed > 0 and ns.queue_to_ralph:
        _submit_failures_to_ralph(rs)

    return 1 if rs.failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
