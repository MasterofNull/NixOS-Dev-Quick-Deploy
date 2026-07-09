#!/usr/bin/env python3
"""Tests for R5.1 — AQ_TRACE_ID auto-seeding at entrypoints (RSI-Readiness).

Run: python3 scripts/testing/test-trace-seed.py
"""

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
SEED = REPO / "scripts" / "ai" / "lib" / "trace-seed.sh"


def _sourced(env_extra: dict) -> str:
    """Source trace-seed.sh in a clean bash and echo the resulting AQ_TRACE_ID."""
    env = {k: v for k, v in os.environ.items() if k not in ("AQ_TRACE_ID", "AQ_TRACE_DISABLE")}
    env.update(env_extra)
    out = subprocess.run(
        ["bash", "-c", f'source "{SEED}"; echo "${{AQ_TRACE_ID:-UNSET}}"'],
        capture_output=True, text=True, env=env,
    ).stdout.strip()
    return out


def test_seeds_when_unset():
    tid = _sourced({})
    assert tid != "UNSET" and len(tid) >= 16, tid
    print(f"PASS seeds a trace id when unset ({tid[:12]}...)")


def test_preserves_parent():
    tid = _sourced({"AQ_TRACE_ID": "parent-trace-123"})
    assert tid == "parent-trace-123", tid
    print("PASS preserves an inherited parent trace id (one trace per chain)")


def test_kill_switch():
    tid = _sourced({"AQ_TRACE_DISABLE": "1"})
    assert tid == "UNSET", tid
    print("PASS AQ_TRACE_DISABLE=1 disables seeding (tracing opt-out)")


def test_entrypoints_source_the_seed():
    # The router, the local delegate, and the loop must all seed.
    aq = (REPO / "scripts" / "ai" / "aq").read_text()
    dtl = (REPO / "scripts" / "ai" / "delegate-to-local").read_text()
    loop = (REPO / "scripts" / "ai" / "aq-loop").read_text()
    assert "trace-seed.sh" in aq, "aq router must seed"
    assert "trace-seed.sh" in dtl, "delegate-to-local must seed"
    assert "AQ_TRACE_ID" in loop and "_seed_trace_id" in loop, "aq-loop must seed"
    print("PASS aq router + delegate-to-local + aq-loop all seed the trace id")


def test_dispatch_opens_root_span():
    disp = (REPO / "scripts" / "ai" / "lib" / "dispatch.py").read_text()
    assert 'span(f"delegate.{resolved_mode}"' in disp, "dispatch must open a root delegate span"
    print("PASS dispatch.py opens a root delegate span (model.generate nests under it)")


if __name__ == "__main__":
    test_seeds_when_unset()
    test_preserves_parent()
    test_kill_switch()
    test_entrypoints_source_the_seed()
    test_dispatch_opens_root_span()
    print("ALL PASS")
