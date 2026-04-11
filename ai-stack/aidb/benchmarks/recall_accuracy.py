#!/usr/bin/env python3
"""
Recall Accuracy Benchmark - Phase 1 Slice 1.5

Measures the recall accuracy of the memory system using a benchmark corpus
of fact-query pairs. Calculates accuracy, Mean Reciprocal Rank (MRR), and
analyzes performance across different query strategies.

Metrics:
- Baseline Recall: Semantic search only (no metadata filtering)
- Metadata-Enhanced Recall: Semantic + project/topic/type filters
- Temporal Recall: Queries with time constraints
- Rank Quality: Mean Reciprocal Rank (MRR) - position of correct fact

Usage:
    from aidb.benchmarks.recall_accuracy import RecallBenchmark

    benchmark = RecallBenchmark("memory-benchmark-corpus.json")

    # Run baseline test (semantic only)
    baseline = benchmark.run_baseline()
    print(f"Baseline accuracy: {baseline['accuracy']:.2%}")
    print(f"MRR: {baseline['mrr']:.3f}")

    # Run with metadata filtering
    metadata = benchmark.run_metadata_enhanced()
    print(f"Metadata accuracy: {metadata['accuracy']:.2%}")
"""

import json
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class QueryResult:
    """Result of a single query test"""
    query: str
    expected_content: str
    found: bool
    rank: int  # 0 = not found, 1+ = position in results
    similarity: Optional[float] = None
    category: Optional[str] = None


