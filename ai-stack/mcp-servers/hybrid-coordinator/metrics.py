"""
Prometheus metric definitions for the hybrid-coordinator service.

Import with:  from metrics import *
or selectively: from metrics import REQUEST_COUNT, ROUTE_DECISIONS, ...
"""

from prometheus_client import Counter, Gauge, Histogram

REQUEST_COUNT = Counter(
    "hybrid_requests_total",
    "Total hybrid coordinator HTTP requests",
    ["endpoint", "status"],
)
REQUEST_ERRORS = Counter(
    "hybrid_request_errors_total",
    "Total hybrid coordinator HTTP request errors",
    ["endpoint", "method"],
)
REQUEST_LATENCY = Histogram(
    "hybrid_request_latency_seconds",
    "Hybrid coordinator HTTP request latency in seconds",
    ["endpoint", "method"],
)
PROCESS_MEMORY_BYTES = Gauge(
    "hybrid_process_memory_bytes",
    "Hybrid coordinator process resident memory in bytes",
)
ROUTE_DECISIONS = Counter(
    "hybrid_route_decisions_total",
    "Hybrid coordinator route decisions",
    ["route"],
)
ROUTE_ERRORS = Counter(
    "hybrid_route_errors_total",
    "Hybrid coordinator route errors",
    ["route"],
)
DISCOVERY_DECISIONS = Counter(
    "hybrid_capability_discovery_decisions_total",
    "Hybrid capability discovery decisions",
    ["decision", "reason"],
)
DISCOVERY_LATENCY = Histogram(
    "hybrid_capability_discovery_latency_seconds",
    "Hybrid capability discovery latency in seconds",
)
AUTONOMY_BUDGET_EXCEEDED = Counter(
    "hybrid_autonomy_budget_exceeded_total",
    "Hybrid autonomy budget exceed events",
    ["budget"],
)
# Phase 2.3.3 — per-backend routing latency (p50/p95/p99 available via Prometheus)
LLM_BACKEND_LATENCY = Histogram(
    "hybrid_llm_backend_latency_seconds",
    "End-to-end LLM call latency by backend (local=llama.cpp, remote=API)",
    ["backend"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)
LLM_BACKEND_SELECTIONS = Counter(
    "hybrid_llm_backend_selections_total",
    "LLM backend selection decisions",
    ["backend", "reason_class"],
)
# Phase 17.4.1 — embedding cache observability
EMBEDDING_CACHE_HITS = Counter(
    "embedding_cache_hits_total",
    "Total embedding cache hits",
)
EMBEDDING_CACHE_MISSES = Counter(
    "embedding_cache_misses_total",
    "Total embedding cache misses",
)
# Phase 21.3 — cache invalidation metrics
EMBEDDING_CACHE_INVALIDATIONS = Counter(
    "embedding_cache_invalidations_total",
    "Total embedding cache invalidation events",
    ["trigger"],  # "manual", "rebuild", "model_change"
)
EMBEDDING_CACHE_SIZE = Gauge(
    "embedding_cache_size_keys",
    "Current number of keys in the embedding cache",
)
# Phase 17.4.2 — context compression observability
CONTEXT_COMPRESSION_TOKENS_BEFORE = Histogram(
    "context_compression_tokens_before",
    "Token count of context before compression",
    buckets=[64, 128, 256, 512, 1024, 2048, 4096, 8192],
)
CONTEXT_COMPRESSION_TOKENS_AFTER = Histogram(
    "context_compression_tokens_after",
    "Token count of context after compression",
    buckets=[64, 128, 256, 512, 1024, 2048, 4096, 8192],
)
# Phase 5 — Model management observability
MODEL_RELOADS = Counter(
    "model_reloads_total",
    "Total model reload operations",
    ["service", "status"],  # status: "success", "failure"
)
MODEL_RELOAD_DURATION = Histogram(
    "model_reload_duration_seconds",
    "Duration of model reload operations",
    ["service"],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
)
MODEL_ACTIVE_INFO = Gauge(
    "model_active_info",
    "Active model information (value=1 when model is loaded)",
    ["service", "model_path"],
)

# Phase 1.1 — AI-specific operations observability
DELEGATED_PROMPT_TOKENS_BEFORE = Histogram(
    "hybrid_delegated_prompt_tokens_before",
    "Estimated delegated prompt tokens before optimization",
    ["profile"],
    buckets=[64, 128, 256, 512, 1024, 2048, 4096, 8192],
)
DELEGATED_PROMPT_TOKENS_AFTER = Histogram(
    "hybrid_delegated_prompt_tokens_after",
    "Estimated delegated prompt tokens after optimization",
    ["profile"],
    buckets=[64, 128, 256, 512, 1024, 2048, 4096, 8192],
)
DELEGATED_PROMPT_TOKEN_SAVINGS = Counter(
    "hybrid_delegated_prompt_token_savings_total",
    "Total estimated delegated prompt tokens saved through envelope optimization",
    ["profile"],
)
DELEGATED_QUALITY_SCORE = Histogram(
    "hybrid_delegated_quality_score",
    "Quality scores assigned to delegated responses",
    ["profile"],
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)
DELEGATED_QUALITY_EVENTS = Counter(
    "hybrid_delegated_quality_events_total",
    "Delegated quality-assurance outcomes",
    ["profile", "outcome"],
)
PROGRESSIVE_CONTEXT_LOADS = Counter(
    "hybrid_progressive_context_loads_total",
    "Progressive disclosure context attachment events",
    ["category", "tier", "profile"],
)
CAPABILITY_GAP_DETECTIONS = Counter(
    "hybrid_capability_gap_detections_total",
    "Capability gaps detected from delegated outcomes",
    ["gap_type", "severity"],
)
REAL_TIME_LEARNING_EVENTS = Counter(
    "hybrid_real_time_learning_events_total",
    "Real-time learning events recorded from delegated outcomes",
    ["profile", "event_type"],
)
META_LEARNING_ADAPTATIONS = Counter(
    "hybrid_meta_learning_adaptations_total",
    "Bounded meta-learning adaptations executed from delegated outcomes",
    ["domain", "method"],
)
