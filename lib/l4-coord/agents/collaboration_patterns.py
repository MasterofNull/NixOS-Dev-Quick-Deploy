#!/usr/bin/env python3
"""
Phase 4: Collaboration Patterns
Orchestrate different multi-agent collaboration patterns.

Patterns:
- Parallel Execution: Independent slices, concurrent execution
- Sequential Delegation: Orchestrator → Planner → Executor → Reviewer
- Consensus Review: Critical decisions require 2/3 majority
- Expert Override: Domain specialist overrides general agents

Features:
- Pattern selection based on task type
- Pattern execution with monitoring
- Performance tracking per pattern
- Adaptive pattern selection
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Tuple

import logging

logger = logging.getLogger(__name__)


class PatternType(Enum):
    """Collaboration pattern types."""
    PARALLEL = "parallel"
    SEQUENTIAL = "sequential"
    CONSENSUS = "consensus"
    EXPERT_OVERRIDE = "expert_override"


class TaskCharacteristic(Enum):
    """Task characteristics for pattern selection."""
    INDEPENDENT_SUBTASKS = "independent_subtasks"
    SEQUENTIAL_DEPENDENCIES = "sequential_dependencies"
    HIGH_STAKES = "high_stakes"
    DOMAIN_SPECIFIC = "domain_specific"
    CREATIVE = "creative"
    ANALYTICAL = "analytical"


@dataclass
class PatternConfig:
    """Configuration for a collaboration pattern."""
    pattern_type: PatternType
    min_agents: int
    max_agents: int
    timeout: int = 3600  # seconds
    retry_on_failure: bool = True
    max_retries: int = 2
    enable_monitoring: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "pattern_type": self.pattern_type.value,
            "min_agents": self.min_agents,
            "max_agents": self.max_agents,
            "timeout": self.timeout,
            "retry_on_failure": self.retry_on_failure,
            "max_retries": self.max_retries,
            "enable_monitoring": self.enable_monitoring,
        }


@dataclass
class PatternExecution:
    """Execution instance of a pattern."""
    execution_id: str
    pattern_type: PatternType
    task_id: str
    team_id: str
    agents: List[str]
    status: str = "pending"  # pending, running, success, failure
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration: int = 0  # seconds
    result: Optional[Any] = None
    error: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "execution_id": self.execution_id,
            "pattern_type": self.pattern_type.value,
            "task_id": self.task_id,
            "team_id": self.team_id,
            "agents": self.agents,
            "status": self.status,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration": self.duration,
            "metrics": self.metrics,
        }


class ParallelExecutionPattern:
    """Parallel execution pattern - independent concurrent work."""

    @staticmethod
    async def execute(agents: List[str],
                     tasks: List[Dict[str, Any]],
                     task_executor: Callable) -> Dict[str, Any]:
        """Execute tasks in parallel."""
        logger.info("parallel_execution_started", agents=len(agents), tasks=len(tasks))

        # Distribute tasks to agents
        agent_tasks = {}
        for i, task in enumerate(tasks):
            agent_id = agents[i % len(agents)]
            if agent_id not in agent_tasks:
                agent_tasks[agent_id] = []
            agent_tasks[agent_id].append(task)

        # Execute in parallel
        execution_futures = []
        for agent_id, assigned_tasks in agent_tasks.items():
            future = task_executor(agent_id, assigned_tasks)
            execution_futures.append(future)

        # Wait for all to complete
        results = await asyncio.gather(*execution_futures, return_exceptions=True)

        # Collect results
        all_results = []
        errors = []

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                errors.append(str(result))
            else:
                all_results.append(result)

        return {
            "results": all_results,
            "errors": errors,
            "success": len(errors) == 0,
            "completed_tasks": len(all_results),
        }


class SequentialDelegationPattern:
    """Sequential delegation pattern - staged workflow."""

    @staticmethod
    async def execute(orchestrator: str,
                     planner: str,
                     executors: List[str],
                     reviewer: str,
                     task: Dict[str, Any],
                     stage_executor: Callable) -> Dict[str, Any]:
        """Execute in sequential stages."""
        logger.info("sequential_delegation_started",
                   orchestrator=orchestrator,
                   planner=planner,
                   executors=len(executors),
                   reviewer=reviewer)

        stages = []

        # Stage 1: Planning
        logger.info("stage_planning", agent=planner)
        plan_result = await stage_executor(planner, "plan", task)
        stages.append({"stage": "planning", "agent": planner, "result": plan_result})

        if not plan_result.get("success"):
            return {"success": False, "error": "Planning failed", "stages": stages}

        # Stage 2: Execution
        logger.info("stage_execution", agents=len(executors))
        exec_results = []
        for executor in executors:
            exec_result = await stage_executor(executor, "execute", plan_result.get("plan"))
            exec_results.append(exec_result)

        stages.append({"stage": "execution", "agents": executors, "results": exec_results})

        # Check if any execution failed
        if not all(r.get("success") for r in exec_results):
            return {"success": False, "error": "Execution failed", "stages": stages}

        # Stage 3: Review
        logger.info("stage_review", agent=reviewer)
        review_result = await stage_executor(reviewer, "review", exec_results)
        stages.append({"stage": "review", "agent": reviewer, "result": review_result})

        # Stage 4: Orchestrator approval
        logger.info("stage_approval", agent=orchestrator)
        approval = await stage_executor(orchestrator, "approve", review_result)
        stages.append({"stage": "approval", "agent": orchestrator, "result": approval})

        return {
            "success": approval.get("approved", False),
            "stages": stages,
            "final_result": approval.get("result"),
        }


class ConsensusReviewPattern:
    """Consensus review pattern - democratic decision making."""

    @staticmethod
    async def execute(reviewers: List[str],
                     artifact: Any,
                     threshold: float,
                     review_executor: Callable) -> Dict[str, Any]:
        """Execute consensus-based review."""
        logger.info("consensus_review_started",
                   reviewers=len(reviewers),
                   threshold=threshold)

        # Collect reviews from all reviewers
        review_futures = [
            review_executor(reviewer, artifact)
            for reviewer in reviewers
        ]

        reviews = await asyncio.gather(*review_futures, return_exceptions=True)

        # Count approvals
        valid_reviews = []
        errors = []

        for review in reviews:
            if isinstance(review, Exception):
                errors.append(str(review))
            else:
                valid_reviews.append(review)

        if not valid_reviews:
            return {
                "success": False,
                "error": "No valid reviews",
                "consensus_achieved": False,
            }

        approvals = sum(1 for r in valid_reviews if r.get("approved", False))
        approval_rate = approvals / len(valid_reviews)

        consensus_achieved = approval_rate >= threshold

        return {
            "success": True,
            "consensus_achieved": consensus_achieved,
            "approval_rate": approval_rate,
            "approvals": approvals,
            "total_reviews": len(valid_reviews),
            "reviews": valid_reviews,
            "errors": errors,
        }


class ExpertOverridePattern:
    """Expert override pattern - domain specialist has final say."""

    @staticmethod
    async def execute(general_agents: List[str],
                     expert: str,
                     task: Dict[str, Any],
                     agent_executor: Callable) -> Dict[str, Any]:
        """Execute with expert override capability."""
        logger.info("expert_override_started",
                   general_agents=len(general_agents),
                   expert=expert)

        # Get solutions from general agents
        general_futures = [
            agent_executor(agent, task)
            for agent in general_agents
        ]

        general_results = await asyncio.gather(*general_futures, return_exceptions=True)

        # Filter valid results
        valid_results = [
            r for r in general_results
            if not isinstance(r, Exception)
        ]

        # Expert reviews and potentially overrides
        logger.info("expert_review", expert=expert)
        expert_review = await agent_executor(expert, {
            "task": task,
            "general_solutions": valid_results,
        })

        # Check if expert overrides
        override = expert_review.get("override", False)

        if override:
            logger.info("expert_override_triggered", expert=expert)
            final_result = expert_review.get("expert_solution")
            decision_maker = expert
        else:
            # Use best general solution (expert endorses)
            final_result = expert_review.get("endorsed_solution")
            decision_maker = "general_consensus"

        return {
            "success": True,
            "override_triggered": override,
            "decision_maker": decision_maker,
            "general_solutions": len(valid_results),
            "final_result": final_result,
            "expert_reasoning": expert_review.get("reasoning", ""),
        }


class CollaborationPatterns:
    """Collaboration patterns orchestrator."""

    def __init__(self, state_dir: Optional[Path] = None):
        """Initialize collaboration patterns."""
        self.state_dir = state_dir or Path.home() / ".cache" / "ai-harness" / "patterns"
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.pattern_configs: Dict[PatternType, PatternConfig] = self._default_configs()
        self.execution_history: List[Dict[str, Any]] = []
        self.pattern_performance: Dict[PatternType, Dict[str, Any]] = {}

        self._load_state()

    def _default_configs(self) -> Dict[PatternType, PatternConfig]:
        """Default pattern configurations."""
        return {
            PatternType.PARALLEL: PatternConfig(
                pattern_type=PatternType.PARALLEL,
                min_agents=2,
                max_agents=10,
            ),
            PatternType.SEQUENTIAL: PatternConfig(
                pattern_type=PatternType.SEQUENTIAL,
                min_agents=4,
                max_agents=6,
            ),
            PatternType.CONSENSUS: PatternConfig(
                pattern_type=PatternType.CONSENSUS,
                min_agents=3,
                max_agents=7,
            ),
            PatternType.EXPERT_OVERRIDE: PatternConfig(
                pattern_type=PatternType.EXPERT_OVERRIDE,
                min_agents=2,
                max_agents=5,
            ),
        }

    def _load_state(self):
        """Load state from disk."""
        history_file = self.state_dir / "execution_history.json"
        performance_file = self.state_dir / "pattern_performance.json"

        try:
            if history_file.exists():
                with open(history_file) as f:
                    data = json.load(f)
                    self.execution_history = data.get("history", [])
        except Exception as e:
            logger.warning(f"Failed to load execution history: {e}")

        try:
            if performance_file.exists():
                with open(performance_file) as f:
                    data = json.load(f)
                    for pattern_str, perf in data.get("performance", {}).items():
                        pattern = PatternType(pattern_str)
                        self.pattern_performance[pattern] = perf
        except Exception as e:
            logger.warning(f"Failed to load pattern performance: {e}")

    def _save_state(self):
        """Save state to disk."""
        history_file = self.state_dir / "execution_history.json"
        performance_file = self.state_dir / "pattern_performance.json"

        try:
            # Keep last 100 executions
            recent_history = self.execution_history[-100:]
            with open(history_file, 'w') as f:
                json.dump({"history": recent_history}, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save execution history: {e}")

        try:
            perf_dict = {
                pattern.value: perf
                for pattern, perf in self.pattern_performance.items()
            }
            with open(performance_file, 'w') as f:
                json.dump({"performance": perf_dict}, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save pattern performance: {e}")

    def select_pattern(self, task_characteristics: List[TaskCharacteristic]) -> PatternType:
        """Select best pattern based on task characteristics."""
        # Simple heuristic-based selection
        char_set = set(task_characteristics)

        if TaskCharacteristic.INDEPENDENT_SUBTASKS in char_set:
            return PatternType.PARALLEL

        if TaskCharacteristic.SEQUENTIAL_DEPENDENCIES in char_set:
            return PatternType.SEQUENTIAL

        if TaskCharacteristic.HIGH_STAKES in char_set:
            return PatternType.CONSENSUS

        if TaskCharacteristic.DOMAIN_SPECIFIC in char_set:
            return PatternType.EXPERT_OVERRIDE

        # Default to parallel for general tasks
        return PatternType.PARALLEL

    async def execute_pattern(self,
                            pattern_type: PatternType,
                            task_id: str,
                            team_id: str,
                            agents: List[str],
                            task_data: Any,
                            executor_callback: Callable) -> PatternExecution:
        """Execute a collaboration pattern."""
        execution_id = str(uuid.uuid4())

        execution = PatternExecution(
            execution_id=execution_id,
            pattern_type=pattern_type,
            task_id=task_id,
            team_id=team_id,
            agents=agents,
            status="running",
            start_time=datetime.now(timezone.utc),
        )

        logger.info("pattern_execution_started",
                   execution_id=execution_id,
                   pattern=pattern_type.value,
                   agents=len(agents))

        try:
            if pattern_type == PatternType.PARALLEL:
                result = await ParallelExecutionPattern.execute(
                    agents=agents,
                    tasks=task_data.get("tasks", []),
                    task_executor=executor_callback,
                )

            elif pattern_type == PatternType.SEQUENTIAL:
                result = await SequentialDelegationPattern.execute(
                    orchestrator=agents[0] if agents else "",
                    planner=agents[1] if len(agents) > 1 else agents[0],
                    executors=agents[2:-1] if len(agents) > 3 else agents[1:],
                    reviewer=agents[-1] if len(agents) > 1 else agents[0],
                    task=task_data,
                    stage_executor=executor_callback,
                )

            elif pattern_type == PatternType.CONSENSUS:
                result = await ConsensusReviewPattern.execute(
                    reviewers=agents,
                    artifact=task_data.get("artifact"),
                    threshold=task_data.get("threshold", 0.66),
                    review_executor=executor_callback,
                )

            elif pattern_type == PatternType.EXPERT_OVERRIDE:
                expert = task_data.get("expert", agents[0])
                general = [a for a in agents if a != expert]
                result = await ExpertOverridePattern.execute(
                    general_agents=general,
                    expert=expert,
                    task=task_data,
                    agent_executor=executor_callback,
                )

            else:
                raise ValueError(f"Unknown pattern type: {pattern_type}")

            execution.status = "success" if result.get("success") else "failure"
            execution.result = result

        except Exception as e:
            execution.status = "failure"
            execution.error = str(e)
            logger.error("pattern_execution_failed",
                        execution_id=execution_id,
                        error=str(e))

        execution.end_time = datetime.now(timezone.utc)
        execution.duration = int((execution.end_time - execution.start_time).total_seconds())

        # Record execution
        self.execution_history.append({
            "execution_id": execution_id,
            "pattern": pattern_type.value,
            "task_id": task_id,
            "success": execution.status == "success",
            "duration": execution.duration,
            "agents": len(agents),
            "timestamp": execution.end_time.isoformat(),
        })

        # Update performance metrics
        self._update_performance(pattern_type, execution)

        self._save_state()

        logger.info("pattern_execution_completed",
                   execution_id=execution_id,
                   pattern=pattern_type.value,
                   status=execution.status,
                   duration=execution.duration)

        return execution

    def _update_performance(self, pattern_type: PatternType, execution: PatternExecution):
        """Update pattern performance metrics."""
        if pattern_type not in self.pattern_performance:
            self.pattern_performance[pattern_type] = {
                "total_executions": 0,
                "successful_executions": 0,
                "total_duration": 0,
                "success_rate": 0.0,
                "avg_duration": 0,
            }

        perf = self.pattern_performance[pattern_type]
        perf["total_executions"] += 1

        if execution.status == "success":
            perf["successful_executions"] += 1

        perf["total_duration"] += execution.duration
        perf["success_rate"] = perf["successful_executions"] / perf["total_executions"]
        perf["avg_duration"] = perf["total_duration"] // perf["total_executions"]

    def get_pattern_metrics(self) -> Dict[str, Any]:
        """Get pattern performance metrics."""
        metrics = {}

        for pattern_type in PatternType:
            perf = self.pattern_performance.get(pattern_type, {
                "total_executions": 0,
                "success_rate": 0.0,
                "avg_duration": 0,
            })

            metrics[pattern_type.value] = {
                "executions": perf.get("total_executions", 0),
                "success_rate": round(perf.get("success_rate", 0.0), 3),
                "avg_duration": perf.get("avg_duration", 0),
            }

        return metrics

    def recommend_pattern(self,
                         task_characteristics: List[TaskCharacteristic],
                         available_agents: int) -> Tuple[PatternType, float]:
        """Recommend pattern with confidence score."""
        # Select base pattern
        pattern = self.select_pattern(task_characteristics)

        # Check if enough agents
        config = self.pattern_configs[pattern]
        if available_agents < config.min_agents:
            # Fallback to pattern requiring fewer agents
            pattern = PatternType.PARALLEL
            confidence = 0.5
        else:
            # Calculate confidence based on historical performance
            perf = self.pattern_performance.get(pattern)
            if perf:
                confidence = perf.get("success_rate", 0.5)
            else:
                confidence = 0.7  # Default confidence

        return pattern, confidence
