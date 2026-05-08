#!/usr/bin/env python3
"""
Delegation Protocol

Enables local agents to delegate tasks to remote agents (Claude, OpenRouter, etc.)
with standardized task format, context provision, and result collection.

Part of Phase 12 Batch 12.1: Autonomous Agentic Orchestration
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import aiohttp

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """Type of task to delegate."""
    IMPLEMENTATION = "implementation"
    REFACTORING = "refactoring"
    DOCUMENTATION = "documentation"
    TESTING = "testing"
    ANALYSIS = "analysis"
    PLANNING = "planning"


class AgentPreference(Enum):
    """Which type of agent to use."""
    LOCAL = "local"  # Use local llama.cpp agent
    REMOTE = "remote"  # Use remote Claude/OpenRouter
    ANY = "any"  # System chooses best
    CLAUDE = "claude"  # Specifically Claude
    OPENROUTER = "openrouter"  # Specifically OpenRouter
    FLAGSHIP = "flagship"  # Best quality (Claude Opus)


class TaskStatus(Enum):
    """Status of delegated task."""
    PENDING = "pending"
    DELEGATED = "delegated"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class TaskContext:
    """Context information for a task."""

    # Files to read
    files_to_read: List[str] = field(default_factory=list)

    # Relevant documentation
    relevant_docs: List[str] = field(default_factory=list)

    # Hints/queries for context
    hints: List[str] = field(default_factory=list)

    # Dependencies
    depends_on: List[str] = field(default_factory=list)

    # Environment info
    environment: Dict[str, str] = field(default_factory=dict)


@dataclass
class TaskConstraints:
    """Constraints for task execution."""

    # Maximum files that can be changed
    max_files_changed: int = 10

    # Require tests for implementation
    require_tests: bool = True

    # Safety level
    safety_level: str = "medium"  # low, medium, high

    # Maximum lines of code
    max_lines_added: int = 1000

    # Timeout
    timeout_seconds: int = 600


@dataclass
class DelegatedTask:
    """A task delegated to an agent."""

    # Task identification
    task_id: str
    task_type: TaskType
    description: str

    # Context and constraints
    context: TaskContext = field(default_factory=TaskContext)
    acceptance_criteria: List[str] = field(default_factory=list)
    constraints: TaskConstraints = field(default_factory=TaskConstraints)

    # Agent selection
    agent_preference: AgentPreference = AgentPreference.ANY

    # Status tracking
    status: TaskStatus = TaskStatus.PENDING
    assigned_agent: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    # Budget
    max_cost_usd: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "task_id": self.task_id,
            "type": self.task_type.value,
            "description": self.description,
            "context": {
                "files_to_read": self.context.files_to_read,
                "relevant_docs": self.context.relevant_docs,
                "hints": self.context.hints,
                "depends_on": self.context.depends_on,
                "environment": self.context.environment,
            },
            "acceptance_criteria": self.acceptance_criteria,
            "constraints": {
                "max_files_changed": self.constraints.max_files_changed,
                "require_tests": self.constraints.require_tests,
                "safety_level": self.constraints.safety_level,
                "max_lines_added": self.constraints.max_lines_added,
                "timeout_seconds": self.constraints.timeout_seconds,
            },
            "agent_preference": self.agent_preference.value,
            "max_cost_usd": self.max_cost_usd,
        }


@dataclass
class FileChange:
    """A file change made by an agent."""

    file_path: str
    action: str  # modified, created, deleted
    diff: Optional[str] = None
    lines_added: int = 0
    lines_removed: int = 0
    content: Optional[str] = None  # Full content for new files


@dataclass
class ValidationResults:
    """Validation results for agent output."""

    syntax_check: str = "not_run"  # passed, failed, not_run
    tests: str = "not_run"
    linting: str = "not_run"
    security_scan: str = "not_run"
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class AgentQuestion:
    """A question from an agent that needs answering."""

    question: str
    options: List[str]
    recommendation: Optional[str] = None
    priority: str = "medium"  # low, medium, high


@dataclass
class TaskResult:
    """Result of a delegated task."""

    task_id: str
    status: TaskStatus
    changes: List[FileChange] = field(default_factory=list)
    validation_results: ValidationResults = field(default_factory=ValidationResults)
    questions: List[AgentQuestion] = field(default_factory=list)
    execution_time_seconds: float = 0.0
    agent_used: Optional[str] = None
    quality_score: float = 0.0
    cost_usd: float = 0.0
    error: Optional[str] = None
    output: str = ""


class ClaudeAPIClient:
    """
    Client for delegating tasks to Claude via API.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Claude API client.

        Args:
            api_key: Anthropic API key (reads from env if not provided)
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            logger.warning("No ANTHROPIC_API_KEY found - Claude delegation will fail")

        self.api_url = "https://api.anthropic.com/v1/messages"
        self.default_model = "claude-sonnet-4-5-20250929"
        self.max_tokens = 8192

    async def delegate_task(
        self,
        task: DelegatedTask,
        model: Optional[str] = None,
    ) -> TaskResult:
        """
        Delegate task to Claude.

        Args:
            task: Task to delegate
            model: Override default model

        Returns:
            TaskResult with Claude's response
        """
        start_time = time.time()

        # Build prompt for Claude
        prompt = self._build_task_prompt(task)

        # Call Claude API
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                }

                payload = {
                    "model": model or self.default_model,
                    "max_tokens": self.max_tokens,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt,
                        }
                    ],
                }

                async with session.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=task.constraints.timeout_seconds),
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Claude API error: {response.status} - {error_text}")
                        return TaskResult(
                            task_id=task.task_id,
                            status=TaskStatus.FAILED,
                            error=f"API error: {response.status}",
                            execution_time_seconds=time.time() - start_time,
                        )

                    data = await response.json()

                    # Extract response
                    content = data.get("content", [])
                    if content and len(content) > 0:
                        text_content = content[0].get("text", "")
                    else:
                        text_content = ""

                    # Parse result
                    result = self._parse_claude_response(
                        task,
                        text_content,
                        data.get("usage", {}),
                    )

                    result.execution_time_seconds = time.time() - start_time
                    result.agent_used = model or self.default_model

                    return result

        except asyncio.TimeoutError:
            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                error=f"Timeout after {task.constraints.timeout_seconds}s",
                execution_time_seconds=time.time() - start_time,
            )
        except Exception as e:
            logger.exception(f"Claude delegation error: {e}")
            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                error=str(e),
                execution_time_seconds=time.time() - start_time,
            )

    def _build_task_prompt(self, task: DelegatedTask) -> str:
        """
        Build prompt for Claude from task.

        Args:
            task: Task to convert to prompt

        Returns:
            Prompt string
        """
        prompt_parts = []

        # Task description
        prompt_parts.append(f"# Task: {task.description}\n")
        prompt_parts.append(f"**Type:** {task.task_type.value}\n")
        prompt_parts.append(f"**Task ID:** {task.task_id}\n\n")

        # Context
        if task.context.files_to_read:
            prompt_parts.append("## Files to Review\n")
            for file_path in task.context.files_to_read:
                prompt_parts.append(f"- {file_path}\n")
            prompt_parts.append("\n")

        if task.context.relevant_docs:
            prompt_parts.append("## Relevant Documentation\n")
            for doc in task.context.relevant_docs:
                prompt_parts.append(f"- {doc}\n")
            prompt_parts.append("\n")

        if task.context.hints:
            prompt_parts.append("## Hints\n")
            for hint in task.context.hints:
                prompt_parts.append(f"- {hint}\n")
            prompt_parts.append("\n")

        # Acceptance criteria
        if task.acceptance_criteria:
            prompt_parts.append("## Acceptance Criteria\n")
            for i, criterion in enumerate(task.acceptance_criteria, 1):
                prompt_parts.append(f"{i}. {criterion}\n")
            prompt_parts.append("\n")

        # Constraints
        prompt_parts.append("## Constraints\n")
        prompt_parts.append(f"- Maximum files changed: {task.constraints.max_files_changed}\n")
        prompt_parts.append(f"- Maximum lines added: {task.constraints.max_lines_added}\n")
        prompt_parts.append(f"- Require tests: {task.constraints.require_tests}\n")
        prompt_parts.append(f"- Safety level: {task.constraints.safety_level}\n")
        prompt_parts.append(f"- Timeout: {task.constraints.timeout_seconds}s\n\n")

        # Instructions
        prompt_parts.append("## Instructions\n\n")
        prompt_parts.append("Please complete this task following the acceptance criteria and constraints.\n\n")
        prompt_parts.append("**Format your response as JSON:**\n\n")
        prompt_parts.append("```json\n")
        prompt_parts.append("{\n")
        prompt_parts.append('  "status": "completed" | "failed" | "blocked",\n')
        prompt_parts.append('  "changes": [\n')
        prompt_parts.append('    {\n')
        prompt_parts.append('      "file_path": "path/to/file",\n')
        prompt_parts.append('      "action": "modified" | "created" | "deleted",\n')
        prompt_parts.append('      "content": "full file content for new/modified files",\n')
        prompt_parts.append('      "lines_added": 10,\n')
        prompt_parts.append('      "lines_removed": 2\n')
        prompt_parts.append('    }\n')
        prompt_parts.append('  ],\n')
        prompt_parts.append('  "questions": [\n')
        prompt_parts.append('    {\n')
        prompt_parts.append('      "question": "Should I add feature X?",\n')
        prompt_parts.append('      "options": ["yes", "no", "defer"],\n')
        prompt_parts.append('      "recommendation": "yes"\n')
        prompt_parts.append('    }\n')
        prompt_parts.append('  ],\n')
        prompt_parts.append('  "output": "Summary of changes made"\n')
        prompt_parts.append('}\n')
        prompt_parts.append('```\n')

        return "".join(prompt_parts)

    def _parse_claude_response(
        self,
        task: DelegatedTask,
        response_text: str,
        usage: Dict[str, Any],
    ) -> TaskResult:
        """
        Parse Claude's response into TaskResult.

        Args:
            task: Original task
            response_text: Claude's response text
            usage: Token usage from API

        Returns:
            TaskResult
        """
        # Try to extract JSON from response
        try:
            # Look for JSON block
            if "```json" in response_text:
                json_start = response_text.index("```json") + 7
                json_end = response_text.index("```", json_start)
                json_str = response_text[json_start:json_end].strip()
            else:
                # Try to parse entire response as JSON
                json_str = response_text.strip()

            data = json.loads(json_str)

            # Parse changes
            changes = []
            for change_data in data.get("changes", []):
                changes.append(FileChange(
                    file_path=change_data.get("file_path", ""),
                    action=change_data.get("action", "modified"),
                    content=change_data.get("content"),
                    lines_added=change_data.get("lines_added", 0),
                    lines_removed=change_data.get("lines_removed", 0),
                ))

            # Parse questions
            questions = []
            for q_data in data.get("questions", []):
                questions.append(AgentQuestion(
                    question=q_data.get("question", ""),
                    options=q_data.get("options", []),
                    recommendation=q_data.get("recommendation"),
                    priority=q_data.get("priority", "medium"),
                ))

            # Calculate cost (rough estimate)
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
            # Sonnet pricing: ~$3/MTok input, ~$15/MTok output
            cost_usd = (input_tokens / 1_000_000 * 3.0) + (output_tokens / 1_000_000 * 15.0)

            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus(data.get("status", "completed")),
                changes=changes,
                questions=questions,
                output=data.get("output", ""),
                cost_usd=cost_usd,
            )

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"Failed to parse Claude response as JSON: {e}")
            # Return raw response
            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.COMPLETED,
                output=response_text,
            )


