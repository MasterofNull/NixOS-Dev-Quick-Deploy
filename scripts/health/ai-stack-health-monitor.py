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

from attention_queue import push, retire_recovered, snapshot_recovery_candidate  # noqa: E402

_HARNESS_RUNNER = _SCRIPT_DIR / "ai" / "lib" / "harness_runner.py"
_TMPDIR = _REPO_ROOT / ".agents" / "tmp"
_PYTHONPYCACHEPREFIX = _TMPDIR / "pycache"
_CARGO_TARGET_DIR = _TMPDIR / "cargo-target"
_STATUS_PATH = _REPO_ROOT / ".agents" / "health-monitor" / "latest.json"
_PYTHON_BIN = str(Path(sys.executable).resolve().parent)
_SYSTEM_BIN = "/run/current-system/sw/bin"
_PHASES = ["0"]  # phase 0 = pre-flight smoke; fast enough for a 15-min timer
_SOURCE = "ai-stack-health-monitor"
# Pure time/expiry checks (Rule 19 gate corollary): reported as a separate lower-severity maintenance alert,
# never counted toward the outage severity. Match by id only; a message match would hide real bugs
# (e.g. 0.10.54 reports "bump-expired" when its fixture is wrong).
_FRESHNESS_CHECK_IDS = frozenset({"0.10.5"})
_PAYLOAD_AUDIT = _SCRIPT_DIR / "ai" / "aq-payload-audit"
_PAYLOAD_AUDIT_TIMEOUT_S = 60
_ALERT_TTL_S = 3600  # > 3x the 15-min timer so one failing issue stays ONE alert (updated in place)
_HARNESS_TIMEOUT_S = int(os.environ.get("HARNESS_TIMEOUT_S", "430"))  # ~2.5x measured phase-0 wall (147-171s)


def push_alert(**spec) -> None:
    title = spec["title"]
    if len(title) > 80:
        spec["title"] = title[:79] + "…"
        spec["detail"] = title + "\n\n" + spec["detail"]
    try:
        push(**spec)
    except (ValueError, TypeError) as exc:
        print(f"[{_SOURCE}] Skipping invalid alert: {exc}", file=sys.stderr)


