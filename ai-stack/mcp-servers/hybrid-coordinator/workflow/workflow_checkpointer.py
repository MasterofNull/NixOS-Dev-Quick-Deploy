"""
workflow_checkpointer.py — Durable DAG execution checkpoint/resume (Phase 54.4)
                           ReAct DAG backtracking (Phase 68.1)

Provides checkpoint-save / checkpoint-resume capability for WorkflowExecutor.
After each phase/node completes, state is persisted to PostgreSQL so a workflow
interrupted mid-run can resume from its last successful step.

Phase 68.1 adds ReAct DAG backtracking:
  - classify_error() distinguishes retryable vs fatal failures
  - push_dlq() / pop_dlq() enqueue retryable failures to a Redis DLQ
  - backtrack_to() prunes descendant nodes and re-plans from a parent node
  - max_backtrack_depth ceiling (default 3) prevents infinite re-planning loops
  - Backtrack events persisted to workflow_backtrack_log for audit / replay

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
    workflow_backtrack_log(
        id              SERIAL PRIMARY KEY,
        workflow_id     TEXT NOT NULL,
        parent_node_id  TEXT NOT NULL,
        pruned_nodes    JSONB NOT NULL DEFAULT '[]',
        backtrack_depth INTEGER NOT NULL DEFAULT 1,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
    )

Usage inside WorkflowExecutor:
    from workflow.workflow_checkpointer import WorkflowCheckpointer

    cp = WorkflowCheckpointer(postgres_client, redis_client=redis)
    await cp.ensure_schema()
    await cp.save(workflow_id, completed_nodes, node_outputs, pending_nodes)
    state = await cp.load(workflow_id)
    if state:
        # resume from state["pending_nodes"]
    await cp.delete(workflow_id)  # on successful completion

    # Phase 68.1 — on fatal step failure:
    error_class = WorkflowCheckpointer.classify_error(str(exc))
    if error_class == "retryable":
        await cp.push_dlq(workflow_id, node_id, str(exc), retry_count)
    else:
        result = await cp.backtrack_to(
            workflow_id, parent_node_id,
            completed_nodes, node_outputs, pending_nodes, node_graph,
        )
        # result["new_pending"] contains the re-planned pending list
"""

from __future__ import annotations

import json
import logging
from collections import deque
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("workflow-executor")

# Dead-letter queue key (Redis) — nodes that exceed max retries land here
WORKFLOW_DLQ_KEY = "workflow_dlq"

# Default ceiling for consecutive backtracks on a single workflow
DEFAULT_MAX_BACKTRACK_DEPTH = 3

# Error substrings that classify a failure as retryable (transient)
_RETRYABLE_PATTERNS = (
    "timeout",
    "timed out",
    "rate_limit",
    "rate limit",
    "429",
    "503",
    "502",
    "connection",
    "temporarily unavailable",
    "too many requests",
    "backoff",
    "retry",
)

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

# Phase 68.1 — backtrack audit log
_DDL_BACKTRACK_LOG = """
CREATE TABLE IF NOT EXISTS workflow_backtrack_log (
    id              SERIAL PRIMARY KEY,
    workflow_id     TEXT NOT NULL,
    parent_node_id  TEXT NOT NULL,
    pruned_nodes    JSONB NOT NULL DEFAULT '[]',
    backtrack_depth INTEGER NOT NULL DEFAULT 1,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_workflow_backtrack_log_workflow_id
    ON workflow_backtrack_log (workflow_id);
"""

_DDL_CLEANUP = """
DELETE FROM workflow_checkpoints
WHERE updated_at < now() - INTERVAL '7 days';
"""


class BacktrackDepthExceeded(RuntimeError):
    """Raised when backtrack_to() is called beyond max_backtrack_depth."""