class DelegationProtocol:
    """
    Delegation protocol for multi-agent task orchestration.

    Handles task serialization, agent selection, and result collection.
    """

    def __init__(
        self,
        claude_client: Optional[ClaudeAPIClient] = None,
    ):
        """
        Initialize delegation protocol.

        Args:
            claude_client: Claude API client (creates default if None)
        """
        self.claude_client = claude_client or ClaudeAPIClient()

        # Task tracking
        self.active_tasks: Dict[str, DelegatedTask] = {}
        self.completed_tasks: Dict[str, TaskResult] = {}
        self.failed_tasks: Dict[str, TaskResult] = {}

        # Statistics
        self.total_delegations = 0
        self.successful_delegations = 0
        self.failed_delegations = 0
        self.total_cost_usd = 0.0

    async def delegate(
        self,
        task: DelegatedTask,
    ) -> TaskResult:
        """
        Delegate task to appropriate agent.

        Args:
            task: Task to delegate

        Returns:
            TaskResult with outcome
        """
        self.total_delegations += 1
        self.active_tasks[task.task_id] = task

        task.status = TaskStatus.DELEGATED
        task.started_at = time.time()

        try:
            # Select agent based on preference
            if task.agent_preference in (
                AgentPreference.CLAUDE,
                AgentPreference.REMOTE,
                AgentPreference.FLAGSHIP,
                AgentPreference.ANY,
            ):
                # Use Claude
                result = await self.claude_client.delegate_task(task)
            else:
                # TODO: Support local agent delegation
                result = TaskResult(
                    task_id=task.task_id,
                    status=TaskStatus.FAILED,
                    error="Local agent delegation not yet implemented",
                )

            # Update tracking
            if result.status == TaskStatus.COMPLETED:
                self.successful_delegations += 1
                self.completed_tasks[task.task_id] = result
            else:
                self.failed_delegations += 1
                self.failed_tasks[task.task_id] = result

            self.total_cost_usd += result.cost_usd

            del self.active_tasks[task.task_id]

            return result

        except Exception as e:
            logger.exception(f"Delegation error for task {task.task_id}: {e}")
            result = TaskResult(
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                error=str(e),
            )
            self.failed_delegations += 1
            self.failed_tasks[task.task_id] = result
            del self.active_tasks[task.task_id]
            return result

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get delegation statistics.

        Returns:
            Dict with statistics
        """
        success_rate = (
            self.successful_delegations / self.total_delegations
            if self.total_delegations > 0
            else 0.0
        )

        return {
            "total_delegations": self.total_delegations,
            "successful": self.successful_delegations,
            "failed": self.failed_delegations,
            "success_rate": success_rate,
            "active_tasks": len(self.active_tasks),
            "total_cost_usd": self.total_cost_usd,
            "avg_cost_per_task": (
                self.total_cost_usd / self.total_delegations
                if self.total_delegations > 0
                else 0.0
            ),
        }


# Singleton instance
_protocol: Optional[DelegationProtocol] = None


def get_delegation_protocol() -> DelegationProtocol:
    """
    Get global delegation protocol instance.

    Returns:
        DelegationProtocol instance
    """
    global _protocol
    if _protocol is None:
        _protocol = DelegationProtocol()
    return _protocol


# Example usage
async def main():
    """Example usage."""
    protocol = get_delegation_protocol()

    # Create a task
    task = DelegatedTask(
        task_id="test-task-1",
        task_type=TaskType.IMPLEMENTATION,
        description="Add OpenTelemetry instrumentation to AIDB",
        context=TaskContext(
            files_to_read=["ai-stack/aidb/server.py"],
            relevant_docs=["docs/observability/opentelemetry.md"],
            hints=["use aidb opentelemetry"],
        ),
        acceptance_criteria=[
            "All HTTP endpoints instrumented",
            "Metrics exported to Prometheus",
            "Tests pass",
        ],
        constraints=TaskConstraints(
            max_files_changed=3,
            require_tests=True,
            safety_level="medium",
        ),
        agent_preference=AgentPreference.CLAUDE,
        max_cost_usd=0.50,
    )

    # Delegate to Claude
    print(f"Delegating task: {task.task_id}")
    result = await protocol.delegate(task)

    print(f"\nResult:")
    print(f"  Status: {result.status.value}")
    print(f"  Changes: {len(result.changes)} files")
    print(f"  Questions: {len(result.questions)}")
    print(f"  Cost: ${result.cost_usd:.4f}")
    print(f"  Time: {result.execution_time_seconds:.2f}s")

    if result.questions:
        print(f"\n  Questions from agent:")
        for q in result.questions:
            print(f"    - {q.question}")
            print(f"      Options: {', '.join(q.options)}")
            print(f"      Recommendation: {q.recommendation}")

    # Statistics
    stats = protocol.get_statistics()
    print(f"\nStatistics:")
    print(f"  Total delegations: {stats['total_delegations']}")
    print(f"  Success rate: {stats['success_rate']:.1%}")
    print(f"  Total cost: ${stats['total_cost_usd']:.4f}")


if __name__ == "__main__":
    asyncio.run(main())
