#!/usr/bin/env python3
"""Tests for FA-3 auto-fold (approved candidate -> plan tracker slice)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "scripts" / "ai" / "lib" / "frontier_fold.py"


def load():
    spec = importlib.util.spec_from_file_location("frontier_fold", LIB)
    m = importlib.util.module_from_spec(spec)
    sys.modules["frontier_fold"] = m
    spec.loader.exec_module(m)
    return m


def _cand(**over):
    base = {"id": "FE-8", "technique": "Landlock egress", "proposed_slice": "pin MCP to loopback",
            "acceptance_goal": "deny-closed proof", "verdict": "adopt", "status": "accepted",
            "source": "Landlock LSM"}
    base.update(over)
    return base


def _tracker():
    return {"plan": {"id": "t"}, "phases": [{"id": "p0", "name": "P0", "order": 1}], "items": []}


def test_fold_adds_slice():
    ff = load()
    tr, added, _ = ff.fold_candidate(_tracker(), _cand())
    assert added is True
    it = tr["items"][0]
    assert it["id"] == "frontier-fe-8" and it["goal"] == "pin MCP to loopback"
    assert it["validation_goal"] == "deny-closed proof" and it["phase"] == "p0"
    assert "[frontier-fold FE-8]" in it["editorial_note"]


def test_fold_is_idempotent():
    ff = load()
    tr, a1, _ = ff.fold_candidate(_tracker(), _cand())
    tr, a2, msg = ff.fold_candidate(tr, _cand())
    assert a1 is True and a2 is False and "already folded" in msg
    assert len([i for i in tr["items"] if i["id"] == "frontier-fe-8"]) == 1


def test_fold_refuses_non_foldable_status():
    ff = load()
    for status in ("new", "deferred", "dropped"):
        _, added, msg = ff.fold_candidate(_tracker(), _cand(status=status))
        assert added is False and "not foldable" in msg


def test_fold_requires_valid_phase():
    ff = load()
    no_phase = {"plan": {"id": "t"}, "phases": [], "items": []}
    _, added, msg = ff.fold_candidate(no_phase, _cand())
    assert added is False and "no phases" in msg
    _, added2, msg2 = ff.fold_candidate(_tracker(), _cand(), phase_id="nope")
    assert added2 is False and "not in target tracker" in msg2


def main() -> int:
    test_fold_adds_slice()
    test_fold_is_idempotent()
    test_fold_refuses_non_foldable_status()
    test_fold_requires_valid_phase()
    print("test-frontier-fold: ok 4/4")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
