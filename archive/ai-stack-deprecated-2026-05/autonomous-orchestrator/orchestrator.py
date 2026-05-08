#!/usr/bin/env python3
"""
Autonomous Orchestrator

Main orchestration engine that autonomously executes roadmap batches by:
1. Reading roadmap files
2. Breaking into delegatable tasks
3. Delegating to appropriate agents
4. Verifying results
5. Approving/rejecting changes
6. Committing approved work

Part of Phase 12 Batch 12.5: Autonomous Agentic Orchestration
"""

import asyncio
import json
import logging
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from .delegation_protocol import (
    DelegatedTask,
    TaskType,
    AgentPreference,
    TaskContext,
    TaskConstraints,
    TaskStatus,
    get_delegation_protocol,
)
from .verification import get_verifier
from .approval import get_approval_workflow, ApprovalTier

logger = logging.getLogger(__name__)


class ApprovalMode(Enum):
    """Approval mode for orchestrator."""
    AUTO = "auto"  # Auto-approve low-risk
    AGENT_VERIFY = "agent_verify"  # Require agent verification
    HUMAN_REQUIRED = "human_required"  # Require human approval


@dataclass
class OrchestrationResult:
    """Result of orchestrating a roadmap execution."""

    success: bool
    tasks_completed: int = 0
    tasks_failed: int = 0
    commits_made: int = 0
    total_cost_usd: float = 0.0
    execution_time_seconds: float = 0.0
    errors: List[str] = field(default_factory=list)


