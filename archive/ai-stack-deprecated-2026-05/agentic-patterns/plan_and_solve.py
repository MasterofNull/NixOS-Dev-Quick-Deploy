#!/usr/bin/env python3
"""
Plan-and-Solve Pattern

Separates planning from execution so agents can first produce an explicit plan
and then solve the task step by step.

Part of Phase 4: Advanced Agentic Pattern Library
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class PlanStep:
    """A single step in a plan."""
    step_id: str
    description: str
    expected_output: str = ""


@dataclass
class PlanExecutionResult:
    """Final result of executing a plan."""
    objective: str
    plan: List[PlanStep]
    step_outputs: List[Dict[str, Any]] = field(default_factory=list)
    final_answer: Any = None


class PlanAndSolveAgent:
    """Create an explicit plan and execute it incrementally."""

    def __init__(
        self,
        planner: Callable[[str], Awaitable[List[PlanStep] | List[Dict[str, Any]] | List[str]] | List[PlanStep] | List[Dict[str, Any]] | List[str]],
        executor: Callable[[PlanStep, Dict[str, Any]], Awaitable[Any] | Any],
    ) -> None:
        self.planner = planner
        self.executor = executor

    async def solve(self, objective: str) -> PlanExecutionResult:
        """Create a plan and execute its steps in sequence."""
        raw_plan = self.planner(objective)
        if asyncio.iscoroutine(raw_plan):
            raw_plan = await raw_plan
        plan = self._normalize_plan(raw_plan)

        context: Dict[str, Any] = {"objective": objective, "completed_steps": []}
        result = PlanExecutionResult(objective=objective, plan=plan)

        for step in plan:
            output = self.executor(step, context)
            if asyncio.iscoroutine(output):
                output = await output
            step_record = {
                "step_id": step.step_id,
                "description": step.description,
                "output": output,
            }
            result.step_outputs.append(step_record)
            context["completed_steps"].append(step_record)
            context["latest_output"] = output

        if result.step_outputs:
            result.final_answer = result.step_outputs[-1]["output"]
        logger.info("Plan-and-solve completed %s steps", len(result.step_outputs))
        return result

    @staticmethod
    def _normalize_plan(raw_plan: List[PlanStep] | List[Dict[str, Any]] | List[str]) -> List[PlanStep]:
        normalized: List[PlanStep] = []
        for index, item in enumerate(raw_plan or [], start=1):
            step_id = f"step-{index}"
            if isinstance(item, PlanStep):
                normalized.append(item)
            elif isinstance(item, dict):
                normalized.append(
                    PlanStep(
                        step_id=str(item.get("step_id", step_id)),
                        description=str(item.get("description", "")),
                        expected_output=str(item.get("expected_output", "")),
                    )
                )
            else:
                normalized.append(PlanStep(step_id=step_id, description=str(item)))
        return normalized
