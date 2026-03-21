#!/usr/bin/env python3
"""
Phase 4: Collaborative Planning
Multiple agents contribute to planning with LLM synthesis.

Features:
- Multi-agent plan contribution
- LLM-powered synthesis into coherent strategy
- Phase assignment to best-suited agents
- Plan validation and feasibility checking
- Parallel vs sequential planning
- Plan versioning and evolution
- Confidence scoring
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
from typing import Dict, List, Optional, Any, Tuple

import logging

logger = logging.getLogger(__name__)


class PlanningMode(Enum):
    """Planning collaboration mode."""
    PARALLEL = "parallel"  # All agents contribute simultaneously
    SEQUENTIAL = "sequential"  # Agents contribute in sequence
    HIERARCHICAL = "hierarchical"  # Lead planner coordinates


class PhaseType(Enum):
    """Type of plan phase."""
    RESEARCH = "research"
    DESIGN = "design"
    IMPLEMENTATION = "implementation"
    TESTING = "testing"
    REVIEW = "review"
    DEPLOYMENT = "deployment"


@dataclass
class PlanContribution:
    """Contribution from an agent to the plan."""
    contribution_id: str
    agent_id: str
    content: str
    suggested_phases: List[Dict[str, Any]] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    confidence: float = 0.5  # 0-1
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "contribution_id": self.contribution_id,
            "agent_id": self.agent_id,
            "content": self.content,
            "suggested_phases": self.suggested_phases,
            "dependencies": self.dependencies,
            "risks": self.risks,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class PlanPhase:
    """A phase in the execution plan."""
    phase_id: str
    name: str
    description: str
    phase_type: PhaseType
    assigned_agent: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    estimated_duration: int = 0  # seconds
    required_capabilities: List[str] = field(default_factory=list)
    success_criteria: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "phase_id": self.phase_id,
            "name": self.name,
            "description": self.description,
            "phase_type": self.phase_type.value,
            "assigned_agent": self.assigned_agent,
            "dependencies": self.dependencies,
            "estimated_duration": self.estimated_duration,
            "required_capabilities": self.required_capabilities,
            "success_criteria": self.success_criteria,
            "risks": self.risks,
        }


@dataclass
class CollaborativePlan:
    """Collaboratively created execution plan."""
    plan_id: str
    task_id: str
    team_id: str
    version: int = 1
    contributions: List[PlanContribution] = field(default_factory=list)
    phases: List[PlanPhase] = field(default_factory=list)
    overall_strategy: str = ""
    feasibility_score: float = 0.0  # 0-1
    completeness_score: float = 0.0  # 0-1
    coherence_score: float = 0.0  # 0-1
    total_estimated_duration: int = 0  # seconds
    risks: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finalized: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "plan_id": self.plan_id,
            "task_id": self.task_id,
            "team_id": self.team_id,
            "version": self.version,
            "contributions_count": len(self.contributions),
            "phases": [phase.to_dict() for phase in self.phases],
            "overall_strategy": self.overall_strategy,
            "feasibility_score": self.feasibility_score,
            "completeness_score": self.completeness_score,
            "coherence_score": self.coherence_score,
            "total_estimated_duration": self.total_estimated_duration,
            "risks": self.risks,
            "created_at": self.created_at.isoformat(),
            "finalized": self.finalized,
        }


class PlanValidator:
    """Validates plan quality and feasibility."""

    @staticmethod
    def check_dependencies(phases: List[PlanPhase]) -> List[str]:
        """Check for dependency issues."""
        issues = []
        phase_ids = {phase.phase_id for phase in phases}

        for phase in phases:
            for dep in phase.dependencies:
                if dep not in phase_ids:
                    issues.append(f"Phase {phase.phase_id} depends on non-existent phase {dep}")

        # Check for circular dependencies
        visited = set()
        rec_stack = set()

        def has_cycle(phase_id: str) -> bool:
            visited.add(phase_id)
            rec_stack.add(phase_id)

            # Find phase
            phase = next((p for p in phases if p.phase_id == phase_id), None)
            if not phase:
                return False

            for dep in phase.dependencies:
                if dep not in visited:
                    if has_cycle(dep):
                        return True
                elif dep in rec_stack:
                    return True

            rec_stack.remove(phase_id)
            return False

        for phase in phases:
            if phase.phase_id not in visited:
                if has_cycle(phase.phase_id):
                    issues.append(f"Circular dependency detected involving {phase.phase_id}")

        return issues

    @staticmethod
    def check_completeness(phases: List[PlanPhase], task_description: str) -> float:
        """Check plan completeness (0-1)."""
        # Simple heuristic: check for key phase types
        phase_types = {phase.phase_type for phase in phases}

        required_types = [PhaseType.DESIGN, PhaseType.IMPLEMENTATION, PhaseType.TESTING]
        present_types = sum(1 for t in required_types if t in phase_types)

        completeness = present_types / len(required_types)
        return completeness

    @staticmethod
    def check_coherence(phases: List[PlanPhase]) -> float:
        """Check plan coherence (0-1)."""
        if not phases:
            return 0.0

        # Check logical ordering
        phase_order = [PhaseType.RESEARCH, PhaseType.DESIGN,
                      PhaseType.IMPLEMENTATION, PhaseType.TESTING,
                      PhaseType.REVIEW, PhaseType.DEPLOYMENT]

        # Count proper ordering
        ordered_count = 0
        for i in range(len(phases) - 1):
            try:
                curr_idx = phase_order.index(phases[i].phase_type)
                next_idx = phase_order.index(phases[i + 1].phase_type)
                if curr_idx <= next_idx:
                    ordered_count += 1
            except ValueError:
                pass

        if len(phases) <= 1:
            return 1.0

        coherence = ordered_count / (len(phases) - 1)
        return coherence

    @staticmethod
    def check_feasibility(phases: List[PlanPhase], available_agents: List[str]) -> float:
        """Check plan feasibility (0-1)."""
        if not phases:
            return 0.0

        # Check if all phases can be assigned
        assignable = sum(1 for phase in phases if not phase.assigned_agent or
                        phase.assigned_agent in available_agents)

        feasibility = assignable / len(phases)
        return feasibility


class CollaborativePlanning:
    """Collaborative planning engine."""

    def __init__(self, state_dir: Optional[Path] = None):
        """Initialize collaborative planning."""
        self.state_dir = state_dir or Path.home() / ".cache" / "ai-harness" / "planning"
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.active_plans: Dict[str, CollaborativePlan] = {}
        self.plan_history: List[Dict[str, Any]] = []
        self.validator = PlanValidator()

        self._load_state()

    def _load_state(self):
        """Load state from disk."""
        history_file = self.state_dir / "plan_history.json"

        try:
            if history_file.exists():
                with open(history_file) as f:
                    data = json.load(f)
                    self.plan_history = data.get("history", [])
        except Exception as e:
            logger.warning(f"Failed to load plan history: {e}")

    def _save_state(self):
        """Save state to disk."""
        history_file = self.state_dir / "plan_history.json"

        try:
            # Keep last 100 plans
            recent_history = self.plan_history[-100:]
            with open(history_file, 'w') as f:
                json.dump({"history": recent_history}, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save plan history: {e}")

    def create_plan(self,
                   task_id: str,
                   team_id: str,
                   mode: PlanningMode = PlanningMode.PARALLEL) -> str:
        """Create new collaborative plan."""
        plan_id = f"plan-{task_id}-{int(time.time())}"

        plan = CollaborativePlan(
            plan_id=plan_id,
            task_id=task_id,
            team_id=team_id,
        )

        self.active_plans[plan_id] = plan

        logger.info("plan_created",
                   plan_id=plan_id,
                   task_id=task_id,
                   team_id=team_id,
                   mode=mode.value)

        return plan_id

    def add_contribution(self,
                        plan_id: str,
                        agent_id: str,
                        content: str,
                        suggested_phases: List[Dict[str, Any]] = None,
                        dependencies: List[str] = None,
                        risks: List[str] = None,
                        confidence: float = 0.5) -> str:
        """Add agent contribution to plan."""
        if plan_id not in self.active_plans:
            raise ValueError(f"Plan {plan_id} not found")

        plan = self.active_plans[plan_id]

        contribution_id = str(uuid.uuid4())
        contribution = PlanContribution(
            contribution_id=contribution_id,
            agent_id=agent_id,
            content=content,
            suggested_phases=suggested_phases or [],
            dependencies=dependencies or [],
            risks=risks or [],
            confidence=confidence,
        )

        plan.contributions.append(contribution)

        logger.info("contribution_added",
                   plan_id=plan_id,
                   agent_id=agent_id,
                   contribution_id=contribution_id)

        return contribution_id

    def _synthesize_strategy(self, contributions: List[PlanContribution]) -> str:
        """Synthesize overall strategy from contributions."""
        # In a real implementation, this would use an LLM
        # For now, combine contributions
        parts = []
        for contrib in contributions:
            parts.append(f"[{contrib.agent_id}]: {contrib.content}")

        strategy = "\n\n".join(parts)
        return strategy

    def _synthesize_phases(self,
                          contributions: List[PlanContribution]) -> List[PlanPhase]:
        """Synthesize execution phases from contributions."""
        phases = []

        # Collect all suggested phases
        for contrib in contributions:
            for phase_data in contrib.suggested_phases:
                phase_id = phase_data.get("id", str(uuid.uuid4()))
                phase = PlanPhase(
                    phase_id=phase_id,
                    name=phase_data.get("name", "Unnamed Phase"),
                    description=phase_data.get("description", ""),
                    phase_type=PhaseType(phase_data.get("type", "implementation")),
                    dependencies=phase_data.get("dependencies", []),
                    estimated_duration=phase_data.get("estimated_duration", 300),
                    required_capabilities=phase_data.get("required_capabilities", []),
                    success_criteria=phase_data.get("success_criteria", []),
                    risks=phase_data.get("risks", []),
                )
                phases.append(phase)

        # If no phases suggested, create default phases
        if not phases:
            phases = [
                PlanPhase(
                    phase_id="phase-design",
                    name="Design",
                    description="Design the solution",
                    phase_type=PhaseType.DESIGN,
                    estimated_duration=600,
                ),
                PlanPhase(
                    phase_id="phase-implement",
                    name="Implementation",
                    description="Implement the solution",
                    phase_type=PhaseType.IMPLEMENTATION,
                    dependencies=["phase-design"],
                    estimated_duration=1800,
                ),
                PlanPhase(
                    phase_id="phase-test",
                    name="Testing",
                    description="Test the implementation",
                    phase_type=PhaseType.TESTING,
                    dependencies=["phase-implement"],
                    estimated_duration=900,
                ),
            ]

        return phases

    def _assign_phases_to_agents(self,
                                phases: List[PlanPhase],
                                agent_capabilities: Dict[str, List[str]]) -> None:
        """Assign phases to best-suited agents."""
        for phase in phases:
            if not phase.required_capabilities:
                # Default assignment to first available agent
                if agent_capabilities:
                    phase.assigned_agent = list(agent_capabilities.keys())[0]
                continue

            # Find best match
            best_agent = None
            best_score = 0.0

            for agent_id, capabilities in agent_capabilities.items():
                # Count matching capabilities
                matches = sum(1 for cap in phase.required_capabilities
                            if cap in capabilities)
                score = matches / len(phase.required_capabilities)

                if score > best_score:
                    best_score = score
                    best_agent = agent_id

            phase.assigned_agent = best_agent

    async def synthesize_plan(self,
                            plan_id: str,
                            agent_capabilities: Dict[str, List[str]] = None) -> CollaborativePlan:
        """Synthesize contributions into coherent plan."""
        if plan_id not in self.active_plans:
            raise ValueError(f"Plan {plan_id} not found")

        plan = self.active_plans[plan_id]

        # Synthesize overall strategy
        plan.overall_strategy = self._synthesize_strategy(plan.contributions)

        # Synthesize phases
        plan.phases = self._synthesize_phases(plan.contributions)

        # Assign phases to agents
        if agent_capabilities:
            self._assign_phases_to_agents(plan.phases, agent_capabilities)

        # Collect risks
        all_risks = []
        for contrib in plan.contributions:
            all_risks.extend(contrib.risks)
        for phase in plan.phases:
            all_risks.extend(phase.risks)
        plan.risks = list(set(all_risks))  # Deduplicate

        # Calculate total duration
        plan.total_estimated_duration = sum(p.estimated_duration for p in plan.phases)

        # Validate and score
        plan = await self.validate_plan(plan_id, list(agent_capabilities.keys()) if agent_capabilities else [])

        # Increment version
        plan.version += 1

        logger.info("plan_synthesized",
                   plan_id=plan_id,
                   phases=len(plan.phases),
                   feasibility=plan.feasibility_score,
                   completeness=plan.completeness_score,
                   coherence=plan.coherence_score)

        return plan

    async def validate_plan(self,
                          plan_id: str,
                          available_agents: List[str]) -> CollaborativePlan:
        """Validate plan and compute quality scores."""
        if plan_id not in self.active_plans:
            raise ValueError(f"Plan {plan_id} not found")

        plan = self.active_plans[plan_id]

        # Check dependencies
        dep_issues = self.validator.check_dependencies(plan.phases)
        if dep_issues:
            logger.warning("dependency_issues", plan_id=plan_id, issues=dep_issues)

        # Check completeness
        plan.completeness_score = self.validator.check_completeness(
            plan.phases,
            plan.overall_strategy
        )

        # Check coherence
        plan.coherence_score = self.validator.check_coherence(plan.phases)

        # Check feasibility
        plan.feasibility_score = self.validator.check_feasibility(
            plan.phases,
            available_agents
        )

        logger.info("plan_validated",
                   plan_id=plan_id,
                   feasibility=plan.feasibility_score,
                   completeness=plan.completeness_score,
                   coherence=plan.coherence_score)

        return plan

    def finalize_plan(self, plan_id: str) -> CollaborativePlan:
        """Finalize plan and move to history."""
        if plan_id not in self.active_plans:
            raise ValueError(f"Plan {plan_id} not found")

        plan = self.active_plans[plan_id]
        plan.finalized = True

        # Add to history
        self.plan_history.append({
            "plan_id": plan_id,
            "task_id": plan.task_id,
            "team_id": plan.team_id,
            "phases": len(plan.phases),
            "feasibility": plan.feasibility_score,
            "completeness": plan.completeness_score,
            "coherence": plan.coherence_score,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        self._save_state()

        logger.info("plan_finalized", plan_id=plan_id)

        return plan

    def get_plan(self, plan_id: str) -> Optional[CollaborativePlan]:
        """Get plan by ID."""
        return self.active_plans.get(plan_id)

    def get_planning_metrics(self) -> Dict[str, Any]:
        """Get planning metrics."""
        if not self.plan_history:
            return {
                "total_plans": 0,
                "avg_phases": 0,
                "avg_feasibility": 0,
                "avg_completeness": 0,
                "avg_coherence": 0,
            }

        total = len(self.plan_history)
        avg_phases = sum(p["phases"] for p in self.plan_history) / total
        avg_feasibility = sum(p["feasibility"] for p in self.plan_history) / total
        avg_completeness = sum(p["completeness"] for p in self.plan_history) / total
        avg_coherence = sum(p["coherence"] for p in self.plan_history) / total

        return {
            "total_plans": total,
            "active_plans": len(self.active_plans),
            "avg_phases": round(avg_phases, 2),
            "avg_feasibility": round(avg_feasibility, 3),
            "avg_completeness": round(avg_completeness, 3),
            "avg_coherence": round(avg_coherence, 3),
        }
