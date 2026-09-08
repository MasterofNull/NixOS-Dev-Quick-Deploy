#!/usr/bin/env python3
"""Tests for the slice/path claim registry (C-1 anti-collision primitive)."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "scripts" / "ai" / "lib" / "slice_claim.py"


def load():
    spec = importlib.util.spec_from_file_location("slice_claim", LIB)
    m = importlib.util.module_from_spec(spec)
    # Register before exec so the module's @dataclass can resolve its __module__.
    sys.modules["slice_claim"] = m
    spec.loader.exec_module(m)
    return m


def test_take_and_conflict_on_overlap() -> None:
    sc = load()
    with tempfile.TemporaryDirectory() as d:
        store = f"{d}/claims.json"
        assert sc.take_claim(store, "s1", "claude", ["scripts/ai/foo.py"])["ok"]
        # another lane, same file -> conflict, not recorded
        res = sc.take_claim(store, "s2", "codex", ["scripts/ai/foo.py"])
        assert res["ok"] is False and res["conflicts"], res
        assert res["conflicts"][0]["lane"] == "claude"
        # the conflicting claim must NOT have been written
        assert all(c.slice_id != "s2" for c in sc.load_claims(store))


def test_no_false_conflict_on_disjoint_paths() -> None:
    sc = load()
    with tempfile.TemporaryDirectory() as d:
        store = f"{d}/claims.json"
        assert sc.take_claim(store, "s1", "claude", ["scripts/ai/foo.py"])["ok"]
        assert sc.take_claim(store, "s2", "codex", ["scripts/other/bar.py"])["ok"]


def test_directory_ancestor_overlap() -> None:
    sc = load()
    with tempfile.TemporaryDirectory() as d:
        store = f"{d}/claims.json"
        assert sc.take_claim(store, "dir", "claude", ["scripts/ai"])["ok"]
        # a file under the claimed dir conflicts for another lane
        res = sc.take_claim(store, "file", "codex", ["scripts/ai/foo.py"])
        assert res["ok"] is False and res["conflicts"], res


def test_same_lane_reclaim_is_idempotent() -> None:
    sc = load()
    with tempfile.TemporaryDirectory() as d:
        store = f"{d}/claims.json"
        assert sc.take_claim(store, "s1", "claude", ["a/b.py"])["ok"]
        assert sc.take_claim(store, "s1", "claude", ["a/b.py", "a/c.py"])["ok"]  # refresh, no conflict
        claims = [c for c in sc.load_claims(store) if c.slice_id == "s1"]
        assert len(claims) == 1 and set(claims[0].paths) == {"a/b.py", "a/c.py"}


def test_expiry_auto_releases() -> None:
    sc = load()
    with tempfile.TemporaryDirectory() as d:
        store = f"{d}/claims.json"
        sc.take_claim(store, "s1", "claude", ["a/b.py"], ttl_seconds=100, now=1000.0)
        # far in the future the claim is gone, so another lane is clear
        assert sc.load_claims(store, now=2000.0) == []
        assert sc.check_paths(store, ["a/b.py"], "codex", now=2000.0)["clear"]


def test_release() -> None:
    sc = load()
    with tempfile.TemporaryDirectory() as d:
        store = f"{d}/claims.json"
        sc.take_claim(store, "s1", "claude", ["a/b.py"])
        assert sc.release_claim(store, "s1", "claude")["released"] == 1
        assert sc.check_paths(store, ["a/b.py"], "codex")["clear"]


def test_corrupt_store_is_failsafe() -> None:
    sc = load()
    with tempfile.TemporaryDirectory() as d:
        store = f"{d}/claims.json"
        open(store, "w").write("{ not valid json ")
        assert sc.load_claims(store) == []  # never crashes; treated as no claims


def test_check_is_readonly() -> None:
    sc = load()
    with tempfile.TemporaryDirectory() as d:
        store = f"{d}/claims.json"
        # check on a nonexistent store is clear and creates nothing
        assert sc.check_paths(store, ["a/b.py"], "claude")["clear"]
        assert not Path(store).exists()


def main() -> int:
    test_take_and_conflict_on_overlap()
    test_no_false_conflict_on_disjoint_paths()
    test_directory_ancestor_overlap()
    test_same_lane_reclaim_is_idempotent()
    test_expiry_auto_releases()
    test_release()
    test_corrupt_store_is_failsafe()
    test_check_is_readonly()
    print("test-slice-claim: ok 8/8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
