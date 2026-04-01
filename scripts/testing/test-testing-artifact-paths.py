#!/usr/bin/env python3
"""Static regression checks for writable testing artifact paths."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CHAOS = ROOT / "ai-stack" / "testing" / "chaos_engineering.py"
BENCH = ROOT / "ai-stack" / "testing" / "performance_benchmarks.py"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    chaos_text = CHAOS.read_text(encoding="utf-8")
    bench_text = BENCH.read_text(encoding="utf-8")

    assert_true(
        'def _chaos_artifact_path() -> Path:' in chaos_text,
        "chaos engineering should resolve artifact paths through a helper",
    )
    assert_true(
        'return Path("/var/lib/ai-stack/hybrid/testing/chaos/experiment_results.json")' in chaos_text,
        "chaos engineering should default to a writable runtime artifact path",
    )
    assert_true(
        "report_path = _chaos_artifact_path()" in chaos_text,
        "chaos engineering should use the writable artifact helper",
    )
    assert_true(
        'def _benchmark_artifact_dir() -> Path:' in bench_text,
        "performance benchmarks should resolve artifact paths through a helper",
    )
    assert_true(
        'return Path("/var/lib/ai-stack/hybrid/testing/benchmarks")' in bench_text,
        "performance benchmarks should default to a writable runtime artifact directory",
    )
    assert_true(
        'results_path = artifact_dir / "performance_results.json"' in bench_text,
        "performance benchmarks should write results under the writable artifact directory",
    )
    assert_true(
        'baseline_path = artifact_dir / "baseline.json"' in bench_text,
        "performance benchmarks should read baseline data from the writable artifact directory",
    )

    print("PASS: testing artifact paths now target writable runtime state")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
