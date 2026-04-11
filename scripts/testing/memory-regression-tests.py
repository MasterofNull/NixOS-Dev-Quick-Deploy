#!/usr/bin/env python3
"""Memory benchmark regression checks for the AI harness."""

import importlib.machinery
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AI_STACK_ROOT = ROOT / "ai-stack"
AQ_BENCHMARK_PATH = AI_STACK_ROOT / "aidb" / "benchmarks" / "aq-benchmark"
CORPUS_PATH = AI_STACK_ROOT / "aidb" / "benchmarks" / "memory-benchmark-corpus.json"

if str(AI_STACK_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_STACK_ROOT))


def load_module(module_name: str, module_path: Path):
    """Load a repo script even when it has no .py suffix."""
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        loader = importlib.machinery.SourceFileLoader(module_name, str(module_path))
        spec = importlib.util.spec_from_loader(module_name, loader)
    if spec is None or spec.loader is None:
        raise SystemExit(f"ERROR: unable to load {module_name} from {module_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


AQ_BENCHMARK = load_module("aq_benchmark", AQ_BENCHMARK_PATH)
AQ_MEMORY = load_module("aq_memory", ROOT / "scripts" / "ai" / "aq-memory")


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage_path = Path(tmp_dir) / "temporal_facts.json"
        fact_store = AQ_MEMORY.InMemoryFactStore(str(storage_path))

        recall = AQ_BENCHMARK.RecallBenchmark(str(CORPUS_PATH), fact_store=fact_store)
        recall_results = recall.run_all(limit=10)

        baseline_accuracy = recall_results["summary"]["baseline_accuracy"]
        metadata_accuracy = recall_results["summary"]["metadata_accuracy"]
        temporal_accuracy = recall_results["summary"]["temporal_accuracy"]

        assert_true(baseline_accuracy >= 0.60, f"baseline recall too low: {baseline_accuracy:.3f}")
        assert_true(metadata_accuracy >= baseline_accuracy, "metadata recall regressed below baseline")
        assert_true(temporal_accuracy >= 0.60, f"temporal recall too low: {temporal_accuracy:.3f}")

        perf = AQ_BENCHMARK.PerformanceBenchmark(fact_store=fact_store, corpus_file=str(CORPUS_PATH))
        latency = perf.run_latency_test(queries=100)
        throughput = perf.run_throughput_test(duration_sec=1)
        storage = perf.run_storage_efficiency_test()

    assert_true(latency["p95"] < 5, f"p95 latency regression: {latency['p95']:.2f} ms")
    assert_true(throughput["qps"] > 1000, f"throughput regression: {throughput['qps']:.2f} qps")
    assert_true("error" not in storage, f"storage benchmark failed: {storage.get('error')}")
    assert_true(storage["file_size_bytes"] > 0, "storage benchmark did not persist benchmark data")

    summary = {
        "recall": {
            "baseline_accuracy": baseline_accuracy,
            "metadata_accuracy": metadata_accuracy,
            "temporal_accuracy": temporal_accuracy,
        },
        "performance": {
            "p95_latency_ms": latency["p95"],
            "throughput_qps": throughput["qps"],
            "storage_overhead_ratio": storage["storage_overhead_ratio"],
        },
    }
    print(json.dumps(summary, indent=2))
    print("PASS: memory benchmark regression checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
