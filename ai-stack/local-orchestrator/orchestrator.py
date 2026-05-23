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
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from .mcp_client import MCPClient, get_mcp_client
    from .router import TaskRouter, TaskCategory
except ImportError:
    from mcp_client import MCPClient, get_mcp_client
    from router import TaskRouter, TaskCategory

try:
    from routing_contract import RoutingDecision, RoutingTier
except ImportError:
    # Handle if not in path, but it should be added by the wrapper script
    sys.path.insert(0, str(Path(__file__).parent.parent / "mcp-servers" / "hybrid-coordinator"))
    from routing_contract import RoutingDecision, RoutingTier

from orchestration.delegation_api import (
    DelegationAPI,
    DelegationRequest as DelegatedTask,
    DelegationStatus as TaskStatus,
    AgentCapability as TaskType,
)
from orchestration.agent_hq import AgentHQ, Session, TaskInfo, AgentStatus

# Map AgentPreference to a local enum for compatibility (Tier-based, not model-based)
class AgentPreference(Enum):
    LOCAL = "local"
    TIER1 = "tier1"  # e.g. Free remote
    TIER2 = "tier2"  # e.g. Paid/Pro
    TIER3 = "tier3"  # e.g. Flagship/Reasoning
    ANY = "any"

# Stub for TaskContext and TaskConstraints if not in new API
@dataclass
class TaskContext:
    files_to_read: List[str] = field(default_factory=list)
    hints: List[str] = field(default_factory=list)

@dataclass
class TaskConstraints:
    max_files_changed: int = 10
    require_tests: bool = False
    safety_level: str = "medium"

