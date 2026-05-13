#!/usr/bin/env python3
"""
Query Batching System for Optimized Vector Operations.

Implements intelligent query batching with automatic batch size optimization,
latency-based batching windows, priority queues, and throughput metrics.

Target Performance:
- Batch efficiency > 75%
- Max batching latency < 50ms for non-priority queries
- Throughput increase of 3-5x for burst workloads

Usage:
    from lib.search.query_batcher import QueryBatcher

    batcher = QueryBatcher(
        search_fn=vector_search,
        config=config
    )
    await batcher.start()

    # Submit query (batched automatically)
    result = await batcher.submit_query(
        query_vector=vector,
        collection="my_collection",
        limit=10,
        priority=False
    )
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
from uuid import uuid4

logger = logging.getLogger(__name__)


class Priority(Enum):
    """Query priority levels."""

    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


@dataclass
class BatchConfig:
    """Query batching configuration."""

    # Batch sizing
    min_batch_size: int = 5  # Minimum queries to form a batch
    max_batch_size: int = 50  # Maximum queries per batch
    optimal_batch_size: int = 20  # Target batch size

    # Timing
    max_wait_ms: float = 50.0  # Maximum wait for non-urgent queries
    urgent_wait_ms: float = 5.0  # Maximum wait for urgent queries
    batch_interval_ms: float = 10.0  # Batch processing interval

    # Optimization
    auto_tune_batch_size: bool = True  # Automatically adjust batch size
    target_latency_ms: float = 100.0  # Target per-query latency
    tune_interval_seconds: int = 60  # How often to retune batch size

    # Metrics
    enable_metrics: bool = True


@dataclass
class QueryRequest:
    """Individual query request."""

    id: str
    query_vector: List[float]
    collection: str
    limit: int
    priority: Priority
    submit_time: float
    future: asyncio.Future = field(default_factory=asyncio.Future)
    metadata: Dict[str, Any] = field(default_factory=dict)


class QueryBatcher:
    """
    Intelligent query batching system.

    Features:
    - Automatic batch formation with configurable sizes
    - Priority queue for urgent queries
    - Latency-based batching windows (max 50ms wait)
    - Automatic batch size optimization
    - Throughput vs latency trade-off tuning
    - Comprehensive metrics for batch efficiency
    """

    def __init__(
        self,
        search_fn: Callable,
        config: Optional[BatchConfig] = None,
    ):
        """
        Initialize query batcher.

        Args:
            search_fn: Async function to execute searches
                       Should accept (collection, query_vectors, limit) and return results
            config: Batching configuration
        """
        self.search_fn = search_fn
        self.config = config or BatchConfig()

        # Query queues by priority
        self.queues: Dict[Priority, asyncio.Queue] = {
            Priority.URGENT: asyncio.Queue(),
            Priority.HIGH: asyncio.Queue(),
            Priority.NORMAL: asyncio.Queue(),
            Priority.LOW: asyncio.Queue(),
        }

        # Batch processing
        self.running = False
        self.processor_task: Optional[asyncio.Task] = None
        self.tuner_task: Optional[asyncio.Task] = None

        # Current batch size (can be auto-tuned)
        self.current_batch_size = self.config.optimal_batch_size

        # Metrics
        self.metrics = {
            "total_queries": 0,
            "batches_processed": 0,
            "total_batch_latency_ms": 0.0,
            "total_wait_time_ms": 0.0,
            "queries_by_priority": {p: 0 for p in Priority},
            "batch_sizes": [],
            "efficiency_scores": [],
        }

        logger.info(
            f"QueryBatcher initialized: batch_size={self.current_batch_size}, "
            f"max_wait={self.config.max_wait_ms}ms"
        )

    async def start(self) -> None:
        """Start batch processor."""
        if self.running:
            logger.warning("QueryBatcher already running")
            return

        self.running = True
        self.processor_task = asyncio.create_task(self._process_batches())

        if self.config.auto_tune_batch_size:
            self.tuner_task = asyncio.create_task(self._auto_tune_batch_size())

        logger.info("QueryBatcher started")

    async def stop(self) -> None:
        """Stop batch processor."""
        if not self.running:
            return

        self.running = False

        # Cancel processor tasks
        if self.processor_task:
            self.processor_task.cancel()
            try:
                await self.processor_task
            except asyncio.CancelledError:
                pass

        if self.tuner_task:
            self.tuner_task.cancel()
            try:
                await self.tuner_task
            except asyncio.CancelledError:
                pass

        # Clear remaining queries
        for queue in self.queues.values():
            while not queue.empty():
                try:
                    request = queue.get_nowait()
                    if not request.future.done():
                        request.future.set_exception(
                            RuntimeError("QueryBatcher stopped")
                        )
                except asyncio.QueueEmpty:
                    break

        logger.info("QueryBatcher stopped")

    async def submit_query(
        self,
        query_vector: List[float],
        collection: str,
        limit: int = 10,
        priority: str = "normal",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Submit query for batched execution.

        Args:
            query_vector: Query embedding vector
            collection: Target collection
            limit: Result limit
            priority: Priority level ("urgent", "high", "normal", "low")
            metadata: Optional metadata to attach to request

        Returns:
            Query results
        """
        if not self.running:
            raise RuntimeError("QueryBatcher not running. Call start() first.")

        # Create request
        priority_enum = Priority[priority.upper()]
        request = QueryRequest(
            id=str(uuid4()),
            query_vector=query_vector,
            collection=collection,
            limit=limit,
            priority=priority_enum,
            submit_time=time.time(),
            metadata=metadata or {},
        )

        # Add to appropriate queue
        await self.queues[priority_enum].put(request)

        # Update metrics
        self.metrics["total_queries"] += 1
        self.metrics["queries_by_priority"][priority_enum] += 1

        # Wait for result
        return await request.future

    async def _process_batches(self) -> None:
        """Main batch processing loop."""
        while self.running:
            try:
                # Process urgent queries immediately
                urgent_batch = await self._collect_batch(
                    Priority.URGENT,
                    max_wait_ms=self.config.urgent_wait_ms,
                    min_size=1,  # Process immediately
                )
                if urgent_batch:
                    await self._execute_batch(urgent_batch)

                # Process other priorities with batching
                for priority in [Priority.HIGH, Priority.NORMAL, Priority.LOW]:
                    batch = await self._collect_batch(
                        priority,
                        max_wait_ms=self._get_wait_time(priority),
                        min_size=self.config.min_batch_size,
                    )
                    if batch:
                        await self._execute_batch(batch)

                # Small sleep to avoid busy-waiting
                await asyncio.sleep(self.config.batch_interval_ms / 1000.0)

            except Exception as e:
                logger.error(f"Batch processing error: {e}", exc_info=True)
                await asyncio.sleep(0.1)

    def _get_wait_time(self, priority: Priority) -> float:
        """Get max wait time for priority level."""
        if priority == Priority.URGENT:
            return self.config.urgent_wait_ms
        elif priority == Priority.HIGH:
            return self.config.max_wait_ms * 0.5
        elif priority == Priority.NORMAL:
            return self.config.max_wait_ms
        else:  # LOW
            return self.config.max_wait_ms * 1.5

    async def _collect_batch(
        self,
        priority: Priority,
        max_wait_ms: float,
        min_size: int,
    ) -> List[QueryRequest]:
        """Collect queries for a batch."""
        batch: List[QueryRequest] = []
        queue = self.queues[priority]
        deadline = time.time() + (max_wait_ms / 1000.0)

        while len(batch) < self.current_batch_size and time.time() < deadline:
            try:
                # Calculate remaining wait time
                timeout = max(0.001, deadline - time.time())

                # Try to get query from queue
                request = await asyncio.wait_for(
                    queue.get(),
                    timeout=timeout,
                )
                batch.append(request)

                # If we have enough, don't wait longer
                if len(batch) >= min_size:
                    break

            except asyncio.TimeoutError:
                break

        return batch if len(batch) >= min_size else []

    async def _execute_batch(self, batch: List[QueryRequest]) -> None:
        """Execute a batch of queries."""
        if not batch:
            return

        start_time = time.time()
        batch_size = len(batch)

        try:
            # Group by collection and limit
            groups: Dict[Tuple[str, int], List[QueryRequest]] = {}
            for request in batch:
                key = (request.collection, request.limit)
                if key not in groups:
                    groups[key] = []
                groups[key].append(request)

            # Execute each group
            for (collection, limit), requests in groups.items():
                try:
                    # Extract query vectors
                    query_vectors = [r.query_vector for r in requests]

                    # Execute batch search
                    results = await self.search_fn(
                        collection=collection,
                        query_vectors=query_vectors,
                        limit=limit,
                    )

                    # Distribute results
                    for i, request in enumerate(requests):
                        if not request.future.done():
                            request.future.set_result(results[i])

                        # Track wait time
                        wait_time_ms = (start_time - request.submit_time) * 1000
                        self.metrics["total_wait_time_ms"] += wait_time_ms

                except Exception as e:
                    logger.error(f"Batch execution error for {collection}: {e}")
                    # Fail all requests in group
                    for request in requests:
                        if not request.future.done():
                            request.future.set_exception(e)

            # Track batch metrics
            batch_latency_ms = (time.time() - start_time) * 1000
            self.metrics["batches_processed"] += 1
            self.metrics["total_batch_latency_ms"] += batch_latency_ms
            self.metrics["batch_sizes"].append(batch_size)

            # Calculate efficiency
            efficiency = self._calculate_efficiency(batch_size, batch_latency_ms)
            self.metrics["efficiency_scores"].append(efficiency)

            logger.debug(
                f"Batch executed: size={batch_size}, latency={batch_latency_ms:.1f}ms, "
                f"efficiency={efficiency:.1%}"
            )

        except Exception as e:
            logger.error(f"Critical batch execution error: {e}", exc_info=True)
            # Fail all requests
            for request in batch:
                if not request.future.done():
                    request.future.set_exception(e)

    def _calculate_efficiency(self, batch_size: int, latency_ms: float) -> float:
        """
        Calculate batch efficiency score.

        Efficiency = (batch_size / max_batch_size) * (target_latency / actual_latency)
        """
        size_ratio = min(1.0, batch_size / self.config.max_batch_size)
        latency_ratio = min(1.0, self.config.target_latency_ms / max(latency_ms, 1.0))
        return size_ratio * latency_ratio

    async def _auto_tune_batch_size(self) -> None:
        """Automatically tune batch size based on performance."""
        while self.running:
            try:
                await asyncio.sleep(self.config.tune_interval_seconds)

                if len(self.metrics["efficiency_scores"]) < 10:
                    continue  # Not enough data

                # Calculate average efficiency
                recent_efficiency = sum(self.metrics["efficiency_scores"][-20:]) / min(
                    20, len(self.metrics["efficiency_scores"])
                )

                # Adjust batch size
                if recent_efficiency < 0.6:
                    # Low efficiency, try smaller batches
                    new_size = max(
                        self.config.min_batch_size,
                        int(self.current_batch_size * 0.8),
                    )
                elif recent_efficiency > 0.85:
                    # High efficiency, try larger batches
                    new_size = min(
                        self.config.max_batch_size,
                        int(self.current_batch_size * 1.2),
                    )
                else:
                    continue  # Keep current size

                if new_size != self.current_batch_size:
                    logger.info(
                        f"Auto-tuning batch size: {self.current_batch_size} -> {new_size} "
                        f"(efficiency: {recent_efficiency:.1%})"
                    )
                    self.current_batch_size = new_size

            except Exception as e:
                logger.error(f"Auto-tune error: {e}")

    def get_metrics(self) -> Dict[str, Any]:
        """Get batching metrics."""
        avg_batch_size = (
            sum(self.metrics["batch_sizes"]) / len(self.metrics["batch_sizes"])
            if self.metrics["batch_sizes"]
            else 0
        )

        avg_efficiency = (
            sum(self.metrics["efficiency_scores"]) / len(self.metrics["efficiency_scores"])
            if self.metrics["efficiency_scores"]
            else 0
        )

        avg_wait_time_ms = (
            self.metrics["total_wait_time_ms"] / self.metrics["total_queries"]
            if self.metrics["total_queries"] > 0
            else 0
        )

        avg_batch_latency_ms = (
            self.metrics["total_batch_latency_ms"] / self.metrics["batches_processed"]
            if self.metrics["batches_processed"] > 0
            else 0
        )

        return {
            **self.metrics,
            "current_batch_size": self.current_batch_size,
            "avg_batch_size": avg_batch_size,
            "avg_efficiency": avg_efficiency,
            "avg_wait_time_ms": avg_wait_time_ms,
            "avg_batch_latency_ms": avg_batch_latency_ms,
        }

    def reset_metrics(self) -> None:
        """Reset batching metrics."""
        self.metrics = {
            "total_queries": 0,
            "batches_processed": 0,
            "total_batch_latency_ms": 0.0,
            "total_wait_time_ms": 0.0,
            "queries_by_priority": {p: 0 for p in Priority},
            "batch_sizes": [],
            "efficiency_scores": [],
        }
