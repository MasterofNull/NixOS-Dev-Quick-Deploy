#!/usr/bin/env python3
"""
Reflexion Pattern Implementation (Self-Reflection + Learning)

Implements the Reflexion pattern for agentic AI systems:
- Actor: Execute tasks using available tools
- Evaluator: Assess task completion and quality
- Self-Reflection: Generate insights from failures
- Memory: Store reflections for future attempts
- Retry: Improve performance using accumulated wisdom

Part of Phase 4 Batch 4.1: Agentic Pattern Library

Reference: "Reflexion: Language Agents with Verbal Reinforcement Learning"
https://arxiv.org/abs/2303.11366
"""

import asyncio
import json
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class ReflexionOutcome(Enum):
    """Outcome of a reflexion attempt"""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"
    TIMEOUT = "timeout"


@dataclass
class Reflection:
    """A single reflection from a failed attempt"""
    attempt_number: int
    outcome: ReflexionOutcome
    error_description: str
    insight: str
    suggested_improvement: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ReflexionAttempt:
    """Single attempt in reflexion loop"""
    attempt_number: int
    task: str
    action_trace: List[Dict[str, Any]]
    result: Any
    outcome: ReflexionOutcome
    evaluation_score: float  # 0.0-1.0
    reflection: Optional[Reflection] = None
    duration_ms: float = 0.0


@dataclass
class ReflexionResult:
    """Final result of reflexion execution"""
    task: str
    success: bool
    final_answer: Optional[Any]
    attempts: List[ReflexionAttempt]
    total_attempts: int
    accumulated_reflections: List[Reflection]
    final_score: float
    learning_applied: bool


class ReflexionMemory:
    """Long-term memory for reflexion insights"""

    def __init__(self, max_reflections: int = 100, persistence_path: Optional[Path] = None):
        self.max_reflections = max_reflections
        self.persistence_path = persistence_path
        self.reflections: deque[Reflection] = deque(maxlen=max_reflections)
        self.task_reflections: Dict[str, List[Reflection]] = {}

        if persistence_path and persistence_path.exists():
            self._load()

    def add_reflection(self, task_type: str, reflection: Reflection):
        """Add reflection to memory"""
        self.reflections.append(reflection)

        if task_type not in self.task_reflections:
            self.task_reflections[task_type] = []
        self.task_reflections[task_type].append(reflection)

        if self.persistence_path:
            self._save()

        logger.info(f"Reflexion memory: Added reflection for {task_type}")

    def get_relevant_reflections(self, task_type: str, limit: int = 5) -> List[Reflection]:
        """Get relevant reflections for a task type"""
        task_specific = self.task_reflections.get(task_type, [])
        return task_specific[-limit:] if task_specific else []

    def get_all_insights(self) -> List[str]:
        """Get all accumulated insights"""
        return [r.insight for r in self.reflections]

    def _save(self):
        """Persist reflections to disk"""
        if not self.persistence_path:
            return

        data = {
            "reflections": [
                {
                    "attempt_number": r.attempt_number,
                    "outcome": r.outcome.value,
                    "error_description": r.error_description,
                    "insight": r.insight,
                    "suggested_improvement": r.suggested_improvement,
                    "timestamp": r.timestamp.isoformat(),
                }
                for r in self.reflections
            ],
            "task_reflections": {
                k: [
                    {
                        "attempt_number": r.attempt_number,
                        "outcome": r.outcome.value,
                        "error_description": r.error_description,
                        "insight": r.insight,
                        "suggested_improvement": r.suggested_improvement,
                        "timestamp": r.timestamp.isoformat(),
                    }
                    for r in v
                ]
                for k, v in self.task_reflections.items()
            },
        }

        self.persistence_path.parent.mkdir(parents=True, exist_ok=True)
        self.persistence_path.write_text(json.dumps(data, indent=2))

    def _load(self):
        """Load reflections from disk"""
        if not self.persistence_path or not self.persistence_path.exists():
            return

        try:
            data = json.loads(self.persistence_path.read_text())

            for r_data in data.get("reflections", []):
                reflection = Reflection(
                    attempt_number=r_data["attempt_number"],
                    outcome=ReflexionOutcome(r_data["outcome"]),
                    error_description=r_data["error_description"],
                    insight=r_data["insight"],
                    suggested_improvement=r_data["suggested_improvement"],
                    timestamp=datetime.fromisoformat(r_data["timestamp"]),
                )
                self.reflections.append(reflection)

            for task_type, reflections in data.get("task_reflections", {}).items():
                self.task_reflections[task_type] = [
                    Reflection(
                        attempt_number=r["attempt_number"],
                        outcome=ReflexionOutcome(r["outcome"]),
                        error_description=r["error_description"],
                        insight=r["insight"],
                        suggested_improvement=r["suggested_improvement"],
                        timestamp=datetime.fromisoformat(r["timestamp"]),
                    )
                    for r in reflections
                ]

            logger.info(f"Loaded {len(self.reflections)} reflections from memory")
        except Exception as e:
            logger.warning(f"Failed to load reflexion memory: {e}")


