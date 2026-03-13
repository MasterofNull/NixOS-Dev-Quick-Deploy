#!/usr/bin/env python3
"""Targeted checks for aq-report llama benchmark appendix helpers."""

import importlib.machinery
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "ai" / "aq-report"
SPEC = importlib.util.spec_from_file_location("aq_report", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    loader = importlib.machinery.SourceFileLoader("aq_report", str(MODULE_PATH))
    SPEC = importlib.util.spec_from_loader("aq_report", loader)
if SPEC is None or SPEC.loader is None:
    raise SystemExit("ERROR: unable to load aq-report module")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def write_run(path: Path, *, run_id: str, warm_latency: float, tps: float, quality: bool, saved_at: str) -> None:
    payload = {
        "run_id": run_id,
        "target_model": "Qwen3-4B-Instruct-2507-Q4_K_M.gguf",
        "target_ctx_size": 8192,
        "saved_at": saved_at,
        "summary": {
            "avg_warm_latency_s": warm_latency,
            "avg_completion_tokens_per_second": tps,
            "all_quality_checks_passed": quality,
        },
        "resource_observations": {
            "peak_rss_mb": 500.0,
            "avg_gpu_busy_percent": 95.0,
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        write_run(tmp_path / "20260313T120000Z-run-a.json", run_id="run-a", warm_latency=2.0, tps=12.0, quality=True, saved_at="2026-03-13T12:00:00Z")
        write_run(tmp_path / "20260313T120100Z-run-b.json", run_id="run-b", warm_latency=3.0, tps=18.0, quality=True, saved_at="2026-03-13T12:01:00Z")
        write_run(tmp_path / "20260313T120200Z-run-c.json", run_id="run-c", warm_latency=1.0, tps=30.0, quality=False, saved_at="2026-03-13T12:02:00Z")

        original_dir = MODULE.LLAMA_BENCHMARK_RUNS_DIR
        MODULE.LLAMA_BENCHMARK_RUNS_DIR = tmp_path
        try:
            data = MODULE.read_llama_benchmark_runs(MODULE.datetime.now(tz=MODULE.timezone.utc) - MODULE.timedelta(days=365))
            summary = MODULE.summarize_llama_benchmark_runs(data)
        finally:
            MODULE.LLAMA_BENCHMARK_RUNS_DIR = original_dir

    assert_true(summary["available"] is True, "expected available summary")
    assert_true(summary["total_runs"] == 3, "expected all runs loaded")
    assert_true(summary["quality_passed_runs"] == 2, "expected quality-pass count")
    assert_true(summary["best_latency_run"]["run_id"] == "run-a", "expected best latency to prefer quality-passing run")
    assert_true(summary["best_tps_run"]["run_id"] == "run-b", "expected best throughput to prefer quality-passing run")
    assert_true(summary["latest_run"]["run_id"] == "run-c", "expected latest run ordering by filename timestamp")
    print("PASS: aq-report summarizes saved llama benchmark runs without touching JSON schema")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
