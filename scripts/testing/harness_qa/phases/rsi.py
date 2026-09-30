"""RSI queue integration and unattended wake-up coverage."""
from __future__ import annotations

import json
import subprocess
import sys

from ..core.context import RunContext
from ..core.result import CheckResult, failed, passed


def run(ctx: RunContext) -> list[CheckResult]:
    if not ctx.should_run(3):
        return []
    results = []
    try:
        proc = subprocess.run(
            [sys.executable, str(ctx.repo_root / "scripts/automation/prsi-orchestrator.py"), "list"],
            capture_output=True, text=True, timeout=30, check=True,
        )
        payload = json.loads(proc.stdout)
        summary = payload["rsi"]
        keys = ("pending", "running", "failed", "stalled", "awaiting_validation")
        if any(type(summary[k]) is not int or summary[k] < 0 for k in keys):
            raise ValueError("invalid RSI counters")
        if "oldest_pending" not in summary:
            raise ValueError("missing queue age")
        results.append(passed(3, "rsi.1", "RSI queue integration", phase="rsi"))
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError) as exc:
        results.append(failed(3, "rsi.1", "RSI queue integration", str(exc)[:300], phase="rsi"))
    try:
        proc = subprocess.run(
            ["systemctl", "is-active", "ai-prsi-rsi-dispatch.path", "ai-prsi-rsi-dispatch.timer"],
            capture_output=True, text=True, timeout=10,
        )
        if proc.stdout.splitlines() != ["active", "active"]:
            raise ValueError("RSI event trigger and reconciliation timer must both be active")
        results.append(passed(3, "rsi.2", "RSI wake-up coverage", phase="rsi"))
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        results.append(failed(3, "rsi.2", "RSI wake-up coverage", str(exc)[:300], phase="rsi"))
    return results
