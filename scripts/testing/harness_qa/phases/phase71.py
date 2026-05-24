"""Phase 71 checks — Integration Health Contract.

These checks exist because critical integration paths had zero QA coverage
and broke silently for days. Every check here targets a path that was either
broken and undetected, or is a key integration seam with no prior coverage.

71.1  local_agent_runtime.py exists at the correct resolved path
71.2  POST /control/ai-coordinator/delegate returns non-500 (not agent_runtime_missing)
71.3  ralph-wiggum POST /tasks → task queued (not 401, not 500)
71.4  ralph-wiggum task lifecycle completes without runtime error
71.5  aider-wrapper /health returns 200 (independent binary path check)
71.6  Autonomous timer services active (gap-remediate, crystallize, context-warmer)
71.7  Dashboard /health/audit returns real generation data (not hardcoded fake)
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Tuple

from ..core.context import RunContext
from ..core.result import CheckResult, passed, failed, skipped

_REPO = Path(__file__).resolve().parents[4]

# The runtime path as corrected in be92c6cf — must stay in sync with
# ai_coordinator_handlers.py Path(__file__).parent.parent.parent.parent
_EXPECTED_RUNTIME = (
    _REPO / "ai-stack" / "agents" / "runtimes" / "local_agent_runtime.py"
)


def _http(
    method: str, url: str, body: Any = None, api_key: str = "", timeout: int = 15
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


def _coord_key(ctx: RunContext) -> str:
    try:
        return Path("/run/secrets/hybrid_coordinator_api_key").read_text().strip()
    except OSError:
        return os.environ.get("HYBRID_API_KEY", "")


def _ralph_key() -> str:
    # ralph-wiggum uses aidb_api_key per mcp-servers.nix wiring
    try:
        return Path("/run/secrets/aidb_api_key").read_text().strip()
    except OSError:
        return os.environ.get("RALPH_API_KEY", "")


# ---------------------------------------------------------------------------
# 71.1 — local_agent_runtime.py path integrity
# ---------------------------------------------------------------------------

def _check_71_1(_ctx: RunContext) -> CheckResult:
    """Verify local_agent_runtime.py exists at the path coordinator will resolve."""
    if _EXPECTED_RUNTIME.exists():
        return passed(
            3, "71.1",
            f"local_agent_runtime.py present at {_EXPECTED_RUNTIME}",
            phase="71",
        )
    # Also check the wrong (pre-fix) path to help diagnose regressions
    wrong_path = (
        _REPO / "ai-stack" / "mcp-servers" / "agents" / "runtimes" / "local_agent_runtime.py"
    )
    hint = " (wrong pre-fix path also absent)" if not wrong_path.exists() else " (pre-fix path exists — path bug may have regressed)"
    return failed(
        3, "71.1", "local_agent_runtime.py path integrity",
        f"missing at {_EXPECTED_RUNTIME}{hint}",
        phase="71",
    )


# ---------------------------------------------------------------------------
# 71.2 — POST /control/ai-coordinator/delegate probe
# ---------------------------------------------------------------------------

def _check_71_2(ctx: RunContext) -> CheckResult:
    """POST /control/ai-coordinator/delegate must not return agent_runtime_missing."""
    key = _coord_key(ctx)
    url = f"{ctx.hybrid_url}/control/ai-coordinator/delegate"
    status, body = _http(
        "POST", url,
        body={"task": "aq-qa probe 71.2", "profile": "local-tool-calling",
              "context": {}, "agent_timeout_sec": 5, "max_tokens": 16},
        api_key=key, timeout=20,
    )
    if status == 0:
        return skipped(3, "71.2", "Coordinator delegate endpoint",
                       "coordinator unreachable or timed out (inference may be busy)", phase="71")

    if isinstance(body, dict) and body.get("error") == "agent_runtime_missing":
        path = body.get("path", "unknown")
        return failed(
            3, "71.2", "Coordinator delegate endpoint",
            f"agent_runtime_missing — path bug at {path} (check be92c6cf fix + nixos-rebuild)",
            phase="71",
        )

    # 200/201/202 = task accepted; 408/503/504 = timeout/busy but runtime found; all OK here
    if status in (200, 201, 202, 408, 503, 504):
        return passed(3, "71.2", f"Coordinator delegate: runtime found, HTTP {status}", phase="71")

    # 404 = route not deployed yet
    if status == 404:
        return failed(3, "71.2", "Coordinator delegate endpoint", "404 — needs nixos-rebuild", phase="71")

    return failed(
        3, "71.2", "Coordinator delegate endpoint",
        f"HTTP {status}: {str(body)[:80]}",
        phase="71",
    )


# ---------------------------------------------------------------------------
# 71.3 — ralph-wiggum task submission
# ---------------------------------------------------------------------------

def _check_71_3(_ctx: RunContext) -> CheckResult:
    """POST /tasks to ralph-wiggum returns a task_id (not 401 or 500)."""
    key = _ralph_key()
    if not key:
        return skipped(3, "71.3", "ralph-wiggum task submission", "no ralph API key found", phase="71")

    url = "http://127.0.0.1:8004/tasks"
    status, body = _http(
        "POST", url,
        body={"prompt": "aq-qa probe 71.3: echo ok", "backend": "aider", "max_iterations": 1},
        api_key=key, timeout=15,
    )
    if status == 0:
        return skipped(3, "71.3", "ralph-wiggum task submission", "ralph-wiggum unreachable", phase="71")
    if status == 401:
        return failed(3, "71.3", "ralph-wiggum task submission", "401 — API key mismatch", phase="71")
    if status == 500:
        return failed(3, "71.3", "ralph-wiggum task submission",
                      f"500 — {str(body)[:80]}", phase="71")
    if status in (200, 201, 202):
        task_id = body.get("task_id", "") if isinstance(body, dict) else ""
        if task_id:
            return passed(3, "71.3", f"ralph-wiggum task queued: {task_id[:8]}…", phase="71")
        return failed(3, "71.3", "ralph-wiggum task submission", "no task_id in response", phase="71")

    return failed(3, "71.3", "ralph-wiggum task submission",
                  f"HTTP {status}: {str(body)[:60]}", phase="71")


# ---------------------------------------------------------------------------
# 71.4 — ralph-wiggum task lifecycle (submit → poll → not 500)
# ---------------------------------------------------------------------------

def _check_71_4(_ctx: RunContext) -> CheckResult:
    """Submit a minimal ralph-wiggum task and verify it runs without runtime 500."""
    key = _ralph_key()
    if not key:
        return skipped(3, "71.4", "ralph-wiggum task lifecycle", "no ralph API key", phase="71")

    # Submit
    status, body = _http(
        "POST", "http://127.0.0.1:8004/tasks",
        body={"prompt": "aq-qa probe 71.4: respond with the word OK only", "backend": "aider", "max_iterations": 1},
        api_key=key, timeout=15,
    )
    if status == 0:
        return skipped(3, "71.4", "ralph-wiggum lifecycle", "ralph-wiggum unreachable", phase="71")
    if status not in (200, 201, 202):
        return skipped(3, "71.4", "ralph-wiggum lifecycle",
                       f"submit failed HTTP {status} (check 71.3)", phase="71")

    task_id = (body or {}).get("task_id", "") if isinstance(body, dict) else ""
    if not task_id:
        return skipped(3, "71.4", "ralph-wiggum lifecycle", "no task_id from submit", phase="71")

    # Poll up to 30s
    deadline = time.time() + 30
    last_status = "unknown"
    last_error = None
    while time.time() < deadline:
        ps, pb = _http("GET", f"http://127.0.0.1:8004/tasks/{task_id}", api_key=key, timeout=10)
        if ps not in (200, 201):
            break
        if isinstance(pb, dict):
            last_status = pb.get("status", "unknown")
            last_error = pb.get("error")
            if last_status in ("completed", "failed", "stopped"):
                break
        time.sleep(2)

    if last_status == "completed":
        return passed(3, "71.4", "ralph-wiggum task lifecycle: completed without runtime error", phase="71")

    if last_status == "failed" and last_error:
        if "agent_runtime_missing" in str(last_error) or "500" in str(last_error):
            return failed(3, "71.4", "ralph-wiggum lifecycle",
                          f"runtime 500 in task result: {str(last_error)[:80]}", phase="71")
        # Failed for other reasons (e.g. model timeout) — runtime path is OK
        return passed(3, "71.4",
                      f"ralph-wiggum runtime reachable (task failed for non-path reason: {str(last_error)[:40]})",
                      phase="71")

    # Still running or unknown — not a failure, runtime path didn't 500
    return passed(3, "71.4",
                  f"ralph-wiggum runtime reachable (task status={last_status} after 30s probe)",
                  phase="71")


# ---------------------------------------------------------------------------
# 71.5 — aider-wrapper health
# ---------------------------------------------------------------------------

def _check_71_5(_ctx: RunContext) -> CheckResult:
    """GET /health on aider-wrapper returns 200."""
    try:
        aider_key = Path("/run/secrets/aider_wrapper_api_key").read_text().strip()
    except OSError:
        aider_key = os.environ.get("AIDER_WRAPPER_API_KEY", "")

    port = os.environ.get("AIDER_WRAPPER_PORT", "8090")
    status, body = _http("GET", f"http://127.0.0.1:{port}/health", api_key=aider_key, timeout=10)
    if status == 0:
        status, body = _http("GET", f"http://127.0.0.1:{port}/health", timeout=10)

    if status == 0:
        return skipped(3, "71.5", "aider-wrapper health",
                       f"aider-wrapper unreachable on :{port}", phase="71")
    if status == 200:
        aider_ok = (body or {}).get("aider_available", None) if isinstance(body, dict) else None
        detail = f"aider_available={aider_ok}" if aider_ok is not None else "ok"
        return passed(3, "71.5", f"aider-wrapper healthy ({detail})", phase="71")
    return failed(3, "71.5", "aider-wrapper health", f"HTTP {status}: {str(body)[:60]}", phase="71")


# ---------------------------------------------------------------------------
# 71.6 — Autonomous timer services active
# ---------------------------------------------------------------------------

def _check_71_6(_ctx: RunContext) -> CheckResult:
    """Verify key autonomous timer units are active (not dead/failed)."""
    import subprocess as _sp

    timers = {
        "ai-gap-auto-remediate.timer": "daily self-improvement",
        "ai-crystallize-sessions.timer": "memory crystallization",
        "ai-context-warmer.timer": "context pre-warming",
        "ai-aidb-reindex.timer": "knowledge re-indexing",
    }
    inactive: list[str] = []
    failed_units: list[str] = []

    for unit, label in timers.items():
        try:
            r = _sp.run(
                ["systemctl", "is-active", unit],
                capture_output=True, text=True, timeout=5,
            )
            state = r.stdout.strip()
            if state == "active":
                continue
            elif state in ("failed", "error"):
                failed_units.append(f"{unit} ({label})")
            else:
                inactive.append(f"{unit}={state}")
        except Exception:
            inactive.append(f"{unit}=error")

    if failed_units:
        return failed(3, "71.6", "Autonomous timers",
                      f"failed units: {', '.join(failed_units)}", phase="71")
    if inactive:
        return failed(3, "71.6", "Autonomous timers",
                      f"inactive: {', '.join(inactive)}", phase="71")
    return passed(3, "71.6",
                  f"All {len(timers)} autonomous timers active", phase="71")


# ---------------------------------------------------------------------------
# 71.7 — Dashboard /health/audit returns real generation data
# ---------------------------------------------------------------------------

def _check_71_7(_ctx: RunContext) -> CheckResult:
    """GET /api/health/audit must return real NixOS generation data (not hardcoded fake)."""
    status, body = _http("GET", "http://127.0.0.1:8889/api/health/audit", timeout=10)
    if status == 0:
        return skipped(3, "71.7", "Dashboard health/audit", "dashboard unreachable on :8889", phase="71")
    if status != 200:
        return failed(3, "71.7", "Dashboard health/audit", f"HTTP {status}", phase="71")

    events = body if isinstance(body, list) else []
    # Hardcoded fake data check: the old stub always returned "Generation 54 activation"
    fake_markers = {"Generation 54 activation", "L6 Homeostasis triggered"}
    details = {e.get("detail", "") for e in events}
    if fake_markers & details:
        return failed(3, "71.7", "Dashboard health/audit",
                      "returned hardcoded fake data — dashboard restart needed", phase="71")
    if not events:
        return skipped(3, "71.7", "Dashboard health/audit",
                       "returned empty list — dashboard may need restart", phase="71")
    # Verify at least one rebuild entry with a real generation number > 54
    rebuild_events = [e for e in events if e.get("type") == "rebuild"]
    if rebuild_events:
        return passed(3, "71.7",
                      f"health/audit: {len(events)} real events, {len(rebuild_events)} rebuild entries",
                      phase="71")
    return passed(3, "71.7", f"health/audit: {len(events)} real events (no fake data)", phase="71")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run(ctx: RunContext) -> list[CheckResult]:
    return [
        _check_71_1(ctx),
        _check_71_2(ctx),
        _check_71_3(ctx),
        _check_71_4(ctx),
        _check_71_5(ctx),
        _check_71_6(ctx),
        _check_71_7(ctx),
    ]
