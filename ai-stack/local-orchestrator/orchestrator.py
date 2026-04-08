#!/usr/bin/env python3
"""
Local Orchestrator

Primary AI interface that processes all prompts through local Gemma model,
uses MCP tools for context, and delegates to remote agents when needed.
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .mcp_client import MCPClient, get_mcp_client
from .router import TaskRouter, RouteDecision, AgentBackend, TaskCategory

# Add parent path for autonomous-orchestrator imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from autonomous_orchestrator import (
    DelegatedTask,
    TaskType,
    AgentPreference,
    TaskContext,
    TaskConstraints,
    get_delegation_protocol,
)

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorResponse:
    """Response from orchestrator."""
    action: str  # "direct_response", "delegate", "plan", "error"
    content: str
    backend_used: str
    tokens_used: int = 0
    cost_usd: float = 0.0
    execution_time: float = 0.0
    context_gathered: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class LocalOrchestrator:
    """
    Primary AI orchestrator using local Gemma model.

    All prompts flow through this orchestrator, which:
    1. Gathers context via MCP tools
    2. Routes to appropriate backend
    3. Executes or delegates
    4. Validates and returns results
    """

    def __init__(
        self,
        mcp_client: Optional[MCPClient] = None,
        router: Optional[TaskRouter] = None,
        repo_root: Optional[Path] = None,
        cost_budget: float = 5.0,
    ):
        """
        Initialize orchestrator.

        Args:
            mcp_client: MCP client for tool access
            router: Task router
            repo_root: Repository root
            cost_budget: Session cost budget in USD
        """
        self.mcp = mcp_client or get_mcp_client()
        self.router = router or TaskRouter(cost_budget_usd=cost_budget)
        self.repo_root = repo_root or Path.cwd()

        # Load system prompt
        self.system_prompt = self._load_system_prompt()

        # Session state
        self.conversation_history: List[Dict[str, str]] = []
        self.session_start = time.time()
        self.total_prompts = 0
        self.total_cost = 0.0

    def _load_system_prompt(self) -> str:
        """Load system prompt from file."""
        prompt_path = Path(__file__).parent / "system-prompt.md"
        if prompt_path.exists():
            return prompt_path.read_text()
        return "You are a helpful AI assistant."

    async def process(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> OrchestratorResponse:
        """
        Process a user prompt.

        Args:
            prompt: User prompt
            context: Optional additional context

        Returns:
            OrchestratorResponse
        """
        start_time = time.time()
        self.total_prompts += 1
        context = context or {}

        # 1. Route the task
        decision = self.router.route(prompt, context)
        logger.info(f"Routing decision: {decision.reasoning}")

        # 2. Gather context based on needs
        gathered_context = await self._gather_context(prompt, decision)

        # 3. Execute based on backend
        if decision.backend == AgentBackend.LOCAL:
            response = await self._execute_local(prompt, gathered_context, decision)
        else:
            response = await self._execute_delegate(prompt, gathered_context, decision)

        # 4. Update stats
        response.execution_time = time.time() - start_time
        response.context_gathered = gathered_context
        self.total_cost += response.cost_usd
        self.router.record_cost(response.cost_usd)

        # 5. Store in conversation history
        self.conversation_history.append({
            "role": "user",
            "content": prompt,
        })
        self.conversation_history.append({
            "role": "assistant",
            "content": response.content,
        })

        return response

    async def _gather_context(
        self,
        prompt: str,
        decision: RouteDecision,
    ) -> Dict[str, Any]:
        """
        Gather context based on routing decision needs.

        Args:
            prompt: User prompt
            decision: Routing decision

        Returns:
            Dict of gathered context
        """
        context = {
            "hints": [],
            "search_results": [],
            "memories": [],
            "files": [],
        }

        # Always get hints for non-trivial tasks
        if decision.estimated_complexity != "trivial":
            hints = self.mcp.get_hints(prompt, limit=3)
            context["hints"] = [h.content for h in hints]

        # Search for relevant context
        if "relevant_files" in decision.context_needed:
            results = self.mcp.hybrid_search(prompt, limit=5)
            context["search_results"] = [
                {"content": r.content, "source": r.source}
                for r in results
            ]

        # Recall relevant memories
        memories = self.mcp.recall_memory(prompt, limit=3)
        context["memories"] = [m.content for m in memories]

        return context

    async def _execute_local(
        self,
        prompt: str,
        context: Dict[str, Any],
        decision: RouteDecision,
    ) -> OrchestratorResponse:
        """
        Execute task locally using Gemma model.

        Args:
            prompt: User prompt
            context: Gathered context
            decision: Routing decision

        Returns:
            OrchestratorResponse
        """
        # Build messages for chat
        messages = []

        # System message with context
        system_content = self.system_prompt
        if context["hints"]:
            system_content += "\n\n## Relevant Hints\n"
            for hint in context["hints"]:
                system_content += f"- {hint}\n"

        if context["search_results"]:
            system_content += "\n\n## Relevant Context\n"
            for result in context["search_results"][:3]:
                system_content += f"Source: {result['source']}\n{result['content'][:500]}\n\n"

        messages.append({"role": "system", "content": system_content})

        # Add conversation history (last 4 turns)
        for msg in self.conversation_history[-8:]:
            messages.append(msg)

        # Add current prompt
        messages.append({"role": "user", "content": prompt})

        # Call local model
        response_text = self.mcp.llm_chat(
            messages,
            max_tokens=decision.estimated_tokens,
            temperature=0.7,
        )

        # Store memory if significant
        if decision.category in (TaskCategory.PLANNING, TaskCategory.ANALYSIS):
            self.mcp.store_memory(
                f"Analyzed: {prompt[:100]}... Response key points: {response_text[:200]}",
                memory_type="semantic",
            )

        return OrchestratorResponse(
            action="direct_response",
            content=response_text,
            backend_used="local",
            tokens_used=decision.estimated_tokens,
            cost_usd=0.0,
        )

    async def _execute_delegate(
        self,
        prompt: str,
        context: Dict[str, Any],
        decision: RouteDecision,
    ) -> OrchestratorResponse:
        """
        Delegate task to remote agent.

        Args:
            prompt: User prompt
            context: Gathered context
            decision: Routing decision

        Returns:
            OrchestratorResponse
        """
        # Map category to TaskType
        task_type_map = {
            TaskCategory.IMPLEMENTATION: TaskType.IMPLEMENTATION,
            TaskCategory.REFACTORING: TaskType.REFACTORING,
            TaskCategory.DOCUMENTATION: TaskType.DOCUMENTATION,
            TaskCategory.TESTING: TaskType.TESTING,
            TaskCategory.ANALYSIS: TaskType.ANALYSIS,
            TaskCategory.PLANNING: TaskType.PLANNING,
            TaskCategory.SECURITY: TaskType.ANALYSIS,
            TaskCategory.CONFIGURATION: TaskType.IMPLEMENTATION,
        }

        # Map backend to AgentPreference
        agent_pref_map = {
            AgentBackend.QWEN: AgentPreference.LOCAL,  # Use local for Qwen (via OpenRouter)
            AgentBackend.CLAUDE_SONNET: AgentPreference.CLAUDE,
            AgentBackend.CLAUDE_OPUS: AgentPreference.FLAGSHIP,
        }

        # Create delegated task
        task = DelegatedTask(
            task_id=f"local-orch-{int(time.time())}",
            task_type=task_type_map.get(decision.category, TaskType.IMPLEMENTATION),
            description=prompt,
            context=TaskContext(
                files_to_read=[r["source"] for r in context.get("search_results", [])],
                hints=context.get("hints", []),
            ),
            acceptance_criteria=[
                "Changes match the requested task",
                "No breaking changes introduced",
            ],
            constraints=TaskConstraints(
                max_files_changed=decision.constraints.get("max_files", 10),
                require_tests=decision.constraints.get("require_tests", False),
                safety_level=decision.constraints.get("safety_level", "medium"),
            ),
            agent_preference=agent_pref_map.get(decision.backend, AgentPreference.ANY),
            max_cost_usd=min(decision.estimated_cost_usd * 2, 1.0),
        )

        # Delegate
        protocol = get_delegation_protocol()
        result = await protocol.delegate(task)

        # Format response
        content = result.output or f"Task {result.status.value}"
        if result.changes:
            content += f"\n\nChanges:\n"
            for change in result.changes:
                content += f"- {change.file_path}: {change.action}\n"

        if result.questions:
            content += f"\n\nQuestions from agent:\n"
            for q in result.questions:
                content += f"- {q.question}\n"

        return OrchestratorResponse(
            action="delegate",
            content=content,
            backend_used=decision.backend.value,
            tokens_used=decision.estimated_tokens,
            cost_usd=result.cost_usd,
            metadata={
                "task_id": task.task_id,
                "status": result.status.value,
                "changes_count": len(result.changes),
            },
        )

    async def plan_task(
        self,
        objective: str,
        constraints: Optional[List[str]] = None,
    ) -> OrchestratorResponse:
        """
        Create a workflow plan for a task.

        Args:
            objective: Task objective
            constraints: Optional constraints

        Returns:
            OrchestratorResponse with plan
        """
        start_time = time.time()

        # Use MCP workflow planning
        plan_result = self.mcp.workflow_plan(objective)

        if "error" in plan_result:
            return OrchestratorResponse(
                action="error",
                content=f"Planning failed: {plan_result['error']}",
                backend_used="local",
            )

        # Format plan
        content = f"# Plan: {objective}\n\n"

        phases = plan_result.get("phases", [])
        for i, phase in enumerate(phases, 1):
            content += f"## Phase {i}: {phase.get('name', 'Unnamed')}\n"
            content += f"{phase.get('description', '')}\n\n"
            for step in phase.get("steps", []):
                content += f"- {step}\n"
            content += "\n"

        # Store plan in memory
        self.mcp.store_memory(
            f"Plan created for: {objective}. Phases: {len(phases)}",
            memory_type="procedural",
        )

        return OrchestratorResponse(
            action="plan",
            content=content,
            backend_used="local",
            execution_time=time.time() - start_time,
            metadata={"phases": len(phases)},
        )

    def get_status(self) -> Dict[str, Any]:
        """Get orchestrator status."""
        services = self.mcp.health_check()

        return {
            "session_duration": time.time() - self.session_start,
            "total_prompts": self.total_prompts,
            "total_cost_usd": self.total_cost,
            "budget": self.router.get_budget_status(),
            "services": services,
            "mcp_stats": self.mcp.get_stats(),
            "conversation_length": len(self.conversation_history),
        }


# Singleton
_orchestrator: Optional[LocalOrchestrator] = None


def get_orchestrator(
    cost_budget: float = 5.0,
    repo_root: Optional[Path] = None,
) -> LocalOrchestrator:
    """Get global orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = LocalOrchestrator(
            cost_budget=cost_budget,
            repo_root=repo_root,
        )
    return _orchestrator


# CLI interface
async def main():
    """Interactive CLI for local orchestrator."""
    import readline  # Enable line editing

    print("Local AI Orchestrator")
    print("=" * 50)
    print("Type your prompts, 'status' for stats, 'quit' to exit")
    print()

    orchestrator = get_orchestrator()

    # Check services
    status = orchestrator.get_status()
    print(f"Services: {status['services']}")
    print()

    while True:
        try:
            prompt = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not prompt:
            continue

        if prompt.lower() == "quit":
            print("Goodbye!")
            break

        if prompt.lower() == "status":
            status = orchestrator.get_status()
            print(json.dumps(status, indent=2))
            continue

        if prompt.lower().startswith("plan:"):
            objective = prompt[5:].strip()
            response = await orchestrator.plan_task(objective)
        else:
            response = await orchestrator.process(prompt)

        print(f"\nAssistant ({response.backend_used}):")
        print(response.content)
        print(f"\n[{response.execution_time:.2f}s, ${response.cost_usd:.4f}]")
        print()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
