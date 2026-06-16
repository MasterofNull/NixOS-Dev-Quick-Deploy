"""
WorkflowNodeDispatcher — dispatches workflow node batches to agent sub-systems.

Phase 185A Phase A: serial dispatch (max_parallel=1, WORKFLOW_MAX_PARALLEL_TASKS env).
Phase 185A Phase C: parallel dispatch — raise WORKFLOW_MAX_PARALLEL_TASKS > 1.
"""

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# WorkflowPhaseExecutor lives in the coordinator's workflow/ package.
# Path: ai-stack/mcp-servers/hybrid-coordinator/workflow/workflow_executor.py
_COORDINATOR_WORKFLOW_PATH = str(
    Path(__file__).resolve().parent.parent
    / "mcp-servers" / "hybrid-coordinator" / "workflow"
)
if _COORDINATOR_WORKFLOW_PATH not in sys.path:
    sys.path.insert(0, _COORDINATOR_WORKFLOW_PATH)

try:
    from workflow_executor import WorkflowPhaseExecutor as _WPE
except ImportError:
    _WPE = None  # type: ignore[assignment,misc]
    logger.warning("[node_dispatcher] WorkflowPhaseExecutor unavailable — using stub dispatch")

# Telemetry path (user spool, world-writable by service via group)
_REPO_ROOT = Path(os.getenv("REPO_ROOT", Path(__file__).resolve().parents[2]))
_HYBRID_EVENTS = _REPO_ROOT / ".agents" / "telemetry" / "hybrid-events.jsonl"

# Coordinator URL (never hardcoded)
_COORDINATOR_URL = os.getenv(
    "COORDINATOR_URL",
    os.getenv("HYBRID_COORDINATOR_URL", "http://127.0.0.1:8003"),
)

# Phase A: serial (1). Raise env var to unlock parallel dispatch for Phase C.
_MAX_PARALLEL_DEFAULT = int(os.getenv("WORKFLOW_MAX_PARALLEL_TASKS", "1"))


def _write_event(event_type: str, execution_id: str, **kwargs: Any) -> None:
    """Append a workflow telemetry event to the user spool (best-effort)."""
    try:
        event = {
            "ts": time.time(),
            "event_type": event_type,
            "execution_id": execution_id,
            **kwargs,
        }
        _HYBRID_EVENTS.parent.mkdir(parents=True, exist_ok=True)
        with open(_HYBRID_EVENTS, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(event) + "\n")
    except Exception:
        pass


class WorkflowNodeDispatcher:
    """Dispatches workflow node batches to local harness sub-agents."""

    def __init__(
        self,
        execution_id: str,
        coordinator_url: str = _COORDINATOR_URL,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.execution_id = execution_id
        self.coordinator_url = coordinator_url
        self._config = config or {}
        self._max_parallel = int(
            self._config.get("max_parallel_tasks", _MAX_PARALLEL_DEFAULT)
        )
        self._sem = asyncio.Semaphore(max(1, self._max_parallel))
        self._executor = (
            _WPE(coordinator_url=coordinator_url) if _WPE is not None else None
        )
        self._serial_durations: List[float] = []
        self._batch_durations: List[float] = []

    async def _dispatch_node(
        self,
        node: Any,
        node_outputs: Dict[str, Any],
        batch_id: str,
    ) -> Dict[str, Any]:
        node_id = getattr(node, "id", str(node))
        t0 = time.time()
        _write_event(
            "workflow_step_dispatched",
            self.execution_id,
            node_id=node_id,
            batch_id=batch_id,
            agent=getattr(node, "agent", "local"),
        )
        try:
            if self._executor is not None:
                phase = {
                    "id": node_id,
                    "title": getattr(node, "agent", node_id),
                    "acceptance": [],
                }
                ctx: Dict[str, Any] = {
                    "safety_mode": "execute-mutating",
                    "inputs": node_outputs,
                    "budget": {"token_limit": 512},
                }
                result = await self._executor.execute_phase(
                    phase,
                    objective=str(getattr(node, "prompt", node_id)),
                    context=ctx,
                )
                output = result.get("output", "")
            else:
                output = f"[stub] node {node_id} — WorkflowPhaseExecutor unavailable"

            duration = time.time() - t0
            self._serial_durations.append(duration)
            _write_event(
                "workflow_step_complete",
                self.execution_id,
                node_id=node_id,
                batch_id=batch_id,
                status="completed",
                duration_s=round(duration, 3),
            )
            return {"status": "completed", "output": output, "duration_s": duration}

        except Exception as exc:
            duration = time.time() - t0
            _write_event(
                "workflow_step_complete",
                self.execution_id,
                node_id=node_id,
                batch_id=batch_id,
                status="failed",
                error=str(exc),
                duration_s=round(duration, 3),
            )
            logger.warning("[workflow] node %s failed: %s", node_id, exc)
            return {"status": "failed", "error": str(exc), "output": "", "duration_s": duration}

    async def dispatch_batch(
        self,
        batch: List[Any],
        node_outputs: Dict[str, Any],
        batch_id: str,
    ) -> Dict[str, Any]:
        """Dispatch one batch of nodes. Serial (Phase A) or parallel (Phase C)."""
        batch_start = time.time()
        results: Dict[str, Any] = {}

        if self._max_parallel <= 1:
            for node in batch:
                node_id = getattr(node, "id", str(node))
                async with self._sem:
                    results[node_id] = await self._dispatch_node(node, node_outputs, batch_id)
        else:
            async def _guarded(node: Any) -> tuple:
                node_id = getattr(node, "id", str(node))
                async with self._sem:
                    return node_id, await self._dispatch_node(node, node_outputs, batch_id)

            gathered = await asyncio.gather(
                *[_guarded(n) for n in batch], return_exceptions=True
            )
            for item in gathered:
                if isinstance(item, Exception):
                    logger.error("[workflow] batch gather exception: %s", item)
                else:
                    nid, res = item
                    results[nid] = res

        self._batch_durations.append(time.time() - batch_start)
        return results

    def speedup_ratio(self) -> float:
        """Parallel speedup ratio = sum(serial durations) / sum(batch durations)."""
        total_batch = sum(self._batch_durations)
        if total_batch == 0:
            return 1.0
        return round(sum(self._serial_durations) / total_batch, 2)
