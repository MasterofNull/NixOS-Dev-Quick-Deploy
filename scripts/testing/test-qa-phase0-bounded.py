#!/usr/bin/env python3
"""Phase 0 must return a partial per-check result under a deadline, never an all-or-nothing timeout."""
import importlib.util
import os
import subprocess as sp
import sys
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace

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

    def _times_out(ctx):
        try:
            phase0.subprocess.run(["sleep", "5"], timeout=0.05)
        except sp.TimeoutExpired:
            return [failed(4, "t.to", "to", "timeout")]
    os.environ["AQ_QA_TIMEOUT_SCALE"] = "1"
    check(phase0._demote_timeouts(_times_out)(None)[0].status == Status.SKIP, "subprocess timeout -> DEGRADED SKIP")
    check(phase0._demote_timeouts(_bad)(None)[0].status == Status.FAIL, "non-timeout failure stays FAIL")

    # Finding 1: mixed results in the same check function must demote ONLY the timeout result.
    def _mixed_fail_then_timeout(ctx):
        out = [failed(4, "t.real", "real", "real failure")]
        try:
            phase0.subprocess.run(["sleep", "5"], timeout=0.05)
        except sp.TimeoutExpired:
            out.append(failed(4, "t.to", "to", "timeout"))
        return out

    mixed1 = phase0._demote_timeouts(_mixed_fail_then_timeout)(None)
    check([x.status for x in mixed1] == [Status.FAIL, Status.SKIP],
          f"independent FAIL before timeout must stay FAIL: {[x.status for x in mixed1]}")

    def _mixed_timeout_then_fail(ctx):
        out = []
        try:
            phase0.subprocess.run(["sleep", "5"], timeout=0.05)
        except sp.TimeoutExpired:
            out.append(failed(4, "t.to", "to", "timeout"))
        out.append(failed(4, "t.real", "real", "exit 1"))
        return out

    mixed2 = phase0._demote_timeouts(_mixed_timeout_then_fail)(None)
    check([x.status for x in mixed2] == [Status.SKIP, Status.FAIL],
          f"independent FAIL after timeout must stay FAIL: {[x.status for x in mixed2]}")

    # Finding 1 (_check_flagship_cli): 0.6.1 failure must survive a 0.6.2 gemini probe timeout.
    with tempfile.TemporaryDirectory() as td:
        repo = Path(td)
        probe_path = repo / "scripts" / "testing" / "qa-provider-probe.py"
        probe_path.parent.mkdir(parents=True, exist_ok=True)
        probe_path.write_text(
            "def run_provider_probe(**kwargs):\n"
            "    return [{'provider_id': 'codex', 'result': 'fail'}]\n",
            encoding="utf-8",
        )
        orig_run = phase0.subprocess.run

        def _fake_gemini_timeout(*args, **kwargs):
            raise sp.TimeoutExpired(cmd=args[0], timeout=kwargs.get("timeout", 20))

        phase0.subprocess.run = _fake_gemini_timeout
        try:
            ctx = SimpleNamespace(
                should_run=lambda _layer: True,
                repo_root=repo,
                qa_invocation_id="test-invocation",
                primary_user_path="/bin",
                primary_home="/tmp",
                primary_user="test",
            )
            cli_res = phase0._demote_timeouts(phase0._check_flagship_cli)(ctx)
        finally:
            phase0.subprocess.run = orig_run
        check(len(cli_res) == 2, f"_check_flagship_cli yields 2 results: {len(cli_res)}")
        check(cli_res[0].id == "0.6.1" and cli_res[0].status == Status.FAIL,
              f"0.6.1 CLI smoke failure must stay FAIL when 0.6.2 times out: {cli_res[0]}")
        check(cli_res[1].id == "0.6.2" and cli_res[1].status == Status.SKIP and "DEGRADED:" in cli_res[1].reason,
              f"0.6.2 gemini timeout must demote to DEGRADED SKIP: {cli_res[1]}")

    # Finding 2: timed-out still-alive threads count against the concurrency cap.
    lock = threading.Lock()
    active = 0
    max_active = 0
    slow_done = threading.Event()

    def _slow_then_finish(ctx):
        nonlocal active, max_active
        with lock:
            active += 1
            max_active = max(max_active, active)
        try:
            time.sleep(0.35)
            return [passed(4, "t.slow", "slow")]
        finally:
            with lock:
                active -= 1
            slow_done.set()

    def _tracked_ok(ctx):
        nonlocal active, max_active
        with lock:
            active += 1
            max_active = max(max_active, active)
        try:
            return [passed(4, "t.fast", "fast")]
        finally:
            with lock:
                active -= 1

    r_cap = scheduler.run_checks(None, [_slow_then_finish, _tracked_ok, _tracked_ok],
                                 workers=1, per_check_s=0.1, budget_s=2.0)
    slow_done.wait(timeout=2.0)
    check(max_active == 1, f"workers=1 concurrency must stay <= 1 across per-check timeout (got {max_active})")
    check([x.status for x in r_cap] == [Status.SKIP, Status.PASS, Status.PASS],
          f"slow check degrades, subsequent checks run after slot frees: {[x.status for x in r_cap]}")

    # Finding 3: phase expiry collects completed workers before marking running checks degraded.
    finished = threading.Event()

    def _finishes_before_expiry(ctx):
        finished.set()
        return [failed(4, "t.done", "done", "real fail right before expiry")]

    ticks = iter([0.0, 0.0, 0.0, 10.0, 10.0, 10.0])

    def _expiry_clock():
        # Hold clock below budget until _finishes_before_expiry has returned, then jump past expiry.
        if not finished.is_set():
            return next(ticks, 0.0)
        return 10.0

    r_exp = scheduler.run_checks(None, [_finishes_before_expiry, _hang], workers=2,
                                 per_check_s=5.0, budget_s=1.0, clock=_expiry_clock)
    check(r_exp[0].status == Status.FAIL and "real fail" in r_exp[0].reason,
          f"completed worker at expiry must keep its FAIL result: {r_exp[0]}")
    check(r_exp[1].status == Status.SKIP and "still running" in r_exp[1].reason,
          f"actually running worker at expiry must be marked still running: {r_exp[1]}")

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

    # Finding 4: monitor clamps oversized AQ_QA_PHASE0_BUDGET_S strictly below _HARNESS_TIMEOUT_S.
    captured_envs = []
    orig_mon_run = mon.subprocess.run
    orig_budget_env = os.environ.get("AQ_QA_PHASE0_BUDGET_S")
    try:
        def _capture_run(cmd, *, env=None, capture_output=False, text=False, timeout=None):
            captured_envs.append((dict(env or {}), timeout))
            return sp.CompletedProcess(cmd, 0, stdout='{"tests":[]}', stderr="")

        mon.subprocess.run = _capture_run
        for oversized in (str(mon._HARNESS_TIMEOUT_S), str(mon._HARNESS_TIMEOUT_S + 500), "0", "bogus"):
            os.environ["AQ_QA_PHASE0_BUDGET_S"] = oversized
            mon.run_aq_qa("0")
            env_seen, outer_t = captured_envs[-1]
            bval = float(env_seen["AQ_QA_PHASE0_BUDGET_S"])
            check(0 < bval < outer_t,
                  f"monitor must clamp AQ_QA_PHASE0_BUDGET_S={oversized!r} strictly below {outer_t}, got {bval}")

        os.environ["AQ_QA_PHASE0_BUDGET_S"] = "60"
        mon.run_aq_qa("0")
        check(captured_envs[-1][0]["AQ_QA_PHASE0_BUDGET_S"] == "60",
              "monitor preserves a smaller valid AQ_QA_PHASE0_BUDGET_S override")
    finally:
        mon.subprocess.run = orig_mon_run
        if orig_budget_env is None:
            os.environ.pop("AQ_QA_PHASE0_BUDGET_S", None)
        else:
            os.environ["AQ_QA_PHASE0_BUDGET_S"] = orig_budget_env
    print("PASS: phase 0 bounded scheduler (partial results, DEGRADED semantics, env limits, monitor)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
