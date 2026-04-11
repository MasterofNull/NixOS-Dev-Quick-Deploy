#!/usr/bin/env python3
"""
Performance Benchmark - Phase 1 Slice 1.5

Measures performance characteristics of the memory system including
query latency, throughput, storage efficiency, and concurrency.

Metrics:
- Query Latency: p50, p95, p99 percentiles
- Throughput: Queries per second (QPS)
- Storage: Database size, index size, storage efficiency
- Memory Usage: RAM consumption during operations
- Concurrency: Performance under parallel load

Usage:
    from aidb.benchmarks.performance_bench import PerformanceBenchmark

    benchmark = PerformanceBenchmark()

    # Run latency test
    latency = benchmark.run_latency_test(queries=1000)
    print(f"p95 latency: {latency['p95']:.2f}ms")

    # Run throughput test
    throughput = benchmark.run_throughput_test(duration_sec=10)
    print(f"Throughput: {throughput['qps']:.1f} qps")
"""

import time
import json
import statistics
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class LatencyMeasurement:
    """Single latency measurement"""
    query: str
    latency_ms: float
    timestamp: float
    cache_hit: bool = False


class PerformanceBenchmark:
    """
    Performance benchmarking suite for memory system.

    Measures:
    - Latency distribution (p50, p95, p99)
    - Throughput (queries/sec)
    - Storage efficiency
    - Memory usage
    - Concurrency performance
    """

    def __init__(self, fact_store=None, corpus_file: Optional[str] = None):
        """
        Initialize performance benchmark.

        Args:
            fact_store: Fact store implementation
            corpus_file: Optional corpus file for realistic queries
        """
        self.fact_store = fact_store or self._get_default_fact_store()
        self.corpus_file = Path(corpus_file) if corpus_file else None
        self.queries = self._load_queries() if corpus_file else self._generate_queries()

    def _get_default_fact_store(self):
        """Get default in-memory fact store"""
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts" / "ai"))

        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "aq_memory",
                Path(__file__).parent.parent.parent.parent / "scripts" / "ai" / "aq-memory"
            )
            aq_memory = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(aq_memory)
            return aq_memory.InMemoryFactStore()
        except Exception as e:
            logger.warning(f"Could not load default fact store: {e}")
            return None

    def _load_queries(self) -> List[str]:
        """Load queries from corpus file"""
        if not self.corpus_file or not self.corpus_file.exists():
            return self._generate_queries()

        with open(self.corpus_file, 'r') as f:
            corpus = json.load(f)

        queries = []
        for category in corpus.get("categories", []):
            for pair in category.get("pairs", []):
                queries.extend(pair.get("queries", []))

        logger.info(f"Loaded {len(queries)} queries from corpus")
        return queries

    def _generate_queries(self) -> List[str]:
        """Generate synthetic queries for testing"""
        queries = [
            "authentication method",
            "JWT token configuration",
            "database choice",
            "semantic search implementation",
            "deployment strategy",
            "NixOS modules",
            "local AI agents",
            "qwen usage",
            "memory optimization",
            "layered loading",
            "orchestration pattern",
            "hybrid workflow",
            "agent diaries",
            "git commit format",
            "documentation approach",
            "temporal validity",
            "metadata taxonomy",
            "testing framework",
            "storage backend",
            "confidence scoring",
        ]
        return queries * 10  # Repeat for more samples

    def _populate_fact_store(self, num_facts: int = 100):
        """Populate fact store with test data"""
        from aidb.temporal_facts import TemporalFact

        if not self.fact_store:
            return

        # Generate test facts
        for i in range(num_facts):
            fact = TemporalFact(
                content=f"Test fact {i}: This is a benchmark fact about topic {i % 10}",
                project="benchmark",
                topic=f"topic-{i % 10}",
                type=["decision", "preference", "discovery"][i % 3],
                tags=[f"tag-{i % 5}", f"tag-{i % 7}"],
                confidence=0.9,
                source="performance-benchmark"
            )
            self.fact_store.add(fact)

        logger.info(f"Populated fact store with {num_facts} facts")

    def run_latency_test(
        self,
        queries: int = 1000,
        cold_cache: bool = False
    ) -> Dict[str, Any]:
        """
        Measure query latency distribution.

        Args:
            queries: Number of queries to run
            cold_cache: If True, clear cache between queries

        Returns:
            Dictionary with p50, p95, p99 latencies and full distribution
        """
        logger.info(f"Running latency test with {queries} queries")

        # Ensure fact store has data
        self._populate_fact_store(num_facts=500)

        measurements = []

        for i in range(queries):
            query = self.queries[i % len(self.queries)]

            # Measure query time
            start = time.perf_counter()
            self._execute_search(query)
            end = time.perf_counter()

            latency_ms = (end - start) * 1000

            measurements.append(LatencyMeasurement(
                query=query,
                latency_ms=latency_ms,
                timestamp=start,
                cache_hit=not cold_cache and i > 0
            ))

            # Optional: clear cache for cold test
            if cold_cache and hasattr(self.fact_store, 'clear_cache'):
                self.fact_store.clear_cache()

        # Calculate percentiles
        latencies = [m.latency_ms for m in measurements]
        latencies.sort()

        return {
            "test": "latency",
            "queries": queries,
            "cold_cache": cold_cache,
            "p50": statistics.median(latencies),
            "p95": self._percentile(latencies, 95),
            "p99": self._percentile(latencies, 99),
            "min": min(latencies),
            "max": max(latencies),
            "mean": statistics.mean(latencies),
            "stdev": statistics.stdev(latencies) if len(latencies) > 1 else 0,
            "measurements": [
                {"query": m.query[:50], "latency_ms": m.latency_ms}
                for m in measurements[:100]  # Include first 100 for analysis
            ]
        }

    def run_throughput_test(self, duration_sec: int = 10) -> Dict[str, Any]:
        """
        Measure query throughput (queries per second).

        Args:
            duration_sec: How long to run test

        Returns:
            Dictionary with QPS and query count
        """
        logger.info(f"Running throughput test for {duration_sec} seconds")

        # Ensure fact store has data
        self._populate_fact_store(num_facts=500)

        start_time = time.perf_counter()
        end_time = start_time + duration_sec
        query_count = 0

        while time.perf_counter() < end_time:
            query = self.queries[query_count % len(self.queries)]
            self._execute_search(query)
            query_count += 1

        actual_duration = time.perf_counter() - start_time
        qps = query_count / actual_duration

        return {
            "test": "throughput",
            "duration_sec": actual_duration,
            "queries": query_count,
            "qps": qps,
        }

    def run_concurrency_test(
        self,
        num_workers: int = 10,
        queries_per_worker: int = 100
    ) -> Dict[str, Any]:
        """
        Measure performance under concurrent load.

        Args:
            num_workers: Number of parallel workers
            queries_per_worker: Queries each worker executes

        Returns:
            Dictionary with concurrency metrics
        """
        logger.info(
            f"Running concurrency test with {num_workers} workers, "
            f"{queries_per_worker} queries each"
        )

        # Ensure fact store has data
        self._populate_fact_store(num_facts=500)

        def worker_task(worker_id: int) -> Dict[str, Any]:
            """Single worker task"""
            latencies = []

            for i in range(queries_per_worker):
                query = self.queries[(worker_id * queries_per_worker + i) % len(self.queries)]

                start = time.perf_counter()
                self._execute_search(query)
                end = time.perf_counter()

                latencies.append((end - start) * 1000)

            return {
                "worker_id": worker_id,
                "queries": len(latencies),
                "p50": statistics.median(latencies),
                "p95": self._percentile(latencies, 95),
                "mean": statistics.mean(latencies),
            }

        # Run workers in parallel
        start_time = time.perf_counter()

        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [
                executor.submit(worker_task, i)
                for i in range(num_workers)
            ]

            worker_results = [f.result() for f in as_completed(futures)]

        total_duration = time.perf_counter() - start_time
        total_queries = num_workers * queries_per_worker
        overall_qps = total_queries / total_duration

        # Aggregate latencies
        all_p50s = [r["p50"] for r in worker_results]
        all_p95s = [r["p95"] for r in worker_results]

        return {
            "test": "concurrency",
            "num_workers": num_workers,
            "queries_per_worker": queries_per_worker,
            "total_queries": total_queries,
            "duration_sec": total_duration,
            "overall_qps": overall_qps,
            "median_p50_latency": statistics.median(all_p50s),
            "median_p95_latency": statistics.median(all_p95s),
            "worker_results": worker_results,
        }

    def run_storage_efficiency_test(self) -> Dict[str, Any]:
        """
        Measure storage efficiency and size.

        Returns:
            Dictionary with storage metrics
        """
        logger.info("Running storage efficiency test")

        if not self.fact_store:
            return {"error": "No fact store available"}

        # Get storage file path
        storage_file = getattr(self.fact_store, 'storage_file', None)

        if not storage_file or not storage_file.exists():
            return {"error": "Storage file not found"}

        # File size in bytes
        file_size_bytes = storage_file.stat().st_size
        file_size_mb = file_size_bytes / (1024 * 1024)

        # Count facts
        facts = self.fact_store.get_all()
        num_facts = len(facts)

        # Calculate average fact size
        avg_fact_size_bytes = file_size_bytes / num_facts if num_facts > 0 else 0

        # Estimate compression ratio (JSON vs raw text)
        total_content_length = sum(len(f.content) for f in facts)
        compression_ratio = file_size_bytes / total_content_length if total_content_length > 0 else 1.0

        return {
            "test": "storage_efficiency",
            "file_size_bytes": file_size_bytes,
            "file_size_mb": file_size_mb,
            "num_facts": num_facts,
            "avg_fact_size_bytes": avg_fact_size_bytes,
            "total_content_bytes": total_content_length,
            "storage_overhead_ratio": compression_ratio,
        }

    def run_memory_usage_test(self) -> Dict[str, Any]:
        """
        Measure memory usage during operations.

        Returns:
            Dictionary with memory metrics
        """
        logger.info("Running memory usage test")

        try:
            import psutil
            import os

            process = psutil.Process(os.getpid())

            # Measure baseline
            baseline_mb = process.memory_info().rss / (1024 * 1024)

            # Load facts
            self._populate_fact_store(num_facts=1000)
            after_load_mb = process.memory_info().rss / (1024 * 1024)

            # Execute queries
            for i in range(100):
                query = self.queries[i % len(self.queries)]
                self._execute_search(query)

            after_queries_mb = process.memory_info().rss / (1024 * 1024)

            return {
                "test": "memory_usage",
                "baseline_mb": baseline_mb,
                "after_load_mb": after_load_mb,
                "after_queries_mb": after_queries_mb,
                "load_increase_mb": after_load_mb - baseline_mb,
                "query_increase_mb": after_queries_mb - after_load_mb,
            }

        except ImportError:
            logger.warning("psutil not available, skipping memory test")
            return {"test": "memory_usage", "error": "psutil not installed"}

    def _execute_search(self, query: str) -> List[Any]:
        """Execute a search query"""
        if not self.fact_store:
            return []

        # Simple text search
        all_facts = self.fact_store.get_all()

        query_lower = query.lower()
        results = [
            f for f in all_facts
            if query_lower in f.content.lower()
        ]

        return results[:10]

    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile from sorted data"""
        if not data:
            return 0.0

        k = (len(data) - 1) * (percentile / 100)
        f = int(k)
        c = f + 1 if f < len(data) - 1 else f

        if f == c:
            return data[f]

        # Linear interpolation
        d0 = data[f] * (c - k)
        d1 = data[c] * (k - f)
        return d0 + d1

    def run_all(self) -> Dict[str, Any]:
        """
        Run all performance benchmarks.

        Returns:
            Combined results from all tests
        """
        logger.info("Running all performance benchmarks")

        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "latency_cold": self.run_latency_test(queries=1000, cold_cache=True),
            "latency_warm": self.run_latency_test(queries=1000, cold_cache=False),
            "throughput": self.run_throughput_test(duration_sec=10),
            "concurrency_10": self.run_concurrency_test(num_workers=10, queries_per_worker=100),
            "concurrency_50": self.run_concurrency_test(num_workers=50, queries_per_worker=50),
            "storage": self.run_storage_efficiency_test(),
            "memory": self.run_memory_usage_test(),
        }

        # Summary
        results["summary"] = {
            "p50_latency_ms": results["latency_warm"]["p50"],
            "p95_latency_ms": results["latency_warm"]["p95"],
            "p99_latency_ms": results["latency_warm"]["p99"],
            "throughput_qps": results["throughput"]["qps"],
            "concurrent_qps_10_workers": results["concurrency_10"]["overall_qps"],
            "storage_mb": results["storage"].get("file_size_mb", 0),
            "facts_count": results["storage"].get("num_facts", 0),
        }

        return results

    def save_results(self, results: Dict[str, Any], output_file: str):
        """Save benchmark results to JSON file"""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)

        logger.info(f"Saved results to {output_path}")


if __name__ == "__main__":
    # Demo usage
    import sys
    from pathlib import Path

    # Setup logging
    logging.basicConfig(level=logging.INFO)

    # Find corpus file
    corpus_file = Path(__file__).parent / "memory-benchmark-corpus.json"

    # Run benchmark
    print("=== Performance Benchmark ===\n")

    benchmark = PerformanceBenchmark(
        corpus_file=str(corpus_file) if corpus_file.exists() else None
    )
    results = benchmark.run_all()

    # Print summary
    print("\n=== Results Summary ===")
    summary = results["summary"]
    print(f"p50 Latency:        {summary['p50_latency_ms']:.2f} ms")
    print(f"p95 Latency:        {summary['p95_latency_ms']:.2f} ms")
    print(f"p99 Latency:        {summary['p99_latency_ms']:.2f} ms")
    print(f"Throughput:         {summary['throughput_qps']:.1f} qps")
    print(f"Concurrent (10w):   {summary['concurrent_qps_10_workers']:.1f} qps")
    print(f"Storage:            {summary['storage_mb']:.2f} MB ({summary['facts_count']} facts)")

    # Save results
    output_file = Path(__file__).parent / "results" / f"performance-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    benchmark.save_results(results, str(output_file))
    print(f"\nDetailed results saved to: {output_file}")
