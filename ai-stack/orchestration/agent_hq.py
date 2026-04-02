#!/usr/bin/env python3
"""
Agent HQ - Centralized Multi-Agent Session Management

Provides unified control center for orchestrating multiple AI agents with:
- Session lifecycle management (create, pause, resume, terminate)
- Checkpoint/restore for session state persistence
- Real-time agent status tracking
- Cross-agent delegation and coordination
- Session history and timeline

Part of Phase 4.2: Multi-Agent Orchestration Enhancements
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class AgentStatus(str, Enum):
    """Real-time agent operational status."""
    IDLE = "idle"
    EXECUTING = "executing"
    WAITING = "waiting"
    PAUSED = "paused"
    FAILED = "failed"
    DISCONNECTED = "disconnected"


class SessionState(str, Enum):
    """Session lifecycle states."""
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    TERMINATED = "terminated"


@dataclass
class AgentInfo:
    """Registered agent metadata and runtime state."""
    agent_id: str
    name: str
    capabilities: Set[str] = field(default_factory=set)
    status: AgentStatus = AgentStatus.IDLE
    current_task: Optional[str] = None
    load: float = 0.0
    success_rate: float = 1.0
    total_tasks: int = 0
    failed_tasks: int = 0
    last_heartbeat: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "capabilities": list(self.capabilities),
            "status": self.status.value,
            "current_task": self.current_task,
            "load": self.load,
            "success_rate": self.success_rate,
            "total_tasks": self.total_tasks,
            "failed_tasks": self.failed_tasks,
            "last_heartbeat": self.last_heartbeat,
            "metadata": self.metadata,
        }


@dataclass
class Checkpoint:
    """Session state snapshot for restore capability."""
    checkpoint_id: str
    session_id: str
    name: str
    created_at: float
    agent_states: Dict[str, Dict[str, Any]]
    pending_tasks: List[Dict[str, Any]]
    completed_tasks: List[Dict[str, Any]]
    context: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "session_id": self.session_id,
            "name": self.name,
            "created_at": self.created_at,
            "agent_states": self.agent_states,
            "pending_tasks": self.pending_tasks,
            "completed_tasks": self.completed_tasks,
            "context": self.context,
        }


@dataclass
class TaskInfo:
    """Task metadata for tracking and delegation."""
    task_id: str
    description: str
    assigned_agent: Optional[str] = None
    status: str = "pending"
    priority: int = 5
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Any = None
    error: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "description": self.description,
            "assigned_agent": self.assigned_agent,
            "status": self.status,
            "priority": self.priority,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "error": self.error,
            "dependencies": self.dependencies,
            "metadata": self.metadata,
        }


@dataclass
class Session:
    """Multi-agent orchestration session."""
    session_id: str
    name: str
    state: SessionState = SessionState.CREATED
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    paused_at: Optional[float] = None
    completed_at: Optional[float] = None
    agents: Dict[str, AgentInfo] = field(default_factory=dict)
    tasks: Dict[str, TaskInfo] = field(default_factory=dict)
    checkpoints: List[Checkpoint] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    event_log: List[Dict[str, Any]] = field(default_factory=list)

    def log_event(self, event_type: str, details: Dict[str, Any]) -> None:
        self.event_log.append({
            "timestamp": time.time(),
            "event_type": event_type,
            "details": details,
        })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "name": self.name,
            "state": self.state.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "paused_at": self.paused_at,
            "completed_at": self.completed_at,
            "agents": {k: v.to_dict() for k, v in self.agents.items()},
            "tasks": {k: v.to_dict() for k, v in self.tasks.items()},
            "checkpoints": [c.to_dict() for c in self.checkpoints],
            "context": self.context,
            "event_count": len(self.event_log),
        }


class AgentHQ:
    """
    Centralized multi-agent orchestration control center.

    Manages sessions, coordinates agents, handles task delegation,
    and provides checkpoint/restore capabilities.
    """

    def __init__(
        self,
        persistence_dir: Optional[Path] = None,
        executor_fn: Optional[Callable[[str, TaskInfo, AgentInfo], Awaitable[Any]]] = None,
    ) -> None:
        self.sessions: Dict[str, Session] = {}
        self.global_agents: Dict[str, AgentInfo] = {}
        self.persistence_dir = persistence_dir or Path.home() / ".agent-hq"
        self.executor_fn = executor_fn
        self._listeners: List[Callable[[str, Dict[str, Any]], None]] = []
        self._ensure_persistence_dir()

    def _ensure_persistence_dir(self) -> None:
        self.persistence_dir.mkdir(parents=True, exist_ok=True)
        (self.persistence_dir / "sessions").mkdir(exist_ok=True)
        (self.persistence_dir / "checkpoints").mkdir(exist_ok=True)

    def add_listener(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        """Register event listener for real-time updates."""
        self._listeners.append(callback)

    def _emit(self, event_type: str, data: Dict[str, Any]) -> None:
        for listener in self._listeners:
            try:
                listener(event_type, data)
            except Exception as e:
                logger.warning("Event listener error: %s", e)

    # -------------------------------------------------------------------------
    # Agent Registry
    # -------------------------------------------------------------------------

    def register_agent(
        self,
        name: str,
        capabilities: Optional[Set[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentInfo:
        """Register an agent globally for delegation."""
        agent_id = f"agent-{uuid.uuid4().hex[:8]}"
        agent = AgentInfo(
            agent_id=agent_id,
            name=name,
            capabilities=capabilities or set(),
            metadata=metadata or {},
        )
        self.global_agents[agent_id] = agent
        self._emit("agent_registered", agent.to_dict())
        logger.info("Registered agent: %s (%s)", name, agent_id)
        return agent

    def update_agent_status(
        self,
        agent_id: str,
        status: AgentStatus,
        current_task: Optional[str] = None,
        load: Optional[float] = None,
    ) -> None:
        """Update agent runtime status."""
        if agent_id not in self.global_agents:
            return
        agent = self.global_agents[agent_id]
        agent.status = status
        agent.last_heartbeat = time.time()
        if current_task is not None:
            agent.current_task = current_task
        if load is not None:
            agent.load = load
        self._emit("agent_status_changed", {
            "agent_id": agent_id,
            "status": status.value,
            "current_task": current_task,
        })

    def get_available_agents(
        self,
        required_capabilities: Optional[Set[str]] = None,
    ) -> List[AgentInfo]:
        """Get agents available for task assignment."""
        available = []
        for agent in self.global_agents.values():
            if agent.status not in (AgentStatus.IDLE, AgentStatus.WAITING):
                continue
            if required_capabilities and not required_capabilities.issubset(agent.capabilities):
                continue
            available.append(agent)
        return sorted(available, key=lambda a: (a.load, -a.success_rate))

    # -------------------------------------------------------------------------
    # Session Management
    # -------------------------------------------------------------------------

    def create_session(
        self,
        name: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Session:
        """Create a new orchestration session."""
        session_id = f"session-{uuid.uuid4().hex[:8]}"
        session = Session(
            session_id=session_id,
            name=name,
            context=context or {},
        )
        session.log_event("session_created", {"name": name})
        self.sessions[session_id] = session
        self._emit("session_created", session.to_dict())
        logger.info("Created session: %s (%s)", name, session_id)
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """Retrieve session by ID."""
        return self.sessions.get(session_id)

    def list_sessions(self, state_filter: Optional[SessionState] = None) -> List[Session]:
        """List all sessions, optionally filtered by state."""
        sessions = list(self.sessions.values())
        if state_filter:
            sessions = [s for s in sessions if s.state == state_filter]
        return sorted(sessions, key=lambda s: s.created_at, reverse=True)

    async def start_session(self, session_id: str) -> bool:
        """Start or resume a session."""
        session = self.sessions.get(session_id)
        if not session:
            return False
        if session.state not in (SessionState.CREATED, SessionState.PAUSED):
            return False

        session.state = SessionState.RUNNING
        session.started_at = session.started_at or time.time()
        session.paused_at = None
        session.log_event("session_started", {})
        self._emit("session_started", {"session_id": session_id})

        # Resume pending tasks
        await self._process_pending_tasks(session)
        return True

    async def pause_session(self, session_id: str) -> bool:
        """Pause a running session."""
        session = self.sessions.get(session_id)
        if not session or session.state != SessionState.RUNNING:
            return False

        session.state = SessionState.PAUSED
        session.paused_at = time.time()
        session.log_event("session_paused", {})
        self._emit("session_paused", {"session_id": session_id})

        # Mark executing agents as paused
        for agent_id in session.agents:
            if agent_id in self.global_agents:
                agent = self.global_agents[agent_id]
                if agent.status == AgentStatus.EXECUTING:
                    agent.status = AgentStatus.PAUSED
        return True

    async def terminate_session(self, session_id: str) -> bool:
        """Terminate a session permanently."""
        session = self.sessions.get(session_id)
        if not session:
            return False

        session.state = SessionState.TERMINATED
        session.completed_at = time.time()
        session.log_event("session_terminated", {})
        self._emit("session_terminated", {"session_id": session_id})

        # Release agents
        for agent_id in session.agents:
            if agent_id in self.global_agents:
                self.global_agents[agent_id].status = AgentStatus.IDLE
                self.global_agents[agent_id].current_task = None
        return True

    # -------------------------------------------------------------------------
    # Checkpoint/Restore
    # -------------------------------------------------------------------------

    def create_checkpoint(
        self,
        session_id: str,
        name: Optional[str] = None,
    ) -> Optional[Checkpoint]:
        """Create a named checkpoint of session state."""
        session = self.sessions.get(session_id)
        if not session:
            return None

        checkpoint_id = f"checkpoint-{uuid.uuid4().hex[:8]}"
        checkpoint_name = name or f"checkpoint-{len(session.checkpoints) + 1}"

        checkpoint = Checkpoint(
            checkpoint_id=checkpoint_id,
            session_id=session_id,
            name=checkpoint_name,
            created_at=time.time(),
            agent_states={
                agent_id: agent.to_dict()
                for agent_id, agent in session.agents.items()
            },
            pending_tasks=[
                t.to_dict() for t in session.tasks.values()
                if t.status in ("pending", "executing")
            ],
            completed_tasks=[
                t.to_dict() for t in session.tasks.values()
                if t.status == "completed"
            ],
            context=dict(session.context),
        )
        session.checkpoints.append(checkpoint)
        session.log_event("checkpoint_created", {"checkpoint_id": checkpoint_id, "name": checkpoint_name})

        # Persist checkpoint
        self._persist_checkpoint(checkpoint)
        self._emit("checkpoint_created", checkpoint.to_dict())
        logger.info("Created checkpoint: %s for session %s", checkpoint_name, session_id)
        return checkpoint

    def restore_checkpoint(self, session_id: str, checkpoint_id: str) -> bool:
        """Restore session state from a checkpoint."""
        session = self.sessions.get(session_id)
        if not session:
            return False

        checkpoint = next(
            (c for c in session.checkpoints if c.checkpoint_id == checkpoint_id),
            None,
        )
        if not checkpoint:
            # Try loading from persistence
            checkpoint = self._load_checkpoint(checkpoint_id)
            if not checkpoint or checkpoint.session_id != session_id:
                return False

        # Restore agent states
        for agent_id, agent_data in checkpoint.agent_states.items():
            if agent_id in session.agents:
                agent = session.agents[agent_id]
                agent.status = AgentStatus(agent_data.get("status", "idle"))
                agent.current_task = agent_data.get("current_task")
                agent.load = agent_data.get("load", 0.0)

        # Restore tasks
        session.tasks.clear()
        for task_data in checkpoint.pending_tasks + checkpoint.completed_tasks:
            task = TaskInfo(
                task_id=task_data["task_id"],
                description=task_data["description"],
                assigned_agent=task_data.get("assigned_agent"),
                status=task_data.get("status", "pending"),
                priority=task_data.get("priority", 5),
                created_at=task_data.get("created_at", time.time()),
                started_at=task_data.get("started_at"),
                completed_at=task_data.get("completed_at"),
                result=task_data.get("result"),
                error=task_data.get("error"),
                dependencies=task_data.get("dependencies", []),
                metadata=task_data.get("metadata", {}),
            )
            session.tasks[task.task_id] = task

        # Restore context
        session.context = dict(checkpoint.context)
        session.log_event("checkpoint_restored", {"checkpoint_id": checkpoint_id})
        self._emit("checkpoint_restored", {"session_id": session_id, "checkpoint_id": checkpoint_id})
        logger.info("Restored checkpoint: %s for session %s", checkpoint_id, session_id)
        return True

    def list_checkpoints(self, session_id: str) -> List[Checkpoint]:
        """List all checkpoints for a session."""
        session = self.sessions.get(session_id)
        if not session:
            return []
        return sorted(session.checkpoints, key=lambda c: c.created_at, reverse=True)

    def _persist_checkpoint(self, checkpoint: Checkpoint) -> None:
        checkpoint_path = self.persistence_dir / "checkpoints" / f"{checkpoint.checkpoint_id}.json"
        with open(checkpoint_path, "w", encoding="utf-8") as f:
            json.dump(checkpoint.to_dict(), f, indent=2)

    def _load_checkpoint(self, checkpoint_id: str) -> Optional[Checkpoint]:
        checkpoint_path = self.persistence_dir / "checkpoints" / f"{checkpoint_id}.json"
        if not checkpoint_path.exists():
            return None
        with open(checkpoint_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Checkpoint(
            checkpoint_id=data["checkpoint_id"],
            session_id=data["session_id"],
            name=data["name"],
            created_at=data["created_at"],
            agent_states=data["agent_states"],
            pending_tasks=data["pending_tasks"],
            completed_tasks=data["completed_tasks"],
            context=data["context"],
        )

    # -------------------------------------------------------------------------
    # Task Delegation
    # -------------------------------------------------------------------------

    async def submit_task(
        self,
        session_id: str,
        description: str,
        priority: int = 5,
        required_capabilities: Optional[Set[str]] = None,
        dependencies: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[TaskInfo]:
        """Submit a task for delegation to available agents."""
        session = self.sessions.get(session_id)
        if not session:
            return None

        task_id = f"task-{uuid.uuid4().hex[:8]}"
        task = TaskInfo(
            task_id=task_id,
            description=description,
            priority=priority,
            dependencies=dependencies or [],
            metadata=metadata or {},
        )
        if required_capabilities:
            task.metadata["required_capabilities"] = list(required_capabilities)

        session.tasks[task_id] = task
        session.log_event("task_submitted", {"task_id": task_id, "description": description})
        self._emit("task_submitted", task.to_dict())

        # Auto-delegate if session is running
        if session.state == SessionState.RUNNING:
            await self._delegate_task(session, task, required_capabilities)

        return task

    async def _delegate_task(
        self,
        session: Session,
        task: TaskInfo,
        required_capabilities: Optional[Set[str]] = None,
    ) -> bool:
        """Delegate task to the best available agent."""
        # Check dependencies
        for dep_id in task.dependencies:
            dep_task = session.tasks.get(dep_id)
            if dep_task and dep_task.status != "completed":
                return False  # Dependencies not met

        # Find available agent
        available = self.get_available_agents(required_capabilities)
        if not available:
            logger.warning("No available agents for task: %s", task.task_id)
            return False

        agent = available[0]
        task.assigned_agent = agent.agent_id
        task.status = "executing"
        task.started_at = time.time()

        # Add agent to session if not already
        if agent.agent_id not in session.agents:
            session.agents[agent.agent_id] = agent

        # Update agent status
        agent.status = AgentStatus.EXECUTING
        agent.current_task = task.task_id
        agent.total_tasks += 1

        session.log_event("task_delegated", {
            "task_id": task.task_id,
            "agent_id": agent.agent_id,
        })
        self._emit("task_delegated", {
            "task_id": task.task_id,
            "agent_id": agent.agent_id,
            "session_id": session.session_id,
        })

        # Execute task
        if self.executor_fn:
            asyncio.create_task(self._execute_task(session, task, agent))

        return True

    async def _execute_task(
        self,
        session: Session,
        task: TaskInfo,
        agent: AgentInfo,
    ) -> None:
        """Execute task via executor function."""
        try:
            result = await self.executor_fn(session.session_id, task, agent)
            task.status = "completed"
            task.completed_at = time.time()
            task.result = result
            agent.success_rate = (
                (agent.success_rate * (agent.total_tasks - 1) + 1.0) / agent.total_tasks
            )
            session.log_event("task_completed", {"task_id": task.task_id, "result": str(result)[:100]})
            self._emit("task_completed", task.to_dict())
        except Exception as e:
            task.status = "failed"
            task.completed_at = time.time()
            task.error = str(e)
            agent.failed_tasks += 1
            agent.success_rate = (
                (agent.success_rate * (agent.total_tasks - 1)) / agent.total_tasks
            )
            session.log_event("task_failed", {"task_id": task.task_id, "error": str(e)})
            self._emit("task_failed", {"task_id": task.task_id, "error": str(e)})
        finally:
            agent.status = AgentStatus.IDLE
            agent.current_task = None
            # Process any waiting tasks
            await self._process_pending_tasks(session)

    async def _process_pending_tasks(self, session: Session) -> None:
        """Process pending tasks in priority order."""
        if session.state != SessionState.RUNNING:
            return

        pending = [
            t for t in session.tasks.values()
            if t.status == "pending"
        ]
        pending.sort(key=lambda t: t.priority)

        for task in pending:
            required_caps = set(task.metadata.get("required_capabilities", []))
            await self._delegate_task(session, task, required_caps or None)

    # -------------------------------------------------------------------------
    # Status & Monitoring
    # -------------------------------------------------------------------------

    def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed session status."""
        session = self.sessions.get(session_id)
        if not session:
            return None

        pending = sum(1 for t in session.tasks.values() if t.status == "pending")
        executing = sum(1 for t in session.tasks.values() if t.status == "executing")
        completed = sum(1 for t in session.tasks.values() if t.status == "completed")
        failed = sum(1 for t in session.tasks.values() if t.status == "failed")

        return {
            "session_id": session_id,
            "name": session.name,
            "state": session.state.value,
            "agents": {
                "total": len(session.agents),
                "active": sum(
                    1 for a in session.agents.values()
                    if a.status == AgentStatus.EXECUTING
                ),
            },
            "tasks": {
                "pending": pending,
                "executing": executing,
                "completed": completed,
                "failed": failed,
                "total": len(session.tasks),
            },
            "checkpoints": len(session.checkpoints),
            "uptime_seconds": (
                time.time() - session.started_at
                if session.started_at else 0
            ),
        }

    def get_agent_matrix(self) -> List[Dict[str, Any]]:
        """Get capability matrix for all registered agents."""
        return [agent.to_dict() for agent in self.global_agents.values()]

    def get_delegation_flow(self, session_id: str) -> List[Dict[str, Any]]:
        """Get delegation flow timeline for visualization."""
        session = self.sessions.get(session_id)
        if not session:
            return []

        return [
            event for event in session.event_log
            if event["event_type"] in ("task_delegated", "task_completed", "task_failed")
        ]

    # -------------------------------------------------------------------------
    # Persistence
    # -------------------------------------------------------------------------

    def save_session(self, session_id: str) -> bool:
        """Persist session state to disk."""
        session = self.sessions.get(session_id)
        if not session:
            return False

        session_path = self.persistence_dir / "sessions" / f"{session_id}.json"
        data = session.to_dict()
        data["event_log"] = session.event_log  # Include full event log

        with open(session_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info("Saved session: %s", session_id)
        return True

    def load_session(self, session_id: str) -> Optional[Session]:
        """Load session from disk."""
        session_path = self.persistence_dir / "sessions" / f"{session_id}.json"
        if not session_path.exists():
            return None

        with open(session_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        session = Session(
            session_id=data["session_id"],
            name=data["name"],
            state=SessionState(data["state"]),
            created_at=data["created_at"],
            started_at=data.get("started_at"),
            paused_at=data.get("paused_at"),
            completed_at=data.get("completed_at"),
            context=data.get("context", {}),
            event_log=data.get("event_log", []),
        )

        # Restore agents
        for agent_id, agent_data in data.get("agents", {}).items():
            session.agents[agent_id] = AgentInfo(
                agent_id=agent_data["agent_id"],
                name=agent_data["name"],
                capabilities=set(agent_data.get("capabilities", [])),
                status=AgentStatus(agent_data.get("status", "idle")),
                current_task=agent_data.get("current_task"),
                load=agent_data.get("load", 0.0),
                success_rate=agent_data.get("success_rate", 1.0),
                total_tasks=agent_data.get("total_tasks", 0),
                failed_tasks=agent_data.get("failed_tasks", 0),
                metadata=agent_data.get("metadata", {}),
            )

        # Restore tasks
        for task_id, task_data in data.get("tasks", {}).items():
            session.tasks[task_id] = TaskInfo(
                task_id=task_data["task_id"],
                description=task_data["description"],
                assigned_agent=task_data.get("assigned_agent"),
                status=task_data.get("status", "pending"),
                priority=task_data.get("priority", 5),
                created_at=task_data.get("created_at", time.time()),
                started_at=task_data.get("started_at"),
                completed_at=task_data.get("completed_at"),
                result=task_data.get("result"),
                error=task_data.get("error"),
                dependencies=task_data.get("dependencies", []),
                metadata=task_data.get("metadata", {}),
            )

        self.sessions[session_id] = session
        logger.info("Loaded session: %s", session_id)
        return session
