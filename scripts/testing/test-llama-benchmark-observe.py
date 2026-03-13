#!/usr/bin/env python3
"""Targeted checks for aq-llama-benchmark-observe sampling summaries."""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "ai" / "aq-llama-benchmark-observe.py"
SPEC = importlib.util.spec_from_file_location("aq_llama_benchmark_observe", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise SystemExit("ERROR: unable to load aq-llama-benchmark-observe module")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    summary = MODULE.summarize_samples(
        [
            {
                "timestamp": 1.0,
                "cpu_percent": 10.0,
                "rss_mb": 2048.0,
                "gpu_busy_percent": 20.0,
                "vram_used_mb": 1024.0,
                "vram_total_mb": 8192.0,
                "gpu_temp_c": 55.0,
                "gpu_power_watts": 18.0,
            },
            {
                "timestamp": 2.0,
                "cpu_percent": 40.0,
                "rss_mb": 3072.0,
                "gpu_busy_percent": 35.0,
                "vram_used_mb": 2048.0,
                "vram_total_mb": 8192.0,
                "gpu_temp_c": 61.0,
                "gpu_power_watts": 25.0,
            },
        ],
        pid=123,
    )
    assert_true(summary["status"] == "ok", "expected ok summary")
    assert_true(summary["avg_cpu_percent"] == 25.0, "expected average CPU")
    assert_true(summary["peak_rss_mb"] == 3072.0, "expected peak RSS")
    assert_true(summary["avg_gpu_power_watts"] == 21.5, "expected average GPU power")
    assert_true(summary["peak_vram_used_mb"] == 2048.0, "expected peak VRAM")
    print("PASS: aq-llama-benchmark-observe summarizes CPU/GPU/RSS samples")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
