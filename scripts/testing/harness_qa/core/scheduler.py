"""Bounded, partial-result check scheduler for QA phases.

A phase is a list of independent check functions. Each runs on a daemon thread under a per-check deadline and
a whole-phase budget, so one slow or hung check (or a busy dependency) cannot turn the phase into an
all-or-nothing outer timeout. A check that does not finish is reported as SKIP with a "DEGRADED:" reason
(never PASS), so monitors can tell "busy" from "healthy" and from "failed"."""
from __future__ import annotations

import os
import threading
import time
from typing import Callable

from .result import CheckResult, failed, skipped

DEGRADED = "DEGRADED"


def _env_float(name: str) -> float | None:
    try:
        v = float(os.environ.get(name, "").strip())
        return v if v > 0 else None
    except ValueError:
        return None


def resolve_limits(n_checks: int) -> tuple[int, float, float]:
    """(workers, per_check_s, budget_s). Env overrides: AQ_QA_PHASE0_WORKERS / _CHECK_TIMEOUT_S / _BUDGET_S.
    Defaults derive from the host and the plan: budget = 85% of the caller's outer deadline (HARNESS_TIMEOUT_S)
    when known, else 5 s per check; per-check = budget/4; workers = a quarter of the CPUs, 1..4."""
    w = _env_float("AQ_QA_PHASE0_WORKERS")
    workers = int(w) if w else max(1, min(4, (os.cpu_count() or 2) // 4))
    budget = _env_float("AQ_QA_PHASE0_BUDGET_S")
    if budget is None:
        outer = _env_float("HARNESS_TIMEOUT_S")
        budget = outer * 0.85 if outer else 5.0 * n_checks
    per_check = _env_float("AQ_QA_PHASE0_CHECK_TIMEOUT_S") or budget / 4
    return max(1, workers), per_check, budget


def degraded_result(name: str, reason: str) -> CheckResult:
    return skipped(4, f"0.degraded.{name.removeprefix('_check_')}", f"{name.removeprefix('_check_')} check", f"{DEGRADED}: {reason}")


def run_checks(
    ctx,
    checks: list[Callable],
    *,
    workers: int,
    per_check_s: float,
    budget_s: float,
    busy_hint: Callable[[], str] | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> list[CheckResult]:
    """Run checks (each `fn(ctx) -> list[CheckResult]`), preserving plan order in the returned list."""
    workers = max(1, workers)
    n = len(checks)
    slots: list[list[CheckResult] | None] = [None] * n
    pending = list(range(n))
    running: dict[int, tuple[threading.Thread, float, dict]] = {}
    timed_out_threads: list[threading.Thread] = []
    start = clock()

    hint_lock = threading.Lock()
    hint_value = ""
    hint_thread: threading.Thread | None = None
    hint_at = -1.0
    # Bound hint probes strictly so a stalled /slots HTTP call cannot push past budget_s or the outer timeout.
    hint_wait_s = min(0.15, max(0.02, budget_s * 0.05))

    def hint() -> str:
        nonlocal hint_value, hint_thread, hint_at
        probe_fn = busy_hint
        if probe_fn is None:
            return ""
        now_real = time.monotonic()
        with hint_lock:
            t = hint_thread
            if t is not None:
                if t.is_alive():
                    return hint_value
                if now_real - hint_at < 2.0:
                    return hint_value

            def _probe() -> None:
                nonlocal hint_value, hint_at
                try:
                    val = probe_fn() or ""
                except Exception:
                    val = ""
                with hint_lock:
                    hint_value = val
                    hint_at = time.monotonic()

            t = threading.Thread(target=_probe, name="qa-busy-hint", daemon=True)
            hint_thread = t
            hint_value = ""
            hint_at = now_real
            t.start()
        t.join(hint_wait_s)
        with hint_lock:
            return hint_value

    def drain_completed() -> None:
        timed_out_threads[:] = [t for t in timed_out_threads if t.is_alive()]
        for i in list(running):
            t, _, box = running[i]
            if not t.is_alive():
                slots[i] = box["r"]
                del running[i]

    def launch(i: int) -> None:
        box: dict = {}

        def target() -> None:
            try:
                box["r"] = list(checks[i](ctx))
            except BaseException as exc:  # a crashing check is a real defect, never a pass
                box["r"] = [failed(4, f"0.error.{checks[i].__name__.removeprefix('_check_')}",
                                   f"{checks[i].__name__.removeprefix('_check_')} check", f"raised {type(exc).__name__}: {str(exc)[:160]}")]

        t = threading.Thread(target=target, name=checks[i].__name__, daemon=True)
        running[i] = (t, clock(), box)
        t.start()

    while pending or running:
        drain_completed()
        if not pending and not running:
            break
        now = clock()
        if now - start >= budget_s:
            why = f"phase budget {budget_s:.0f}s exhausted{hint()}"
            # Re-drain in case a worker finished while busy_hint() was queried.
            drain_completed()
            for i in list(running):
                slots[i] = [degraded_result(checks[i].__name__, f"still running at {why}")]
            for i in pending:
                slots[i] = [degraded_result(checks[i].__name__, f"not started, {why}")]
            break
        for i in list(running):
            t, t0, box = running[i]
            if not t.is_alive():
                slots[i] = box["r"]
                del running[i]
            elif now - t0 >= per_check_s:
                slots[i] = [degraded_result(checks[i].__name__, f"exceeded {per_check_s:.0f}s per-check budget{hint()}")]
                timed_out_threads.append(t)
                del running[i]
        while pending and (len(running) + len(timed_out_threads)) < workers:
            launch(pending.pop(0))
        wait_target = next(iter(running.values()))[0] if running else (timed_out_threads[0] if timed_out_threads else None)
        if wait_target is not None:
            wait_target.join(0.05)
    out: list[CheckResult] = []
    for s in slots:
        out.extend(s or [])
    return out
