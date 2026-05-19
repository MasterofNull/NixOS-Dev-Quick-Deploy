"""mlfq_scheduler.py - MLFQ scheduler for MAEAH edge AI harness.

Three queues:
  L0 = interactive/reactive (user-facing, low latency)
  L1 = background/proactive (agent-initiated, medium priority)
  L2 = batch (background, preemptible)

Admission control:
  - Reject when token budget exhausted (configurable per level)
  - AIMD backpressure on cascade failure (HiveMind pattern)
  - Thermal-aware: if thermal_tier in (critical, shutdown), suspend L2 admission
    and reduce L1 concurrency to 1 (AM-G3 requirement)

Zombie reaping:
  - Tasks stuck >120s (configurable) are evicted and marked failed
  - Reaper loop runs every 30s
"""
from __future__ import annotations

import asyncio
import inspect
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Dict, Literal, Optional

try:
    from circuit_breaker import CircuitBreaker
except Exception:  # pragma: no cover - import safety for standalone parsing
    CircuitBreaker = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

TaskClass = Literal["interactive", "background", "batch"]
TaskStatus = Literal["queued", "running", "done", "failed", "evicted"]

TASK_CLASS_TO_LEVEL: Dict[str, int] = {
    "interactive": 0,
    "background": 1,
    "batch": 2,
}


@dataclass
class WorkloadDescriptor:
    task_id: str
    task_class: TaskClass
    priority: int  # 0-9, lower = higher priority within class
    token_budget: int  # max tokens this task may consume
    agent_id: str | None
    x_maeah: dict


@dataclass
class TaskHandle:
    task_id: str
    queue_level: int
    queued_at: float
    status: TaskStatus
    result: Any | None
    error: str | None


@dataclass
class _TaskRecord:
    desc: WorkloadDescriptor
    handle: TaskHandle
    coro: Awaitable[Any]
    event: asyncio.Event = field(default_factory=asyncio.Event)
    started_at: float | None = None
    task: asyncio.Task[Any] | None = None


class MLFQAdmissionError(RuntimeError):
    """Raised when the scheduler rejects a submitted workload."""


