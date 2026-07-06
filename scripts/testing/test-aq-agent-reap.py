#!/usr/bin/env python3
"""Unit tests for aq-agent-reap reap-decision logic (pure, no processes killed)."""
import importlib.util
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_loader = SourceFileLoader("aq_agent_reap", str(ROOT / "scripts" / "ai" / "aq-agent-reap"))
_spec = importlib.util.spec_from_loader("aq_agent_reap", _loader)
mod = importlib.util.module_from_spec(_spec)
_loader.exec_module(mod)


def _fail(m):
    print(f"FAIL: {m}"); sys.exit(1)


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


if __name__ == "__main__":
    test_orphan_reaped()
    test_runaway_reaped()
    test_healthy_kept()
    test_boundary()
    print("\n4/4 reap-decision tests passed")
