#!/usr/bin/env python3
"""
Pipeline Orchestration Pattern

Sequential multi-agent pipeline with stage handoffs, dynamic redistribution,
and cross-team coordination capabilities.
Part of Phase 4 Batch 4.2: Multi-Agent Orchestration

Key Features:
- Sequential stage execution with typed handoffs
- Dynamic task redistribution based on load/failures
- Cross-team coordination for complex workflows
- Stage-level checkpointing and recovery
- Pipeline branching and merging
- Real-time progress monitoring

Reference: Data pipeline patterns, workflow orchestration systems
"""

import asyncio
import hashlib
import json
import logging
import os
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Runtime writable state
PIPELINE_STATE = Path(os.getenv(
    "PIPELINE_STATE",
    "/var/lib/ai-stack/hybrid/pipeline-orchestration"
))


class StageStatus(Enum):
    """Pipeline stage status"""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    REDISTRIBUTED = "redistributed"


class HandoffType(Enum):
    """Type of data handoff between stages"""
    FULL = "full"  # Pass complete output
    FILTERED = "filtered"  # Pass subset based on criteria
    TRANSFORMED = "transformed"  # Apply transformation
    REFERENCE = "reference"  # Pass reference only (lazy load)


class RedistributionReason(Enum):
    """Reason for task redistribution"""
    AGENT_OVERLOAD = "agent_overload"
    AGENT_FAILURE = "agent_failure"
    TIMEOUT = "timeout"
    QUALITY_ISSUE = "quality_issue"
    CAPABILITY_MISMATCH = "capability_mismatch"
    LOAD_BALANCING = "load_balancing"


@dataclass
class StageResult:
    """Result from a pipeline stage"""
    stage_id: str
    status: StageStatus
    output: Any
    metadata: Dict = field(default_factory=dict)
    duration_ms: float = 0.0
    agent_id: Optional[str] = None
    error: Optional[str] = None
    quality_score: float = 0.0


@dataclass
class Handoff:
    """Data handoff between stages"""
    from_stage: str
    to_stage: str
    handoff_type: HandoffType
    data: Any
    transform_fn: Optional[str] = None
    filter_criteria: Optional[Dict] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class PipelineStage:
    """A stage in the pipeline"""
    stage_id: str
    name: str
    required_capability: str
    dependencies: List[str] = field(default_factory=list)
    timeout_seconds: int = 300
    retry_count: int = 2
    handoff_type: HandoffType = HandoffType.FULL
    transform_fn: Optional[Callable] = None
    filter_criteria: Optional[Dict] = None

    # Runtime state
    status: StageStatus = StageStatus.PENDING
    assigned_agent: Optional[str] = None
    result: Optional[StageResult] = None
    start_time: Optional[datetime] = None
    attempts: int = 0


@dataclass
class Pipeline:
    """A complete pipeline definition"""
    pipeline_id: str
    name: str
    stages: List[PipelineStage]
    metadata: Dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Execution state
    status: StageStatus = StageStatus.PENDING
    current_stage: Optional[str] = None
    checkpoints: Dict[str, Any] = field(default_factory=dict)
    handoffs: List[Handoff] = field(default_factory=list)


@dataclass
class AgentLoad:
    """Agent load tracking"""
    agent_id: str
    current_tasks: int
    max_tasks: int
    capabilities: Set[str]
    avg_completion_time: float
    failure_rate: float
    last_heartbeat: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def is_available(self) -> bool:
        return (
            self.current_tasks < self.max_tasks and
            (datetime.now(timezone.utc) - self.last_heartbeat) < timedelta(minutes=5)
        )

    def load_factor(self) -> float:
        return self.current_tasks / max(self.max_tasks, 1)


@dataclass
class Team:
    """A team of agents"""
    team_id: str
    name: str
    agents: List[str]
    capabilities: Set[str]
    lead_agent: Optional[str] = None
    coordination_mode: str = "parallel"  # parallel, sequential, hybrid


