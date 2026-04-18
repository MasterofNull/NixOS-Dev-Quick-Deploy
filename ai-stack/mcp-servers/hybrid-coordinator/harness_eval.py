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
import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from config import Config

logger = logging.getLogger("hybrid-coordinator")

_GENERIC_SUMMARY_LABELS = {
    "result",
    "results",
    "general",
    "unknown",
    "feature",
    "documentation",
    "docs",
    "change",
    "update",
}

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


def _collect_route_evidence_text(result: Dict[str, Any]) -> str:
    """Build a searchable text blob from route_search output for eval scoring."""
    parts: List[str] = []
    response = result.get("response")
    if isinstance(response, str) and response.strip():
        parts.append(response)

    results = result.get("results")
    if isinstance(results, dict):
        for bucket in ("combined_results", "semantic_results", "keyword_results"):
            rows = results.get(bucket)
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                payload = row.get("payload")
                if isinstance(payload, dict):
                    parts.extend(str(v) for v in payload.values() if v is not None)
                content = row.get("content")
                if isinstance(content, str) and content.strip():
                    parts.append(content)

    return "\n".join(parts)


def _classify_eval_failure(metrics: Dict[str, Any]) -> str:
    if not metrics.get("response_non_empty", False):
        return "empty_response"
    if metrics.get("latency_ok") is False:
        return "latency_slo_exceeded"
    if float(metrics.get("relevance_score", 0.0)) < 0.5:
        return "low_relevance"
    return "score_below_threshold"


def _compact_summary_text(value: Any, *, max_len: int = 96) -> str:
    if value is None:
        return ""
    text = " ".join(str(value).split()).strip()
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."


def _is_generic_summary_label(value: str) -> bool:
    normalized = _compact_summary_text(value, max_len=64).lower()
    return not normalized or normalized in _GENERIC_SUMMARY_LABELS


def _result_file_hint(payload: Dict[str, Any]) -> str:
    direct = _compact_summary_text(payload.get("file_path") or payload.get("relative_path"), max_len=72)
    if direct:
        return direct
    files_changed = payload.get("files_changed")
    if isinstance(files_changed, list):
        fallback = ""
        for entry in files_changed:
            compact = _compact_summary_text(entry, max_len=72)
            if not compact:
                continue
            fallback = fallback or compact
            lowered = compact.lower()
            if not any(marker in lowered for marker in (".agent/", ".agents/", "docs/", "readme.md", "primer", "workflow")):
                return compact
        return fallback
    return ""


def _result_summary_label(item: Dict[str, Any]) -> str:
    payload = item.get("payload") if isinstance(item, dict) else {}
    if not isinstance(payload, dict):
        payload = {}

    primary = (
        payload.get("commit_subject")
        or payload.get("title")
        or payload.get("name")
        or payload.get("file_path")
        or payload.get("relative_path")
        or payload.get("skill_name")
        or payload.get("error_type")
        or payload.get("practice_name")
    )
    primary_text = _compact_summary_text(primary)
    file_hint = _result_file_hint(payload)

    if _is_generic_summary_label(primary_text):
        primary_text = _compact_summary_text(
            payload.get("summary")
            or payload.get("description")
            or item.get("content")
            or payload.get("content")
        )

    if not primary_text:
        primary_text = _compact_summary_text(payload.get("category")) or "result"

    if file_hint and primary_text != file_hint and file_hint not in primary_text:
        return f"{primary_text} [{file_hint}]"
    return primary_text


def _summarize_results(items: List[Dict[str, Any]], max_items: int = 3) -> str:
    lines: List[str] = []
    for item in items[:max_items]:
        title = _result_summary_label(item)
        sources = item.get("sources") or ([item.get("source")] if item.get("source") else [])
        source_text = ",".join(sources) if isinstance(sources, list) else str(sources)
        lines.append(f"- {title} (score={item.get('score', 0):.2f}, source={source_text})")
    return "\n".join(lines) if lines else "No results."


def _failure_fix_hint(failure_category: str) -> str:
    category = str(failure_category or "").strip().lower()
    if category == "evaluation_timeout":
        return "Reduce eval breadth or timeout-sensitive work before retrying route_search."
    if category == "latency_slo_exceeded":
        return "Check retrieval fan-out, reasoning-lane routing, and context budget before widening prompts."
    if category == "low_relevance":
        return "Inspect retrieval context quality and prompt grounding before adjusting acceptance thresholds."
    if category == "empty_response":
        return "Check model availability, prompt construction, and backend fallback behavior."
    return "Inspect failed case evidence before changing prompts or thresholds."