def run_aq_qa(phase: str) -> dict:
    """Run aq-qa <phase> --json and return parsed output."""
    try:
        _TMPDIR.mkdir(parents=True, exist_ok=True)
        _PYTHONPYCACHEPREFIX.mkdir(parents=True, exist_ok=True)
        _CARGO_TARGET_DIR.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env.update({"TMPDIR": str(_TMPDIR), "TEMP": str(_TMPDIR), "TMP": str(_TMPDIR)})
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        # Scheduled monitoring must not read "cannot run here" as healthy: an unreachable systemd user manager
        # fails 0.10.66 instead of skipping it (phase0._confine_context_gap). No unit change needed.
        env["AQ_CONFINE_REQUIRE_CONTEXT"] = "1"
        env["PYTHONPYCACHEPREFIX"] = str(_PYTHONPYCACHEPREFIX)
        env["CARGO_TARGET_DIR"] = str(_CARGO_TARGET_DIR)
        env["PATH"] = f"{_PYTHON_BIN}:{_SYSTEM_BIN}:{env.get('PATH', '')}"
        result = subprocess.run(
            [sys.executable, str(_HARNESS_RUNNER), phase, "--json"],
            env=env,
            capture_output=True, text=True, timeout=_HARNESS_TIMEOUT_S,
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
        if not isinstance(data, dict):
            return {"error": f"phase output is not a JSON object; rc={result.returncode}", "phase": phase,
                    "checks": [], "summary": {"failed": 1}}
        data["_monitor_returncode"] = result.returncode  # actual subprocess result; JSON must not shadow it
        if result.stderr:
            data.setdefault("_monitor_stderr", result.stderr[-1000:])
        return data
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return {"error": str(e), "phase": phase, "checks": [], "summary": {"failed": 1}}


def _count(v: object) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


def is_complete_clean_phase0_result(data: object) -> bool:
    """True only for a complete, non-degraded phase-0 run whose every emitted test passed.

    Fail closed: SKIP, unknown status, partial/empty tests, count mismatch or a nonzero exit are not clean.
    """
    if not isinstance(data, dict) or "error" in data or data.get("phase") != "0":
        return False
    rc = data.get("_monitor_returncode")
    if not isinstance(rc, int) or isinstance(rc, bool) or rc != 0:
        return False
    if data.get("degraded_confidence") is not False:
        return False
    passed, failed, skipped = data.get("passed"), data.get("failed"), data.get("skipped")
    if not (_count(passed) and _count(failed) and _count(skipped)):
        return False
    tests = data.get("tests")
    if not isinstance(tests, list) or not tests:
        return False
    for t in tests:
        if not (isinstance(t, dict) and isinstance(t.get("id"), str) and t["id"] and t.get("status") == "PASS"):
            return False
    return passed == len(tests) and failed == 0 and skipped == 0


def run_payload_audit() -> dict:
    """Run aq-payload-audit --json (~0.2s); returns {"state": ok|findings|unknown, ...} for the status file."""
    try:
        result = subprocess.run(
            [sys.executable, str(_PAYLOAD_AUDIT), "--json", "--days", "2", "--repo", str(_REPO_ROOT)],
            capture_output=True, text=True, timeout=_PAYLOAD_AUDIT_TIMEOUT_S,
        )
        data = json.loads(result.stdout)
        findings = data["findings"]
        summary = data["summary"]
    except (subprocess.TimeoutExpired, OSError, json.JSONDecodeError, KeyError) as exc:
        return {"state": "unknown", "error": f"{type(exc).__name__}: {exc}"}
    return {
        "state": "findings" if findings else "ok",
        "high": summary.get("high", 0),
        "medium": summary.get("medium", 0),
        "findings": [{k: f.get(k) for k in ("lane", "check_id", "severity", "measured", "threshold", "evidence_path")}
                     for f in findings],
    }


def alert_payload_audit(audit: dict) -> None:
    """HIGH payload findings (quota exhaustion, thinking enabled, ...) are attention-worthy but never an outage."""
    high = [f for f in audit.get("findings", []) if f.get("severity") == "high"]
    if not high:
        return
    push_alert(
        source=_SOURCE,
        severity="medium",
        autonomy_boundary="human_gate",
        title=f"Payload audit: {len(high)} high finding(s) ({', '.join(str(f['lane']) + ' ' + str(f['check_id']) for f in high[:3])})",
        detail="aq-payload-audit reported high-severity agent payload findings:\n"
        + "\n".join(f"  [{f['lane']} {f['check_id']}] {f['measured']} (threshold {f['threshold']}): {f['evidence_path']}"
                    for f in high),
        proposed_action="Read `aq-payload-audit --days 2` and fix or route around each high finding.",
        dedup_key="payload-audit-high",
        ttl_s=_ALERT_TTL_S,
        why="Payload/quota findings degrade agent lanes but are maintenance signals, not a stack outage.",
        next_step="Run the audit and act on the high rows.",
        command="aq-payload-audit --days 2",
    )


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
        # Snapshot before the probe so a failure observed while it runs cannot be retired by a later clean result.
        recovery_snapshot = snapshot_recovery_candidate() if phase == "0" else None
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
            push_alert(
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
                dedup_key=f"qa-phase-{phase}-error",
                why="Without this monitor, stack failures are not detected on schedule.",
                next_step="Check the monitor service log.",
                command="journalctl -u ai-stack-health-monitor.service -n 50 --no-pager",
                ttl_s=_ALERT_TTL_S,
            )
            total_failures += 1
            continue

        all_failures = failed_checks(data)
        failures = [c for c in all_failures if str(c.get("id", "")) not in _FRESHNESS_CHECK_IDS]
        stale = [c for c in all_failures if str(c.get("id", "")) in _FRESHNESS_CHECK_IDS]
        if stale:
            push_alert(
                source=_SOURCE,
                severity="medium",
                autonomy_boundary="human_gate",
                title=f"Maintenance due: {len(stale)} freshness check(s) expired (QA phase {phase})",
                detail=(
                    "Time-based freshness signals expired; nothing is broken, a periodic review/probe is overdue:\n"
                    + "\n".join(f"  [{c.get('id', '?')}] {c.get('name') or c.get('description') or '?'}: "
                                f"{c.get('message') or c.get('detail') or ''}" for c in stale)
                ),
                proposed_action="Re-probe and re-review the model profile/catalog (owner maintenance task).",
                ttl_s=_ALERT_TTL_S,
                dedup_key=f"qa-phase-{phase}-freshness",
                why="A stale review window is tracked maintenance (Rule 19 gate corollary), not an outage.",
                next_step="Run the model profile refresh when convenient.",
                command=f"aq-qa {phase} --machine",
            )
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
            if recovery_snapshot is not None and is_complete_clean_phase0_result(data):
                try:
                    if retire_recovered(recovery_snapshot):
                        print(f"[{_SOURCE}] Retired recovered alert {recovery_snapshot['id']} (phase-0-clean)")
                except (OSError, RuntimeError, ValueError) as exc:
                    print(f"[{_SOURCE}] Recovery retirement skipped: {exc}", file=sys.stderr)
            continue

        # Group failures into one alert per phase for readability.
        lines = []
        for c in failures:
            label = c.get("name") or c.get("description") or "?"
            message = c.get("message") or c.get("detail") or ""
            lines.append(f"  [{c.get('id', '?')}] {label}: {message}")

        ids = [str(c.get("id", "?")) + " " + str(c.get("name") or c.get("description") or "?")[:28]
               for c in failures]
        shown = ", ".join(ids[:3]) + (f" +{len(ids) - 3} more" if len(ids) > 3 else "")
        noun = "check" if len(failures) == 1 else "checks"
        push_alert(
            source=_SOURCE,
            severity="critical" if len(failures) >= 3 else "high",
            autonomy_boundary="human_gate",
            title=f"QA phase {phase}: {len(failures)} {noun} failing ({shown})",
            detail=(
                f"Scheduled health monitor found {len(failures)} failing {noun}:\n"
                + "\n".join(lines)
            ),
            proposed_action=f"Re-run `aq-qa {phase} --machine` and fix the failing check(s).",
            ttl_s=_ALERT_TTL_S,
            dedup_key=f"qa-phase-{phase}",
            why="The AI stack pre-flight smoke test is failing; dependent services may be degraded.",
            next_step="Re-run the phase to see per-check output.",
            command=f"aq-qa {phase} --machine",
        )
        total_failures += len(failures)

    audit = run_payload_audit()
    alert_payload_audit(audit)
    write_status({
        "source": _SOURCE,
        "payload_audit": audit,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tmpdir": str(_TMPDIR),
        "total_failures": total_failures,
        "phase_results": phase_results,
    })

    if total_failures == 0:
        print(f"[{_SOURCE}] All checks passed at {time.strftime('%Y-%m-%dT%H:%M:%S')}")
    else:
        print(f"[{_SOURCE}] {total_failures} failure(s) found; attention queue submission attempted", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