def get_delegation_protocol():
    """Bridge to the new DelegationAPI."""
    return DelegationAPI()

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

        # Phase 60: Agent HQ Integration (Dynamic Discovery)
        agent_name = os.getenv("AI_AGENT_NAME", "local-edge-agent")
        model_id = os.getenv("AI_LOCAL_MODEL_ID", "unidentified-local-model")
        
        self.hq = AgentHQ(persistence_dir=self.repo_root / ".agent-hq")
        self.session = self.hq.create_session(name=f"{agent_name}-session")
        self.hq.register_agent(
            name=agent_name,
            capabilities={"implementer", "architect", "reviewer", "domain:python", "domain:nixos"},
            metadata={"model": model_id}
        )

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

    def _get_role_prompt(self, role: str) -> str:
        """Load role-specific instructions (SSOT from .agent/roles/)."""
        role_path = self.repo_root / ".agent" / "roles" / f"{role.lower()}.md"
        if role_path.exists():
            return role_path.read_text()
        return ""

    def _get_domain_prompt(self, domain: str) -> str:
        """Load domain-specific instructions (e.g. .agent/SECURITY-SYSTEMS-INSTRUCTIONS.md)."""
        # Mapping from router category to domain filename
        domain_map = {
            TaskCategory.SECURITY: "SECURITY",
            TaskCategory.CONFIGURATION: "SYSTEMS",
            # Add others as needed
        }
        domain_key = domain_map.get(domain, domain.upper() if isinstance(domain, str) else "")
        domain_path = self.repo_root / ".agent" / f"{domain_key}-SYSTEMS-INSTRUCTIONS.md"
        if domain_path.exists():
            return domain_path.read_text()
        return ""

    async def _plan_task(self, prompt: str, context: Dict[str, Any]) -> str:
        """Use local model as Architect to generate a formal technical plan."""
        role_instructions = self._get_role_prompt("architect")
        
        plan_prompt = (
            "You are the Task Architect. Based on the objective and context below, "
            "generate a formal technical plan in markdown format. "
            "The plan must include: Objective, Scope Lock, Workstreams, Step Plan, "
            "Validation Strategy, and Rollback Path.\n\n"
            f"Objective: {prompt}\n"
            f"Context: {json.dumps(context, indent=2)}\n\n"
            "Plan:"
        )
        
        messages = [
            {"role": "system", "content": f"{self.system_prompt}\n\n{role_instructions}"},
            {"role": "user", "content": plan_prompt}
        ]
        
        response_text = self.mcp.llm_chat(messages, max_tokens=2000, temperature=0.1)
        return response_text

    async def process(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> OrchestratorResponse:
        """
        Process a user prompt with Local-First orchestration.
        """
        start_time = time.time()
        self.total_prompts += 1
        context = context or {}

        # Log task to HQ
        hq_task = await self.hq.submit_task(
            self.session.session_id,
            description=prompt,
            metadata={"source": "cli", "context": context}
        )

        # 1. Route the task
        decision = self.router.route(prompt, context)
        logger.info(f"Routing decision: {decision.extra['reasoning']}")

        # 2. Gather context
        gathered_context = await self._gather_context(prompt, decision)

        # 3. Task Architect Phase (Planning)
        # If the task is non-trivial and we are going to delegate or perform heavy local work, plan it first.
        if decision.extra["estimated_complexity"] != "trivial":
            logger.info("Phase: Plan (Task Architect)")
            plan = await self._plan_task(prompt, gathered_context)
            gathered_context["architect_plan"] = plan
            
            # Persist plan for agent transparency
            plan_id = int(time.time())
            plan_path = self.repo_root / ".agents" / "plans" / f"auto-plan-{plan_id}.md"
            plan_path.parent.mkdir(parents=True, exist_ok=True)
            plan_path.write_text(plan)
            logger.info(f"Architect plan persisted: {plan_path}")

        # 4. Execute based on backend
        try:
            if decision.is_local:
                response = await self._execute_local(prompt, gathered_context, decision)
            else:
                response = await self._execute_delegate(prompt, gathered_context, decision)
            
            if hq_task:
                hq_task.status = "completed"
                hq_task.result = response.content

        except Exception as e:
            if hq_task:
                hq_task.status = "failed"
                hq_task.error = str(e)
            raise e

        # 5. Update stats
        response.execution_time = time.time() - start_time
        response.context_gathered = gathered_context
        self.total_cost += response.cost_usd
        self.router.record_cost(response.cost_usd)

        # 6. Store in conversation history
        self.conversation_history.append({"role": "user", "content": prompt})
        self.conversation_history.append({"role": "assistant", "content": response.content})

        return response

    async def _gather_context(
        self,
        prompt: str,
        decision: RoutingDecision,
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
        if decision.extra["estimated_complexity"] != "trivial":
            hints = self.mcp.get_hints(prompt, limit=3)
            context["hints"] = [h.content for h in hints]

        # Search for relevant context
        if "relevant_files" in decision.extra["context_needed"]:
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
        decision: RoutingDecision,
    ) -> OrchestratorResponse:
        """
        Execute task locally with Dynamic Role Assignment.
        """
        # 1. Determine Role & Domain
        role = "implementer"  # Default for execution
        domain = decision.extra.get("category", "general")
        
        role_instructions = self._get_role_prompt(role)
        domain_instructions = self._get_domain_prompt(domain)

        # 2. Build system message with context
        system_content = f"{self.system_prompt}\n\n{role_instructions}\n\n{domain_instructions}"
        
        if context["hints"]:
            system_content += "\n\n## Relevant Hints\n"
            for hint in context["hints"]:
                system_content += f"- {hint}\n"

        if context["search_results"]:
            system_content += "\n\n## Relevant Context\n"
            for result in context["search_results"][:3]:
                system_content += f"Source: {result['source']}\n{result['content'][:500]}\n\n"
        
        if "architect_plan" in context:
            system_content += f"\n\n## Approved Technical Plan\n{context['architect_plan']}\n"

        # 3. Build message list
        messages = [{"role": "system", "content": system_content}]

        # Add history
        for msg in self.conversation_history[-8:]:
            messages.append(msg)

        # Add prompt
        messages.append({"role": "user", "content": prompt})

        # 4. Call local model
        response_text = self.mcp.llm_chat(
            messages,
            max_tokens=decision.extra["estimated_tokens"],
            temperature=0.7,
        )

        # 5. Store memory
        if decision.extra["category"] in (TaskCategory.PLANNING, TaskCategory.ANALYSIS):
            self.mcp.store_memory(
                f"Analyzed: {prompt[:100]}... Response: {response_text[:200]}",
                memory_type="semantic",
            )

        return OrchestratorResponse(
            action="direct_response",
            content=response_text,
            backend_used="local-qwen",
            tokens_used=decision.extra["estimated_tokens"],
            cost_usd=0.0,
        )

    async def _execute_delegate(
        self,
        prompt: str,
        context: Dict[str, Any],
        decision: RoutingDecision,
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

        # Map canonical routing tiers to delegation preferences.
        agent_pref_map = {
            RoutingTier.LOCAL: AgentPreference.LOCAL,
            RoutingTier.EDGE: AgentPreference.LOCAL,
            RoutingTier.REMOTE_FREE: AgentPreference.TIER1,
            RoutingTier.REMOTE_PAID: AgentPreference.TIER2,
            RoutingTier.REMOTE_FLAGSHIP: AgentPreference.TIER3,
        }

        # Create delegated task
        task = DelegatedTask(
            task_id=f"local-orch-{int(time.time())}",
            task_type=task_type_map.get(decision.extra["category"], TaskType.IMPLEMENTATION),
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
                max_files_changed=decision.extra["constraints"].get("max_files", 10),
                require_tests=decision.extra["constraints"].get("require_tests", False),
                safety_level=decision.extra["constraints"].get("safety_level", "medium"),
            ),
            agent_preference=agent_pref_map.get(decision.tier, AgentPreference.ANY),
            max_cost_usd=min(decision.extra["estimated_cost_usd"] * 2, 1.0),
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
            backend_used=decision.tier.value,
            tokens_used=decision.extra["estimated_tokens"],
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
            "session_id": self.session.session_id if hasattr(self, "session") else None
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
    print(f"Session: {status['session_id']}")
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
