#!/usr/bin/env python3
"""Hermetic tests for the advisory, transaction-safe slice claim registry."""
from __future__ import annotations

import importlib.util
import json
import multiprocessing
import sys
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "scripts" / "ai" / "lib" / "slice_claim.py"


def load():
    spec = importlib.util.spec_from_file_location("slice_claim", LIB)
    module = importlib.util.module_from_spec(spec)
    sys.modules["slice_claim"] = module
    spec.loader.exec_module(module)
    return module


def _take_race(store: str, lane: str, barrier, results) -> None:
    barrier.wait()
    results.put(load().take_claim(store, f"slice-{lane}", lane, ["scripts/ai/shared.py"]))


def _release_race(store: str, token: str, barrier, results) -> None:
    barrier.wait()
    results.put(load().release_claim(store, "old", "lane-old", owner_token=token))


def _unrelated_take_race(store: str, barrier, results) -> None:
    barrier.wait()
    results.put(load().take_claim(store, "new", "lane-new", ["scripts/other/new.py"]))


def test_overlap_and_token_capability() -> None:
    sc = load()
    with tempfile.TemporaryDirectory() as directory:
        store = f"{directory}/claims.json"
        first = sc.take_claim(store, "s1", "claude", ["scripts/ai/foo.py"])
        assert first["ok"] and len(first["owner_token"]) >= 32
        assert "owner_token" not in first["claim"]
        wrong_lane = sc.take_claim(store, "s1", "claude", ["scripts/ai/foo.py"], owner_token="wrong")
        assert not wrong_lane["ok"] and "owner_token" not in json.dumps(wrong_lane)
        refresh = sc.take_claim(store, "s1", "claude", ["scripts/ai/foo.py", "scripts/ai/bar.py"],
                                owner_token=first["owner_token"])
        assert refresh["ok"] and "owner_token" not in refresh
        assert not sc.release_claim(store, "s1", "claude", owner_token="wrong")["ok"]
        assert sc.release_claim(store, "s1", "claude", owner_token=first["owner_token"])["released"] == 1


def test_path_policy_and_ttl_boundary() -> None:
    sc = load()
    with tempfile.TemporaryDirectory() as directory:
        store = f"{directory}/claims.json"
        for path in ("", "/", "/etc/passwd", ".", "..", "a/../b", "./a", "a//b", "a/./b", "a\\b"):
            result = sc.take_claim(store, "bad", "lane", [path])
            assert not result["ok"], (path, result)
        good = sc.take_claim(store, "ttl", "lane", ["a/b.py"], ttl_seconds=10, now=100.0)
        assert good["ok"]
        assert sc.load_claims(store, now=109.999)
        assert sc.load_claims(store, now=110.0) == []


def test_malformed_rows_are_ignored_without_crashing() -> None:
    sc = load()
    with tempfile.TemporaryDirectory() as directory:
        store = Path(directory) / "claims.json"
        store.write_text(json.dumps({"claims": [
            {"slice_id": "bad", "lane": "lane", "paths": ["../escape"], "created_at": 0, "expires_at": 9999999999},
            {"slice_id": "missing-token", "lane": "lane", "paths": ["a/b"], "created_at": 0, "expires_at": 9999999999},
        ]}))
        assert sc.load_claims(store, now=1.0) == []


def test_multiprocess_overlap_has_one_winner() -> None:
    with tempfile.TemporaryDirectory() as directory:
        store = f"{directory}/claims.json"
        context = multiprocessing.get_context("fork")
        barrier, results = context.Barrier(2), context.Queue()
        processes = [context.Process(target=_take_race, args=(store, lane, barrier, results)) for lane in ("a", "b")]
        for process in processes:
            process.start()
        for process in processes:
            process.join(10)
            assert process.exitcode == 0
        outcomes = [results.get(timeout=2) for _ in processes]
        assert sum(bool(outcome.get("ok")) for outcome in outcomes) == 1, outcomes


def test_release_preserves_concurrent_unrelated_claim() -> None:
    sc = load()
    with tempfile.TemporaryDirectory() as directory:
        store = f"{directory}/claims.json"
        old = sc.take_claim(store, "old", "lane-old", ["scripts/old.py"])
        context = multiprocessing.get_context("fork")
        barrier, results = context.Barrier(2), context.Queue()
        release = context.Process(target=_release_race, args=(store, old["owner_token"], barrier, results))
        take = context.Process(target=_unrelated_take_race, args=(store, barrier, results))
        release.start(); take.start()
        release.join(10); take.join(10)
        assert release.exitcode == 0 and take.exitcode == 0
        outcomes = [results.get(timeout=2) for _ in range(2)]
        assert all(outcome.get("ok") for outcome in outcomes), outcomes
        claims = sc.load_claims(store)
        assert [claim.slice_id for claim in claims] == ["new"]


def main() -> int:
    test_overlap_and_token_capability()
    test_path_policy_and_ttl_boundary()
    test_malformed_rows_are_ignored_without_crashing()
    test_multiprocess_overlap_has_one_winner()
    test_release_preserves_concurrent_unrelated_claim()
    print("test-slice-claim: ok 5/5")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
