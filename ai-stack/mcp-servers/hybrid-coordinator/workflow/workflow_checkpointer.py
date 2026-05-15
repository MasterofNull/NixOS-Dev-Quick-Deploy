"""
workflow_checkpointer.py — Durable DAG execution checkpoint/resume (Phase 54.4)

Provides checkpoint-save / checkpoint-resume capability for WorkflowExecutor.
After each phase/node completes, state is persisted to PostgreSQL so a workflow
interrupted mid-run can resume from its last successful step.

Schema (created by _ensure_schema()):
    workflow_checkpoints(
        id              SERIAL PRIMARY KEY,
        workflow_id     TEXT NOT NULL,
        completed_nodes JSONB NOT NULL,
        node_outputs    JSONB NOT NULL,
        pending_nodes   JSONB NOT NULL,
        updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    workflow_execution_patterns(
        id           SERIAL PRIMARY KEY,
        workflow_id  TEXT NOT NULL,
        pattern_type TEXT NOT NULL,     -- sequential|parallel|conditional
        latency_ms   INTEGER NOT NULL,
        success      BOOLEAN NOT NULL,
        created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
    )

Usage inside WorkflowExecutor:
    from workflow.workflow_checkpointer import WorkflowCheckpointer

    cp = WorkflowCheckpointer(postgres_client)
    await cp.ensure_schema()
    await cp.save(workflow_id, completed_nodes, node_outputs, pending_nodes)
    state = await cp.load(workflow_id)
    if state:
        # resume from state["pending_nodes"]
    await cp.delete(workflow_id)  # on successful completion
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("workflow-executor")

# Dead-letter queue key (Redis) — nodes that exceed max retries land here
WORKFLOW_DLQ_KEY = "workflow_dlq"

_DDL_CHECKPOINTS = """
CREATE TABLE IF NOT EXISTS workflow_checkpoints (
    id              SERIAL PRIMARY KEY,
    workflow_id     TEXT NOT NULL UNIQUE,
    completed_nodes JSONB NOT NULL DEFAULT '[]',
    node_outputs    JSONB NOT NULL DEFAULT '{}',
    pending_nodes   JSONB NOT NULL DEFAULT '[]',
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_workflow_checkpoints_workflow_id
    ON workflow_checkpoints (workflow_id);
"""

_DDL_PATTERNS = """
CREATE TABLE IF NOT EXISTS workflow_execution_patterns (
    id           SERIAL PRIMARY KEY,
    workflow_id  TEXT NOT NULL,
    pattern_type TEXT NOT NULL,
    latency_ms   INTEGER NOT NULL,
    success      BOOLEAN NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

_DDL_CLEANUP = """
DELETE FROM workflow_checkpoints
WHERE updated_at < now() - INTERVAL '7 days';
"""


class WorkflowCheckpointer:
    """
    Persists and restores DAG execution state to/from PostgreSQL.

    One WorkflowCheckpointer instance is shared across all workflow runs.
    """

    def __init__(self, postgres_client: Any) -> None:
        self._pg = postgres_client
        self._schema_ready = False

    # ------------------------------------------------------------------
    # Schema bootstrap
    # ------------------------------------------------------------------

    async def ensure_schema(self) -> None:
        """Idempotent: create tables if they don't exist."""
        if self._schema_ready:
            return
        try:
            await self._pg.execute(_DDL_CHECKPOINTS)
            await self._pg.execute(_DDL_PATTERNS)
            self._schema_ready = True
            logger.info("workflow_checkpointer: schema ready")
        except Exception as exc:
            logger.warning("workflow_checkpointer: schema setup failed: %s", exc)

    # ------------------------------------------------------------------
    # Checkpoint operations
    # ------------------------------------------------------------------

    async def save(
        self,
        workflow_id: str,
        completed_nodes: List[str],
        node_outputs: Dict[str, Any],
        pending_nodes: List[str],
    ) -> None:
        """Upsert checkpoint for workflow_id."""
        if not self._schema_ready:
            await self.ensure_schema()
        try:
            await self._pg.execute(
                """
                INSERT INTO workflow_checkpoints
                    (workflow_id, completed_nodes, node_outputs, pending_nodes, updated_at)
                VALUES (%s, %s, %s, %s, now())
                ON CONFLICT (workflow_id) DO UPDATE SET
                    completed_nodes = EXCLUDED.completed_nodes,
                    node_outputs    = EXCLUDED.node_outputs,
                    pending_nodes   = EXCLUDED.pending_nodes,
                    updated_at      = now()
                """,
                workflow_id,
                json.dumps(completed_nodes),
                json.dumps(node_outputs),
                json.dumps(pending_nodes),
            )
            logger.debug(
                "workflow_checkpointer.save wf=%s completed=%d pending=%d",
                workflow_id, len(completed_nodes), len(pending_nodes),
            )
        except Exception as exc:
            logger.warning("workflow_checkpointer.save failed wf=%s exc=%s", workflow_id, exc)

    async def load(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Load checkpoint for workflow_id; returns None if not found."""
        if not self._schema_ready:
            await self.ensure_schema()
        try:
            rows = await self._pg.fetch(
                """
                SELECT completed_nodes, node_outputs, pending_nodes, updated_at
                FROM workflow_checkpoints WHERE workflow_id = %s
                """,
                workflow_id,
            )
            if not rows:
                return None
            row = rows[0]
            return {
                "workflow_id": workflow_id,
                "completed_nodes": row["completed_nodes"] or [],
                "node_outputs": row["node_outputs"] or {},
                "pending_nodes": row["pending_nodes"] or [],
                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
            }
        except Exception as exc:
            logger.warning("workflow_checkpointer.load failed wf=%s exc=%s", workflow_id, exc)
            return None

    async def delete(self, workflow_id: str) -> None:
        """Remove checkpoint after successful completion."""
        try:
            await self._pg.execute(
                "DELETE FROM workflow_checkpoints WHERE workflow_id = %s",
                workflow_id,
            )
            logger.debug("workflow_checkpointer.delete wf=%s", workflow_id)
        except Exception as exc:
            logger.warning("workflow_checkpointer.delete failed wf=%s exc=%s", workflow_id, exc)

    async def purge_stale(self) -> None:
        """Delete checkpoints older than 7 days (call periodically)."""
        try:
            await self._pg.execute(_DDL_CLEANUP)
        except Exception as exc:
            logger.debug("workflow_checkpointer.purge_stale error: %s", exc)

    # ------------------------------------------------------------------
    # Execution pattern tracking (evolving orchestration)
    # ------------------------------------------------------------------

    async def record_pattern(
        self,
        workflow_id: str,
        pattern_type: str,
        latency_ms: int,
        success: bool,
    ) -> None:
        """Log execution pattern for evolving orchestration analysis."""
        if not self._schema_ready:
            await self.ensure_schema()
        try:
            await self._pg.execute(
                """
                INSERT INTO workflow_execution_patterns
                    (workflow_id, pattern_type, latency_ms, success, created_at)
                VALUES (%s, %s, %s, %s, now())
                """,
                workflow_id, pattern_type, latency_ms, success,
            )
        except Exception as exc:
            logger.debug("workflow_checkpointer.record_pattern error: %s", exc)

    async def get_pattern_insights(self, pattern_type: str = "sequential") -> Dict[str, Any]:
        """Return avg latency and success rate for a pattern type (last 100 runs)."""
        try:
            rows = await self._pg.fetch(
                """
                SELECT
                    COUNT(*)                          AS total,
                    AVG(latency_ms)                   AS avg_latency_ms,
                    SUM(CASE WHEN success THEN 1 ELSE 0 END) AS successes
                FROM workflow_execution_patterns
                WHERE pattern_type = %s
                ORDER BY created_at DESC
                LIMIT 100
                """,
                pattern_type,
            )
            if rows:
                r = rows[0]
                total = int(r["total"] or 0)
                return {
                    "pattern_type": pattern_type,
                    "total_runs": total,
                    "avg_latency_ms": round(float(r["avg_latency_ms"] or 0)),
                    "success_rate": round(int(r["successes"] or 0) / max(total, 1), 3),
                }
        except Exception as exc:
            logger.debug("workflow_checkpointer.get_pattern_insights error: %s", exc)
        return {"pattern_type": pattern_type, "total_runs": 0}
