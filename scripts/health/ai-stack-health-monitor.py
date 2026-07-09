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

_HARNESS_RUNNER = _SCRIPT_DIR / "ai" / "lib" / "harness_runner.py"
_TMPDIR = _REPO_ROOT / ".agents" / "tmp"
_STATUS_PATH = _REPO_ROOT / ".agents" / "health-monitor" / "latest.json"
_SYSTEM_BIN = "/run/current-system/sw/bin"
_PHASES = ["0"]  # phase 0 = pre-flight smoke; fast enough for a 15-min timer
_SOURCE = "ai-stack-health-monitor"
_COOLDOWN_S = 600  # don't re-alert the same failure within 10 minutes


def run_aq_qa(phase: str) -> dict:
    """Run aq-qa <phase> --json and return parsed output."""
    try:
        _TMPDIR.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env.update({"TMPDIR": str(_TMPDIR), "TEMP": str(_TMPDIR), "TMP": str(_TMPDIR)})
        env["PATH"] = f"{_SYSTEM_BIN}:{env.get('PATH', '')}"
        result = subprocess.run(
            [sys.executable, str(_HARNESS_RUNNER), phase, "--json"],
            env=env,
            capture_output=True, text=True, timeout=120,
        )
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            return {
                "error": f"{e}; rc={result.returncode}",
                "phase": phase,
                "stdout": result.stdout[-500:],
                "stderr": result.stderr[-1000:],
                "checks": [],
                "summary": {"failed": 1},
            }
        data.setdefault("_monitor_returncode", result.returncode)
        if result.stderr:
            data.setdefault("_monitor_stderr", result.stderr[-1000:])
        return data
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return {"error": str(e), "phase": phase, "checks": [], "summary": {"failed": 1}}


def failed_checks(data: dict) -> list[dict]:
    """Return failed checks from both legacy `checks` and current `tests` aq-qa JSON."""
    checks = data.get("checks")
    if not isinstance(checks, list):
        checks = data.get("tests", [])
    return [
        c for c in checks
        if str(c.get("status", "")).lower() in {"fail", "failed", "error"}
    ]


def write_status(status: dict) -> None:
    """Write the latest monitor run for dashboard/API consumers."""
    _STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = _STATUS_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(_STATUS_PATH)


def main() -> int:
    total_failures = 0
    phase_results = []
    for phase in _PHASES:
        data = run_aq_qa(phase)
        if "error" in data:
            phase_results.append({
                "phase": phase,
                "status": "error",
                "error": data["error"],
                "stderr": data.get("stderr", ""),
                "stdout": data.get("stdout", ""),
                "failed": 1,
            })
            push(
                source=_SOURCE,
                severity="high",
                autonomy_boundary="human_gate",
                title=f"aq-qa phase {phase} could not run: {data['error']}",
                detail=(
                    f"The scheduled health monitor failed to execute aq-qa phase {phase}.\n"
                    f"Error: {data['error']}\n"
                    f"stderr: {data.get('stderr', '')}\n"
                    f"Check: systemctl status ai-stack-health-monitor.service"
                ),
                proposed_action="Investigate aq-qa and health monitor logs.",
                ttl_s=_COOLDOWN_S,
            )
            total_failures += 1
            continue

        failures = failed_checks(data)
        failure_summaries = [
            {
                "id": c.get("id", "?"),
                "label": c.get("name") or c.get("description") or "?",
                "message": c.get("message") or c.get("detail") or "",
            }
            for c in failures
        ]
        phase_results.append({
            "phase": phase,
            "status": "failed" if failures else "passed",
            "failed": len(failures),
            "failures": failure_summaries,
            "total": len(data.get("tests") or data.get("checks") or []),
            "summary": data.get("summary", {}),
            "returncode": data.get("_monitor_returncode"),
            "stderr": data.get("_monitor_stderr", ""),
        })
        if not failures:
            continue

        # Group failures into one alert per phase for readability.
        lines = []
        for c in failures:
            label = c.get("name") or c.get("description") or "?"
            message = c.get("message") or c.get("detail") or ""
            lines.append(f"  [{c.get('id', '?')}] {label}: {message}")

        push(
            source=_SOURCE,
            severity="critical" if len(failures) >= 3 else "high",
            autonomy_boundary="human_gate",
            title=f"aq-qa phase {phase}: {len(failures)} check(s) failing",
            detail=(
                f"Scheduled health monitor found {len(failures)} failing check(s):\n"
                + "\n".join(lines)
                + "\n\nRun: aq-qa 0  for full detail."
            ),
            proposed_action="Run: aq-qa 0  to see full failure detail.",
            ttl_s=_COOLDOWN_S,
        )
        total_failures += len(failures)

    write_status({
        "source": _SOURCE,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tmpdir": str(_TMPDIR),
        "total_failures": total_failures,
        "phase_results": phase_results,
    })

    if total_failures == 0:
        print(f"[{_SOURCE}] All checks passed at {time.strftime('%Y-%m-%dT%H:%M:%S')}")
    else:
        print(f"[{_SOURCE}] {total_failures} failure(s) pushed to attention queue", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
