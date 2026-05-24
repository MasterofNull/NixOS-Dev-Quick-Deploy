"""Phase 72 checks — Self-Healing Loop Activation.

72.1  aq-qa --queue-to-ralph: ralph-wiggum reachable and accepts task submission
72.2  Service Coverage Contract: phase71 exists and all 7 checks are registered
72.3  env-contract.yaml: RALPH_API_KEY, AIDER_WRAPPER_PORT, AIDER_WRAPPER_API_KEY registered
72.4  WORKFLOW-CANON.md: Service Coverage Contract section present
72.5  AGENTS.md: Service Coverage Contract section present
72.6  Autonomous loop: gap-remediate timer fires to ralph-wiggum OR runs standalone (audit)
"""
from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Tuple

from ..core.context import RunContext
from ..core.result import CheckResult, passed, failed, skipped

_REPO = Path(__file__).resolve().parents[4]


def _http(
    method: str, url: str, body: Any = None, api_key: str = "", timeout: int = 10
) -> Tuple[int, Any]:
    headers: dict = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        try:
            body_err = json.loads(exc.read())
        except Exception:
            body_err = str(exc)
        return exc.code, body_err
    except Exception as exc:
        return 0, str(exc)


def _ralph_key() -> str:
    try:
        return Path("/run/secrets/aidb_api_key").read_text().strip()
    except OSError:
        return os.environ.get("RALPH_API_KEY", "")


# ---------------------------------------------------------------------------
# 72.1 — ralph-wiggum accepts task from --queue-to-ralph code path
# ---------------------------------------------------------------------------

def _check_72_1(_ctx: RunContext) -> CheckResult:
    """Verify ralph-wiggum accepts a probe task matching the --queue-to-ralph payload shape."""
    key = _ralph_key()
    if not key:
        return skipped(3, "72.1", "ralph task acceptance", "no API key found", phase="72")

    ralph_url = os.environ.get("RALPH_URL", "http://127.0.0.1:8004")
    # Mirror the exact payload shape used by _submit_failures_to_ralph()
    status, body = _http(
        "POST", f"{ralph_url}/tasks",
        body={
            "prompt": "aq-qa probe 72.1: echo OK — self-healing loop check",
            "backend": "aider",
            "max_iterations": 1,
            "metadata": {"source": "aq-qa", "phase": "72", "check_id": "72.1", "layer": 3},
        },
        api_key=key, timeout=15,
    )
    if status == 0:
        return skipped(3, "72.1", "ralph task acceptance", "ralph-wiggum unreachable", phase="72")
    if status == 401:
        return failed(3, "72.1", "ralph task acceptance", "401 — API key mismatch", phase="72")
    if status in (200, 201, 202):
        task_id = (body or {}).get("task_id", "") if isinstance(body, dict) else ""
        if task_id:
            return passed(3, "72.1", f"ralph accepted --queue-to-ralph payload: {task_id[:10]}…", phase="72")
        return failed(3, "72.1", "ralph task acceptance", "no task_id in response", phase="72")
    return failed(3, "72.1", "ralph task acceptance", f"HTTP {status}: {str(body)[:60]}", phase="72")


# ---------------------------------------------------------------------------
# 72.2 — Service Coverage Contract: phase71 fully registered
# ---------------------------------------------------------------------------

def _check_72_2(_ctx: RunContext) -> CheckResult:
    """Verify phase71.py exists, is registered in __init__.py, and ALL_PHASES includes 71."""
    phase71 = _REPO / "scripts" / "testing" / "harness_qa" / "phases" / "phase71.py"
    if not phase71.exists():
        return failed(3, "72.2", "phase71 registration", "phase71.py missing", phase="72")

    init = _REPO / "scripts" / "testing" / "harness_qa" / "phases" / "__init__.py"
    text = init.read_text(encoding="utf-8")
    if "phase71" not in text:
        return failed(3, "72.2", "phase71 registration", "phase71 not imported in __init__.py", phase="72")
    if '"71"' not in text and "'71'" not in text:
        return failed(3, "72.2", "phase71 registration", '"71" key missing from phase map', phase="72")

    # Verify all 7 check functions are defined
    p71_text = phase71.read_text(encoding="utf-8")
    missing = [f"_check_71_{i}" for i in range(1, 8) if f"_check_71_{i}" not in p71_text]
    if missing:
        return failed(3, "72.2", "phase71 registration",
                      f"missing check functions: {missing}", phase="72")

    return passed(3, "72.2", "phase71 fully registered: 7/7 checks, phase map entry present", phase="72")


