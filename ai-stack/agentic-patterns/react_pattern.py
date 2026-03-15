#!/usr/bin/env python3
"""
ReAct Pattern Implementation (Reasoning + Acting)

Implements the ReAct pattern for agentic AI systems:
- Thought: Reason about the current state and next action
- Action: Execute an action using available tools
- Observation: Observe the result of the action
- Repeat until task complete

Part of Phase 4 Batch 4.1: Agentic Pattern Library

Reference: "ReAct: Synergizing Reasoning and Acting in Language Models"
https://arxiv.org/abs/2210.03629
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class ReActStepType(Enum):
    """Type of ReAct step"""
    THOUGHT = "thought"
    ACTION = "action"
    OBSERVATION = "observation"


@dataclass
class ReActStep:
    """Single step in ReAct loop"""
    step_number: int
    step_type: ReActStepType
    content: str
    timestamp: datetime
    metadata: Dict[str, Any] = None


@dataclass
class ReActResult:
    """Result of ReAct execution"""
    task: str
    success: bool
    final_answer: Optional[str]
    steps: List[ReActStep]
    total_steps: int
    reasoning_quality: float  # 0.0-1.0
    error_message: Optional[str] = None


class ReActAgent:
    """ReAct (Reasoning + Acting) agent"""

    def __init__(
        self,
        tools: Dict[str, Callable],
        llm_client: Optional[Any] = None,
        max_iterations: int = 10,
    ):
        self.tools = tools
        self.llm_client = llm_client
        self.max_iterations = max_iterations

        logger.info(
            f"ReAct agent initialized "
            f"({len(tools)} tools, max_iterations={max_iterations})"
        )

    async def solve(self, task: str) -> ReActResult:
        """Solve a task using ReAct pattern"""
        logger.info(f"ReAct: Solving task: {task}")

        steps = []
        step_number = 0

        try:
            for iteration in range(self.max_iterations):
                # Step 1: THOUGHT - Reason about next action
                thought = await self._generate_thought(task, steps)
                step_number += 1

                steps.append(ReActStep(
                    step_number=step_number,
                    step_type=ReActStepType.THOUGHT,
                    content=thought,
                    timestamp=datetime.now(),
                ))

                logger.info(f"  Thought #{iteration + 1}: {thought[:100]}...")

                # Check if task is complete
                if self._is_task_complete(thought):
                    final_answer = self._extract_final_answer(thought, steps)

                    return ReActResult(
                        task=task,
                        success=True,
                        final_answer=final_answer,
                        steps=steps,
                        total_steps=step_number,
                        reasoning_quality=self._assess_reasoning_quality(steps),
                    )

                # Step 2: ACTION - Execute an action
                action, action_input = self._extract_action(thought)

                if action and action in self.tools:
                    step_number += 1
                    steps.append(ReActStep(
                        step_number=step_number,
                        step_type=ReActStepType.ACTION,
                        content=f"Action: {action}({action_input})",
                        timestamp=datetime.now(),
                        metadata={"action": action, "input": action_input},
                    ))

                    logger.info(f"  Action #{iteration + 1}: {action}({action_input})")

                    # Step 3: OBSERVATION - Observe result
                    try:
                        observation = await self._execute_action(action, action_input)
                    except Exception as e:
                        observation = f"Error: {e}"

                    step_number += 1
                    steps.append(ReActStep(
                        step_number=step_number,
                        step_type=ReActStepType.OBSERVATION,
                        content=observation,
                        timestamp=datetime.now(),
                    ))

                    logger.info(f"  Observation #{iteration + 1}: {observation[:100]}...")

            # Max iterations reached
            return ReActResult(
                task=task,
                success=False,
                final_answer=None,
                steps=steps,
                total_steps=step_number,
                reasoning_quality=self._assess_reasoning_quality(steps),
                error_message=f"Max iterations ({self.max_iterations}) reached",
            )

        except Exception as e:
            logger.exception(f"ReAct error: {e}")
            return ReActResult(
                task=task,
                success=False,
                final_answer=None,
                steps=steps,
                total_steps=step_number,
                reasoning_quality=0.0,
                error_message=str(e),
            )

    async def _generate_thought(
        self,
        task: str,
        previous_steps: List[ReActStep],
    ) -> str:
        """Generate next thought"""
        # Build context from previous steps
        context = self._build_context(task, previous_steps)

        # Query LLM for next thought
        if self.llm_client:
            # Would call actual LLM
            thought = await self._query_llm(context)
        else:
            # Fallback: simple rule-based thinking
            thought = self._rule_based_thought(task, previous_steps)

        return thought

    def _build_context(
        self,
        task: str,
        previous_steps: List[ReActStep],
    ) -> str:
        """Build context prompt from previous steps"""
        prompt = f"""Task: {task}

Available tools:
{self._format_tools()}