class RecallBenchmark:
    """
    Benchmark for measuring recall accuracy of memory system.

    Tests different query strategies:
    - Baseline: Semantic search only
    - Metadata-enhanced: Semantic + metadata filters
    - Temporal: Time-constrained queries
    """

    def __init__(self, corpus_file: str, fact_store=None):
        """
        Initialize recall benchmark.

        Args:
            corpus_file: Path to benchmark corpus JSON
            fact_store: Fact store implementation (defaults to in-memory JSON store)
        """
        self.corpus_file = Path(corpus_file)
        self.corpus = self._load_corpus()
        self.fact_store = fact_store or self._get_default_fact_store()

    def _load_corpus(self) -> Dict[str, Any]:
        """Load benchmark corpus from JSON file"""
        if not self.corpus_file.exists():
            raise FileNotFoundError(f"Corpus file not found: {self.corpus_file}")

        with open(self.corpus_file, 'r') as f:
            corpus = json.load(f)

        logger.info(
            f"Loaded corpus v{corpus['version']} with {corpus['total_pairs']} pairs"
        )
        return corpus

    def _get_default_fact_store(self):
        """Get default in-memory fact store for testing"""
        # Import here to avoid circular dependencies
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts" / "ai"))

        try:
            # Try to import from aq-memory
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

    def _populate_fact_store(self):
        """Populate fact store with corpus facts"""
        from aidb.temporal_facts import TemporalFact

        if not self.fact_store:
            logger.error("No fact store available")
            return

        fact_count = 0
        for category in self.corpus.get("categories", []):
            for pair in category.get("pairs", []):
                fact_data = pair["fact"]

                # Create temporal fact
                fact = TemporalFact(
                    content=fact_data["content"],
                    project=fact_data["project"],
                    topic=fact_data.get("topic"),
                    type=fact_data["type"],
                    tags=fact_data.get("tags", []),
                    confidence=fact_data.get("confidence", 1.0),
                    source="benchmark-corpus"
                )

                self.fact_store.add(fact)
                fact_count += 1

        logger.info(f"Populated fact store with {fact_count} facts")

    def run_baseline(self, limit: int = 10) -> Dict[str, Any]:
        """
        Run baseline recall test (semantic search only, no metadata filtering).

        Args:
            limit: Maximum number of results to consider per query

        Returns:
            Dictionary with accuracy, MRR, and detailed results
        """
        logger.info("Running baseline recall benchmark (semantic only)")

        # Ensure fact store is populated
        self._populate_fact_store()

        results = []

        for category in self.corpus.get("categories", []):
            category_name = category["name"]

            for pair in category.get("pairs", []):
                expected_content = pair["fact"]["content"]

                for query in pair.get("queries", []):
                    # Perform semantic search (simple keyword matching for now)
                    rank = self._find_rank_baseline(query, expected_content, limit)

                    results.append(QueryResult(
                        query=query,
                        expected_content=expected_content,
                        found=rank > 0,
                        rank=rank,
                        category=category_name
                    ))

        # Calculate metrics
        accuracy = sum(1 for r in results if r.found) / len(results) if results else 0
        mrr = self._calculate_mrr(results)

        # Category breakdown
        category_stats = self._calculate_category_stats(results)

        return {
            "strategy": "baseline",
            "accuracy": accuracy,
            "mrr": mrr,
            "total_queries": len(results),
            "found": sum(1 for r in results if r.found),
            "not_found": sum(1 for r in results if not r.found),
            "category_stats": category_stats,
            "results": [self._result_to_dict(r) for r in results]
        }

    def run_metadata_enhanced(self, limit: int = 10) -> Dict[str, Any]:
        """
        Run metadata-enhanced recall test (semantic + metadata filtering).

        Uses project, topic, and type filters to narrow search space before
        semantic search, improving precision.

        Args:
            limit: Maximum number of results to consider per query

        Returns:
            Dictionary with accuracy, MRR, and detailed results
        """
        logger.info("Running metadata-enhanced recall benchmark")

        # Ensure fact store is populated
        self._populate_fact_store()

        results = []

        for category in self.corpus.get("categories", []):
            category_name = category["name"]

            for pair in category.get("pairs", []):
                expected_content = pair["fact"]["content"]
                fact_metadata = pair["fact"]

                for query in pair.get("queries", []):
                    # Perform metadata-filtered search
                    rank = self._find_rank_metadata(
                        query,
                        expected_content,
                        fact_metadata,
                        limit
                    )

                    results.append(QueryResult(
                        query=query,
                        expected_content=expected_content,
                        found=rank > 0,
                        rank=rank,
                        category=category_name
                    ))

        # Calculate metrics
        accuracy = sum(1 for r in results if r.found) / len(results) if results else 0
        mrr = self._calculate_mrr(results)

        # Category breakdown
        category_stats = self._calculate_category_stats(results)

        return {
            "strategy": "metadata_enhanced",
            "accuracy": accuracy,
            "mrr": mrr,
            "total_queries": len(results),
            "found": sum(1 for r in results if r.found),
            "not_found": sum(1 for r in results if not r.found),
            "category_stats": category_stats,
            "results": [self._result_to_dict(r) for r in results]
        }

    def run_temporal(self, limit: int = 10) -> Dict[str, Any]:
        """
        Run temporal recall test (queries with time constraints).

        Tests retrieval of facts valid at specific times, including
        historical queries and staleness detection.

        Args:
            limit: Maximum number of results to consider per query

        Returns:
            Dictionary with accuracy, MRR, and detailed results
        """
        logger.info("Running temporal recall benchmark")

        # Ensure fact store is populated
        self._populate_fact_store()

        results = []

        # For temporal testing, we use current time (all facts should be valid now)
        current_time = datetime.now(timezone.utc)

        for category in self.corpus.get("categories", []):
            category_name = category["name"]

            for pair in category.get("pairs", []):
                expected_content = pair["fact"]["content"]
                fact_metadata = pair["fact"]

                # Use first query only for temporal test
                if pair.get("queries"):
                    query = pair["queries"][0]

                    # Perform temporal-aware search
                    rank = self._find_rank_temporal(
                        query,
                        expected_content,
                        fact_metadata,
                        current_time,
                        limit
                    )

                    results.append(QueryResult(
                        query=query,
                        expected_content=expected_content,
                        found=rank > 0,
                        rank=rank,
                        category=category_name
                    ))

        # Calculate metrics
        accuracy = sum(1 for r in results if r.found) / len(results) if results else 0
        mrr = self._calculate_mrr(results)

        # Category breakdown
        category_stats = self._calculate_category_stats(results)

        return {
            "strategy": "temporal",
            "accuracy": accuracy,
            "mrr": mrr,
            "total_queries": len(results),
            "found": sum(1 for r in results if r.found),
            "not_found": sum(1 for r in results if not r.found),
            "category_stats": category_stats,
            "results": [self._result_to_dict(r) for r in results]
        }

    def _find_rank_baseline(
        self,
        query: str,
        expected_content: str,
        limit: int
    ) -> int:
        """
        Find rank of expected fact using baseline semantic search.

        Returns:
            Rank (1-based) or 0 if not found in top results
        """
        if not self.fact_store:
            return 0

        # Get all facts
        all_facts = self.fact_store.get_all()

        # Simple keyword matching (in production, would use embeddings)
        query_lower = query.lower()
        query_words = set(query_lower.split())

        # Score facts by keyword overlap
        scored_facts = []
        for fact in all_facts:
            content_lower = fact.content.lower()
            content_words = set(content_lower.split())

            # Calculate overlap score
            overlap = len(query_words & content_words)
            if overlap > 0 or query_lower in content_lower:
                score = overlap + (2 if query_lower in content_lower else 0)
                scored_facts.append((score, fact))

        # Sort by score (descending)
        scored_facts.sort(reverse=True, key=lambda x: x[0])

        # Find rank of expected fact
        for i, (score, fact) in enumerate(scored_facts[:limit], 1):
            if fact.content == expected_content:
                return i

        return 0

    def _find_rank_metadata(
        self,
        query: str,
        expected_content: str,
        fact_metadata: Dict[str, Any],
        limit: int
    ) -> int:
        """
        Find rank using metadata-enhanced search.

        Returns:
            Rank (1-based) or 0 if not found
        """
        if not self.fact_store:
            return 0

        from aidb.temporal_query import (
            filter_facts_by_project,
            filter_facts_by_topic,
            filter_facts_by_type,
        )

        # Start with all facts
        facts = self.fact_store.get_all()

        # Apply metadata filters
        if "project" in fact_metadata:
            facts = filter_facts_by_project(facts, fact_metadata["project"])

        if fact_metadata.get("topic"):
            facts = filter_facts_by_topic(facts, fact_metadata["topic"])

        if "type" in fact_metadata:
            facts = filter_facts_by_type(facts, fact_metadata["type"])

        # Now do semantic search on filtered set
        query_lower = query.lower()
        query_words = set(query_lower.split())

        scored_facts = []
        for fact in facts:
            content_lower = fact.content.lower()
            content_words = set(content_lower.split())

            overlap = len(query_words & content_words)
            if overlap > 0 or query_lower in content_lower:
                score = overlap + (2 if query_lower in content_lower else 0)
                scored_facts.append((score, fact))

        scored_facts.sort(reverse=True, key=lambda x: x[0])

        # Find rank
        for i, (score, fact) in enumerate(scored_facts[:limit], 1):
            if fact.content == expected_content:
                return i

        return 0

    def _find_rank_temporal(
        self,
        query: str,
        expected_content: str,
        fact_metadata: Dict[str, Any],
        valid_at: datetime,
        limit: int
    ) -> int:
        """
        Find rank using temporal-aware search.

        Returns:
            Rank (1-based) or 0 if not found
        """
        if not self.fact_store:
            return 0

        from aidb.temporal_facts import get_valid_facts
        from aidb.temporal_query import (
            filter_facts_by_project,
            filter_facts_by_type,
        )

        # Start with all facts
        facts = self.fact_store.get_all()

        # Filter to valid facts at specified time
        facts = get_valid_facts(facts, at_time=valid_at)

        # Apply metadata filters
        if "project" in fact_metadata:
            facts = filter_facts_by_project(facts, fact_metadata["project"])

        if "type" in fact_metadata:
            facts = filter_facts_by_type(facts, fact_metadata["type"])

        # Semantic search on filtered set
        query_lower = query.lower()
        query_words = set(query_lower.split())

        scored_facts = []
        for fact in facts:
            content_lower = fact.content.lower()
            content_words = set(content_lower.split())

            overlap = len(query_words & content_words)
            if overlap > 0 or query_lower in content_lower:
                score = overlap + (2 if query_lower in content_lower else 0)
                scored_facts.append((score, fact))

        scored_facts.sort(reverse=True, key=lambda x: x[0])

        # Find rank
        for i, (score, fact) in enumerate(scored_facts[:limit], 1):
            if fact.content == expected_content:
                return i

        return 0

    def _calculate_mrr(self, results: List[QueryResult]) -> float:
        """
        Calculate Mean Reciprocal Rank.

        MRR is the average of reciprocal ranks (1/rank) for all queries.
        Queries where the fact wasn't found contribute 0.
        """
        if not results:
            return 0.0

        reciprocal_ranks = [1.0 / r.rank if r.rank > 0 else 0.0 for r in results]
        return sum(reciprocal_ranks) / len(reciprocal_ranks)

    def _calculate_category_stats(
        self,
        results: List[QueryResult]
    ) -> Dict[str, Dict[str, Any]]:
        """Calculate accuracy and MRR breakdown by category"""
        categories = {}

        for result in results:
            cat = result.category
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(result)

        stats = {}
        for cat, cat_results in categories.items():
            accuracy = sum(1 for r in cat_results if r.found) / len(cat_results)
            mrr = self._calculate_mrr(cat_results)

            stats[cat] = {
                "accuracy": accuracy,
                "mrr": mrr,
                "total": len(cat_results),
                "found": sum(1 for r in cat_results if r.found)
            }

        return stats

    def _result_to_dict(self, result: QueryResult) -> Dict[str, Any]:
        """Convert QueryResult to dictionary"""
        return {
            "query": result.query,
            "expected": result.expected_content[:100],
            "found": result.found,
            "rank": result.rank,
            "category": result.category
        }

    def run_all(self, limit: int = 10) -> Dict[str, Any]:
        """
        Run all benchmark strategies and return combined results.

        Args:
            limit: Maximum number of results per query

        Returns:
            Combined results from all strategies
        """
        logger.info("Running all recall benchmarks")

        baseline = self.run_baseline(limit)
        metadata = self.run_metadata_enhanced(limit)
        temporal = self.run_temporal(limit)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "corpus_version": self.corpus["version"],
            "corpus_total_pairs": self.corpus["total_pairs"],
            "limit": limit,
            "baseline": baseline,
            "metadata_enhanced": metadata,
            "temporal": temporal,
            "summary": {
                "baseline_accuracy": baseline["accuracy"],
                "metadata_accuracy": metadata["accuracy"],
                "temporal_accuracy": temporal["accuracy"],
                "baseline_mrr": baseline["mrr"],
                "metadata_mrr": metadata["mrr"],
                "temporal_mrr": temporal["mrr"],
            }
        }

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

    if not corpus_file.exists():
        print(f"Error: Corpus file not found: {corpus_file}")
        sys.exit(1)

    # Run benchmark
    print("=== Recall Accuracy Benchmark ===\n")

    benchmark = RecallBenchmark(str(corpus_file))
    results = benchmark.run_all(limit=10)

    # Print summary
    print("\n=== Results Summary ===")
    print(f"Baseline Accuracy:  {results['summary']['baseline_accuracy']:.2%}")
    print(f"Metadata Accuracy:  {results['summary']['metadata_accuracy']:.2%}")
    print(f"Temporal Accuracy:  {results['summary']['temporal_accuracy']:.2%}")
    print(f"\nBaseline MRR:       {results['summary']['baseline_mrr']:.3f}")
    print(f"Metadata MRR:       {results['summary']['metadata_mrr']:.3f}")
    print(f"Temporal MRR:       {results['summary']['temporal_mrr']:.3f}")

    # Save results
    output_file = Path(__file__).parent / "results" / f"recall-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    benchmark.save_results(results, str(output_file))
    print(f"\nDetailed results saved to: {output_file}")