class AutonomousOrchestrator:
    """
    Autonomous orchestration engine.

    Executes roadmap batches end-to-end with minimal human intervention.
    """

    def __init__(
        self,
        approval_mode: ApprovalMode = ApprovalMode.AUTO,
        max_cost_usd: float = 10.0,
        max_runtime_hours: float = 24.0,
        repo_root: Optional[Path] = None,
    ):
        """
        Initialize orchestrator.

        Args:
            approval_mode: Approval mode
            max_cost_usd: Maximum cost budget
            max_runtime_hours: Maximum runtime
            repo_root: Repository root directory
        """
        self.approval_mode = approval_mode
        self.max_cost_usd = max_cost_usd
        self.max_runtime_hours = max_runtime_hours
        self.repo_root = repo_root or Path.cwd()

        # Get components
        self.delegation_protocol = get_delegation_protocol()
        self.verifier = get_verifier(repo_root=self.repo_root)
        self.approval_workflow = get_approval_workflow()

        # Statistics
        self.total_cost_usd = 0.0
        self.start_time: Optional[float] = None

    async def execute_task_autonomously(
        self,
        task: DelegatedTask,
    ) -> bool:
        """
        Execute a single task autonomously.

        Args:
            task: Task to execute

        Returns:
            True if successful and committed
        """
        logger.info(f"Executing task: {task.task_id}")

        # 1. Delegate to agent
        result = await self.delegation_protocol.delegate(task)

        if result.status != TaskStatus.COMPLETED:
            logger.error(f"Task {task.task_id} failed: {result.error}")
            return False

        self.total_cost_usd += result.cost_usd

        # Check budget
        if self.total_cost_usd > self.max_cost_usd:
            logger.error(f"Budget exceeded: ${self.total_cost_usd:.2f} > ${self.max_cost_usd:.2f}")
            return False

        # 2. Verify changes
        verification_passed = True
        for change in result.changes:
            verify_result = await self.verifier.verify(
                change.file_path,
                content=change.content,
                run_tests=task.constraints.require_tests,
            )

            if not verify_result.passed:
                logger.error(f"Verification failed for {change.file_path}: {verify_result.reason}")
                verification_passed = False
                break

        if not verification_passed:
            return False

        # 3. Get approval
        # Use the last verification result for approval decision
        approval_decision = await self.approval_workflow.assess(result, verify_result)

        # Check approval mode
        if self.approval_mode == ApprovalMode.HUMAN_REQUIRED:
            # Always require human approval
            if approval_decision.approval_tier != ApprovalTier.HUMAN:
                logger.info(f"Task {task.task_id} needs human approval (mode: human_required)")
            return False  # Can't auto-commit in human-required mode

        elif self.approval_mode == ApprovalMode.AGENT_VERIFY:
            # Require at least agent verification
            if approval_decision.approval_tier == ApprovalTier.HUMAN:
                logger.info(f"Task {task.task_id} needs human approval")
                return False

        # Check if approved
        if not approval_decision.approved:
            logger.warning(f"Task {task.task_id} not approved: {approval_decision.reason}")
            return False

        # 4. Apply changes
        for change in result.changes:
            try:
                file_path = self.repo_root / change.file_path

                if change.action == "modified" or change.action == "created":
                    # Write content
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    file_path.write_text(change.content)
                    logger.info(f"Applied change: {change.file_path} ({change.action})")

                elif change.action == "deleted":
                    # Delete file (requires explicit approval)
                    if approval_decision.approval_tier == ApprovalTier.AUTO:
                        logger.error(f"Cannot auto-delete file: {change.file_path}")
                        return False
                    file_path.unlink(missing_ok=True)
                    logger.info(f"Deleted file: {change.file_path}")

            except Exception as e:
                logger.exception(f"Failed to apply change to {change.file_path}: {e}")
                return False

        # 5. Commit changes
        try:
            # Git add
            subprocess.run(
                ["git", "add", "-A"],
                cwd=str(self.repo_root),
                check=True,
                capture_output=True,
            )

            # Git commit
            commit_message = f"""auto: {task.description}

Task ID: {task.task_id}
Type: {task.task_type.value}
Agent: {result.agent_used}
Approval: {approval_decision.approval_tier.value}
Quality: {verify_result.overall_quality_score:.2f}
Cost: ${result.cost_usd:.4f}

{result.output[:500] if result.output else 'No output'}

Co-Authored-By: {result.agent_used} (autonomous)
"""

            subprocess.run(
                ["git", "commit", "-m", commit_message],
                cwd=str(self.repo_root),
                check=True,
                capture_output=True,
            )

            logger.info(f"Committed task {task.task_id}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Git operation failed: {e.stderr.decode()}")
            return False

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get orchestration statistics.

        Returns:
            Dict with statistics
        """
        elapsed_time = time.time() - self.start_time if self.start_time else 0

        return {
            "elapsed_hours": elapsed_time / 3600,
            "total_cost_usd": self.total_cost_usd,
            "budget_remaining_usd": self.max_cost_usd - self.total_cost_usd,
            "delegation": self.delegation_protocol.get_statistics(),
            "verification": self.verifier.get_statistics(),
            "approval": self.approval_workflow.get_statistics(),
        }


# Singleton instance
_orchestrator: Optional[AutonomousOrchestrator] = None


def get_orchestrator(
    approval_mode: ApprovalMode = ApprovalMode.AUTO,
    max_cost_usd: float = 10.0,
) -> AutonomousOrchestrator:
    """
    Get global orchestrator instance.

    Args:
        approval_mode: Approval mode
        max_cost_usd: Maximum cost

    Returns:
        AutonomousOrchestrator
    """
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AutonomousOrchestrator(
            approval_mode=approval_mode,
            max_cost_usd=max_cost_usd,
        )
    return _orchestrator


# Example usage
async def main():
    """Example usage."""
    orchestrator = get_orchestrator(
        approval_mode=ApprovalMode.AUTO,
        max_cost_usd=5.0,
    )

    # Create a simple documentation task
    task = DelegatedTask(
        task_id="auto-doc-1",
        task_type=TaskType.DOCUMENTATION,
        description="Add usage examples to delegation protocol documentation",
        context=TaskContext(
            files_to_read=["ai-stack/autonomous-orchestrator/delegation_protocol.py"],
        ),
        acceptance_criteria=[
            "Add 3 usage examples",
            "Include code snippets",
        ],
        constraints=TaskConstraints(
            max_files_changed=1,
            require_tests=False,
        ),
        agent_preference=AgentPreference.CLAUDE,
        max_cost_usd=0.25,
    )

    # Execute
    orchestrator.start_time = time.time()
    success = await orchestrator.execute_task_autonomously(task)

    print(f"\nTask execution: {'SUCCESS' if success else 'FAILED'}")

    # Statistics
    stats = orchestrator.get_statistics()
    print(f"\nStatistics:")
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
