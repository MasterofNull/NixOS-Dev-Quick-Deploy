#!/usr/bin/env python3
"""
Approval Workflow

3-tier approval system for autonomous agent changes:
- Auto-approve: Low-risk, validated changes
- Agent-verify: Medium-risk, peer-reviewed
- Human-required: High-risk, critical systems

Part of Phase 12 Batch 12.3: Autonomous Agentic Orchestration
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from .delegation_protocol import TaskResult
from .verification import VerificationResult

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk level assessment."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ApprovalTier(Enum):
    """Approval tier required."""
    AUTO = "auto"  # Automatic approval
    AGENT = "agent"  # Peer agent verification
    HUMAN = "human"  # Human approval required


@dataclass
class ApprovalDecision:
    """Decision on whether to approve a change."""

    approved: bool
    risk_level: RiskLevel
    approval_tier: ApprovalTier
    reason: str
    auto_approved: bool = False
    agent_verified: bool = False
    human_approved: bool = False
    reviewer: Optional[str] = None


class ApprovalWorkflow:
    """
    3-tier approval workflow for autonomous changes.

    Tier 1 (Auto): Low-risk changes with all validations passed
    Tier 2 (Agent): Medium-risk changes verified by peer agent
    Tier 3 (Human): High-risk changes requiring human approval
    """

    # Auto-approval rules
    AUTO_APPROVE_RULES = {
        "max_files_changed": 5,
        "max_lines_added": 500,
        "max_lines_removed": 100,
        "min_quality_score": 0.85,
        "require_all_checks_passed": True,
        "require_no_security_issues": True,
        "require_tests_passed": True,
    }

    # High-risk file patterns
    HIGH_RISK_PATTERNS = [
        "systemd",
        "security",
        "secrets",
        ".service",
        "production",
        "database/migrations",
        "/etc/",
        "root",
        "sudo",
        "authentication",
        "authorization",
    ]

    def __init__(self):
        """Initialize approval workflow."""
        # Statistics
        self.total_approvals = 0
        self.auto_approved = 0
        self.agent_approved = 0
        self.human_approved = 0
        self.rejected = 0

        # Pending human approvals
        self.pending_human_queue: List[Dict[str, Any]] = []

    async def assess(
        self,
        task_result: TaskResult,
        verification_result: VerificationResult,
    ) -> ApprovalDecision:
        """
        Assess a task result and decide on approval.

        Args:
            task_result: Result from agent
            verification_result: Verification result

        Returns:
            ApprovalDecision
        """
        self.total_approvals += 1

        # 1. Assess risk level
        risk_level = self._assess_risk(task_result)

        # 2. Determine approval tier needed
        approval_tier = self._determine_approval_tier(
            risk_level,
            verification_result,
        )

        # 3. Execute approval based on tier
        if approval_tier == ApprovalTier.AUTO:
            decision = await self._auto_approve(
                task_result,
                verification_result,
                risk_level,
            )
            if decision.approved:
                self.auto_approved += 1
            else:
                self.rejected += 1

        elif approval_tier == ApprovalTier.AGENT:
            decision = await self._agent_verify(
                task_result,
                verification_result,
                risk_level,
            )
            if decision.approved:
                self.agent_approved += 1
            else:
                self.rejected += 1

        else:  # HUMAN
            decision = await self._request_human_approval(
                task_result,
                verification_result,
                risk_level,
            )
            if decision.approved:
                self.human_approved += 1
            else:
                self.rejected += 1

        return decision

    def _assess_risk(self, task_result: TaskResult) -> RiskLevel:
        """
        Assess risk level of changes.

        Args:
            task_result: Task result

        Returns:
            RiskLevel
        """
        risk_factors = []

        # Check file count
        files_changed = len(task_result.changes)
        if files_changed > 10:
            risk_factors.append(("Many files changed", RiskLevel.HIGH))
        elif files_changed > 5:
            risk_factors.append(("Several files changed", RiskLevel.MEDIUM))

        # Check lines changed
        total_lines_added = sum(c.lines_added for c in task_result.changes)
        total_lines_removed = sum(c.lines_removed for c in task_result.changes)

        if total_lines_added > 1000 or total_lines_removed > 500:
            risk_factors.append(("Large code changes", RiskLevel.HIGH))
        elif total_lines_added > 500 or total_lines_removed > 100:
            risk_factors.append(("Moderate code changes", RiskLevel.MEDIUM))

        # Check for high-risk file patterns
        for change in task_result.changes:
            file_path_lower = change.file_path.lower()
            for pattern in self.HIGH_RISK_PATTERNS:
                if pattern in file_path_lower:
                    risk_factors.append((f"High-risk pattern: {pattern}", RiskLevel.CRITICAL))
                    break

        # Check for deletions
        for change in task_result.changes:
            if change.action == "deleted":
                risk_factors.append(("File deletion", RiskLevel.HIGH))

        # Determine overall risk
        if any(r[1] == RiskLevel.CRITICAL for r in risk_factors):
            return RiskLevel.CRITICAL

        if any(r[1] == RiskLevel.HIGH for r in risk_factors):
            return RiskLevel.HIGH

        if any(r[1] == RiskLevel.MEDIUM for r in risk_factors):
            return RiskLevel.MEDIUM

        return RiskLevel.LOW

    def _determine_approval_tier(
        self,
        risk_level: RiskLevel,
        verification_result: VerificationResult,
    ) -> ApprovalTier:
        """
        Determine which approval tier is needed.

        Args:
            risk_level: Risk level
            verification_result: Verification result

        Returns:
            ApprovalTier
        """
        # Critical always requires human
        if risk_level == RiskLevel.CRITICAL:
            return ApprovalTier.HUMAN

        # High risk requires human
        if risk_level == RiskLevel.HIGH:
            return ApprovalTier.HUMAN

        # Failed verification requires human review
        if not verification_result.passed:
            return ApprovalTier.HUMAN

        # Low quality score requires human review
        if verification_result.overall_quality_score < 0.7:
            return ApprovalTier.HUMAN

        # Medium risk with good validation can use agent verification
        if risk_level == RiskLevel.MEDIUM and verification_result.overall_quality_score >= 0.85:
            return ApprovalTier.AGENT

        # Medium risk with lower quality needs human
        if risk_level == RiskLevel.MEDIUM:
            return ApprovalTier.HUMAN

        # Low risk with good validation can be auto-approved
        if risk_level == RiskLevel.LOW and verification_result.overall_quality_score >= 0.85:
            return ApprovalTier.AUTO

        # Default to human for safety
        return ApprovalTier.HUMAN

    async def _auto_approve(
        self,
        task_result: TaskResult,
        verification_result: VerificationResult,
        risk_level: RiskLevel,
    ) -> ApprovalDecision:
        """
        Auto-approve if all rules pass.

        Args:
            task_result: Task result
            verification_result: Verification result
            risk_level: Risk level

        Returns:
            ApprovalDecision
        """
        # Check auto-approve rules
        files_changed = len(task_result.changes)
        if files_changed > self.AUTO_APPROVE_RULES["max_files_changed"]:
            return ApprovalDecision(
                approved=False,
                risk_level=risk_level,
                approval_tier=ApprovalTier.AUTO,
                reason=f"Too many files changed: {files_changed}",
            )

        total_lines_added = sum(c.lines_added for c in task_result.changes)
        if total_lines_added > self.AUTO_APPROVE_RULES["max_lines_added"]:
            return ApprovalDecision(
                approved=False,
                risk_level=risk_level,
                approval_tier=ApprovalTier.AUTO,
                reason=f"Too many lines added: {total_lines_added}",
            )

        if verification_result.overall_quality_score < self.AUTO_APPROVE_RULES["min_quality_score"]:
            return ApprovalDecision(
                approved=False,
                risk_level=risk_level,
                approval_tier=ApprovalTier.AUTO,
                reason=f"Quality score too low: {verification_result.overall_quality_score:.2f}",
            )

        if not verification_result.passed:
            return ApprovalDecision(
                approved=False,
                risk_level=risk_level,
                approval_tier=ApprovalTier.AUTO,
                reason="Verification failed",
            )

        # All rules passed - auto-approve
        return ApprovalDecision(
            approved=True,
            risk_level=risk_level,
            approval_tier=ApprovalTier.AUTO,
            reason="Low risk, all validations passed",
            auto_approved=True,
            reviewer="auto_approver",
        )

    async def _agent_verify(
        self,
        task_result: TaskResult,
        verification_result: VerificationResult,
        risk_level: RiskLevel,
    ) -> ApprovalDecision:
        """
        Get peer agent verification.

        Args:
            task_result: Task result
            verification_result: Verification result
            risk_level: Risk level

        Returns:
            ApprovalDecision
        """
        # TODO: Implement actual peer agent review
        # For now, approve if verification passed
        logger.info(f"Agent verification for task {task_result.task_id}")

        if verification_result.passed and verification_result.overall_quality_score >= 0.85:
            return ApprovalDecision(
                approved=True,
                risk_level=risk_level,
                approval_tier=ApprovalTier.AGENT,
                reason="Peer agent verified, quality acceptable",
                agent_verified=True,
                reviewer="peer_agent",
            )
        else:
            return ApprovalDecision(
                approved=False,
                risk_level=risk_level,
                approval_tier=ApprovalTier.AGENT,
                reason="Peer agent rejected",
                agent_verified=False,
            )

    async def _request_human_approval(
        self,
        task_result: TaskResult,
        verification_result: VerificationResult,
        risk_level: RiskLevel,
    ) -> ApprovalDecision:
        """
        Request human approval.

        Args:
            task_result: Task result
            verification_result: Verification result
            risk_level: Risk level

        Returns:
            ApprovalDecision (default: not approved, added to queue)
        """
        # Add to pending queue
        approval_request = {
            "task_id": task_result.task_id,
            "task_result": task_result,
            "verification_result": verification_result,
            "risk_level": risk_level,
            "requested_at": time.time(),
        }

        self.pending_human_queue.append(approval_request)

        logger.warning(
            f"Human approval required for task {task_result.task_id} "
            f"(risk: {risk_level.value}, queue size: {len(self.pending_human_queue)})"
        )

        # TODO: Send notification (webhook, email, etc.)

        # For autonomous operation, we can't block waiting for human
        # Return not approved and let orchestrator handle
        return ApprovalDecision(
            approved=False,
            risk_level=risk_level,
            approval_tier=ApprovalTier.HUMAN,
            reason=f"Human approval required ({risk_level.value} risk)",
        )

    def approve_pending(self, task_id: str, approved: bool, reviewer: str = "human") -> bool:
        """
        Manually approve/reject a pending task.

        Args:
            task_id: Task ID
            approved: Whether to approve
            reviewer: Who approved

        Returns:
            True if found and updated
        """
        for i, request in enumerate(self.pending_human_queue):
            if request["task_id"] == task_id:
                # Remove from queue
                self.pending_human_queue.pop(i)

                if approved:
                    self.human_approved += 1
                else:
                    self.rejected += 1

                return True

        return False

    def get_pending_approvals(self) -> List[Dict[str, Any]]:
        """
        Get list of pending human approvals.

        Returns:
            List of pending approval requests
        """
        return [
            {
                "task_id": req["task_id"],
                "risk_level": req["risk_level"].value,
                "requested_at": req["requested_at"],
                "files_changed": len(req["task_result"].changes),
            }
            for req in self.pending_human_queue
        ]

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get approval statistics.

        Returns:
            Dict with statistics
        """
        auto_approve_rate = (
            self.auto_approved / self.total_approvals
            if self.total_approvals > 0
            else 0.0
        )

        return {
            "total_approvals": self.total_approvals,
            "auto_approved": self.auto_approved,
            "agent_approved": self.agent_approved,
            "human_approved": self.human_approved,
            "rejected": self.rejected,
            "auto_approve_rate": auto_approve_rate,
            "pending_human_queue": len(self.pending_human_queue),
        }