class MLFQScheduler:
    """Async in-process MLFQ scheduler with thermal and AIMD gates."""

    def __init__(
        self,
        *,
        token_budgets: Optional[Dict[int, int]] = None,
        concurrency_limits: Optional[Dict[int, int]] = None,
        zombie_timeout_s: Optional[float] = None,
        reaper_interval_s: Optional[float] = None,
        recovery_interval_s: Optional[float] = None,
    ) -> None:
        self._token_budgets = token_budgets or {
            0: int(os.getenv("MLFQ_L0_TOKEN_BUDGET", "1000000")),
            1: int(os.getenv("MLFQ_L1_TOKEN_BUDGET", "500000")),
            2: int(os.getenv("MLFQ_L2_TOKEN_BUDGET", "250000")),
        }
        self._system_token_budget = int(
            os.getenv("MLFQ_SYSTEM_TOKEN_BUDGET", str(sum(self._token_budgets.values())))
        )
        self._base_concurrency = concurrency_limits or {
            0: int(os.getenv("MLFQ_L0_CONCURRENCY", "8")),
            1: int(os.getenv("MLFQ_L1_CONCURRENCY", "4")),
            2: int(os.getenv("MLFQ_L2_CONCURRENCY", "2")),
        }
        self._concurrency = dict(self._base_concurrency)
        self._reserved_tokens: Dict[int, int] = {0: 0, 1: 0, 2: 0}
        self._queues: Dict[int, asyncio.PriorityQueue[tuple[int, int, str]]] = {
            0: asyncio.PriorityQueue(),
            1: asyncio.PriorityQueue(),
            2: asyncio.PriorityQueue(),
        }
        self._records: Dict[str, _TaskRecord] = {}
        self._running: Dict[str, _TaskRecord] = {}
        self._seq = 0
        self._lock = asyncio.Lock()
        self._started = False
        self._accepting = True
        self._worker_tasks: list[asyncio.Task[Any]] = []
        self._reaper_task: asyncio.Task[Any] | None = None
        self._zombie_timeout_s = zombie_timeout_s or float(os.getenv("MLFQ_ZOMBIE_TIMEOUT_S", "120"))
        self._reaper_interval_s = reaper_interval_s or float(os.getenv("MLFQ_REAPER_INTERVAL_S", "30"))
        self._recovery_interval_s = recovery_interval_s or float(os.getenv("MLFQ_AIMD_RECOVERY_INTERVAL_S", "60"))
        self._thermal_tier = "normal"
        self._zombie_count = 0
        self._failure_streak: Dict[int, int] = {0: 0, 1: 0, 2: 0}
        self._last_failure_at: Dict[int, float] = {0: 0.0, 1: 0.0, 2: 0.0}
        self._last_recovery_at: Dict[int, float] = {0: time.time(), 1: time.time(), 2: time.time()}
        self._backpressure_events: list[dict[str, Any]] = []
        self._circuit_breakers: Dict[int, Any] = {}
        if CircuitBreaker is not None:
            self._circuit_breakers = {
                level: CircuitBreaker(failure_threshold=3, reset_timeout=self._recovery_interval_s)
                for level in (0, 1, 2)
            }

    async def start(self) -> None:
        async with self._lock:
            if self._started:
                return
            self._accepting = True
            self._started = True
            self._worker_tasks = [
                asyncio.create_task(self._worker_loop(level), name=f"mlfq-worker-l{level}")
                for level in (0, 1, 2)
            ]
            self._reaper_task = asyncio.create_task(
                self._zombie_reaper_loop(), name="mlfq-zombie-reaper"
            )
        logger.info("mlfq_scheduler: started")

    async def stop(self) -> None:
        async with self._lock:
            self._accepting = False
        while True:
            async with self._lock:
                queued = sum(queue.qsize() for queue in self._queues.values())
                running = len(self._running)
            if queued == 0 and running == 0:
                break
            await asyncio.sleep(0.1)
        tasks = list(self._worker_tasks)
        if self._reaper_task is not None:
            tasks.append(self._reaper_task)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        async with self._lock:
            self._worker_tasks = []
            self._reaper_task = None
            self._started = False
        logger.info("mlfq_scheduler: stopped")

    async def submit(self, desc: WorkloadDescriptor, coro: Awaitable[Any]) -> TaskHandle:
        level = TASK_CLASS_TO_LEVEL.get(desc.task_class)
        if level is None:
            self._close_awaitable(coro)
            raise MLFQAdmissionError(f"unsupported task_class: {desc.task_class}")
        desc.priority = max(0, min(9, int(desc.priority)))
        async with self._lock:
            if not self._started or not self._accepting:
                self._close_awaitable(coro)
                raise MLFQAdmissionError("scheduler is not accepting work")
            if desc.task_id in self._records:
                self._close_awaitable(coro)
                raise MLFQAdmissionError(f"duplicate task_id: {desc.task_id}")
            if not self._admit_locked(desc, level):
                self._close_awaitable(coro)
                raise MLFQAdmissionError("workload rejected by scheduler admission control")
            self._seq += 1
            handle = TaskHandle(
                task_id=desc.task_id,
                queue_level=level,
                queued_at=time.time(),
                status="queued",
                result=None,
                error=None,
            )
            record = _TaskRecord(desc=desc, handle=handle, coro=coro)
            self._records[desc.task_id] = record
            self._reserved_tokens[level] += max(0, desc.token_budget)
            await self._queues[level].put((desc.priority, self._seq, desc.task_id))
            return handle

    async def cancel(self, task_id: str) -> bool:
        async with self._lock:
            record = self._records.get(task_id)
            if record is None or record.handle.status in ("done", "failed", "evicted"):
                return False
            record.handle.status = "evicted"
            record.handle.error = "cancelled"
            if record.task is not None:
                record.task.cancel()
            else:
                self._release_tokens(record)
                self._close_awaitable(record.coro)
                record.event.set()
            return True

    async def wait(self, task_id: str) -> TaskHandle:
        async with self._lock:
            record = self._records.get(task_id)
            if record is None:
                raise KeyError(task_id)
            event = record.event
        await event.wait()
        return record.handle

    async def status(self) -> dict:
        async with self._lock:
            await self._maybe_restore_concurrency_locked(time.time())
            return {
                "queue_depths": {f"L{level}": queue.qsize() for level, queue in self._queues.items()},
                "running_count": len(self._running),
                "running_by_level": self._running_by_level_locked(),
                "zombie_count": self._zombie_count,
                "thermal_tier": self._thermal_tier,
                "concurrency_limits": {f"L{level}": self._effective_concurrency_locked(level) for level in (0, 1, 2)},
                "configured_concurrency_limits": {f"L{level}": self._concurrency[level] for level in (0, 1, 2)},
                "token_budget": {f"L{level}": self._token_budgets[level] for level in (0, 1, 2)},
                "system_token_budget": self._system_token_budget,
                "reserved_tokens": {f"L{level}": self._reserved_tokens[level] for level in (0, 1, 2)},
                "reserved_tokens_total": sum(self._reserved_tokens.values()),
                "failure_streak": {f"L{level}": self._failure_streak[level] for level in (0, 1, 2)},
                "backpressure_events": list(self._backpressure_events[-20:]),
            }

    def _admit(self, desc: WorkloadDescriptor) -> bool:
        level = TASK_CLASS_TO_LEVEL.get(desc.task_class)
        if level is None:
            return False
        return self._admit_snapshot(desc, level)

    async def _worker_loop(self, level: int) -> None:
        while True:
            await self._maybe_launch_task(level)
            await asyncio.sleep(0.05)

    async def _zombie_reaper_loop(self) -> None:
        while True:
            await asyncio.sleep(self._reaper_interval_s)
            await self._reap_zombies()

    def _aimd_backpressure(self, level: int) -> None:
        old_limit = self._concurrency[level]
        new_limit = max(1, old_limit // 2)
        self._concurrency[level] = new_limit
        event = {
            "ts": time.time(),
            "level": level,
            "old_limit": old_limit,
            "new_limit": new_limit,
            "reason": "cascade_failure",
        }
        self._backpressure_events.append(event)
        logger.warning(
            "mlfq_scheduler: AIMD backpressure level=%s old_limit=%s new_limit=%s",
            level,
            old_limit,
            new_limit,
        )

    async def set_thermal_tier(self, tier: str) -> None:
        normalized = str(tier or "normal").lower()
        async with self._lock:
            previous = self._thermal_tier
            self._thermal_tier = normalized
        # Phase B wires this via IPM._poll_loop() calling scheduler.set_thermal_tier(tier)
        # For now, expose the method and log the tier change.
        if previous != normalized:
            logger.info("mlfq_scheduler: thermal tier changed %s -> %s", previous, normalized)

    def _admit_snapshot(self, desc: WorkloadDescriptor, level: int) -> bool:
        if desc.token_budget <= 0:
            return False
        if sum(self._reserved_tokens.values()) + desc.token_budget > self._system_token_budget:
            return False
        if level != 0:
            if self._reserved_tokens[level] + desc.token_budget > self._token_budgets[level]:
                return False
        if level == 1 and self._thermal_tier == "shutdown":
            return False
        if level == 2:
            if self._thermal_tier in ("critical", "shutdown"):
                return False
            if self._queues[0].qsize() + self._queues[1].qsize() > 20:
                return False
        return True

    def _admit_locked(self, desc: WorkloadDescriptor, level: int) -> bool:
        return self._admit_snapshot(desc, level)

    async def _maybe_launch_task(self, level: int) -> None:
        async with self._lock:
            await self._maybe_restore_concurrency_locked(time.time())
            if self._running_by_level_locked().get(level, 0) >= self._effective_concurrency_locked(level):
                return
        try:
            _, _, task_id = await asyncio.wait_for(self._queues[level].get(), timeout=0.05)
        except asyncio.TimeoutError:
            return
        async with self._lock:
            record = self._records.get(task_id)
            if record is None or record.handle.status != "queued":
                self._queues[level].task_done()
                return
            record.handle.status = "running"
            record.started_at = time.time()
            record.task = asyncio.create_task(self._run_record(record), name=f"mlfq-task-{task_id}")
            self._running[task_id] = record
            self._queues[level].task_done()

    async def _run_record(self, record: _TaskRecord) -> None:
        level = record.handle.queue_level
        try:
            result = await record.coro
            async with self._lock:
                if record.handle.status != "evicted":
                    record.handle.status = "done"
                    record.handle.result = result
                    record.handle.error = None
                    self._failure_streak[level] = 0
        except asyncio.CancelledError:
            async with self._lock:
                if record.handle.status != "evicted":
                    record.handle.status = "evicted"
                    record.handle.error = "cancelled"
            raise
        except Exception as exc:
            async with self._lock:
                if record.handle.status != "evicted":
                    record.handle.status = "failed"
                    record.handle.error = str(exc)
                    self._record_failure_locked(level)
        finally:
            async with self._lock:
                self._running.pop(record.handle.task_id, None)
                self._release_tokens(record)
                record.event.set()

    async def _reap_zombies(self) -> None:
        now = time.time()
        to_cancel: list[_TaskRecord] = []
        async with self._lock:
            for record in list(self._running.values()):
                if record.started_at is not None and now - record.started_at > self._zombie_timeout_s:
                    record.handle.status = "evicted"
                    record.handle.error = f"zombie timeout exceeded ({self._zombie_timeout_s:.0f}s)"
                    self._zombie_count += 1
                    to_cancel.append(record)
                    self._record_failure_locked(record.handle.queue_level)
            for record in self._records.values():
                if record.handle.status == "queued" and now - record.handle.queued_at > self._zombie_timeout_s:
                    record.handle.status = "evicted"
                    record.handle.error = f"queue timeout exceeded ({self._zombie_timeout_s:.0f}s)"
                    self._zombie_count += 1
                    self._release_tokens(record)
                    self._close_awaitable(record.coro)
                    record.event.set()
                    self._record_failure_locked(record.handle.queue_level)
        for record in to_cancel:
            if record.task is not None:
                record.task.cancel()

    def _record_failure_locked(self, level: int) -> None:
        self._failure_streak[level] += 1
        self._last_failure_at[level] = time.time()
        breaker = self._circuit_breakers.get(level)
        if breaker is not None:
            breaker.failure_count = min(breaker.failure_threshold, breaker.failure_count + 1)
            breaker.last_failure_time = self._last_failure_at[level]
            if breaker.failure_count >= breaker.failure_threshold:
                breaker._trip()
        if self._failure_streak[level] >= 3:
            self._failure_streak[level] = 0
            self._aimd_backpressure(level)

    async def _maybe_restore_concurrency_locked(self, now: float) -> None:
        for level in (0, 1, 2):
            if self._concurrency[level] >= self._base_concurrency[level]:
                continue
            if self._last_failure_at[level] and now - self._last_failure_at[level] < self._recovery_interval_s:
                continue
            if now - self._last_recovery_at[level] < self._recovery_interval_s:
                continue
            old_limit = self._concurrency[level]
            restored = max(old_limit + 1, int(old_limit * 1.1))
            self._concurrency[level] = min(self._base_concurrency[level], restored)
            self._last_recovery_at[level] = now
            self._backpressure_events.append({
                "ts": now,
                "level": level,
                "old_limit": old_limit,
                "new_limit": self._concurrency[level],
                "reason": "aimd_recovery",
            })

    def _effective_concurrency_locked(self, level: int) -> int:
        if level == 1 and self._thermal_tier == "critical":
            return min(self._concurrency[level], 1)
        return self._concurrency[level]

    def _running_by_level_locked(self) -> Dict[int, int]:
        counts = {0: 0, 1: 0, 2: 0}
        for record in self._running.values():
            counts[record.handle.queue_level] += 1
        return counts

    def _release_tokens(self, record: _TaskRecord) -> None:
        level = record.handle.queue_level
        self._reserved_tokens[level] = max(
            0, self._reserved_tokens[level] - max(0, record.desc.token_budget)
        )

    def _close_awaitable(self, awaitable: Awaitable[Any]) -> None:
        if inspect.iscoroutine(awaitable):
            awaitable.close()


_scheduler: Optional[MLFQScheduler] = None


def get_scheduler() -> MLFQScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = MLFQScheduler()
    return _scheduler