@dataclass
class RedistributionEvent:
    """Record of task redistribution"""
    event_id: str
    stage_id: str
    from_agent: str
    to_agent: str
    reason: RedistributionReason
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict = field(default_factory=dict)


class LoadBalancer:
    """Balance load across agents"""

    def __init__(self):
        self.agents: Dict[str, AgentLoad] = {}
        self.redistribution_history: List[RedistributionEvent] = []
        logger.info("Load Balancer initialized")

    def register_agent(
        self,
        agent_id: str,
        max_tasks: int,
        capabilities: Set[str],
    ):
        """Register an agent for load balancing"""
        self.agents[agent_id] = AgentLoad(
            agent_id=agent_id,
            current_tasks=0,
            max_tasks=max_tasks,
            capabilities=capabilities,
            avg_completion_time=0.0,
            failure_rate=0.0,
        )

    def update_heartbeat(self, agent_id: str):
        """Update agent heartbeat"""
        if agent_id in self.agents:
            self.agents[agent_id].last_heartbeat = datetime.now(timezone.utc)

    def acquire_slot(self, agent_id: str) -> bool:
        """Acquire a task slot for an agent"""
        agent = self.agents.get(agent_id)
        if not agent or not agent.is_available():
            return False

        agent.current_tasks += 1
        return True

    def release_slot(
        self,
        agent_id: str,
        success: bool,
        duration_ms: float,
    ):
        """Release a task slot"""
        agent = self.agents.get(agent_id)
        if not agent:
            return

        agent.current_tasks = max(0, agent.current_tasks - 1)

        # Update metrics (exponential moving average)
        if agent.avg_completion_time == 0:
            agent.avg_completion_time = duration_ms
        else:
            agent.avg_completion_time = 0.9 * agent.avg_completion_time + 0.1 * duration_ms

        if success:
            agent.failure_rate = 0.95 * agent.failure_rate
        else:
            agent.failure_rate = 0.95 * agent.failure_rate + 0.05

    def select_agent(
        self,
        required_capability: str,
        exclude_agents: Optional[Set[str]] = None,
    ) -> Optional[str]:
        """Select best available agent for capability"""
        exclude_agents = exclude_agents or set()

        candidates = []
        for agent_id, agent in self.agents.items():
            if agent_id in exclude_agents:
                continue
            if not agent.is_available():
                continue
            if required_capability not in agent.capabilities:
                continue

            # Score: lower load + lower failure rate = better
            score = agent.load_factor() + agent.failure_rate
            candidates.append((agent_id, score))

        if not candidates:
            return None

        # Return agent with lowest score
        candidates.sort(key=lambda x: x[1])
        return candidates[0][0]

    def should_redistribute(
        self,
        agent_id: str,
        stage: PipelineStage,
    ) -> Optional[RedistributionReason]:
        """Check if task should be redistributed"""
        agent = self.agents.get(agent_id)
        if not agent:
            return RedistributionReason.AGENT_FAILURE

        # Agent overloaded
        if agent.load_factor() > 0.9:
            return RedistributionReason.AGENT_OVERLOAD

        # Agent not responding
        if not agent.is_available():
            return RedistributionReason.AGENT_FAILURE

        # High failure rate
        if agent.failure_rate > 0.3:
            return RedistributionReason.QUALITY_ISSUE

        return None

    def redistribute(
        self,
        stage: PipelineStage,
        reason: RedistributionReason,
    ) -> Optional[str]:
        """Redistribute task to another agent"""
        excluded = {stage.assigned_agent} if stage.assigned_agent else set()

        new_agent = self.select_agent(
            stage.required_capability,
            exclude_agents=excluded,
        )

        if new_agent:
            event = RedistributionEvent(
                event_id=hashlib.sha256(
                    f"{stage.stage_id}_{datetime.now().isoformat()}".encode()
                ).hexdigest()[:12],
                stage_id=stage.stage_id,
                from_agent=stage.assigned_agent or "none",
                to_agent=new_agent,
                reason=reason,
            )
            self.redistribution_history.append(event)

            logger.info(
                f"Redistributed stage {stage.stage_id} from "
                f"{stage.assigned_agent} to {new_agent} ({reason.value})"
            )

        return new_agent


