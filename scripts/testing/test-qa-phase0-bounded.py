#!/usr/bin/env python3
"""Phase 0 must return a partial per-check result under a deadline, never an all-or-nothing timeout."""
import importlib.util
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "testing"))
from harness_qa.core import scheduler  # noqa: E402
from harness_qa.core.result import Status, passed, failed  # noqa: E402


def _ok(ctx):
    return [passed(4, "t.ok", "ok")]


def _bad(ctx):
    return [failed(4, "t.bad", "bad", "real failure")]


def _boom(ctx):
    raise RuntimeError("kaboom")


def _hang(ctx):
    time.sleep(30)
    return [passed(4, "t.hang", "hang")]


def check(cond, msg):
    if not cond:
        print(f"FAIL: {msg}")
        raise SystemExit(1)


def main() -> int:
    t0 = time.monotonic()
    r = scheduler.run_checks(None, [_ok, _hang, _bad, _boom, _ok], workers=2, per_check_s=0.4, budget_s=5)
    check(time.monotonic() - t0 < 3, "hung check must not block the phase")
    check(len(r) == 5, f"every check yields a row: {len(r)}")
    check([x.status for x in r] == [Status.PASS, Status.SKIP, Status.FAIL, Status.FAIL, Status.PASS],
          "order preserved; hang=SKIP, real failure and crash stay FAIL")
    check("DEGRADED:" in r[1].to_dict()["description"], "hung check is marked DEGRADED, not passed")
    check("kaboom" in r[3].reason, "crash reason surfaced")

    t0 = time.monotonic()
    r = scheduler.run_checks(None, [_hang, _hang, _ok, _ok], workers=1, per_check_s=30, budget_s=0.5,
                             busy_hint=lambda: "; llama busy")
    check(time.monotonic() - t0 < 3, "phase budget bounds total wall time")
    check([x.status for x in r] == [Status.SKIP] * 4, "budget exhaustion degrades running and unstarted checks")
    check("llama busy" in r[0].reason and "not started" in r[2].reason, "reasons say busy / not started")

    os.environ.pop("AQ_QA_PHASE0_BUDGET_S", None)
    os.environ["HARNESS_TIMEOUT_S"] = "100"
    os.environ["AQ_QA_PHASE0_WORKERS"] = "3"
    w, per, b = scheduler.resolve_limits(10)
    check((w, b, per) == (3, 85.0, 85.0 / 4), f"limits derive from env: {(w, per, b)}")
    os.environ["AQ_QA_PHASE0_BUDGET_S"] = "40"
    os.environ["AQ_QA_PHASE0_CHECK_TIMEOUT_S"] = "7"
    check(scheduler.resolve_limits(10) == (3, 7.0, 40.0), "explicit env overrides win")

    from harness_qa.phases import phase0
    import subprocess as sp

    def _times_out(ctx):
        try:
            phase0.subprocess.run(["sleep", "5"], timeout=0.05)
        except sp.TimeoutExpired:
            return [failed(4, "t.to", "to", "timeout")]
    os.environ["AQ_QA_TIMEOUT_SCALE"] = "1"
    check(phase0._demote_timeouts(_times_out)(None)[0].status == Status.SKIP, "subprocess timeout -> DEGRADED SKIP")
    check(phase0._demote_timeouts(_bad)(None)[0].status == Status.FAIL, "non-timeout failure stays FAIL")

    # phase0.run wires the scheduler; the plan is declarative.
    src = (ROOT / "scripts/testing/harness_qa/phases/phase0.py").read_text()
    check("run_checks(" in src and "def _plan(" in src, "phase0.run uses the bounded scheduler")

    # Monitor: DEGRADED skips are surfaced, are not failures, and never count as clean.
    mspec = importlib.util.spec_from_file_location("mon", ROOT / "scripts/health/ai-stack-health-monitor.py")
    assert mspec is not None and mspec.loader is not None
    mon = importlib.util.module_from_spec(mspec)
    mspec.loader.exec_module(mon)
    data = {"phase": "0", "passed": 1, "failed": 0, "skipped": 1, "degraded_confidence": False,
            "_monitor_returncode": 0,
            "tests": [{"id": "a", "status": "PASS", "description": "x"},
                      {"id": "0.degraded.z", "status": "SKIP", "description": "z check (DEGRADED: exceeded 9s)"}]}
    check(len(mon.degraded_checks(data)) == 1, "monitor finds degraded rows")
    check(not mon.failed_checks(data), "degraded is not a failure")
    check(not mon.is_complete_clean_phase0_result(data), "degraded run is never 'clean'")
    print("PASS: phase 0 bounded scheduler (partial results, DEGRADED semantics, env limits, monitor)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
