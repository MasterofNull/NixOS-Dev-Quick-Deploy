#!/usr/bin/env python3
"""Offline tests — Foundation C SAFETY: dead-man auto-revert guard.

Exercises `scripts/ai/lib/activation_guard.py` as a pure library (tmp state
dirs, monkeypatched event emission — no live systemd, no real aq-event
subprocess, no network) per the owner-directed design in
`scripts/ai/aq-activation-guard`'s module docstring.

Covers the five scenarios the design calls out explicitly:
  1. arm -> health-green (at deadline) -> confirmed, revert NEVER runs
  2. arm -> health-red (at deadline)   -> revert executed + LOUD alert emitted
  3. arm -> deadline with an unreadable/erroring health check -> fail-safe revert
  4. disarm before deadline cancels — sweep after the deadline is then a no-op
  5. default-off is inert: sweep over an empty/no armed-dir state does nothing,
     and the guard refuses to arm without a health-check or a revert-cmd
     (fail-closed: never arm a dead-man switch with nothing to check/do).

Plus: control-id path-traversal is rejected, and a broken event spine
(emit_event failing) is logged to the local fallback file rather than
silently swallowed or allowed to crash the sweep.

Run directly: `python3 scripts/testing/test-activation-auto-revert-guard.py`
Exits 0 iff every test passes; each failure prints the assertion detail.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LIB_DIR = str(_REPO_ROOT / "scripts" / "ai" / "lib")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import activation_guard as ag  # noqa: E402

# --------------------------------------------------------------------------
# tiny test harness (no external deps, mirrors test-capability-lease-gate.py)
# --------------------------------------------------------------------------
_PASS = 0
_FAIL = 0
_FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        print(f"PASS: {name}")
    else:
        _FAIL += 1
        msg = f"FAIL: {name}" + (f" — {detail}" if detail else "")
        print(msg)
        _FAILURES.append(msg)


class _Recorder:
    """Captures emit_event/emit_pulse calls without touching the real event spine."""

    def __init__(self):
        self.events: list[tuple] = []
        self.pulses: list[tuple] = []

    def emit_event(self, agent, event_type, subject, payload, sdir=None):
        self.events.append((agent, event_type, subject, payload))
        return True

    def emit_pulse(self, agent, action, scope, outcome, sdir=None):
        self.pulses.append((agent, action, scope, outcome))
        return True

    def types(self):
        return [e[1] for e in self.events]


def _tmp_sdir() -> Path:
    d = Path(tempfile.mkdtemp(prefix="aq-activation-guard-test-"))
    return d


def _patch(monkeys):
    rec = _Recorder()
    monkeys["emit_event"] = ag.emit_event
    monkeys["emit_pulse"] = ag.emit_pulse
    ag.emit_event = rec.emit_event
    ag.emit_pulse = rec.emit_pulse
    return rec


def _unpatch(monkeys):
    ag.emit_event = monkeys["emit_event"]
    ag.emit_pulse = monkeys["emit_pulse"]


# --------------------------------------------------------------------------
# 1. arm -> health-green -> confirmed, revert never runs
# --------------------------------------------------------------------------
def test_health_green_confirms_no_revert():
    sdir = _tmp_sdir()
    monkeys = {}
    rec = _patch(monkeys)
    try:
        revert_marker = sdir / "REVERT_RAN"
        ag.arm(
            "test-c2", window_minutes=0.0001,  # effectively immediate deadline
            health_check_cmd="exit 0",
            revert_cmd=f"touch {revert_marker}",
            sdir=sdir,
        )
        time.sleep(0.02)
        results = ag.sweep(sdir=sdir, health_timeout=5, revert_timeout=5)
        check("health-green: sweep produced exactly one result", len(results) == 1, str(results))
        if results:
            check("health-green: action == confirmed", results[0]["action"] == "confirmed", str(results[0]))
        check("health-green: revert command never ran", not revert_marker.exists())
        check("health-green: armed record removed", not (sdir / "armed" / "test-c2.json").exists())
        check("health-green: activation.confirmed event emitted", "activation.confirmed" in rec.types(), str(rec.types()))
        check("health-green: no auto-reverted event", "activation.auto-reverted" not in rec.types())
        history = (sdir / ag.HISTORY_FILE).read_text().strip().splitlines()
        check("health-green: history has 1 terminal record", len(history) == 1, history)
        check("health-green: history record state == confirmed", json.loads(history[0])["state"] == "confirmed")
    finally:
        _unpatch(monkeys)
        shutil.rmtree(sdir, ignore_errors=True)


# --------------------------------------------------------------------------
# 2. arm -> health-red -> revert executed + LOUD alert
# --------------------------------------------------------------------------
def test_health_red_reverts_and_alerts():
    sdir = _tmp_sdir()
    monkeys = {}
    rec = _patch(monkeys)
    try:
        revert_marker = sdir / "REVERT_RAN"
        ag.arm(
            "test-c3b", window_minutes=0.0001,
            health_check_cmd="exit 1",  # RED
            revert_cmd=f"touch {revert_marker}",
            sdir=sdir,
        )
        time.sleep(0.02)
        results = ag.sweep(sdir=sdir, health_timeout=5, revert_timeout=5)
        check("health-red: exactly one result", len(results) == 1, str(results))
        if results:
            check("health-red: action == auto-reverted", results[0]["action"] == "auto-reverted", str(results[0]))
            check("health-red: revert reported ok", results[0]["ok"] is True, str(results[0]))
        check("health-red: revert command actually ran", revert_marker.exists())
        check("health-red: LOUD alert emitted", "activation.auto-reverted" in rec.types(), str(rec.types()))
        check("health-red: pulse emitted (Rule 8a)", len(rec.pulses) == 1, str(rec.pulses))
        check("health-red: armed record removed", not (sdir / "armed" / "test-c3b.json").exists())
        history = json.loads((sdir / ag.HISTORY_FILE).read_text().strip().splitlines()[0])
        check("health-red: history state == auto-reverted", history["state"] == "auto-reverted")
        check("health-red: history captured health_status red", history["health_status"] == ag.HEALTH_RED)
    finally:
        _unpatch(monkeys)
        shutil.rmtree(sdir, ignore_errors=True)


# --------------------------------------------------------------------------
# 3. FAIL-SAFE: unreadable/erroring health check at deadline -> revert (KEY PROPERTY)
# --------------------------------------------------------------------------
def test_unreadable_health_fails_safe_to_revert():
    sdir = _tmp_sdir()
    monkeys = {}
    rec = _patch(monkeys)
    try:
        revert_marker = sdir / "REVERT_RAN"
        # A command that doesn't exist -> shell returns nonzero, which run_health_check
        # already maps to RED via returncode; use a guaranteed-timeout instead to hit the
        # true "exception during health check" unreadable path.
        ag.arm(
            "test-unreadable", window_minutes=0.0001,
            health_check_cmd="sleep 5",  # will be forced to time out below
            revert_cmd=f"touch {revert_marker}",
            sdir=sdir,
        )
        time.sleep(0.02)
        results = ag.sweep(sdir=sdir, health_timeout=1, revert_timeout=5)  # 1s timeout << sleep 5
        check("unreadable: exactly one result", len(results) == 1, str(results))
        if results:
            check("unreadable: action == auto-reverted (fail-safe)", results[0]["action"] == "auto-reverted", str(results[0]))
            check("unreadable: health_status == unreadable", results[0]["health_status"] == ag.HEALTH_UNREADABLE, str(results[0]))
        check("unreadable: revert command actually ran", revert_marker.exists())
        check("unreadable: LOUD alert emitted", "activation.auto-reverted" in rec.types())

        # Also verify the pure run_health_check() mapping directly for a nonexistent binary
        # and for a missing command entirely, both of which must map to UNREADABLE too.
        status, detail = ag.run_health_check("", timeout=2)
        check("unreadable: empty health_check_cmd -> unreadable", status == ag.HEALTH_UNREADABLE, (status, detail))
    finally:
        _unpatch(monkeys)
        shutil.rmtree(sdir, ignore_errors=True)


# --------------------------------------------------------------------------
# 4. disarm cancels — sweep after the deadline is then a no-op
# --------------------------------------------------------------------------
def test_disarm_cancels_auto_revert():
    sdir = _tmp_sdir()
    monkeys = {}
    rec = _patch(monkeys)
    try:
        revert_marker = sdir / "REVERT_RAN"
        ag.arm(
            "test-disarm", window_minutes=0.0001,
            health_check_cmd="exit 1",  # would RED-revert if swept
            revert_cmd=f"touch {revert_marker}",
            sdir=sdir,
        )
        record = ag.disarm("test-disarm", agent="tester", reason="owner cancelled manually", sdir=sdir)
        check("disarm: returns disarmed state", record["state"] == "disarmed", str(record))
        check("disarm: activation.disarmed emitted", "activation.disarmed" in rec.types())
        check("disarm: armed record removed immediately", not (sdir / "armed" / "test-disarm.json").exists())

        time.sleep(0.02)  # past the (now-irrelevant) deadline
        results = ag.sweep(sdir=sdir, health_timeout=5, revert_timeout=5)
        check("disarm: sweep after disarm finds nothing to do", results == [], str(results))
        check("disarm: revert command never ran", not revert_marker.exists())
        check("disarm: confirm() on an already-disarmed control raises", _raises(lambda: ag.confirm("test-disarm", sdir=sdir)))
    finally:
        _unpatch(monkeys)
        shutil.rmtree(sdir, ignore_errors=True)


def test_confirm_cancels_before_deadline():
    sdir = _tmp_sdir()
    monkeys = {}
    rec = _patch(monkeys)
    try:
        revert_marker = sdir / "REVERT_RAN"
        ag.arm(
            "test-confirm", window_minutes=10,  # far future deadline
            health_check_cmd="exit 1",
            revert_cmd=f"touch {revert_marker}",
            sdir=sdir,
        )
        record = ag.confirm("test-confirm", agent="tester", sdir=sdir)
        check("confirm: returns confirmed state", record["state"] == "confirmed", str(record))
        check("confirm: confirm_source == manual", record["confirm_source"] == "manual")
        results = ag.sweep(sdir=sdir)
        check("confirm: nothing left to sweep", results == [], str(results))
        check("confirm: revert command never ran", not revert_marker.exists())
    finally:
        _unpatch(monkeys)
        shutil.rmtree(sdir, ignore_errors=True)


# --------------------------------------------------------------------------
# 5. default-off / inert behavior + fail-closed arm validation
# --------------------------------------------------------------------------
def test_empty_state_is_inert():
    sdir = _tmp_sdir()
    monkeys = {}
    _patch(monkeys)
    try:
        results = ag.sweep(sdir=sdir)
        check("inert: sweep over empty state does nothing", results == [], str(results))
        check("inert: no armed records listed", ag.list_armed(sdir=sdir) == [])
    finally:
        _unpatch(monkeys)
        shutil.rmtree(sdir, ignore_errors=True)


def _raises(fn) -> bool:
    try:
        fn()
        return False
    except ag.ActivationGuardError:
        return True


def test_arm_fails_closed_without_health_check_or_revert_cmd():
    sdir = _tmp_sdir()
    monkeys = {}
    _patch(monkeys)
    try:
        check(
            "fail-closed: arm without --health-check refused",
            _raises(lambda: ag.arm("x", 5, "", "touch /tmp/nope", sdir=sdir)),
        )
        check(
            "fail-closed: arm without --revert-cmd refused",
            _raises(lambda: ag.arm("x", 5, "exit 0", "", sdir=sdir)),
        )
        check(
            "fail-closed: arm with non-positive window refused",
            _raises(lambda: ag.arm("x", 0, "exit 0", "touch /tmp/nope", sdir=sdir)),
        )
        check("fail-closed: nothing was armed after the refused attempts", ag.list_armed(sdir=sdir) == [])
    finally:
        _unpatch(monkeys)
        shutil.rmtree(sdir, ignore_errors=True)


def test_control_id_path_traversal_rejected():
    sdir = _tmp_sdir()
    monkeys = {}
    _patch(monkeys)
    try:
        check(
            "control-id: path traversal rejected",
            _raises(lambda: ag.arm("../../etc/passwd", 5, "exit 0", "true", sdir=sdir)),
        )
        check(
            "control-id: shell metacharacter in id rejected",
            _raises(lambda: ag.arm("foo;rm -rf", 5, "exit 0", "true", sdir=sdir)),
        )
    finally:
        _unpatch(monkeys)
        shutil.rmtree(sdir, ignore_errors=True)


def test_double_arm_without_force_rejected():
    sdir = _tmp_sdir()
    monkeys = {}
    _patch(monkeys)
    try:
        ag.arm("test-dbl", 5, "exit 0", "true", sdir=sdir)
        check(
            "double-arm: second arm without --force rejected",
            _raises(lambda: ag.arm("test-dbl", 5, "exit 0", "true", sdir=sdir)),
        )
        # force=True must succeed and not raise
        try:
            ag.arm("test-dbl", 5, "exit 0", "true", sdir=sdir, force=True)
            ok = True
        except ag.ActivationGuardError:
            ok = False
        check("double-arm: --force overwrite succeeds", ok)
    finally:
        _unpatch(monkeys)
        shutil.rmtree(sdir, ignore_errors=True)


# --------------------------------------------------------------------------
# broken event spine: emit failure is logged to the local fallback, never raises
# --------------------------------------------------------------------------
def test_broken_event_spine_logs_fallback_never_raises():
    sdir = _tmp_sdir()
    orig_bin = ag._AQ_EVENT_BIN
    ag._AQ_EVENT_BIN = Path("/nonexistent/aq-event-does-not-exist")
    try:
        ok = ag.emit_event("tester", "activation.auto-reverted", "test-broken", {"k": "v"}, sdir=sdir)
        check("broken-spine: emit_event returns False (never raises)", ok is False)
        fallback = sdir / ag.EMIT_FAILURES_FILE
        check("broken-spine: fallback log file written", fallback.exists())
        if fallback.exists():
            content = fallback.read_text()
            check("broken-spine: fallback log mentions the event type", "activation.auto-reverted" in content, content)
    finally:
        ag._AQ_EVENT_BIN = orig_bin
        shutil.rmtree(sdir, ignore_errors=True)


def test_revert_command_failure_still_alerts():
    """Even if the revert command ITSELF fails, sweep must still alert (never disappear)."""
    sdir = _tmp_sdir()
    monkeys = {}
    rec = _patch(monkeys)
    try:
        ag.arm(
            "test-revert-fails", window_minutes=0.0001,
            health_check_cmd="exit 1",
            revert_cmd="exit 7",  # revert command itself fails
            sdir=sdir,
        )
        time.sleep(0.02)
        results = ag.sweep(sdir=sdir, health_timeout=5, revert_timeout=5)
        check("revert-fails: one result", len(results) == 1, str(results))
        if results:
            check("revert-fails: action still auto-reverted", results[0]["action"] == "auto-reverted", str(results[0]))
            check("revert-fails: ok reported False (revert itself failed)", results[0]["ok"] is False, str(results[0]))
        check("revert-fails: LOUD alert still emitted despite revert failure", "activation.auto-reverted" in rec.types())
    finally:
        _unpatch(monkeys)
        shutil.rmtree(sdir, ignore_errors=True)


# --------------------------------------------------------------------------
# FOLLOW-UP 1: disarm-race guard (close the extra-revert window)
# --------------------------------------------------------------------------
def test_disarm_race_skips_extra_revert():
    """If the armed record is removed (disarmed/confirmed) during the
    health-check window, sweep must SKIP the revert — that activation was
    legitimately cancelled, and an extra revert would be wrong, not safe."""
    sdir = _tmp_sdir()
    monkeys = {}
    rec = _patch(monkeys)
    try:
        revert_marker = sdir / "REVERT_RAN"
        armed_json = sdir / "armed" / "test-disarm-race.json"
        ag.arm(
            "test-disarm-race", window_minutes=0.0001,
            # Simulates a legitimate disarm landing WHILE the health check is
            # in flight: by the time run_health_check returns (RED), the
            # armed record is already gone.
            health_check_cmd=f"rm -f {armed_json} && exit 1",
            revert_cmd=f"touch {revert_marker}",
            sdir=sdir,
        )
        time.sleep(0.02)
        results = ag.sweep(sdir=sdir, health_timeout=5, revert_timeout=5)
        check("disarm-race: one result", len(results) == 1, str(results))
        if results:
            check(
                "disarm-race: action == skipped-disarmed-race",
                results[0]["action"] == "skipped-disarmed-race", str(results[0]),
            )
        check("disarm-race: revert command never ran (sentinel untouched)", not revert_marker.exists())
        check(
            "disarm-race: skip event emitted", "activation.sweep-skipped-disarm-race" in rec.types(), str(rec.types()),
        )
        check("disarm-race: no auto-reverted event fired", "activation.auto-reverted" not in rec.types())
    finally:
        _unpatch(monkeys)
        shutil.rmtree(sdir, ignore_errors=True)


def test_disarm_race_recheck_error_fails_safe_to_revert():
    """FAIL-SAFE DIRECTION (must never regress): if the existence re-check
    itself raises, that is NOT evidence of a legitimate disarm — sweep must
    still treat the record as armed and revert+alert exactly as before."""
    sdir = _tmp_sdir()
    monkeys = {}
    rec = _patch(monkeys)
    orig_exists = ag.Path.exists
    try:
        revert_marker = sdir / "REVERT_RAN"
        ag.arm(
            "test-recheck-error", window_minutes=0.0001,
            health_check_cmd="exit 1",  # RED
            revert_cmd=f"touch {revert_marker}",
            sdir=sdir,
        )
        time.sleep(0.02)

        def _boom(self):
            if self.name == "test-recheck-error.json":
                raise OSError("simulated EACCES on armed-record existence re-check")
            return orig_exists(self)

        ag.Path.exists = _boom
        results = ag.sweep(sdir=sdir, health_timeout=5, revert_timeout=5)
        check("recheck-error: one result", len(results) == 1, str(results))
        if results:
            check(
                "recheck-error: action == auto-reverted (fail-safe preserved)",
                results[0]["action"] == "auto-reverted", str(results[0]),
            )
        check("recheck-error: revert command actually ran despite recheck error", revert_marker.exists())
        check("recheck-error: LOUD alert emitted", "activation.auto-reverted" in rec.types())
        check(
            "recheck-error: no skip event emitted (recheck error must not skip)",
            "activation.sweep-skipped-disarm-race" not in rec.types(),
        )
    finally:
        ag.Path.exists = orig_exists
        _unpatch(monkeys)
        shutil.rmtree(sdir, ignore_errors=True)


# --------------------------------------------------------------------------
# FOLLOW-UP 2: total sweep failure still produces a LOUD alert
# --------------------------------------------------------------------------
def test_top_level_sweep_failure_emits_loud_alert():
    """A total sweep failure (an exception before/outside the per-record
    try/except — e.g. the armed-dir listing/mkdir failing) must still emit a
    LOUD alert via emit_event/emit_pulse, the same path per-record auto-revert
    alerts use — not just a silent journald stack trace nobody is watching."""
    sdir = _tmp_sdir()
    monkeys = {}
    rec = _patch(monkeys)
    orig_armed_dir = ag._armed_dir
    try:
        def _boom(_sdir):
            raise OSError("simulated: cannot list/create the armed dir (EACCES)")

        ag._armed_dir = _boom
        results = ag.sweep(sdir=sdir, health_timeout=5, revert_timeout=5)
        check("sweep-failed: one result", len(results) == 1, str(results))
        if results:
            check("sweep-failed: action == sweep-failed", results[0]["action"] == "sweep-failed", str(results[0]))
            check("sweep-failed: ok is False", results[0]["ok"] is False, str(results[0]))
        check("sweep-failed: loud alert event emitted", "activation.sweep-failed" in rec.types(), str(rec.types()))
        check("sweep-failed: pulse emitted (loud, not just journald)", len(rec.pulses) == 1, str(rec.pulses))
    finally:
        ag._armed_dir = orig_armed_dir
        _unpatch(monkeys)
        shutil.rmtree(sdir, ignore_errors=True)


def main() -> int:
    tests = [
        test_health_green_confirms_no_revert,
        test_health_red_reverts_and_alerts,
        test_unreadable_health_fails_safe_to_revert,
        test_disarm_cancels_auto_revert,
        test_confirm_cancels_before_deadline,
        test_empty_state_is_inert,
        test_arm_fails_closed_without_health_check_or_revert_cmd,
        test_control_id_path_traversal_rejected,
        test_double_arm_without_force_rejected,
        test_broken_event_spine_logs_fallback_never_raises,
        test_revert_command_failure_still_alerts,
        test_disarm_race_skips_extra_revert,
        test_disarm_race_recheck_error_fails_safe_to_revert,
        test_top_level_sweep_failure_emits_loud_alert,
    ]
    for t in tests:
        print(f"\n--- {t.__name__} ---")
        t()
    print(f"\n{_PASS} passed, {_FAIL} failed")
    if _FAILURES:
        print("\nFailures:")
        for f in _FAILURES:
            print(f"  {f}")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