class CrossTeamCoordinator:
    """Coordinate work across multiple teams"""

    def __init__(self):
        self.teams: Dict[str, Team] = {}
        self.shared_state: Dict[str, Any] = {}
        self.pending_handoffs: List[Tuple[str, str, Any]] = []  # (from_team, to_team, data)
        logger.info("Cross-Team Coordinator initialized")

    def register_team(self, team: Team):
        """Register a team"""
        self.teams[team.team_id] = team
        logger.info(f"Registered team: {team.name} ({len(team.agents)} agents)")

    def find_team_for_capability(self, capability: str) -> Optional[str]:
        """Find team that can handle a capability"""
        for team_id, team in self.teams.items():
            if capability in team.capabilities:
                return team_id
        return None

    def request_handoff(
        self,
        from_team: str,
        capability_needed: str,
        data: Any,
        priority: int = 1,
    ) -> Optional[str]:
        """Request handoff to team with capability"""
        target_team = self.find_team_for_capability(capability_needed)

        if not target_team:
            logger.warning(f"No team found for capability: {capability_needed}")
            return None

        self.pending_handoffs.append((from_team, target_team, data))

        logger.info(
            f"Handoff requested: {from_team} -> {target_team} "
            f"(capability: {capability_needed})"
        )

        return target_team

    def get_pending_handoffs(self, team_id: str) -> List[Tuple[str, Any]]:
        """Get pending handoffs for a team"""
        result = []
        remaining = []

        for from_team, to_team, data in self.pending_handoffs:
            if to_team == team_id:
                result.append((from_team, data))
            else:
                remaining.append((from_team, to_team, data))

        self.pending_handoffs = remaining
        return result

    def share_state(self, key: str, value: Any, team_id: str):
        """Share state across teams"""
        self.shared_state[key] = {
            "value": value,
            "from_team": team_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_shared_state(self, key: str) -> Optional[Any]:
        """Get shared state"""
        entry = self.shared_state.get(key)
        return entry["value"] if entry else None


class PipelineOrchestrator:
    """
    Main pipeline orchestration engine.

    Executes multi-stage pipelines with dynamic load balancing,
    task redistribution, and cross-team coordination.
    """

    def __init__(
        self,
        output_dir: Optional[Path] = None,
        execute_fn: Optional[Callable] = None,
    ):
        self.output_dir = output_dir or PIPELINE_STATE
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.execute_fn = execute_fn
        self.load_balancer = LoadBalancer()
        self.cross_team = CrossTeamCoordinator()

        self.pipelines: Dict[str, Pipeline] = {}
        self.active_pipelines: Set[str] = set()

        # Statistics
        self.stats = {
            "total_pipelines": 0,
            "completed_pipelines": 0,
            "failed_pipelines": 0,
            "total_stages": 0,
            "redistributions": 0,
        }

        logger.info(f"Pipeline Orchestrator initialized: {self.output_dir}")

    def create_pipeline(
        self,
        name: str,
        stages: List[Dict[str, Any]],
        metadata: Optional[Dict] = None,
    ) -> Pipeline:
        """Create a new pipeline"""
        pipeline_id = hashlib.sha256(
            f"{name}_{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]

        pipeline_stages = []
        for stage_def in stages:
            stage = PipelineStage(
                stage_id=f"{pipeline_id}_{stage_def['name']}",
                name=stage_def["name"],
                required_capability=stage_def.get("capability", "general"),
                dependencies=stage_def.get("dependencies", []),
                timeout_seconds=stage_def.get("timeout", 300),
                retry_count=stage_def.get("retries", 2),
                handoff_type=HandoffType(stage_def.get("handoff", "full")),
                transform_fn=stage_def.get("transform_fn"),
                filter_criteria=stage_def.get("filter_criteria"),
            )
            pipeline_stages.append(stage)

        pipeline = Pipeline(
            pipeline_id=pipeline_id,
            name=name,
            stages=pipeline_stages,
            metadata=metadata or {},
        )

        self.pipelines[pipeline_id] = pipeline
        self.stats["total_pipelines"] += 1
        self.stats["total_stages"] += len(pipeline_stages)

        logger.info(f"Created pipeline: {name} ({len(pipeline_stages)} stages)")
        return pipeline

    async def execute_pipeline(
        self,
        pipeline_id: str,
        initial_input: Any = None,
    ) -> Dict[str, Any]:
        """Execute a pipeline"""
        pipeline = self.pipelines.get(pipeline_id)
        if not pipeline:
            return {"status": "error", "message": f"Pipeline not found: {pipeline_id}"}

        pipeline.status = StageStatus.RUNNING
        self.active_pipelines.add(pipeline_id)

        try:
            # Build execution order (topological sort)
            execution_order = self._build_execution_order(pipeline)

            # Execute stages in order
            stage_outputs: Dict[str, Any] = {"_initial": initial_input}

            for stage_id in execution_order:
                stage = next(s for s in pipeline.stages if s.stage_id == stage_id)
                pipeline.current_stage = stage_id

                # Gather inputs from dependencies
                stage_input = self._gather_stage_input(stage, stage_outputs, pipeline)

                # Execute stage with retries and redistribution
                result = await self._execute_stage_with_retry(
                    stage, stage_input, pipeline
                )

                stage_outputs[stage_id] = result.output

                if result.status == StageStatus.FAILED:
                    pipeline.status = StageStatus.FAILED
                    self.stats["failed_pipelines"] += 1
                    return {
                        "status": "failed",
                        "failed_stage": stage_id,
                        "error": result.error,
                        "completed_stages": [
                            s.stage_id for s in pipeline.stages
                            if s.status == StageStatus.COMPLETED
                        ],
                    }

                # Create checkpoint
                pipeline.checkpoints[stage_id] = {
                    "output": result.output,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "agent": result.agent_id,
                }

            # Pipeline completed
            pipeline.status = StageStatus.COMPLETED
            self.stats["completed_pipelines"] += 1

            return {
                "status": "completed",
                "pipeline_id": pipeline_id,
                "stages_completed": len(pipeline.stages),
                "final_output": stage_outputs.get(execution_order[-1]),
                "handoffs": len(pipeline.handoffs),
            }

        finally:
            self.active_pipelines.discard(pipeline_id)

    def _build_execution_order(self, pipeline: Pipeline) -> List[str]:
        """Build topological execution order"""
        stage_lookup = {stage.name: stage.stage_id for stage in pipeline.stages}

        # Build dependency graph
        in_degree = {s.stage_id: 0 for s in pipeline.stages}
        graph = defaultdict(list)

        for stage in pipeline.stages:
            for dep in stage.dependencies:
                dep_id = stage_lookup.get(dep)
                if dep_id is None:
                    raise ValueError(f"Unknown dependency '{dep}' for stage '{stage.name}'")
                graph[dep_id].append(stage.stage_id)
                in_degree[stage.stage_id] += 1

        # Kahn's algorithm
        queue = [sid for sid, deg in in_degree.items() if deg == 0]
        result = []

        while queue:
            current = queue.pop(0)
            result.append(current)

            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(result) != len(pipeline.stages):
            raise ValueError(f"Pipeline '{pipeline.name}' contains a dependency cycle")

        return result

    @staticmethod
    def _apply_handoff(stage: PipelineStage, source_stage_id: str, payload: Any) -> Any:
        """Apply the stage's handoff strategy to dependency output."""
        if stage.handoff_type == HandoffType.REFERENCE:
            return {
                "source_stage": source_stage_id,
                "reference_type": "checkpoint",
            }

        if stage.handoff_type == HandoffType.FILTERED:
            criteria = stage.filter_criteria or {}
            if isinstance(payload, dict):
                keys = [str(key) for key in (criteria.get("keys") or []) if str(key)]
                if keys:
                    return {key: payload[key] for key in keys if key in payload}
            if isinstance(payload, list):
                max_items = max(0, int(criteria.get("max_items", len(payload)) or 0))
                return payload[:max_items] if max_items else []
            return payload

        if stage.handoff_type == HandoffType.TRANSFORMED and callable(stage.transform_fn):
            return stage.transform_fn(payload)

        return payload

    def _team_for_agent(self, agent_id: Optional[str]) -> Optional[str]:
        if not agent_id:
            return None
        for team_id, team in self.cross_team.teams.items():
            if agent_id in team.agents:
                return team_id
        return None

    def _gather_stage_input(
        self,
        stage: PipelineStage,
        stage_outputs: Dict[str, Any],
        pipeline: Pipeline,
    ) -> Any:
        """Gather input for a stage from dependencies"""
        if not stage.dependencies:
            return stage_outputs.get("_initial")

        inputs = {}
        for dep in stage.dependencies:
            dep_id = f"{pipeline.pipeline_id}_{dep}"
            inputs[dep] = self._apply_handoff(stage, dep_id, stage_outputs.get(dep_id))

        # Create handoff record
        for dep in stage.dependencies:
            dep_id = f"{pipeline.pipeline_id}_{dep}"
            handoff = Handoff(
                from_stage=dep_id,
                to_stage=stage.stage_id,
                handoff_type=stage.handoff_type,
                data=inputs.get(dep),
                transform_fn=getattr(stage.transform_fn, "__name__", None) if callable(stage.transform_fn) else None,
                filter_criteria=stage.filter_criteria,
            )
            pipeline.handoffs.append(handoff)

            source_stage = next((item for item in pipeline.stages if item.stage_id == dep_id), None)
            from_team = self._team_for_agent(source_stage.assigned_agent if source_stage else None)
            to_team = self.cross_team.find_team_for_capability(stage.required_capability)
            if from_team and to_team and from_team != to_team:
                self.cross_team.request_handoff(
                    from_team=from_team,
                    capability_needed=stage.required_capability,
                    data=handoff.data,
                )

        # If single dependency, return directly
        if len(inputs) == 1:
            return list(inputs.values())[0]

        return inputs

    async def _execute_stage_with_retry(
        self,
        stage: PipelineStage,
        input_data: Any,
        pipeline: Pipeline,
    ) -> StageResult:
        """Execute stage with retries and redistribution"""
        stage.status = StageStatus.QUEUED

        for attempt in range(stage.retry_count + 1):
            stage.attempts = attempt + 1

            # Select agent
            agent_id = self.load_balancer.select_agent(
                stage.required_capability,
                exclude_agents={stage.assigned_agent} if stage.assigned_agent and attempt > 0 else None,
            )

            if not agent_id:
                logger.warning(f"No agent available for stage {stage.stage_id}")
                continue

            stage.assigned_agent = agent_id
            stage.status = StageStatus.RUNNING
            stage.start_time = datetime.now(timezone.utc)

            # Acquire slot
            if not self.load_balancer.acquire_slot(agent_id):
                continue

            try:
                # Check for redistribution need during execution
                redistribution_reason = self.load_balancer.should_redistribute(
                    agent_id, stage
                )

                if redistribution_reason and attempt < stage.retry_count:
                    new_agent = self.load_balancer.redistribute(stage, redistribution_reason)
                    if new_agent:
                        self.load_balancer.release_slot(agent_id, success=False, duration_ms=0)
                        stage.status = StageStatus.REDISTRIBUTED
                        self.stats["redistributions"] += 1
                        continue

                # Execute stage
                result = await self._execute_stage(stage, input_data)

                # Release slot
                duration = (datetime.now(timezone.utc) - stage.start_time).total_seconds() * 1000
                self.load_balancer.release_slot(
                    agent_id,
                    success=result.status == StageStatus.COMPLETED,
                    duration_ms=duration,
                )

                if result.status == StageStatus.COMPLETED:
                    stage.status = StageStatus.COMPLETED
                    stage.result = result
                    return result

            except asyncio.TimeoutError:
                logger.warning(f"Stage {stage.stage_id} timed out")
                self.load_balancer.release_slot(agent_id, success=False, duration_ms=stage.timeout_seconds * 1000)

            except Exception as e:
                logger.error(f"Stage {stage.stage_id} failed: {e}")
                self.load_balancer.release_slot(agent_id, success=False, duration_ms=0)

        # All retries exhausted
        stage.status = StageStatus.FAILED
        return StageResult(
            stage_id=stage.stage_id,
            status=StageStatus.FAILED,
            output=None,
            error=f"Failed after {stage.retry_count + 1} attempts",
            agent_id=stage.assigned_agent,
        )

    async def _execute_stage(
        self,
        stage: PipelineStage,
        input_data: Any,
    ) -> StageResult:
        """Execute a single stage"""
        start_time = datetime.now(timezone.utc)

        try:
            if self.execute_fn:
                output = await asyncio.wait_for(
                    self.execute_fn(
                        stage_id=stage.stage_id,
                        capability=stage.required_capability,
                        input_data=input_data,
                        agent_id=stage.assigned_agent,
                    ),
                    timeout=stage.timeout_seconds,
                )
            else:
                # Simulated execution
                await asyncio.sleep(0.1)
                output = {
                    "stage": stage.name,
                    "input_received": input_data is not None,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

            duration = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

            return StageResult(
                stage_id=stage.stage_id,
                status=StageStatus.COMPLETED,
                output=output,
                duration_ms=duration,
                agent_id=stage.assigned_agent,
                quality_score=0.85,  # Placeholder
            )

        except Exception as e:
            duration = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

            return StageResult(
                stage_id=stage.stage_id,
                status=StageStatus.FAILED,
                output=None,
                duration_ms=duration,
                agent_id=stage.assigned_agent,
                error=str(e),
            )

    def resume_from_checkpoint(
        self,
        pipeline_id: str,
        checkpoint_stage: str,
    ) -> Optional[Any]:
        """Resume pipeline from a checkpoint"""
        pipeline = self.pipelines.get(pipeline_id)
        if not pipeline:
            return None

        checkpoint = pipeline.checkpoints.get(checkpoint_stage)
        if not checkpoint:
            return None

        logger.info(f"Resuming pipeline {pipeline_id} from {checkpoint_stage}")
        return checkpoint["output"]

    def get_pipeline_status(self, pipeline_id: str) -> Dict[str, Any]:
        """Get current pipeline status"""
        pipeline = self.pipelines.get(pipeline_id)
        if not pipeline:
            return {"status": "not_found"}

        return {
            "pipeline_id": pipeline_id,
            "name": pipeline.name,
            "status": pipeline.status.value,
            "current_stage": pipeline.current_stage,
            "stages": [
                {
                    "id": s.stage_id,
                    "name": s.name,
                    "status": s.status.value,
                    "agent": s.assigned_agent,
                    "attempts": s.attempts,
                }
                for s in pipeline.stages
            ],
            "checkpoints": list(pipeline.checkpoints.keys()),
            "handoffs": len(pipeline.handoffs),
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get orchestrator statistics"""
        return {
            **self.stats,
            "active_pipelines": len(self.active_pipelines),
            "registered_agents": len(self.load_balancer.agents),
            "registered_teams": len(self.cross_team.teams),
            "total_redistributions": len(self.load_balancer.redistribution_history),
        }

    def save_state(self) -> Path:
        """Save orchestrator state"""
        state_path = self.output_dir / "orchestrator_state.json"

        state = {
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "stats": self.stats,
            "pipelines": {
                pid: {
                    "name": p.name,
                    "status": p.status.value,
                    "stages": len(p.stages),
                    "checkpoints": list(p.checkpoints.keys()),
                }
                for pid, p in self.pipelines.items()
            },
            "agents": {
                aid: {
                    "current_tasks": a.current_tasks,
                    "failure_rate": a.failure_rate,
                    "capabilities": list(a.capabilities),
                }
                for aid, a in self.load_balancer.agents.items()
            },
        }

        with open(state_path, "w") as f:
            json.dump(state, f, indent=2)

        logger.info(f"Saved state to {state_path}")
        return state_path


async def main():
    """Test pipeline orchestration"""
    logging.basicConfig(level=logging.INFO)

    logger.info("Pipeline Orchestration Test")
    logger.info("=" * 60)

    # Create orchestrator
    orchestrator = PipelineOrchestrator()

    # Register agents
    orchestrator.load_balancer.register_agent(
        "agent_1", max_tasks=3, capabilities={"research", "analysis"}
    )
    orchestrator.load_balancer.register_agent(
        "agent_2", max_tasks=3, capabilities={"implementation", "coding"}
    )
    orchestrator.load_balancer.register_agent(
        "agent_3", max_tasks=3, capabilities={"review", "testing", "analysis"}
    )

    # Register teams
    orchestrator.cross_team.register_team(Team(
        team_id="research_team",
        name="Research Team",
        agents=["agent_1"],
        capabilities={"research", "analysis"},
        lead_agent="agent_1",
    ))
    orchestrator.cross_team.register_team(Team(
        team_id="dev_team",
        name="Development Team",
        agents=["agent_2", "agent_3"],
        capabilities={"implementation", "coding", "review", "testing"},
        lead_agent="agent_2",
    ))

    # Create pipeline
    pipeline = orchestrator.create_pipeline(
        name="Feature Implementation",
        stages=[
            {"name": "research", "capability": "research"},
            {"name": "design", "capability": "analysis", "dependencies": ["research"]},
            {"name": "implement", "capability": "implementation", "dependencies": ["design"]},
            {"name": "test", "capability": "testing", "dependencies": ["implement"]},
            {"name": "review", "capability": "review", "dependencies": ["test"]},
        ],
    )

    logger.info(f"\nCreated pipeline: {pipeline.pipeline_id}")
    logger.info(f"Stages: {[s.name for s in pipeline.stages]}")

    # Execute pipeline
    logger.info("\nExecuting pipeline...")
    result = await orchestrator.execute_pipeline(
        pipeline.pipeline_id,
        initial_input={"feature": "user authentication"},
    )

    logger.info(f"\nPipeline result: {result['status']}")
    if result["status"] == "completed":
        logger.info(f"Stages completed: {result['stages_completed']}")
        logger.info(f"Handoffs: {result['handoffs']}")

    # Show status
    status = orchestrator.get_pipeline_status(pipeline.pipeline_id)
    logger.info(f"\nPipeline status:")
    for stage in status["stages"]:
        logger.info(f"  {stage['name']}: {stage['status']} (agent: {stage['agent']})")

    # Show stats
    stats = orchestrator.get_stats()
    logger.info(f"\nOrchestrator stats:")
    logger.info(f"  Total pipelines: {stats['total_pipelines']}")
    logger.info(f"  Completed: {stats['completed_pipelines']}")
    logger.info(f"  Redistributions: {stats['redistributions']}")

    # Save state
    orchestrator.save_state()


if __name__ == "__main__":
    asyncio.run(main())