class WorkflowCheckpointer:
    """
    Persists and restores DAG execution state to/from PostgreSQL.

    Phase 68.1 adds ReAct DAG backtracking via backtrack_to() and DLQ
    support for retryable failures via push_dlq() / pop_dlq().

    One WorkflowCheckpointer instance is shared across all workflow runs.
    """

    def __init__(
        self,
        postgres_client: Any,
        redis_client: Optional[Any] = None,
        max_backtrack_depth: int = DEFAULT_MAX_BACKTRACK_DEPTH,
    ) -> None:
        self._pg = postgres_client
        self._redis = redis_client
        self.max_backtrack_depth = max_backtrack_depth
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
            await self._pg.execute(_DDL_BACKTRACK_LOG)
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
            rows = await self._pg.fetch_all(
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
    # Phase 68.1 — ReAct DAG backtracking
    # ------------------------------------------------------------------

    @staticmethod
    def classify_error(error: str) -> str:
        """
        Classify an error string as 'retryable' or 'fatal'.

        Retryable: transient infrastructure failures (timeout, rate limit,
        connection drop, HTTP 429/502/503).  All other errors are fatal —
        the step must be replanned via backtrack_to().
        """
        lower = error.lower()
        for pattern in _RETRYABLE_PATTERNS:
            if pattern in lower:
                return "retryable"
        return "fatal"

    @staticmethod
    def _prune_descendant_nodes(
        parent_node_id: str,
        node_graph: Dict[str, List[str]],
    ) -> Set[str]:
        """
        BFS from parent_node_id through node_graph (adjacency list) to collect
        all descendant node IDs.  The parent node itself is NOT included in the
        result — only its downstream dependents are pruned.

        Args:
            parent_node_id: Node to backtrack to (will be re-executed).
            node_graph: Dict mapping node_id → list of direct child node IDs.

        Returns:
            Set of descendant node IDs to be pruned from the plan.
        """
        pruned: Set[str] = set()
        queue: deque[str] = deque(node_graph.get(parent_node_id, []))
        while queue:
            node = queue.popleft()
            if node in pruned:
                continue
            pruned.add(node)
            queue.extend(node_graph.get(node, []))
        return pruned

    async def get_backtrack_count(self, workflow_id: str) -> int:
        """Return the number of backtracks already applied to workflow_id."""
        if not self._schema_ready:
            await self.ensure_schema()
        try:
            rows = await self._pg.fetch_all(
                "SELECT COUNT(*) AS cnt FROM workflow_backtrack_log WHERE workflow_id = %s",
                workflow_id,
            )
            return int(rows[0]["cnt"]) if rows else 0
        except Exception as exc:
            logger.debug("workflow_checkpointer.get_backtrack_count error: %s", exc)
            return 0

    async def backtrack_to(
        self,
        workflow_id: str,
        parent_node_id: str,
        completed_nodes: List[str],
        node_outputs: Dict[str, Any],
        pending_nodes: List[str],
        node_graph: Dict[str, List[str]],
    ) -> Dict[str, Any]:
        """
        Prune descendant nodes of parent_node_id and re-checkpoint the workflow
        so execution resumes from parent_node_id.

        Steps:
          1. Check backtrack depth ceiling — raise BacktrackDepthExceeded if exceeded.
          2. BFS to identify all descendants of parent_node_id.
          3. Strip pruned nodes from completed_nodes and pending_nodes.
          4. Re-insert parent_node_id at the head of pending_nodes.
          5. Upsert the checkpoint with the trimmed state.
          6. Append a row to workflow_backtrack_log for audit.

        Args:
            workflow_id:     Workflow identifier.
            parent_node_id:  Node to rewind to (its children will be re-planned).
            completed_nodes: Current completed node list.
            node_outputs:    Current accumulated node outputs.
            pending_nodes:   Current pending node list.
            node_graph:      Adjacency list of the full DAG (node → [children]).

        Returns:
            {
                "pruned_nodes":     [list of pruned node IDs],
                "new_pending":      [updated pending list],
                "backtrack_depth":  N,  # depth after this backtrack
            }

        Raises:
            BacktrackDepthExceeded: if max_backtrack_depth is already reached.
        """
        if not self._schema_ready:
            await self.ensure_schema()

        depth = await self.get_backtrack_count(workflow_id)
        if depth >= self.max_backtrack_depth:
            raise BacktrackDepthExceeded(
                f"workflow {workflow_id!r} has already backtracked {depth} time(s) "
                f"(ceiling={self.max_backtrack_depth})"
            )

        pruned = self._prune_descendant_nodes(parent_node_id, node_graph)
        pruned_list = sorted(pruned)

        new_completed = [n for n in completed_nodes if n not in pruned and n != parent_node_id]
        new_outputs = {k: v for k, v in node_outputs.items() if k not in pruned and k != parent_node_id}
        new_pending = [parent_node_id] + [n for n in pending_nodes if n not in pruned]

        await self.save(workflow_id, new_completed, new_outputs, new_pending)

        new_depth = depth + 1
        try:
            await self._pg.execute(
                """
                INSERT INTO workflow_backtrack_log
                    (workflow_id, parent_node_id, pruned_nodes, backtrack_depth, created_at)
                VALUES (%s, %s, %s, %s, now())
                """,
                workflow_id,
                parent_node_id,
                json.dumps(pruned_list),
                new_depth,
            )
        except Exception as exc:
            logger.warning("workflow_checkpointer.backtrack_to log failed wf=%s: %s", workflow_id, exc)

        logger.info(
            "workflow_checkpointer.backtrack_to wf=%s parent=%s pruned=%d depth=%d/%d",
            workflow_id, parent_node_id, len(pruned_list), new_depth, self.max_backtrack_depth,
        )
        return {
            "pruned_nodes": pruned_list,
            "new_pending": new_pending,
            "backtrack_depth": new_depth,
        }

    # ------------------------------------------------------------------
    # Phase 68.1 — Redis Dead-Letter Queue (retryable failures)
    # ------------------------------------------------------------------

    async def push_dlq(
        self,
        workflow_id: str,
        node_id: str,
        error: str,
        retry_count: int = 0,
    ) -> bool:
        """
        Push a retryable failure to the Redis DLQ for later reprocessing.

        Entry format (JSON): {workflow_id, node_id, error, retry_count, ts}

        Returns True on success, False if Redis is unavailable.
        """
        if self._redis is None:
            logger.debug("workflow_checkpointer.push_dlq: no Redis client, dropping entry")
            return False
        import time
        entry = json.dumps({
            "workflow_id": workflow_id,
            "node_id": node_id,
            "error": error[:500],
            "retry_count": retry_count,
            "ts": time.time(),
        })
        try:
            await self._redis.rpush(WORKFLOW_DLQ_KEY, entry)
            logger.debug(
                "workflow_checkpointer.push_dlq wf=%s node=%s retry=%d",
                workflow_id, node_id, retry_count,
            )
            return True
        except Exception as exc:
            logger.warning("workflow_checkpointer.push_dlq failed: %s", exc)
            return False

    async def pop_dlq(self) -> Optional[Dict[str, Any]]:
        """
        Pop the oldest entry from the Redis DLQ (FIFO).

        Returns the parsed entry dict, or None if the queue is empty or
        Redis is unavailable.
        """
        if self._redis is None:
            return None
        try:
            raw = await self._redis.lpop(WORKFLOW_DLQ_KEY)
            if raw is None:
                return None
            data = raw if isinstance(raw, str) else raw.decode("utf-8")
            return json.loads(data)
        except Exception as exc:
            logger.warning("workflow_checkpointer.pop_dlq failed: %s", exc)
            return None

    async def dlq_length(self) -> int:
        """Return the current DLQ depth (0 if Redis unavailable)."""
        if self._redis is None:
            return 0
        try:
            return int(await self._redis.llen(WORKFLOW_DLQ_KEY))
        except Exception:
            return 0

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
            rows = await self._pg.fetch_all(
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
