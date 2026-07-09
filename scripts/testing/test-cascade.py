#!/usr/bin/env python3
"""Tests for the draft-and-polish cascade (god-tier prompt 7).

Run: python3 scripts/testing/test-cascade.py
"""

import importlib
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "scripts" / "ai" / "lib"))
sys.path.insert(0, str(REPO))


def _fresh(tmp):
    os.environ["A2A_EVENT_LOG"] = str(Path(tmp) / "ev.jsonl")
    os.environ["CASCADE_LEDGER"] = str(Path(tmp) / "ledger.jsonl")
    import cascade
    importlib.reload(cascade)
    return cascade


def test_confidence_scoring():
    C = _fresh(tempfile.mkdtemp())
    good = C.score_confidence("The loader validates each profile against its schema, resolves "
                              "shared bodies, then applies token-budget checks before returning "
                              "the catalog to the caller for per-request lookup.")
    hedge = C.score_confidence("I'm not sure, it might be somewhere but I don't really know.")
    refuse = C.score_confidence("I cannot answer this; I don't have the information.")
    assert good["confidence"] >= 0.85, good
    assert hedge["confidence"] < 0.70, hedge   # below default threshold -> would escalate
    assert refuse["confidence"] < 0.60, refuse
    assert C.score_confidence("")["confidence"] == 0.0
    print(f"PASS confidence scoring (good={good['confidence']} hedge={hedge['confidence']} refuse={refuse['confidence']})")


def test_high_confidence_keeps_local():
    C = _fresh(tempfile.mkdtemp())
    calls = {"remote": 0}

    def local_fn(task):
        return ("A thorough, confident answer that fully addresses the question with "
                "concrete detail and no hedging whatsoever across several clauses.", 40)

    def remote_fn(task, draft):
        calls["remote"] += 1
        return ("polished", 100)

    res = C.run_cascade("q", task_class="short_critique", local_fn=local_fn, remote_fn=remote_fn)
    assert res.source == "local" and not res.escalated, res
    assert calls["remote"] == 0, "must NOT call remote when confident"
    assert res.remote_tokens == 0 and res.savings_vs_fanout() > 0
    print(f"PASS high-confidence draft kept local (saved {res.savings_vs_fanout()} remote tokens)")


def test_low_confidence_escalates():
    C = _fresh(tempfile.mkdtemp())
    calls = {"remote": 0}

    def local_fn(task):
        return ("I'm not sure, unclear, might be, I don't know.", 12)

    def remote_fn(task, draft):
        calls["remote"] += 1
        assert draft, "remote must receive the local draft to polish"
        return ("Authoritative polished answer.", 80)

    res = C.run_cascade("q", task_class="architecture", local_fn=local_fn, remote_fn=remote_fn)
    assert res.source == "remote" and res.escalated, res
    assert calls["remote"] == 1
    assert res.remote_tokens == 80
    print("PASS low-confidence draft escalates to remote (polish, not redo)")


def test_no_remote_fn_keeps_local():
    C = _fresh(tempfile.mkdtemp())
    res = C.run_cascade("q", task_class="architecture",
                        local_fn=lambda t: ("unclear i don't know", 5), remote_fn=None)
    assert res.source == "local" and not res.escalated
    print("PASS no remote_fn available -> keep local even if low confidence (graceful)")


def test_ledger_summary_per_class():
    C = _fresh(tempfile.mkdtemp())
    # 3 confident short_critiques (kept) + 1 low-confidence architecture (escalated).
    for _ in range(3):
        C.run_cascade("q", task_class="short_critique",
                      local_fn=lambda t: ("Clear confident sufficient answer with real content here.", 20),
                      remote_fn=lambda t, d: ("x", 50))
    C.run_cascade("q", task_class="architecture",
                  local_fn=lambda t: ("i don't know unclear", 4),
                  remote_fn=lambda t, d: ("x", 90))
    summary = C.ledger_summary()
    assert summary["short_critique"]["n"] == 3
    assert summary["short_critique"]["escalation_rate"] == 0.0
    assert summary["short_critique"]["recommend"] == "cascade"
    assert summary["architecture"]["escalated"] == 1
    assert summary["short_critique"]["saved_remote_tokens"] > 0
    print(f"PASS ledger per-class summary (short_critique saved "
          f"{summary['short_critique']['saved_remote_tokens']} remote tokens, esc-rate 0)")


def test_kill_switch():
    C = _fresh(tempfile.mkdtemp())
    os.environ["CASCADE_ENABLED"] = "0"
    assert not C.enabled()
    os.environ.pop("CASCADE_ENABLED")
    assert C.enabled()
    print("PASS kill switch")


if __name__ == "__main__":
    test_confidence_scoring()
    test_high_confidence_keeps_local()
    test_low_confidence_escalates()
    test_no_remote_fn_keeps_local()
    test_ledger_summary_per_class()
    test_kill_switch()
    print("ALL PASS")
