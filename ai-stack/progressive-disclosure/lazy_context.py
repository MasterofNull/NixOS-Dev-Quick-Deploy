#!/usr/bin/env python3
"""
Lazy Context Resolution System

Just-in-time context loading with incremental expansion and prefetching.
Part of Phase 8 Batch 8.2: Lazy Context Resolution

Key Features:
- Just-in-time context loading
- Incremental context expansion
- Context dependency graph
- Parallel context fetching
- Context prefetching based on predictions

Reference: Lazy loading patterns, dependency resolution
"""

import asyncio
import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class ContextStatus(Enum):
    """Status of context chunk"""
    NOT_LOADED = "not_loaded"
    LOADING = "loading"
    LOADED = "loaded"
    FAILED = "failed"


@dataclass
class ContextNode:
    """Node in context dependency graph"""
    node_id: str
    content: str
    dependencies: Set[str] = field(default_factory=set)
    status: ContextStatus = ContextStatus.NOT_LOADED
    load_priority: int = 0
    tokens: int = 0
    metadata: Dict = field(default_factory=dict)


@dataclass
class LoadRequest:
    """Request to load context"""
    request_id: str
    node_ids: List[str]
    requester: str
    timestamp: datetime = field(default_factory=datetime.now)


class ContextDependencyGraph:
    """Dependency graph for context chunks"""

    def __init__(self):
        self.nodes: Dict[str, ContextNode] = {}
        logger.info("Context Dependency Graph initialized")

    def add_node(self, node: ContextNode):
        """Add node to graph"""
        self.nodes[node.node_id] = node

    def add_dependency(self, node_id: str, depends_on: str):
        """Add dependency relationship"""
        if node_id in self.nodes:
            self.nodes[node_id].dependencies.add(depends_on)

    def get_load_order(self, node_ids: List[str]) -> List[List[str]]:
        """Get loading order respecting dependencies (topological sort)"""
        # Build dependency map
        in_degree = defaultdict(int)
        graph = defaultdict(list)

        for node_id in node_ids:
            if node_id not in self.nodes:
                continue

            node = self.nodes[node_id]
            for dep in node.dependencies:
                if dep in node_ids:
                    graph[dep].append(node_id)
                    in_degree[node_id] += 1

        # Topological sort (Kahn's algorithm)
        queue = deque([nid for nid in node_ids if in_degree[nid] == 0])
        result = []
        current_level = []

        while queue:
            # Process nodes at same level (can be loaded in parallel)
            level_size = len(queue)
            current_level = []

            for _ in range(level_size):
                node_id = queue.popleft()
                current_level.append(node_id)

                # Reduce in-degree for dependents
                for dependent in graph[node_id]:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

            if current_level:
                result.append(current_level)

        return result


class LazyContextLoader:
    """Load context lazily as needed"""

    def __init__(self, dependency_graph: ContextDependencyGraph):
        self.graph = dependency_graph
        self.cache: Dict[str, str] = {}  # node_id -> content
        self.load_stats: Dict[str, int] = defaultdict(int)

        logger.info("Lazy Context Loader initialized")

    async def load(
        self,
        node_ids: List[str],
        max_concurrent: int = 5,
    ) -> Dict[str, str]:
        """Load context nodes lazily"""
        logger.info(f"Lazy loading {len(node_ids)} nodes")

        # Get loading order (respects dependencies)
        load_order = self.graph.get_load_order(node_ids)

        loaded = {}

        for level in load_order:
            logger.info(f"  Loading level: {len(level)} nodes")

            # Load nodes in parallel (they have no dependencies on each other)
            tasks = []
            for node_id in level:
                if node_id in self.cache:
                    # Already cached
                    loaded[node_id] = self.cache[node_id]
                else:
                    tasks.append(self._load_node(node_id))

            # Wait for all in this level
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for node_id, result in zip(
                    [nid for nid in level if nid not in self.cache],
                    results
                ):
                    if isinstance(result, Exception):
                        logger.error(f"Failed to load {node_id}: {result}")
                    else:
                        loaded[node_id] = result
                        self.cache[node_id] = result
                        self.load_stats[node_id] += 1

        logger.info(f"Loaded {len(loaded)} nodes")
        return loaded

    async def _load_node(self, node_id: str) -> str:
        """Load single node"""
        node = self.graph.nodes.get(node_id)
        if not node:
            raise ValueError(f"Node {node_id} not found")

        node.status = ContextStatus.LOADING

        # Simulate loading
        await asyncio.sleep(0.01)

        node.status = ContextStatus.LOADED
        return node.content


