"""
eval_runner.py — Continuous spec-driven evaluation (Phase 54.6)

Provides:
  - POST /eval/run   — trigger 12-case benchmark + full aq-qa suite
  - GET  /eval/trend — last 10 eval runs from PostgreSQL

Schema:
    eval_trend(
        id            SERIAL PRIMARY KEY,
        phase_tag     TEXT NOT NULL,
        score         FLOAT NOT NULL,
        checks_passed INTEGER NOT NULL,
        checks_failed INTEGER NOT NULL,
        run_at        TIMESTAMPTZ NOT NULL DEFAULT now()
    )

Pre-commit hook integration:
    tier0-validation-gate.sh calls GET /eval/trend and compares latest
    score against previous; blocks if delta > 5%.
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("hybrid-coordinator")

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
        _schema_ready = True
        logger.info("eval_runner: schema ready")
    except Exception as exc:
        logger.warning("eval_runner: schema setup failed: %s", exc)


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
        rows = await _pg.fetch(
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
    """GET /eval/trend — last 10 eval runs."""
    from aiohttp import web
    try:
        limit = min(int(request.rel_url.query.get("limit", 10)), 50)
        runs = await _fetch_trend(limit)
        return web.json_response({"runs": runs, "count": len(runs)})
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)