class ReflexionAgent:
    """Reflexion agent with self-reflection and learning"""

    def __init__(
        self,
        actor: Callable,
        evaluator: Callable,
        reflector: Optional[Callable] = None,
        memory: Optional[ReflexionMemory] = None,
        max_attempts: int = 3,
        success_threshold: float = 0.8,
    ):
        """
        Initialize Reflexion agent.

        Args:
            actor: Function that executes the task (task, context) -> result
            evaluator: Function that evaluates result (task, result) -> score (0-1)
            reflector: Optional custom reflector (task, result, score) -> Reflection
            memory: Optional persistent memory for reflections
            max_attempts: Maximum retry attempts
            success_threshold: Score threshold for success (0-1)
        """
        self.actor = actor
        self.evaluator = evaluator
        self.reflector = reflector or self._default_reflector
        self.memory = memory or ReflexionMemory()
        self.max_attempts = max_attempts
        self.success_threshold = success_threshold

        logger.info(
            f"Reflexion agent initialized "
            f"(max_attempts={max_attempts}, threshold={success_threshold})"
        )

    async def solve(self, task: str, task_type: str = "general") -> ReflexionResult:
        """
        Solve a task using reflexion pattern.

        The agent will:
        1. Retrieve relevant past reflections
        2. Execute the task with accumulated wisdom
        3. Evaluate the result
        4. If failed, reflect and retry with new insights
        5. Continue until success or max attempts reached
        """
        logger.info(f"Reflexion: Solving task: {task}")

        attempts: List[ReflexionAttempt] = []
        accumulated_reflections: List[Reflection] = []

        # Get relevant past reflections
        past_reflections = self.memory.get_relevant_reflections(task_type)
        if past_reflections:
            logger.info(f"Retrieved {len(past_reflections)} past reflections")
            accumulated_reflections.extend(past_reflections)

        for attempt_num in range(1, self.max_attempts + 1):
            logger.info(f"Reflexion attempt {attempt_num}/{self.max_attempts}")

            # Build context from accumulated reflections
            context = self._build_context(task, accumulated_reflections)

            # Execute task
            start_time = datetime.now()
            try:
                if asyncio.iscoroutinefunction(self.actor):
                    result = await self.actor(task, context)
                else:
                    result = self.actor(task, context)
                action_trace = result.get("trace", []) if isinstance(result, dict) else []
                actual_result = result.get("result", result) if isinstance(result, dict) else result
            except Exception as e:
                logger.warning(f"Actor failed: {e}")
                result = None
                actual_result = None
                action_trace = [{"error": str(e)}]

            duration_ms = (datetime.now() - start_time).total_seconds() * 1000

            # Evaluate result
            try:
                if asyncio.iscoroutinefunction(self.evaluator):
                    score = await self.evaluator(task, actual_result)
                else:
                    score = self.evaluator(task, actual_result)
            except Exception as e:
                logger.warning(f"Evaluator failed: {e}")
                score = 0.0

            # Determine outcome
            if score >= self.success_threshold:
                outcome = ReflexionOutcome.SUCCESS
            elif score >= 0.5:
                outcome = ReflexionOutcome.PARTIAL
            else:
                outcome = ReflexionOutcome.FAILURE

            attempt = ReflexionAttempt(
                attempt_number=attempt_num,
                task=task,
                action_trace=action_trace,
                result=actual_result,
                outcome=outcome,
                evaluation_score=score,
                duration_ms=duration_ms,
            )

            # Success - return result
            if outcome == ReflexionOutcome.SUCCESS:
                attempts.append(attempt)
                logger.info(f"Reflexion: Success on attempt {attempt_num} (score={score:.2f})")

                return ReflexionResult(
                    task=task,
                    success=True,
                    final_answer=actual_result,
                    attempts=attempts,
                    total_attempts=attempt_num,
                    accumulated_reflections=accumulated_reflections,
                    final_score=score,
                    learning_applied=len(past_reflections) > 0,
                )

            # Failed - reflect and retry
            logger.info(f"Reflexion: Attempt {attempt_num} failed (score={score:.2f}), reflecting...")

            reflection = await self._generate_reflection(
                attempt_num, task, actual_result, score, action_trace
            )
            attempt.reflection = reflection
            attempts.append(attempt)

            # Store reflection
            accumulated_reflections.append(reflection)
            self.memory.add_reflection(task_type, reflection)

        # Max attempts reached
        final_attempt = attempts[-1] if attempts else None
        final_score = final_attempt.evaluation_score if final_attempt else 0.0

        logger.warning(f"Reflexion: Max attempts reached, final score={final_score:.2f}")

        return ReflexionResult(
            task=task,
            success=False,
            final_answer=final_attempt.result if final_attempt else None,
            attempts=attempts,
            total_attempts=len(attempts),
            accumulated_reflections=accumulated_reflections,
            final_score=final_score,
            learning_applied=len(past_reflections) > 0,
        )

    def _build_context(self, task: str, reflections: List[Reflection]) -> Dict[str, Any]:
        """Build context from accumulated reflections"""
        if not reflections:
            return {"task": task, "reflections": [], "insights": []}

        insights = [r.insight for r in reflections]
        improvements = [r.suggested_improvement for r in reflections]

        return {
            "task": task,
            "reflections": [
                {
                    "attempt": r.attempt_number,
                    "error": r.error_description,
                    "insight": r.insight,
                    "improvement": r.suggested_improvement,
                }
                for r in reflections
            ],
            "insights": insights,
            "suggested_improvements": improvements,
            "accumulated_wisdom": "\n".join(
                f"- {r.insight}: {r.suggested_improvement}" for r in reflections
            ),
        }

    async def _generate_reflection(
        self,
        attempt_num: int,
        task: str,
        result: Any,
        score: float,
        action_trace: List[Dict],
    ) -> Reflection:
        """Generate reflection from failed attempt"""
        try:
            if asyncio.iscoroutinefunction(self.reflector):
                return await self.reflector(attempt_num, task, result, score, action_trace)
            else:
                return self.reflector(attempt_num, task, result, score, action_trace)
        except Exception as e:
            logger.warning(f"Custom reflector failed: {e}, using default")
            return self._default_reflector(attempt_num, task, result, score, action_trace)

    def _default_reflector(
        self,
        attempt_num: int,
        task: str,
        result: Any,
        score: float,
        action_trace: List[Dict],
    ) -> Reflection:
        """Default reflection generator"""
        # Analyze action trace for errors
        errors = [a.get("error", "") for a in action_trace if a.get("error")]
        error_description = "; ".join(errors) if errors else f"Score {score:.2f} below threshold"

        # Generate insight based on common failure patterns
        if "timeout" in error_description.lower():
            insight = "Task took too long to complete"
            improvement = "Break task into smaller steps or increase timeout"
        elif "not found" in error_description.lower():
            insight = "Required resource or information was missing"
            improvement = "Verify prerequisites before attempting task"
        elif score < 0.3:
            insight = "Approach was fundamentally wrong"
            improvement = "Reconsider the problem from a different angle"
        elif score < 0.5:
            insight = "Approach was partially correct but incomplete"
            improvement = "Add missing steps or handle edge cases"
        else:
            insight = "Approach was close but needs refinement"
            improvement = "Fine-tune the final steps of the solution"

        return Reflection(
            attempt_number=attempt_num,
            outcome=ReflexionOutcome.FAILURE if score < 0.5 else ReflexionOutcome.PARTIAL,
            error_description=error_description,
            insight=insight,
            suggested_improvement=improvement,
        )


# Convenience function for simple usage
async def reflexion_solve(
    task: str,
    actor: Callable,
    evaluator: Callable,
    max_attempts: int = 3,
    success_threshold: float = 0.8,
) -> ReflexionResult:
    """
    Solve a task using reflexion pattern.

    Simple interface for one-off reflexion tasks without persistent memory.

    Example:
        async def my_actor(task, context):
            # Execute task with context
            return {"result": "answer", "trace": [...]}

        def my_evaluator(task, result):
            # Return score 0-1
            return 0.9 if result == expected else 0.0

        result = await reflexion_solve(
            task="Write a function to sort a list",
            actor=my_actor,
            evaluator=my_evaluator,
        )
    """
    agent = ReflexionAgent(
        actor=actor,
        evaluator=evaluator,
        max_attempts=max_attempts,
        success_threshold=success_threshold,
    )
    return await agent.solve(task)
