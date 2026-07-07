#!/usr/bin/env python3
"""Unit tests for aq-agent-reap reap-decision logic (pure, no processes killed)."""
import importlib.util
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_loader = SourceFileLoader("aq_agent_reap", str(ROOT / "scripts" / "ai" / "aq-agent-reap"))
_spec = importlib.util.spec_from_loader("aq_agent_reap", _loader)
mod = importlib.util.module_from_spec(_spec)
_loader.exec_module(mod)

NOW = datetime.now(timezone.utc).timestamp()


def _fail(m):
    print(f"FAIL: {m}"); sys.exit(1)


def _ts(seconds_ago):
    return datetime.fromtimestamp(NOW - seconds_ago, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_orphan_reaped():
    reap, reason = mod.should_reap(ppid=1, etimes=30, max_age=3600)
    if not reap or "orphaned" not in reason:
        _fail(f"orphan (ppid=1) must be reaped; got {reap}, {reason}")
    print("PASS  orphan (ppid=1) reaped regardless of age")


def test_runaway_reaped():
    reap, reason = mod.should_reap(ppid=12345, etimes=4000, max_age=3600)
    if not reap or "runaway" not in reason:
        _fail(f"runaway (age>max) must be reaped; got {reap}, {reason}")
    print("PASS  runaway (age>max_age) reaped")


def test_healthy_kept():
    reap, _ = mod.should_reap(ppid=12345, etimes=120, max_age=3600)
    if reap:
        _fail("a young, parented process must NOT be reaped")
    print("PASS  healthy (parented, young) process kept")


def test_boundary():
    # exactly at max_age is not > max_age -> kept
    reap, _ = mod.should_reap(ppid=999, etimes=3600, max_age=3600)
    if reap:
        _fail("age == max_age should be kept (strict >)")
    print("PASS  age == max_age kept (strict inequality)")


# ── registry reconciliation (--reconcile-registry) ───────────────────────────
def test_live_pid_never_orphaned():
    rec = {"status": "running", "pid": os.getpid(), "created": _ts(99999)}
    if mod.should_orphan_row(rec, NOW, 1800)[0]:
        _fail("a row with a LIVE pid must never be orphaned")
    print("PASS  live pid never orphaned (even if old)")


def test_dead_pid_aged_orphaned():
    ok, reason = mod.should_orphan_row({"status": "running", "pid": 999999999, "created": _ts(3600)}, NOW, 1800)
    if not ok or "dead" not in reason:
        _fail(f"dead pid + aged should orphan: {ok} {reason}")
    print("PASS  dead pid + aged -> orphan")


def test_dead_pid_recent_protected():
    if mod.should_orphan_row({"status": "running", "pid": None, "created": _ts(60)}, NOW, 1800)[0]:
        _fail("recent absent-pid row must NOT be orphaned (dispatch race)")
    print("PASS  recent absent-pid row protected by age bound")


def test_non_running_and_no_ts_untouched():
    for st in ("done", "failed", "orphaned"):
        if mod.should_orphan_row({"status": st, "pid": None, "created": _ts(9999)}, NOW, 1800)[0]:
            _fail(f"status={st} must not be reconciled")
    if mod.should_orphan_row({"status": "running", "pid": None}, NOW, 1800)[0]:
        _fail("row without timestamp should be skipped")
    print("PASS  non-running + missing-timestamp rows untouched")


def _write_registry(rows):
    p = Path(tempfile.mkdtemp()) / "registry.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return p


def test_reconcile_atomic_only_stale():
    rows = [
        {"id": "a", "agent": "antigravity", "status": "running", "pid": None, "created": _ts(7200)},
        {"id": "b", "agent": "local", "status": "running", "pid": os.getpid(), "created": _ts(7200)},
        {"id": "c", "agent": "codex", "status": "done", "pid": 123, "created": _ts(7200)},
        {"id": "d", "agent": "local", "status": "running", "pid": None, "created": _ts(30)},
    ]
    p = _write_registry(rows)
    # force=True: temp registry, bypass the active-dispatch quiescence guard in tests
    changed = mod.reconcile_registry(p, age_s=1800, dry_run=False, force=True)
    if changed != 1:
        _fail(f"exactly 1 row should be orphaned, got {changed}")
    res = {json.loads(l)["id"]: json.loads(l) for l in p.read_text().splitlines() if l.strip()}
    if res["a"]["status"] != "orphaned" or "orphaned_at" not in res["a"]:
        _fail("stale row 'a' should be orphaned with timestamp")
    if res["b"]["status"] != "running" or res["c"]["status"] != "done" or res["d"]["status"] != "running":
        _fail("live/done/recent rows must be preserved")
    if len(res) != 4:
        _fail("row count must be preserved (no deletions)")
    print("PASS  reconcile rewrites only the stale row, preserves rest atomically")


def test_dry_run_no_write():
    p = _write_registry([{"id": "a", "agent": "x", "status": "running", "pid": None, "created": _ts(7200)}])
    before = p.read_text()
    mod.reconcile_registry(p, age_s=1800, dry_run=True)
    if p.read_text() != before:
        _fail("dry-run must not modify the registry")
    print("PASS  dry-run leaves the registry untouched")


if __name__ == "__main__":
    test_orphan_reaped()
    test_runaway_reaped()
    test_healthy_kept()
    test_boundary()
    test_live_pid_never_orphaned()
    test_dead_pid_aged_orphaned()
    test_dead_pid_recent_protected()
    test_non_running_and_no_ts_untouched()
    test_reconcile_atomic_only_stale()
    test_dry_run_no_write()
    print("\n10/10 reap tests passed (4 process + 6 registry)")
