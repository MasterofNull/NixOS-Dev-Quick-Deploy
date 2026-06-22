#!/usr/bin/env python3
"""Scheduled AI stack health monitor.

Runs aq-qa phase 0 (pre-flight smoke) and pushes any failures to the
attention queue so they surface on the next interactive shell prompt
and in the dashboard, rather than being discovered by accident.

Designed to run as a systemd timer every 15 minutes.
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(os.environ.get("REPO_ROOT", Path(__file__).resolve().parent.parent.parent))
_SCRIPT_DIR = _REPO_ROOT / "scripts"
sys.path.insert(0, str(_SCRIPT_DIR / "ai" / "lib"))

from attention_queue import push  # noqa: E402

_AQ_QA = _SCRIPT_DIR / "ai" / "aq-qa"
_PHASES = ["0"]  # phase 0 = pre-flight smoke; fast enough for a 15-min timer
_SOURCE = "ai-stack-health-monitor"
_COOLDOWN_S = 600  # don't re-alert the same failure within 10 minutes


def run_aq_qa(phase: str) -> dict:
    """Run aq-qa <phase> --json and return parsed output."""
    try:
        result = subprocess.run(
            [str(_AQ_QA), phase, "--json"],
            capture_output=True, text=True, timeout=120,
        )
        return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as e:
        return {"error": str(e), "phase": phase, "checks": [], "summary": {"failed": 1}}


def main() -> int:
    total_failures = 0
    for phase in _PHASES:
        data = run_aq_qa(phase)
        if "error" in data:
            push(
                source=_SOURCE,
                severity="high",
                autonomy_boundary="human_gate",
                title=f"aq-qa phase {phase} could not run: {data['error']}",
                detail=(
                    f"The scheduled health monitor failed to execute aq-qa phase {phase}.\n"
                    f"Error: {data['error']}\n"
                    f"Check: systemctl status ai-stack-health-monitor.service"
                ),
                proposed_action="Investigate aq-qa and health monitor logs.",
                ttl_s=_COOLDOWN_S,
            )
            total_failures += 1
            continue

        checks = data.get("checks", [])
        failed_checks = [c for c in checks if c.get("status") in ("fail", "error")]
        if not failed_checks:
            continue

        # Group failures into one alert per phase for readability.
        lines = []
        for c in failed_checks:
            lines.append(f"  [{c.get('id', '?')}] {c.get('name', '?')}: {c.get('message', '')}")

        push(
            source=_SOURCE,
            severity="critical" if len(failed_checks) >= 3 else "high",
            autonomy_boundary="human_gate",
            title=f"aq-qa phase {phase}: {len(failed_checks)} check(s) failing",
            detail=(
                f"Scheduled health monitor found {len(failed_checks)} failing check(s):\n"
                + "\n".join(lines)
                + "\n\nRun: aq-qa 0  for full detail."
            ),
            proposed_action="Run: aq-qa 0  to see full failure detail.",
            ttl_s=_COOLDOWN_S,
        )
        total_failures += len(failed_checks)

    if total_failures == 0:
        print(f"[{_SOURCE}] All checks passed at {time.strftime('%Y-%m-%dT%H:%M:%S')}")
    else:
        print(f"[{_SOURCE}] {total_failures} failure(s) pushed to attention queue", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