def _append_recent_failure(case: Dict[str, Any]) -> None:
    if not isinstance(_HARNESS_STATS, dict):
        return
    recent = _HARNESS_STATS.setdefault("recent_failures", [])
    if not isinstance(recent, list):
        recent = []
        _HARNESS_STATS["recent_failures"] = recent
    recent.append(case)
    del recent[:-10]


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

    start = time.perf_counter()
    timeout_s = (
        max(float(max_latency_ms) / 1000.0, 0.1)
        if isinstance(max_latency_ms, (int, float)) and float(max_latency_ms) > 0
        else max(float(Config.AI_HARNESS_EVAL_TIMEOUT_S), 0.1)
    )
    # Enforce a hard upper bound so misconfigured runtime env cannot produce
    # multi-hour eval waits.
    timeout_hard_cap_s = max(
        1.0,
        float(getattr(Config, "AI_HARNESS_EVAL_TIMEOUT_HARD_CAP_S", 45.0)),
    )
    timeout_s = min(timeout_s, timeout_hard_cap_s)

    route_task = asyncio.create_task(
        _route_search(
            query=query,
            mode=mode,
            prefer_local=True,
            limit=5,
            keyword_limit=5,
            score_threshold=0.7,
            # Keep harness eval deterministic and fast: evaluate retrieval quality
            # without triggering full LLM synthesis on every eval call.
            generate_response=False,
        )
    )
    try:
        result = await asyncio.wait_for(route_task, timeout=timeout_s)
    except asyncio.TimeoutError:
        route_task.cancel()
        try:
            # Cancellation cleanup is bounded so timeout handling itself cannot
            # block indefinitely if inner tasks ignore cancellation.
            await asyncio.wait_for(route_task, timeout=2.0)
        except asyncio.CancelledError:
            pass
        except asyncio.TimeoutError:
            logger.warning("harness_eval_cancel_timeout")

        latency_ms = int((time.perf_counter() - start) * 1000)
        metrics = {
            "relevance_score": 0.0,
            "latency_ms": latency_ms,
            "latency_target_ms": int(max_latency_ms or Config.AI_HARNESS_MAX_LATENCY_MS),
            "latency_ok": False,
            "response_non_empty": False,
            "overall_score": 0.0,
            "timeout_s": round(timeout_s, 3),
            "timeout_triggered": True,
        }
        failure_category = "evaluation_timeout"
        _HARNESS_STATS["failure_taxonomy"][failure_category] = (
            _HARNESS_STATS["failure_taxonomy"].get(failure_category, 0) + 1
        )
        _HARNESS_STATS["total_runs"] += 1
        _HARNESS_STATS["failed"] += 1
        _HARNESS_STATS["last_run_at"] = datetime.now(timezone.utc).isoformat()
        _append_recent_failure(
            {
                "query": query[:200],
                "mode": mode,
                "failure_category": failure_category,
                "metrics": metrics,
                "root_cause_hint": "route_search exceeded the harness eval timeout budget",
                "suggested_fix": _failure_fix_hint(failure_category),
            }
        )
        _record_telemetry(
            "harness_eval",
            {
                "query": query[:200],
                "mode": mode,
                "score": 0.0,
                "passed": False,
                "failure_category": failure_category,
                "latency_ms": latency_ms,
                "timeout_s": timeout_s,
            },
        )
        return {
            "status": "timeout",
            "query": query,
            "mode": mode,
            "passed": False,
            "min_acceptance_score": Config.AI_HARNESS_MIN_ACCEPTANCE_SCORE,
            "metrics": metrics,
            "failure_category": failure_category,
            "route_result": {},
        }

    latency_ms = int((time.perf_counter() - start) * 1000)
    response_text = (result.get("response") or "").strip()
    evidence_text = _collect_route_evidence_text(result)
    keywords = [kw for kw in (expected_keywords or []) if isinstance(kw, str)]
    relevance_score = _keyword_relevance(evidence_text, keywords)

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
        _append_recent_failure(
            {
                "query": query[:200],
                "mode": mode,
                "failure_category": failure_category,
                "metrics": metrics,
                "result_summary": _summarize_results(
                    (
                        (result.get("results") or {}).get("combined_results")
                        or (result.get("results") or {}).get("semantic_results")
                        or (result.get("results") or {}).get("keyword_results")
                        or []
                    ),
                    max_items=2,
                ),
                "root_cause_hint": (
                    "retrieval quality is weak for this eval case"
                    if failure_category == "low_relevance"
                    else "response path violated acceptance checks"
                ),
                "suggested_fix": _failure_fix_hint(failure_category),
            }
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
    reliability_ok = None if total == 0 else pass_rate >= Config.AI_HARNESS_MIN_ACCEPTANCE_SCORE
    discovery_error_rate = (discovery_errors / discovery_total) if discovery_total else 0.0
    safety_ok = discovery_error_rate <= 0.05
    _HARNESS_STATS["scorecards_generated"] = int(_HARNESS_STATS.get("scorecards_generated", 0) or 0) + 1
    recent_failures = _HARNESS_STATS.get("recent_failures", [])
    if not isinstance(recent_failures, list):
        recent_failures = []
    compact_failures = []
    for item in recent_failures[-5:]:
        if not isinstance(item, dict):
            continue
        compact_failures.append(
            {
                "query": str(item.get("query", "") or "")[:200],
                "mode": str(item.get("mode", "auto") or "auto"),
                "failure_category": str(item.get("failure_category", "unknown") or "unknown"),
                "root_cause_hint": str(item.get("root_cause_hint", "") or "").strip(),
                "suggested_fix": str(item.get("suggested_fix", "") or "").strip(),
                "metrics": item.get("metrics", {}) if isinstance(item.get("metrics"), dict) else {},
            }
        )
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
        "failures": {
            "taxonomy": dict(_HARNESS_STATS.get("failure_taxonomy", {}) or {}),
            "recent_failed_cases": compact_failures,
            "analysis_ready": bool(compact_failures),
        },
    }
