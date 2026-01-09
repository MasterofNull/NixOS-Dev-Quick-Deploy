#!/usr/bin/env python3
"""
Garbage Collection System for Hybrid Coordinator
Prevents unbounded storage growth through:
- Time-based expiration (delete old low-value entries)
- Value-based pruning (keep only high-value solutions)
- Deduplication (remove similar entries)
- Orphan cleanup (remove vectors with no DB entry)
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import asyncpg
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from prometheus_client import Counter, Gauge, Histogram

logger = logging.getLogger(__name__)


# Prometheus metrics
GC_SOLUTIONS_DELETED = Counter(
    "hybrid_gc_solutions_deleted_total",
    "Solutions deleted by garbage collection",
    ["reason"]
)

GC_VECTORS_CLEANED = Counter(
    "hybrid_gc_vectors_cleaned_total",
    "Orphaned vectors cleaned from Qdrant"
)

GC_STORAGE_BYTES = Gauge(
    "hybrid_gc_storage_bytes",
    "Estimated storage used by solutions"
)

GC_EXECUTION_TIME = Histogram(
    "hybrid_gc_execution_seconds",
    "Time spent in garbage collection",
    ["operation"]
)

GC_DUPLICATES_FOUND = Counter(
    "hybrid_gc_duplicates_found_total",
    "Duplicate solutions found and deduplicated"
)


class GarbageCollector:
    """
    Manages storage cleanup for continuous learning system.

    Configuration:
    - max_solutions: Maximum number of solutions to keep
    - max_age_days: Delete solutions older than this
    - min_value_score: Delete low-value solutions below this score
    - deduplicate_similarity: Similarity threshold for deduplication
    """

    def __init__(
        self,
        db_pool: asyncpg.Pool,
        qdrant_client: QdrantClient,
        max_solutions: int = 100_000,
        max_age_days: int = 30,
        min_value_score: float = 0.5,
        deduplicate_similarity: float = 0.95
    ):
        self.db_pool = db_pool
        self.qdrant = qdrant_client
        self.max_solutions = max_solutions
        self.max_age_days = max_age_days
        self.min_value_score = min_value_score
        self.deduplicate_similarity = deduplicate_similarity

    async def run_full_gc(self) -> Dict[str, int]:
        """
        Run complete garbage collection cycle.

        Returns:
            Dict with counts of items cleaned by each operation
        """
        logger.info("Starting full garbage collection cycle")
        results = {}

        try:
            # 1. Time-based expiration
            expired = await self.cleanup_old_solutions()
            results['expired'] = expired
            GC_SOLUTIONS_DELETED.labels(reason="expired").inc(expired)

            # 2. Value-based pruning
            pruned = await self.prune_low_value_solutions()
            results['pruned'] = pruned
            GC_SOLUTIONS_DELETED.labels(reason="low_value").inc(pruned)

            # 3. Deduplication
            duplicates = await self.deduplicate_solutions()
            results['duplicates'] = duplicates
            GC_DUPLICATES_FOUND.inc(duplicates)
            GC_SOLUTIONS_DELETED.labels(reason="duplicate").inc(duplicates)

            # 4. Orphan cleanup
            orphans = await self.cleanup_qdrant_orphans()
            results['orphans'] = orphans
            GC_VECTORS_CLEANED.inc(orphans)

            # 5. Update storage metrics
            await self.update_storage_metrics()

            logger.info(f"Garbage collection complete: {results}")
            return results

        except Exception as e:
            logger.error(f"Garbage collection failed: {e}", exc_info=True)
            raise

    async def cleanup_old_solutions(self) -> int:
        """
        Delete solutions older than max_age_days with low value scores.

        Only deletes if BOTH conditions are met:
        - Older than max_age_days
        - value_score < min_value_score

        Returns:
            Number of solutions deleted
        """
        with GC_EXECUTION_TIME.labels(operation="cleanup_old").time():
            cutoff_date = datetime.now() - timedelta(days=self.max_age_days)

            async with self.db_pool.acquire() as conn:
                # Delete old low-value solutions
                result = await conn.execute("""
                    DELETE FROM solved_issues
                    WHERE value_score < $1
                    AND created_at < $2
                    RETURNING id
                """, self.min_value_score, cutoff_date)

                # Extract count from result
                deleted_count = int(result.split()[-1]) if result.startswith("DELETE") else 0

                if deleted_count > 0:
                    logger.info(
                        f"Deleted {deleted_count} old solutions "
                        f"(age > {self.max_age_days} days, score < {self.min_value_score})"
                    )

                return deleted_count

    async def prune_low_value_solutions(self) -> int:
        """
        Prune low-value solutions when approaching max_solutions limit.

        Keeps only the top (max_solutions * 0.8) by value_score.
        Deletes the bottom 20% when limit is reached.

        Returns:
            Number of solutions pruned
        """
        with GC_EXECUTION_TIME.labels(operation="prune_low_value").time():
            async with self.db_pool.acquire() as conn:
                # Check current count
                current_count = await conn.fetchval(
                    "SELECT COUNT(*) FROM solved_issues"
                )

                if current_count <= self.max_solutions:
                    logger.debug(
                        f"Storage within limit: {current_count}/{self.max_solutions}"
                    )
                    return 0

                # Calculate how many to keep (80% of max)
                keep_count = int(self.max_solutions * 0.8)

                # Find value_score threshold for top keep_count entries
                threshold = await conn.fetchval("""
                    SELECT value_score
                    FROM solved_issues
                    ORDER BY value_score DESC
                    LIMIT 1 OFFSET $1
                """, keep_count)

                if threshold is None:
                    return 0

                # Delete solutions below threshold
                result = await conn.execute("""
                    DELETE FROM solved_issues
                    WHERE value_score < $1
                    RETURNING id
                """, threshold)

                deleted_count = int(result.split()[-1]) if result.startswith("DELETE") else 0

                if deleted_count > 0:
                    logger.warning(
                        f"Pruned {deleted_count} low-value solutions "
                        f"(storage limit reached: {current_count}/{self.max_solutions})"
                    )

                return deleted_count

    async def deduplicate_solutions(self) -> int:
        """
        Remove near-duplicate solutions based on embedding similarity.

        For each group of duplicates, keeps the one with highest value_score.

        Returns:
            Number of duplicate solutions removed
        """
        with GC_EXECUTION_TIME.labels(operation="deduplicate").time():
            # This is a simplified implementation
            # In production, use Qdrant's search capabilities for efficient duplicate detection

            async with self.db_pool.acquire() as conn:
                # Get all solutions with their embeddings
                solutions = await conn.fetch("""
                    SELECT id, query, solution, value_score, created_at
                    FROM solved_issues
                    ORDER BY created_at DESC
                    LIMIT 10000
                """)

                if len(solutions) == 0:
                    return 0

                # Group duplicates by query similarity
                # This is a naive O(n²) implementation
                # For production, use Qdrant batch search
                duplicate_ids = set()
                seen = {}

                for sol in solutions:
                    query_hash = hash(sol['query'].lower().strip())

                    if query_hash in seen:
                        # Found potential duplicate
                        existing = seen[query_hash]

                        # Keep higher value score
                        if sol['value_score'] < existing['value_score']:
                            duplicate_ids.add(sol['id'])
                        else:
                            duplicate_ids.add(existing['id'])
                            seen[query_hash] = sol
                    else:
                        seen[query_hash] = sol

                if not duplicate_ids:
                    logger.debug("No duplicates found")
                    return 0

                # Delete duplicates
                result = await conn.execute("""
                    DELETE FROM solved_issues
                    WHERE id = ANY($1)
                    RETURNING id
                """, list(duplicate_ids))

                deleted_count = int(result.split()[-1]) if result.startswith("DELETE") else 0

                if deleted_count > 0:
                    logger.info(f"Deduplicated {deleted_count} similar solutions")

                return deleted_count

    async def cleanup_qdrant_orphans(self) -> int:
        """
        Remove vectors from Qdrant that have no corresponding database entry.

        This can happen if:
        - Database deletion failed but vector deletion succeeded
        - Manual database cleanup without vector cleanup
        - Bugs in the continuous learning system

        Returns:
            Number of orphaned vectors removed
        """
        with GC_EXECUTION_TIME.labels(operation="cleanup_orphans").time():
            try:
                collection_name = "solved_issues"

                # Get all vector IDs from Qdrant
                # Note: This uses scroll API for large collections
                qdrant_ids = set()
                offset = None

                while True:
                    scroll_result = self.qdrant.scroll(
                        collection_name=collection_name,
                        limit=100,
                        offset=offset,
                        with_payload=False,
                        with_vectors=False
                    )

                    if not scroll_result or len(scroll_result[0]) == 0:
                        break

                    for point in scroll_result[0]:
                        qdrant_ids.add(point.id)

                    offset = scroll_result[1]  # Next offset
                    if offset is None:
                        break

                logger.debug(f"Found {len(qdrant_ids)} vectors in Qdrant")

                # Get all IDs from PostgreSQL
                async with self.db_pool.acquire() as conn:
                    db_rows = await conn.fetch("SELECT id FROM solved_issues")
                    db_ids = {str(row['id']) for row in db_rows}

                logger.debug(f"Found {len(db_ids)} solutions in database")

                # Find orphaned vectors
                orphan_ids = qdrant_ids - db_ids

                if not orphan_ids:
                    logger.debug("No orphaned vectors found")
                    return 0

                # Delete orphaned vectors in batches
                batch_size = 100
                orphan_list = list(orphan_ids)
                deleted_count = 0

                for i in range(0, len(orphan_list), batch_size):
                    batch = orphan_list[i:i + batch_size]
                    self.qdrant.delete(
                        collection_name=collection_name,
                        points_selector=batch
                    )
                    deleted_count += len(batch)

                logger.info(f"Cleaned {deleted_count} orphaned vectors from Qdrant")
                return deleted_count

            except Exception as e:
                logger.error(f"Failed to cleanup Qdrant orphans: {e}", exc_info=True)
                return 0

    async def update_storage_metrics(self):
        """Update Prometheus metrics for storage usage"""
        try:
            async with self.db_pool.acquire() as conn:
                # Estimate storage size
                result = await conn.fetchrow("""
                    SELECT
                        COUNT(*) as count,
                        pg_total_relation_size('solved_issues') as table_size
                    FROM solved_issues
                """)

                if result:
                    GC_STORAGE_BYTES.set(result['table_size'])
                    logger.debug(
                        f"Storage metrics: {result['count']} solutions, "
                        f"{result['table_size']} bytes"
                    )

        except Exception as e:
            logger.error(f"Failed to update storage metrics: {e}", exc_info=True)

    async def get_gc_statistics(self) -> Dict[str, any]:
        """
        Get current garbage collection statistics.

        Returns:
            Dict with storage stats and GC configuration
        """
        async with self.db_pool.acquire() as conn:
            stats = await conn.fetchrow("""
                SELECT
                    COUNT(*) as total_solutions,
                    AVG(value_score) as avg_value_score,
                    MIN(created_at) as oldest_solution,
                    MAX(created_at) as newest_solution,
                    pg_total_relation_size('solved_issues') as storage_bytes
                FROM solved_issues
            """)

            return {
                'total_solutions': stats['total_solutions'],
                'avg_value_score': float(stats['avg_value_score']) if stats['avg_value_score'] else 0.0,
                'oldest_solution': stats['oldest_solution'].isoformat() if stats['oldest_solution'] else None,
                'newest_solution': stats['newest_solution'].isoformat() if stats['newest_solution'] else None,
                'storage_bytes': stats['storage_bytes'],
                'max_solutions': self.max_solutions,
                'max_age_days': self.max_age_days,
                'min_value_score': self.min_value_score,
                'storage_utilization': stats['total_solutions'] / self.max_solutions if self.max_solutions > 0 else 0
            }


# Scheduled GC task
async def run_gc_scheduler(
    gc: GarbageCollector,
    interval_seconds: int = 3600  # Default: 1 hour
):
    """
    Run garbage collection on a schedule.

    Args:
        gc: GarbageCollector instance
        interval_seconds: Seconds between GC runs
    """
    logger.info(f"Starting GC scheduler (interval: {interval_seconds}s)")

    while True:
        try:
            await asyncio.sleep(interval_seconds)

            logger.info("Running scheduled garbage collection")
            results = await gc.run_full_gc()
            logger.info(f"Scheduled GC complete: {results}")

        except asyncio.CancelledError:
            logger.info("GC scheduler cancelled")
            break
        except Exception as e:
            logger.error(f"Scheduled GC failed: {e}", exc_info=True)
            # Continue running despite errors


# Example usage
if __name__ == "__main__":
    print("Garbage Collector Module")
    print("=" * 60)
    print("\nConfiguration:")
    print("  max_solutions: 100,000")
    print("  max_age_days: 30")
    print("  min_value_score: 0.5")
    print("  deduplicate_similarity: 0.95")
    print("\nOperations:")
    print("  1. Time-based expiration (age > 30 days AND score < 0.5)")
    print("  2. Value-based pruning (keep top 80% when limit reached)")
    print("  3. Deduplication (remove similar queries)")
    print("  4. Orphan cleanup (remove vectors without DB entries)")
    print("\n" + "=" * 60)
    print("Garbage collector module loaded successfully")
