"""
eval_runner.py — Continuous spec-driven evaluation (Phase 54.6 + 60.5)

Provides:
  - POST /eval/run        — trigger 12-case benchmark + full aq-qa suite
  - GET  /eval/trend      — last 10 eval runs + RAGAS metric averages (Phase 60.5)
  - POST /eval/score-query — record per-query RAGAS metrics (Phase 60.5)

Schema:
    eval_trend(
        id            SERIAL PRIMARY KEY,
        phase_tag     TEXT NOT NULL,
        score         FLOAT NOT NULL,
        checks_passed INTEGER NOT NULL,
        checks_failed INTEGER NOT NULL,
        run_at        TIMESTAMPTZ NOT NULL DEFAULT now()
    )

    eval_results (Phase 60.5 — per-query RAGAS metrics):
        id                SERIAL PRIMARY KEY
        query_text        TEXT
        intent            TEXT
        answer_relevance  FLOAT   -- cosine(query_embed, response_embed) via llama-embed
        context_precision FLOAT   -- fraction of retrieved docs with non-empty content
        faithfulness      FLOAT   -- Qwen-as-judge 0-1 (async 10% sample, nullable)
        run_at            TIMESTAMPTZ NOT NULL DEFAULT now()

Pre-commit hook integration:
    tier0-validation-gate.sh calls GET /eval/trend and compares latest
    score against previous; blocks if delta > 5%.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("hybrid-coordinator")

# ---------------------------------------------------------------------------
# RAGAS config (Phase 60.5 — AM-G1 hybrid strategy)
# ---------------------------------------------------------------------------
_EMBED_URL = os.getenv("LLAMA_EMBED_URL", "http://127.0.0.1:8081")
_LLM_URL = os.getenv("LLAMA_CPP_BASE_URL", "http://127.0.0.1:8080")
# Set RAGAS_FAITHFULNESS_ENABLED=true to enable async Qwen faithfulness scoring.
# Off by default — inline faithfulness adds 3-8s on CPU fallback (AM-C1).
_FAITHFULNESS_ENABLED = os.getenv("RAGAS_FAITHFULNESS_ENABLED", "false").lower() == "true"
_FAITHFULNESS_SAMPLE_RATE = float(os.getenv("RAGAS_FAITHFULNESS_SAMPLE_RATE", "0.10"))

_DDL_EVAL_TREND = """
CREATE TABLE IF NOT EXISTS eval_trend (
    id            SERIAL PRIMARY KEY,
    phase_tag     TEXT NOT NULL,
    score         FLOAT NOT NULL,
    checks_passed INTEGER NOT NULL DEFAULT 0,
    checks_failed INTEGER NOT NULL DEFAULT 0,
    run_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_eval_trend_run_at ON eval_trend (run_at DESC);
"""

# Phase 60.5 — per-query RAGAS metrics table
_DDL_EVAL_RESULTS = """
CREATE TABLE IF NOT EXISTS eval_results (
    id                SERIAL PRIMARY KEY,
    query_text        TEXT,
    intent            TEXT,
    answer_relevance  FLOAT,
    context_precision FLOAT,
    faithfulness      FLOAT,
    run_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_eval_results_run_at ON eval_results (run_at DESC);
"""

_REPO_ROOT = Path(os.getenv(
    "REPO_ROOT",
    str(Path(__file__).parent.parent.parent.parent),
))
_AQ_QA_SCRIPT = _REPO_ROOT / "scripts" / "ai" / "aq-qa"

_pg: Optional[Any] = None
_schema_ready: bool = False


def init(postgres_client: Any) -> None:
    global _pg
    _pg = postgres_client
    logger.info("eval_runner: initialized")


async def ensure_schema() -> None:
    global _schema_ready
    if _schema_ready or _pg is None:
        return
    try:
        await _pg.execute(_DDL_EVAL_TREND)
        await _pg.execute(_DDL_EVAL_RESULTS)
        _schema_ready = True
        logger.info("eval_runner: schema ready (eval_trend + eval_results)")
    except Exception as exc:
        logger.warning("eval_runner: schema setup failed: %s", exc)


# ---------------------------------------------------------------------------
# RAGAS scoring functions (Phase 60.5)
# ---------------------------------------------------------------------------

async def _embed(text: str) -> Optional[List[float]]:
    """Call llama-embed to get a text embedding. Returns None on failure."""
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{_EMBED_URL}/v1/embeddings",
                json={"model": "text-embedding", "input": text[:1024]},
                timeout=aiohttp.ClientTimeout(total=3.0),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["data"][0]["embedding"]
    except Exception as exc:
        logger.debug("eval_runner._embed failed: %s", exc)
    return None


def _cosine_sim(a: List[float], b: List[float]) -> float:
    """Cosine similarity between two embedding vectors."""
    try:
        import numpy as np
        va, vb = np.array(a, dtype=float), np.array(b, dtype=float)
        denom = np.linalg.norm(va) * np.linalg.norm(vb)
        if denom < 1e-9:
            return 0.0
        return float(np.dot(va, vb) / denom)
    except Exception:
        return 0.0


async def score_answer_relevance(query: str, response: str) -> Optional[float]:
    """
    Answer Relevance: cosine similarity between query and response embeddings.
    Uses llama-embed:8081 (fast, <50ms typical). Returns None if embed unavailable.
    """
    if not query or not response:
        return None
    q_emb, r_emb = await asyncio.gather(_embed(query), _embed(response))
    if q_emb is None or r_emb is None:
        return None
    return round(_cosine_sim(q_emb, r_emb), 4)


def score_context_precision(retrieved_docs: List[Any]) -> float:
    """
    Context Precision (simplified): fraction of retrieved docs with non-empty content.
    A proper implementation would check each doc's relevance to the query via embedding;
    this lightweight version measures retrieval completeness (no empty/stub results).
    """
    if not retrieved_docs:
        return 0.0
    non_empty = sum(
        1 for d in retrieved_docs
        if isinstance(d, dict) and d.get("content", "").strip()
    )
    return round(non_empty / len(retrieved_docs), 4)


async def score_faithfulness_async(
    query: str,
    context: str,
    response: str,
) -> Optional[float]:
    """
    Faithfulness (AM-C1): Qwen-as-judge scoring 0–1.
    Only called when RAGAS_FAITHFULNESS_ENABLED=true AND random sample hits.
    Adds 3–8s — NEVER called inline on the response path.
    """
    if not _FAITHFULNESS_ENABLED:
        return None
    if random.random() > _FAITHFULNESS_SAMPLE_RATE:
        return None
    prompt = (
        "You are a faithfulness judge. Given a query, context, and response, "
        "rate how well the response is grounded in the context on a scale of 0 to 1. "
        "Output ONLY a single decimal number (e.g. 0.85). No explanation.\n\n"
        f"Query: {query[:300]}\n\n"
        f"Context: {context[:800]}\n\n"
        f"Response: {response[:500]}\n\n"
        "Faithfulness score (0-1):"
    )
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{_LLM_URL}/v1/chat/completions",
                json={
                    "model": "local",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 8,
                    "temperature": 0.0,
                    "chat_template_kwargs": {"enable_thinking": False},
                },
                timeout=aiohttp.ClientTimeout(total=15.0),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    text = data["choices"][0]["message"]["content"].strip()
                    return round(min(1.0, max(0.0, float(text))), 4)
    except Exception as exc:
        logger.debug("eval_runner.faithfulness_failed: %s", exc)
    return None


async def record_query_metrics(
    *,
    query_text: str,
    intent: str,
    answer_relevance: Optional[float],
    context_precision: Optional[float],
    faithfulness: Optional[float],
) -> None:
    """
    Persist per-query RAGAS metrics to eval_results. Fire-and-forget — never awaited inline.
    """
    if _pg is None:
        return
    await ensure_schema()
    try:
        await _pg.execute(
            """
            INSERT INTO eval_results
                (query_text, intent, answer_relevance, context_precision, faithfulness, run_at)
            VALUES (%s, %s, %s, %s, %s, now())
            """,
            query_text[:500] if query_text else "",
            intent or "",
            answer_relevance,
            context_precision,
            faithfulness,
        )
    except Exception as exc:
        logger.debug("eval_runner.record_query_metrics error: %s", exc)


async def _fetch_ragas_averages(window: int = 100) -> Dict[str, Any]:
    """Return rolling averages of RAGAS metrics from the last N eval_results rows."""
    if _pg is None:
        return {}
    await ensure_schema()
    try:
        rows = await _pg.fetch_all(
            """
            SELECT
                AVG(answer_relevance)  AS answer_relevance_avg,
                AVG(context_precision) AS context_precision_avg,
                AVG(faithfulness)      AS faithfulness_avg,
                COUNT(*)               AS sample_count
            FROM (
                SELECT answer_relevance, context_precision, faithfulness
                FROM eval_results
                ORDER BY run_at DESC
                LIMIT %s
            ) sub
            """,
            window,
        )
        if rows:
            r = rows[0]
            def _fmt(v: Any) -> Optional[float]:
                return round(float(v), 4) if v is not None else None
            return {
                "answer_relevance_avg": _fmt(r["answer_relevance_avg"]),
                "context_precision_avg": _fmt(r["context_precision_avg"]),
                "faithfulness_avg": _fmt(r["faithfulness_avg"]),
                "faithfulness_enabled": _FAITHFULNESS_ENABLED,
                "sample_count": int(r["sample_count"] or 0),
            }
    except Exception as exc:
        logger.debug("eval_runner._fetch_ragas_averages error: %s", exc)
    return {}


async def _run_aq_qa() -> Dict[str, Any]:
    """Run aq-qa 0 as subprocess; parse passed/failed counts."""
    if not _AQ_QA_SCRIPT.exists():
        return {"passed": 0, "failed": 0, "total": 0, "error": "aq-qa not found"}
    try:
        proc = await asyncio.create_subprocess_exec(
            str(_AQ_QA_SCRIPT), "0",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(_REPO_ROOT),
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120.0)
        output = stdout.decode("utf-8", errors="replace")

        # Parse "X passed / Y failed" from aq-qa output
        passed = failed = 0
        for line in output.splitlines():
            if "passed" in line and "failed" in line:
                parts = line.replace("/", " ").split()
                nums = [int(p) for p in parts if p.isdigit()]
                if len(nums) >= 2:
                    passed, failed = nums[0], nums[1]
                    break

        total = passed + failed
        score = round(passed / max(total, 1) * 100, 1)
        return {"passed": passed, "failed": failed, "total": total, "score": score, "output": output[:2000]}
    except asyncio.TimeoutError:
        return {"passed": 0, "failed": 0, "total": 0, "error": "aq-qa timeout"}
    except Exception as exc:
        return {"passed": 0, "failed": 0, "total": 0, "error": str(exc)}


async def _store_result(phase_tag: str, score: float, passed: int, failed: int) -> None:
    if _pg is None:
        return
    await ensure_schema()
    try:
        await _pg.execute(
            """
            INSERT INTO eval_trend (phase_tag, score, checks_passed, checks_failed, run_at)
            VALUES (%s, %s, %s, %s, now())
            """,
            phase_tag, score, passed, failed,
        )
    except Exception as exc:
        logger.warning("eval_runner._store_result error: %s", exc)


async def _fetch_trend(limit: int = 10) -> List[Dict[str, Any]]:
    if _pg is None:
        return []
    await ensure_schema()
    try:
        rows = await _pg.fetch_all(
            """
            SELECT id, phase_tag, score, checks_passed, checks_failed, run_at
            FROM eval_trend ORDER BY run_at DESC LIMIT %s
            """,
            limit,
        )
        return [
            {
                "id": r["id"],
                "phase_tag": r["phase_tag"],
                "score": r["score"],
                "checks_passed": r["checks_passed"],
                "checks_failed": r["checks_failed"],
                "run_at": r["run_at"].isoformat() if r["run_at"] else None,
            }
            for r in rows
        ]
    except Exception as exc:
        logger.warning("eval_runner._fetch_trend error: %s", exc)
        return []


# ---------------------------------------------------------------------------
# HTTP handlers
# ---------------------------------------------------------------------------

async def handle_eval_run(request) -> Any:
    """
    POST /eval/run

    Body (optional): {"phase_tag": "54.1"}
    Triggers aq-qa 0, stores result, returns summary.
    Returns 202 immediately; eval runs in background.
    """
    from aiohttp import web

    try:
        body = await request.json()
    except Exception:
        body = {}

    phase_tag = body.get("phase_tag", "manual")

    async def _run_and_store():
        result = await _run_aq_qa()
        score = result.get("score", 0.0)
        passed = result.get("passed", 0)
        failed = result.get("failed", 0)
        await _store_result(phase_tag, score, passed, failed)
        logger.info(
            "eval_runner.run phase=%s score=%.1f passed=%d failed=%d",
            phase_tag, score, passed, failed,
        )

    asyncio.create_task(_run_and_store())

    return web.json_response(
        {
            "status": "accepted",
            "phase_tag": phase_tag,
            "message": "eval running in background; poll GET /eval/trend for results",
        },
        status=202,
    )


async def handle_eval_trend(request) -> Any:
    """GET /eval/trend — last 10 eval runs + Phase 60.5 RAGAS metric averages."""
    from aiohttp import web
    try:
        limit = min(int(request.rel_url.query.get("limit", 10)), 50)
        runs, ragas = await asyncio.gather(
            _fetch_trend(limit),
            _fetch_ragas_averages(window=100),
        )
        return web.json_response({
            "runs": runs,
            "count": len(runs),
            "ragas_metrics": ragas,  # Phase 60.5 — faithfulness_avg, answer_relevance_avg, context_precision_avg
        })
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


async def handle_eval_score_query(request) -> Any:
    """
    POST /eval/score-query — record per-query RAGAS metrics (Phase 60.5).

    Body: {
        "query": "...",
        "response": "...",
        "intent": "...",
        "retrieved_docs": [...],   // optional list of {content: ...} dicts
        "context": "..."           // optional joined context string for faithfulness
    }

    Computes answer_relevance (embed cosine) and context_precision synchronously;
    faithfulness async/sampled. Returns metric values immediately.
    """
    from aiohttp import web
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "invalid_json"}, status=400)

    query = data.get("query", "")
    response = data.get("response", "")
    intent = data.get("intent", "")
    retrieved_docs = data.get("retrieved_docs") or []
    context = data.get("context") or " ".join(
        d.get("content", "") for d in retrieved_docs if isinstance(d, dict)
    )

    ar = await score_answer_relevance(query, response)
    cp = score_context_precision(retrieved_docs)

    # Faithfulness: fire async, don't block response
    async def _faith_and_record():
        faith = await score_faithfulness_async(query, context, response)
        await record_query_metrics(
            query_text=query,
            intent=intent,
            answer_relevance=ar,
            context_precision=cp,
            faithfulness=faith,
        )

    asyncio.create_task(_faith_and_record())

    return web.json_response({
        "answer_relevance": ar,
        "context_precision": cp,
        "faithfulness": None,  # computed async; check GET /eval/trend for rolling avg
        "faithfulness_enabled": _FAITHFULNESS_ENABLED,
    })
