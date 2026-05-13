"""
Search performance optimization library.

Provides optimized vector search, caching, batching, and profiling capabilities.
"""

__version__ = "1.0.0"

from .vector_search_optimizer import VectorSearchOptimizer
from .query_cache import QueryCache
from .query_batcher import QueryBatcher
from .embedding_optimizer import EmbeddingOptimizer
from .lazy_loader import LazyLoader
from .query_profiler import QueryProfiler

__all__ = [
    "VectorSearchOptimizer",
    "QueryCache",
    "QueryBatcher",
    "EmbeddingOptimizer",
    "LazyLoader",
    "QueryProfiler",
]
