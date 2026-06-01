#!/usr/bin/env python3
"""Regression coverage for Phase 93.4 multi-agent race harness."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ai" / "lib"))
sys.path.insert(0, str(ROOT / "scripts" / "ai"))
os.environ.setdefault("AI_STRICT_ENV", "false")


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _import_race_harness():
    import importlib.util
    from importlib.machinery import SourceFileLoader
    loader = SourceFileLoader("race_harness", str(ROOT / "scripts" / "ai" / "race-harness"))
    spec = importlib.util.spec_from_loader("race_harness", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def test_fixture_run_structure() -> None:
    rh = _import_race_harness()
    run = rh._make_fixture_run(
        experiment_id="exp-test",
        prompt="Build a login form",
        variant="markdown",
        agent_id="local",
        run_id="run-test-001",
    )
    assert_true(run["variant"] == "markdown", "fixture run has correct variant")
    assert_true(run["agent_id"] == "local", "fixture run has correct agent_id")
    assert_true(run["fixture"] is True, "fixture flag set")
    assert_true(isinstance(run["useful_ratio"], float), "useful_ratio is float")
    assert_true(0.0 <= run["useful_ratio"] <= 1.0, "useful_ratio in [0,1]")
    assert_true(isinstance(run["total_tokens"], int) and run["total_tokens"] > 0, "total_tokens > 0")
    assert_true(run["experiment_id"] == "exp-test", "experiment_id preserved")
    # events must be present (emitted separately from run record in main)
    assert_true(isinstance(run.get("events"), list) and len(run["events"]) >= 3, "fixture has events")


def test_fixture_all_variants_and_agents() -> None:
    rh = _import_race_harness()
    runs = []
    for variant in rh.SUPPORTED_VARIANTS:
        for agent_id in rh.SUPPORTED_AGENTS:
            run = rh._make_fixture_run(
                experiment_id="exp-all",
                prompt="test prompt",
                variant=variant,
                agent_id=agent_id,
                run_id=f"run-{variant}-{agent_id}",
            )
            runs.append(run)
    assert_true(
        len(runs) == len(rh.SUPPORTED_VARIANTS) * len(rh.SUPPORTED_AGENTS),
        "one run per variant×agent",
    )
    for r in runs:
        assert_true(r["variant"] in rh.SUPPORTED_VARIANTS, f"valid variant: {r['variant']}")
        assert_true(r["agent_id"] in rh.SUPPORTED_AGENTS, f"valid agent: {r['agent_id']}")


def test_race_winner_correctness_gate() -> None:
    rh = _import_race_harness()
    runs = [
        {"agent_id": "local", "variant": "markdown", "accepted": True, "useful_ratio": 0.71},
        {"agent_id": "gemini", "variant": "html", "accepted": True, "useful_ratio": 0.80},
        {"agent_id": "codex", "variant": "visual_html", "accepted": False, "useful_ratio": 0.90},
    ]
    winner = rh._race_winner(runs)
    assert_true(winner == "gemini/html", f"correctness gate excludes rejected run; got {winner}")

    # No accepted runs => no winner
    no_acc = [{"agent_id": "a", "variant": "markdown", "accepted": False, "useful_ratio": 0.99}]
    assert_true(rh._race_winner(no_acc) is None, "no winner when all runs rejected")

    # None useful_ratio is excluded even if accepted
    partial = [{"agent_id": "b", "variant": "markdown", "accepted": True, "useful_ratio": None}]
    assert_true(rh._race_winner(partial) is None, "no winner with null useful_ratio")


def test_race_harness_dry_run_output() -> None:
    import subprocess
    rh_path = str(ROOT / "scripts" / "ai" / "race-harness")
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = str(Path(tmpdir) / "runs.jsonl")
        result = subprocess.run(
            [
                sys.executable,
                rh_path,
                "--prompt", "test prompt for race",
                "--dry-run",
                "--output", out_path,
                "--format", "json",
            ],
            capture_output=True,
            text=True,
        )
        assert_true(result.returncode == 0, f"dry-run exited nonzero: {result.stderr}")
        doc = json.loads(result.stdout)
        assert_true(doc["dry_run"] is True, "dry_run flag in JSON output")
        assert_true(len(doc["runs"]) == len(doc["variants"]) * len(doc["agents"]), "run count = variants × agents")
        for r in doc["runs"]:
            assert_true(r["fixture"] is True, "all runs are fixture in dry-run")
        assert_true(Path(out_path).exists(), "output JSONL written")
        lines = [l for l in Path(out_path).read_text().splitlines() if l.strip()]
        assert_true(len(lines) == len(doc["runs"]), "JSONL line count matches run count")


def test_live_run_returns_no_data() -> None:
    rh = _import_race_harness()
    run = rh._make_live_run(
        experiment_id="exp-live",
        prompt="live prompt",
        variant="markdown",
        agent_id="local",
        run_id="run-live-001",
    )
    assert_true(run["status"] == "no_data", "live run returns no_data before implementation")
    assert_true(run["fixture"] is False, "live run is not a fixture")
    assert_true(run.get("no_data_reason") is not None, "live run has no_data_reason")


if __name__ == "__main__":
    tests = [
        ("fixture run structure", test_fixture_run_structure),
        ("all variants and agents", test_fixture_all_variants_and_agents),
        ("race winner correctness gate", test_race_winner_correctness_gate),
        ("dry-run subprocess output", test_race_harness_dry_run_output),
        ("live run returns no_data", test_live_run_returns_no_data),
    ]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
        except Exception as exc:
            print(f"  FAIL  {name}: {exc}")
            failed += 1
    if failed:
        print(f"\n{failed}/{len(tests)} tests FAILED")
        sys.exit(1)
    print(f"\n{len(tests)}/{len(tests)} tests passed")