class IncrementalExpander:
    """Incrementally expand context as needed"""

    def __init__(self, loader: LazyContextLoader):
        self.loader = loader
        self.expansion_history: List[Dict] = []

        logger.info("Incremental Expander initialized")

    async def expand_context(
        self,
        current_nodes: Set[str],
        expansion_criteria: Callable[[ContextNode], bool],
        max_expansions: int = 3,
    ) -> Set[str]:
        """Expand context incrementally based on criteria"""
        logger.info(f"Expanding from {len(current_nodes)} nodes")

        expanded = set(current_nodes)
        expansion_count = 0

        while expansion_count < max_expansions:
            # Find candidates for expansion
            candidates = []

            for node_id in list(expanded):
                node = self.loader.graph.nodes.get(node_id)
                if not node:
                    continue

                # Find nodes that depend on this one (forward expansion)
                for other_id, other_node in self.loader.graph.nodes.items():
                    if other_id not in expanded and node_id in other_node.dependencies:
                        if expansion_criteria(other_node):
                            candidates.append(other_id)

            if not candidates:
                break

            # Add candidates
            new_nodes = set(candidates[:5])  # Limit expansion size
            expanded.update(new_nodes)
            expansion_count += 1

            logger.info(f"  Expansion {expansion_count}: added {len(new_nodes)} nodes")

        self.expansion_history.append({
            "timestamp": datetime.now(),
            "initial_size": len(current_nodes),
            "final_size": len(expanded),
            "expansions": expansion_count,
        })

        return expanded


class ContextPrefetcher:
    """Prefetch context based on predictions"""

    def __init__(self, loader: LazyContextLoader):
        self.loader = loader
        self.access_patterns: Dict[str, List[str]] = defaultdict(list)

        logger.info("Context Prefetcher initialized")

    def record_access(self, node_id: str, next_accessed: Optional[str] = None):
        """Record access pattern"""
        if next_accessed:
            self.access_patterns[node_id].append(next_accessed)

    async def prefetch(self, current_node: str, max_prefetch: int = 3) -> List[str]:
        """Prefetch likely next nodes"""
        # Find most common next accesses
        next_nodes = self.access_patterns.get(current_node, [])

        if not next_nodes:
            return []

        # Count frequencies
        from collections import Counter
        frequencies = Counter(next_nodes)

        # Get top N most common
        likely_next = [node for node, _ in frequencies.most_common(max_prefetch)]

        logger.info(f"Prefetching {len(likely_next)} nodes for {current_node}")

        # Load in background
        asyncio.create_task(self.loader.load(likely_next))

        return likely_next


async def main():
    """Test lazy context resolution"""
    logging.basicConfig(level=logging.INFO)

    logger.info("Lazy Context Resolution Test")
    logger.info("=" * 60)

    # Initialize components
    graph = ContextDependencyGraph()

    # Create dependency graph
    nodes = [
        ContextNode("intro", "Introduction", set(), tokens=50),
        ContextNode("setup", "Setup instructions", {"intro"}, tokens=100),
        ContextNode("config", "Configuration", {"setup"}, tokens=150),
        ContextNode("advanced", "Advanced usage", {"config"}, tokens=200),
        ContextNode("troubleshooting", "Troubleshooting", {"setup", "config"}, tokens=120),
    ]

    for node in nodes:
        graph.add_node(node)

    loader = LazyContextLoader(graph)
    expander = IncrementalExpander(loader)
    prefetcher = ContextPrefetcher(loader)

    # Test 1: Lazy loading with dependencies
    logger.info("\n1. Lazy Loading:")

    loaded = await loader.load(["advanced", "troubleshooting"])

    logger.info(f"  Loaded nodes: {list(loaded.keys())}")

    # Test 2: Incremental expansion
    logger.info("\n2. Incremental Expansion:")

    def always_expand(node: ContextNode) -> bool:
        return node.tokens < 200

    expanded = await expander.expand_context(
        {"intro"},
        always_expand,
        max_expansions=2,
    )

    logger.info(f"  Expanded to {len(expanded)} nodes: {expanded}")

    # Test 3: Prefetching
    logger.info("\n3. Context Prefetching:")

    # Record some access patterns
    prefetcher.record_access("intro", "setup")
    prefetcher.record_access("intro", "setup")
    prefetcher.record_access("intro", "config")
    prefetcher.record_access("setup", "config")

    # Prefetch
    prefetched = await prefetcher.prefetch("intro", max_prefetch=2)

    logger.info(f"  Prefetched: {prefetched}")


if __name__ == "__main__":
    asyncio.run(main())
