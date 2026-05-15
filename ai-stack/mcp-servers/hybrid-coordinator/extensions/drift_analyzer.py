"""
drift_analyzer.py - reasoning drift analysis over recent query traces.

Phase 55.3 keeps this deliberately small: derive an operator-facing signal from
the trace rows we already collect, and degrade to a valid null response when the
trace store is unavailable.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from aiohttp import web

logger = logging.getLogger("hybrid-coordinator")

DEFAULT_DRIFT_THRESHOLD = 0.7
_POLICY_PATH = Path(__file__).resolve().parents[4] / "config" / "runtime-budget-policy.json"


def _load_threshold() -> float:
    try:
        with _POLICY_PATH.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
        return float(payload.get("drift_alert_threshold", DEFAULT_DRIFT_THRESHOLD))
    except Exception as exc:
        logger.debug("drift_threshold_load_failed error=%s", exc)
        return DEFAULT_DRIFT_THRESHOLD


class DriftAnalyzer:
    def __init__(self, postgres_client: Optional[Any] = None, *, threshold: Optional[float] = None) -> None:
        self._pg = postgres_client
        self._threshold = float(threshold if threshold is not None else _load_threshold())

    async def compute_drift(self, window: int = 20) -> Dict[str, Any]:
        window = max(2, min(int(window or 20), 200))
        if self._pg is None:
            return {
                "drift_score": None,
                "window_size": 0,
                "alert_triggered": False,
                "threshold": self._threshold,
                "breakdown": {},
                "error": "postgres_unavailable",
            }

        fetch_rows = getattr(self._pg, "fetch_all", None) or getattr(self._pg, "fetch", None)
        if fetch_rows is None:
            raise AttributeError("postgres client supports neither fetch_all nor fetch")
        rows = await fetch_rows(
            """
            SELECT intent, retrieval_hits, retrieval_ms, llm_ms, total_ms
            FROM query_traces
            ORDER BY trace_at DESC
            LIMIT %s
            """,
            window,
        )
        traces = [dict(row) for row in reversed(rows)]
        if len(traces) < 2:
            return {
                "drift_score": 0.0,
                "window_size": len(traces),
                "alert_triggered": False,
                "threshold": self._threshold,
                "breakdown": {
                    "intent_flip_rate": 0.0,
                    "retry_escalation": 0.0,
                    "latency_trend": 0.0,
                },
            }

        intent_flip_rate = _intent_flip_rate(traces)
        retry_escalation = _retry_escalation(traces)
        latency_trend = _latency_trend(traces)
        drift_score = round(
            min(
                1.0,
                (intent_flip_rate * 0.45)
                + (retry_escalation * 0.25)
                + (latency_trend * 0.30),
            ),
            3,
        )
        return {
            "drift_score": drift_score,
            "window_size": len(traces),
            "alert_triggered": drift_score >= self._threshold,
            "threshold": self._threshold,
            "breakdown": {
                "intent_flip_rate": round(intent_flip_rate, 3),
                "retry_escalation": round(retry_escalation, 3),
                "latency_trend": round(latency_trend, 3),
            },
        }


def _intent_flip_rate(traces: List[Dict[str, Any]]) -> float:
    intents = [str(trace.get("intent") or "unknown") for trace in traces]
    flips = sum(1 for prev, cur in zip(intents, intents[1:]) if prev != cur)
    return flips / max(1, len(intents) - 1)


def _retry_escalation(traces: List[Dict[str, Any]]) -> float:
    # TraceCollector does not yet persist retry count. Use rag-skipped inversely
    # as the only stable proxy currently available and keep the score bounded.
    misses = sum(1 for trace in traces if int(trace.get("retrieval_hits") or 0) == 0)
    return min(1.0, misses / len(traces))


def _latency_trend(traces: List[Dict[str, Any]]) -> float:
    first = float(traces[0].get("total_ms") or 0)
    last = float(traces[-1].get("total_ms") or 0)
    if first <= 0 or last <= first:
        return 0.0
    return min(1.0, (last - first) / max(first, 1.0))


_analyzer = DriftAnalyzer()


def init(postgres_client: Optional[Any] = None) -> None:
    global _analyzer
    _analyzer = DriftAnalyzer(postgres_client=postgres_client)


def get_analyzer() -> DriftAnalyzer:
    return _analyzer


async def handle_get_drift(request: web.Request) -> web.Response:
    try:
        window = int(request.query.get("window", "20"))
        return web.json_response(await _analyzer.compute_drift(window=window))
    except Exception as exc:
        logger.warning("drift_analysis_failed error=%s", exc)
        return web.json_response({"drift_score": None, "error": str(exc)}, status=500)


def register_routes(http_app: web.Application) -> None:
    http_app.router.add_get("/api/traces/drift", handle_get_drift)
