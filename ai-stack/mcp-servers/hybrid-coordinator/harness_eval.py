"""
Harness evaluation module for hybrid-coordinator.

Provides deterministic scorecard-based evaluation of retrieval+LLM pipelines.

Extracted from server.py (Phase 6.1 decomposition).

Usage in server.py:
    import harness_eval
    harness_eval.init(
        route_search_fn=route_search,
        record_telemetry_fn=record_telemetry_event,
        harness_stats=HARNESS_STATS,
        hybrid_stats=HYBRID_STATS,
    )
    result = await harness_eval.run_harness_evaluation(query="...")
    scorecard = harness_eval.build_harness_scorecard()
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from config import Config

logger = logging.getLogger("hybrid-coordinator")

# Injected from server.py
_route_search: Optional[Callable] = None
_record_telemetry: Optional[Callable] = None
_HARNESS_STATS: Optional[Dict] = None
_HYBRID_STATS: Optional[Dict] = None


def init(
    *,
    route_search_fn: Callable,
    record_telemetry_fn: Callable,
    harness_stats: Dict,
    hybrid_stats: Dict,
) -> None:
    """Inject runtime dependencies. Call once from server.py initialize_server()."""
    global _route_search, _record_telemetry, _HARNESS_STATS, _HYBRID_STATS
    _route_search = route_search_fn
    _record_telemetry = record_telemetry_fn
    _HARNESS_STATS = harness_stats
    _HYBRID_STATS = hybrid_stats


# ---------------------------------------------------------------------------
# Internal helpers (moved from server.py — only used by harness eval)
# ---------------------------------------------------------------------------

def _keyword_relevance(text: str, expected_keywords: List[str]) -> float:
    if not expected_keywords:
        return 1.0
    if not text:
        return 0.0
    normalized = text.lower()
    hits = sum(1 for kw in expected_keywords if kw and kw.lower() in normalized)
    return hits / max(len(expected_keywords), 1)


def _classify_eval_failure(metrics: Dict[str, Any]) -> str:
    if not metrics.get("response_non_empty", False):
        return "empty_response"
    if metrics.get("latency_ok") is False:
        return "latency_slo_exceeded"
    if float(metrics.get("relevance_score", 0.0)) < 0.5:
        return "low_relevance"
    return "score_below_threshold"


def _summarize_results(items: List[Dict[str, Any]], max_items: int = 3) -> str:
    lines: List[str] = []
    for item in items[:max_items]:
        payload = item.get("payload") or {}
        title = (
            payload.get("title")
            or payload.get("file_path")
            or payload.get("skill_name")
            or payload.get("error_type")
            or payload.get("category")
            or "result"
        )
        sources = item.get("sources") or [item.get("source")] if item.get("source") else []
        source_text = ",".join(sources) if isinstance(sources, list) else str(sources)
        lines.append(f"- {title} (score={item.get('score', 0):.2f}, source={source_text})")
    return "\n".join(lines) if lines else "No results."


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def run_harness_evaluation(
    query: str,
    *,
    expected_keywords: Optional[List[str]] = None,
    mode: str = "auto",
    max_latency_ms: Optional[int] = None,
) -> Dict[str, Any]:
    """Deterministic harness eval scorecard for prompt+retrieval behavior."""
    if not Config.AI_HARNESS_EVAL_ENABLED:
        return {"status": "disabled"}

    start = time.time()
    result = await _route_search(
        query=query,
        mode=mode,
        prefer_local=True,
        limit=5,
        keyword_limit=5,
        score_threshold=0.7,
        generate_response=True,
    )
    latency_ms = int((time.time() - start) * 1000)
    response_text = (result.get("response") or "").strip()
    keywords = [kw for kw in (expected_keywords or []) if isinstance(kw, str)]
    relevance_score = _keyword_relevance(response_text, keywords)

    latency_target = int(max_latency_ms or Config.AI_HARNESS_MAX_LATENCY_MS)
    latency_ok = latency_ms <= latency_target
    response_non_empty = bool(response_text)

    score = (
        (0.5 * relevance_score)
        + (0.3 * (1.0 if latency_ok else 0.0))
        + (0.2 * (1.0 if response_non_empty else 0.0))
    )
    passed = score >= Config.AI_HARNESS_MIN_ACCEPTANCE_SCORE
    metrics = {
        "relevance_score": round(relevance_score, 4),
        "latency_ms": latency_ms,
        "latency_target_ms": latency_target,
        "latency_ok": latency_ok,
        "response_non_empty": response_non_empty,
        "overall_score": round(score, 4),
    }
    failure_category = None
    if not passed:
        failure_category = _classify_eval_failure(metrics)
        _HARNESS_STATS["failure_taxonomy"][failure_category] = (
            _HARNESS_STATS["failure_taxonomy"].get(failure_category, 0) + 1
        )

    _HARNESS_STATS["total_runs"] += 1
    _HARNESS_STATS["passed"] += 1 if passed else 0
    _HARNESS_STATS["failed"] += 0 if passed else 1
    _HARNESS_STATS["last_run_at"] = datetime.now(timezone.utc).isoformat()

    _record_telemetry(
        "harness_eval",
        {
            "query": query[:200],
            "mode": mode,
            "score": metrics["overall_score"],
            "passed": passed,
            "failure_category": failure_category,
            "latency_ms": latency_ms,
        },
    )
    return {
        "status": "ok",
        "query": query,
        "mode": mode,
        "passed": passed,
        "min_acceptance_score": Config.AI_HARNESS_MIN_ACCEPTANCE_SCORE,
        "metrics": metrics,
        "failure_category": failure_category,
        "route_result": result,
    }


def build_harness_scorecard() -> Dict[str, Any]:
    total = int(_HARNESS_STATS.get("total_runs", 0) or 0)
    passed = int(_HARNESS_STATS.get("passed", 0) or 0)
    failed = int(_HARNESS_STATS.get("failed", 0) or 0)
    pass_rate = (passed / total) if total else 0.0
    discovery = _HYBRID_STATS.get("capability_discovery", {})
    discovery_invoked = int(discovery.get("invoked", 0) or 0)
    discovery_skipped = int(discovery.get("skipped", 0) or 0)
    discovery_hits = int(discovery.get("cache_hits", 0) or 0)
    discovery_errors = int(discovery.get("errors", 0) or 0)
    discovery_total = discovery_invoked + discovery_skipped + discovery_hits + discovery_errors
    discovery_cache_rate = (discovery_hits / discovery_total) if discovery_total else 0.0
    reliability_ok = pass_rate >= Config.AI_HARNESS_MIN_ACCEPTANCE_SCORE
    discovery_error_rate = (discovery_errors / discovery_total) if discovery_total else 0.0
    safety_ok = discovery_error_rate <= 0.05
    _HARNESS_STATS["scorecards_generated"] = int(_HARNESS_STATS.get("scorecards_generated", 0) or 0) + 1
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "acceptance": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": round(pass_rate, 4),
            "target": Config.AI_HARNESS_MIN_ACCEPTANCE_SCORE,
            "ok": reliability_ok,
        },
        "discovery": {
            "invoked": discovery_invoked,
            "skipped": discovery_skipped,
            "cache_hits": discovery_hits,
            "errors": discovery_errors,
            "cache_hit_rate": round(discovery_cache_rate, 4),
            "error_rate": round(discovery_error_rate, 4),
            "ok": safety_ok,
        },
        "inference_optimizations": {
            "prompt_cache_policy_enabled": Config.AI_PROMPT_CACHE_POLICY_ENABLED,
            "speculative_decoding_enabled": Config.AI_SPECULATIVE_DECODING_ENABLED,
            "speculative_decoding_mode": Config.AI_SPECULATIVE_DECODING_MODE,
            "context_compression_enabled": Config.AI_CONTEXT_COMPRESSION_ENABLED,
        },
    }
