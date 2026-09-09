#!/usr/bin/env python3
"""Tests for the frontier-evidence backlog (FA-1)."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "scripts" / "ai" / "lib" / "frontier_backlog.py"


def load():
    spec = importlib.util.spec_from_file_location("frontier_backlog", LIB)
    m = importlib.util.module_from_spec(spec)
    sys.modules["frontier_backlog"] = m
    spec.loader.exec_module(m)
    return m


def _rec(**over):
    base = {"technique": "T", "source": "arXiv:x", "claim": "C", "verdict": "adopt",
            "aqos_mapping": "aq-qa", "proposed_slice": "S", "acceptance_goal": "A"}
    base.update(over)
    return base


def test_add_and_dedup():
    fb = load()
    with tempfile.TemporaryDirectory() as d:
        store = f"{d}/b.jsonl"
        assert fb.add(store, _rec())["added"] is True
        # identical technique+claim -> duplicate, not appended
        r = fb.add(store, _rec())
        assert r["added"] is False and r["duplicate"] is True
        assert len(fb.load(store)) == 1
        # different claim -> new
        assert fb.add(store, _rec(claim="C2"))["added"] is True
        assert len(fb.load(store)) == 2


def test_validation_rejects_bad_records():
    fb = load()
    with tempfile.TemporaryDirectory() as d:
        store = f"{d}/b.jsonl"
        assert fb.add(store, _rec(verdict="banana"))["added"] is False
        assert fb.add(store, _rec(technique=""))["added"] is False
        assert fb.load(store) == []


def test_status_transitions():
    fb = load()
    with tempfile.TemporaryDirectory() as d:
        store = f"{d}/b.jsonl"
        rid = fb.add(store, _rec())["id"]
        assert fb.set_status(store, rid, "accepted")["ok"] is True
        assert fb.list_items(store, status="accepted")[0]["id"] == rid
        assert fb.set_status(store, rid, "banana")["ok"] is False
        assert fb.set_status(store, "nope", "accepted")["ok"] is False


def test_default_status_is_new_and_digest():
    fb = load()
    with tempfile.TemporaryDirectory() as d:
        store = f"{d}/b.jsonl"
        fb.add(store, _rec())
        fb.add(store, _rec(claim="C2", status="accepted"))
        dg = fb.digest(store)
        assert dg["total"] == 2
        assert dg["by_status"].get("new") == 1
        assert dg["new_count"] == 1 and dg["new_lines"]


def test_multi_expert_debate_gate():
    fb = load()
    with tempfile.TemporaryDirectory() as d:
        store = f"{d}/b.jsonl"
        rid = fb.add(store, _rec())["id"]
        fb.set_status(store, rid, "in_review")
        rec = lambda: next(r for r in fb.load(store) if r["id"] == rid)
        # one support is not enough (need >= 2 distinct lanes)
        fb.add_verdict(store, rid, "claude", "support")
        assert fb.consensus(rec())["accept_eligible"] is False
        # a second independent support -> eligible
        fb.add_verdict(store, rid, "codex", "support")
        assert fb.consensus(rec())["accept_eligible"] is True
        # an adversarial reject blocks acceptance even with supports
        fb.add_verdict(store, rid, "local", "reject", "hardware won't benefit")
        con = fb.consensus(rec())
        assert con["accept_eligible"] is False and "local" in con["rejects"]
        # re-recording a lane's verdict replaces (no double-count)
        fb.add_verdict(store, rid, "local", "support")
        assert fb.consensus(rec())["accept_eligible"] is True
        # bad stance rejected
        assert fb.add_verdict(store, rid, "x", "banana")["ok"] is False


def test_corrupt_line_is_skipped():
    fb = load()
    with tempfile.TemporaryDirectory() as d:
        store = f"{d}/b.jsonl"
        fb.add(store, _rec())
        with open(store, "a") as f:
            f.write("{ not json\n\n")
        assert len(fb.load(store)) == 1  # bad + blank lines skipped


def main() -> int:
    test_add_and_dedup()
    test_validation_rejects_bad_records()
    test_status_transitions()
    test_default_status_is_new_and_digest()
    test_multi_expert_debate_gate()
    test_corrupt_line_is_skipped()
    print("test-frontier-backlog: ok 6/6")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