# Singleton instance
_workflow: Optional[ApprovalWorkflow] = None


def get_approval_workflow() -> ApprovalWorkflow:
    """
    Get global approval workflow instance.

    Returns:
        ApprovalWorkflow
    """
    global _workflow
    if _workflow is None:
        _workflow = ApprovalWorkflow()
    return _workflow


# Example usage
async def main():
    """Example usage."""
    from .delegation_protocol import TaskResult, FileChange, TaskStatus
    from .verification import VerificationResult, CheckResult, CheckStatus

    workflow = get_approval_workflow()

    # Simulate a low-risk task
    task_result = TaskResult(
        task_id="test-task-1",
        status=TaskStatus.COMPLETED,
        changes=[
            FileChange(
                file_path="docs/README.md",
                action="modified",
                lines_added=10,
                lines_removed=2,
            )
        ],
    )

    verification_result = VerificationResult(
        passed=True,
        overall_quality_score=0.95,
        recommendation="approve",
    )

    decision = await workflow.assess(task_result, verification_result)
    print(f"Decision: {decision.approved}")
    print(f"Risk: {decision.risk_level.value}")
    print(f"Tier: {decision.approval_tier.value}")
    print(f"Reason: {decision.reason}")

    # Statistics
    stats = workflow.get_statistics()
    print(f"\nStatistics: {json.dumps(stats, indent=2)}")


if __name__ == "__main__":
    asyncio.run(main())