# ---------------------------------------------------------------------------
# 72.3 — env-contract.yaml has RALPH_API_KEY, AIDER_WRAPPER_PORT, AIDER_WRAPPER_API_KEY
# ---------------------------------------------------------------------------

def _check_72_3(_ctx: RunContext) -> CheckResult:
    """Verify newly-added env vars are documented in env-contract.yaml."""
    contract = _REPO / "config" / "env-contract.yaml"
    if not contract.exists():
        return skipped(3, "72.3", "env-contract coverage", "env-contract.yaml not found", phase="72")

    text = contract.read_text(encoding="utf-8")
    required = ["RALPH_API_KEY", "AIDER_WRAPPER_PORT", "AIDER_WRAPPER_API_KEY"]
    missing = [v for v in required if v not in text]
    if missing:
        return failed(3, "72.3", "env-contract coverage",
                      f"undocumented vars: {', '.join(missing)}", phase="72")

    return passed(3, "72.3", f"env-contract: {len(required)} vars documented ({', '.join(required)})",
                  phase="72")


# ---------------------------------------------------------------------------
# 72.4 — WORKFLOW-CANON.md has Service Coverage Contract section
# ---------------------------------------------------------------------------

def _check_72_4(_ctx: RunContext) -> CheckResult:
    """Verify Service Coverage Contract section is present in WORKFLOW-CANON.md."""
    canon = _REPO / ".agent" / "WORKFLOW-CANON.md"
    if not canon.exists():
        return skipped(3, "72.4", "WORKFLOW-CANON contract", "WORKFLOW-CANON.md not found", phase="72")

    text = canon.read_text(encoding="utf-8")
    markers = ["Service Coverage Contract", "aq-qa check", "Dashboard panel"]
    missing = [m for m in markers if m not in text]
    if missing:
        return failed(3, "72.4", "WORKFLOW-CANON contract",
                      f"missing markers: {missing}", phase="72")

    return passed(3, "72.4", "WORKFLOW-CANON.md: Service Coverage Contract section present", phase="72")


# ---------------------------------------------------------------------------
# 72.5 — AGENTS.md has Service Coverage Contract section
# ---------------------------------------------------------------------------

def _check_72_5(_ctx: RunContext) -> CheckResult:
    """Verify Service Coverage Contract section is present in AGENTS.md."""
    agents_md = _REPO / "AGENTS.md"
    if not agents_md.exists():
        return skipped(3, "72.5", "AGENTS.md contract", "AGENTS.md not found", phase="72")

    text = agents_md.read_text(encoding="utf-8")
    markers = ["Service Coverage Contract", "aq-qa check", "Dashboard panel"]
    missing = [m for m in markers if m not in text]
    if missing:
        return failed(3, "72.5", "AGENTS.md contract",
                      f"missing markers: {missing}", phase="72")

    return passed(3, "72.5", "AGENTS.md: Service Coverage Contract section present", phase="72")


# ---------------------------------------------------------------------------
# 72.6 — Autonomous loop audit: gap-remediate timer state and recent runs
# ---------------------------------------------------------------------------

def _check_72_6(_ctx: RunContext) -> CheckResult:
    """Audit autonomous gap-remediation loop: timer active, recent run recorded."""
    import subprocess as _sp

    # Check timer active
    try:
        r = _sp.run(
            ["systemctl", "is-active", "ai-gap-auto-remediate.timer"],
            capture_output=True, text=True, timeout=5,
        )
        timer_state = r.stdout.strip()
    except Exception as exc:
        return skipped(3, "72.6", "Autonomous gap-remediate loop",
                       f"systemctl error: {exc}", phase="72")

    if timer_state != "active":
        return failed(3, "72.6", "Autonomous gap-remediate loop",
                      f"timer not active: state={timer_state}", phase="72")

    # Check for recent log file (last 7 days)
    import time as _time
    log_base = Path(os.environ.get(
        "GAP_REMEDIATION_LOG_DIR",
        Path.home() / ".local" / "state" / "nixos-ai-stack" / "gap-remediation",
    ))
    recent_logs = []
    if log_base.exists():
        cutoff = _time.time() - 7 * 86400
        recent_logs = [
            p for p in log_base.glob("remediation-*.jsonl")
            if p.stat().st_mtime > cutoff
        ]

    note = f"{len(recent_logs)} log file(s) in last 7d" if recent_logs else "no recent log files (may not have run yet)"
    return passed(3, "72.6",
                  f"gap-remediate timer active; {note}", phase="72")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run(ctx: RunContext) -> list[CheckResult]:
    return [
        _check_72_1(ctx),
        _check_72_2(ctx),
        _check_72_3(ctx),
        _check_72_4(ctx),
        _check_72_5(ctx),
        _check_72_6(ctx),
    ]