Think step-by-step about what to do next.

Previous steps:
"""

        for step in previous_steps:
            prompt += f"\n{step.step_type.value.capitalize()}: {step.content}"

        prompt += "\n\nWhat should I do next? Think carefully and then decide on an action."

        return prompt

    def _format_tools(self) -> str:
        """Format available tools"""
        tools_desc = []
        for name, func in self.tools.items():
            doc = func.__doc__ or "No description"
            tools_desc.append(f"- {name}: {doc.strip()}")

        return "\n".join(tools_desc)

    async def _query_llm(self, prompt: str) -> str:
        """Query LLM for thought"""
        # Placeholder - would integrate with actual LLM
        # For now, return a default response
        return "I should search for information to help answer this question."

    def _rule_based_thought(
        self,
        task: str,
        previous_steps: List[ReActStep],
    ) -> str:
        """Simple rule-based thinking (fallback)"""
        if not previous_steps:
            return f"To solve '{task}', I should first gather information using the available tools."

        # Check last step type
        last_step = previous_steps[-1]

        if last_step.step_type == ReActStepType.OBSERVATION:
            return "Based on the observation, I can now formulate an answer."

        return "I should continue gathering information."

    def _is_task_complete(self, thought: str) -> bool:
        """Check if task is complete"""
        completion_keywords = [
            "final answer",
            "the answer is",
            "i can conclude",
            "task complete",
            "finished",
        ]

        thought_lower = thought.lower()
        return any(kw in thought_lower for kw in completion_keywords)

    def _extract_final_answer(
        self,
        thought: str,
        steps: List[ReActStep],
    ) -> str:
        """Extract final answer from thought"""
        # Look for "Final Answer: ..." pattern
        if "final answer:" in thought.lower():
            parts = thought.split(":")
            if len(parts) > 1:
                return parts[1].strip()

        # Fallback: return the thought itself
        return thought

    def _extract_action(self, thought: str) -> tuple[Optional[str], Optional[str]]:
        """Extract action and input from thought"""
        # Look for "Action: tool_name(input)" pattern
        if "action:" in thought.lower():
            # Simple parsing
            parts = thought.lower().split("action:")
            if len(parts) > 1:
                action_part = parts[1].strip()

                # Extract tool name
                if "(" in action_part:
                    tool_name = action_part.split("(")[0].strip()
                    action_input = action_part.split("(")[1].split(")")[0].strip()
                    return tool_name, action_input

        return None, None

    async def _execute_action(self, action: str, action_input: str) -> str:
        """Execute an action"""
        if action not in self.tools:
            return f"Error: Tool '{action}' not found"

        try:
            tool = self.tools[action]

            # Execute tool
            if asyncio.iscoroutinefunction(tool):
                result = await tool(action_input)
            else:
                result = tool(action_input)

            return str(result)

        except Exception as e:
            return f"Error executing {action}: {e}"

    def _assess_reasoning_quality(self, steps: List[ReActStep]) -> float:
        """Assess quality of reasoning"""
        if not steps:
            return 0.0

        # Simple heuristic: more thought steps = better reasoning
        thought_steps = sum(1 for s in steps if s.step_type == ReActStepType.THOUGHT)
        action_steps = sum(1 for s in steps if s.step_type == ReActStepType.ACTION)

        # Good reasoning has balanced thoughts and actions
        if thought_steps == 0 or action_steps == 0:
            return 0.3

        balance = min(thought_steps, action_steps) / max(thought_steps, action_steps)

        return balance


# Example tools
def search_tool(query: str) -> str:
    """Search for information"""
    return f"Search results for: {query}"


def calculator_tool(expression: str) -> str:
    """Calculate mathematical expression"""
    try:
        result = eval(expression)  # In production, use safe math parser
        return f"{expression} = {result}"
    except Exception as e:
        return f"Error: {e}"


async def main():
    """Test ReAct pattern"""
    logging.basicConfig(level=logging.INFO)

    # Create tools
    tools = {
        "search": search_tool,
        "calculator": calculator_tool,
    }

    # Create agent
    agent = ReActAgent(tools=tools, max_iterations=5)

    # Test task
    task = "What is 15 * 23?"

    logger.info("ReAct Pattern Test")
    logger.info("=" * 60)

    result = await agent.solve(task)

    logger.info(f"\nResult:")
    logger.info(f"  Success: {result.success}")
    logger.info(f"  Final Answer: {result.final_answer}")
    logger.info(f"  Total Steps: {result.total_steps}")
    logger.info(f"  Reasoning Quality: {result.reasoning_quality:.2f}")

    logger.info(f"\nSteps:")
    for step in result.steps:
        logger.info(f"  {step.step_number}. {step.step_type.value}: {step.content[:80]}...")


if __name__ == "__main__":
    asyncio.run(main())
