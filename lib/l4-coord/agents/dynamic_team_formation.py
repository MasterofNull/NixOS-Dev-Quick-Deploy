#!/usr/bin/env python3
"""
Phase 4: Dynamic Team Formation
Automatically form optimal agent teams based on task requirements.

Features:
- Capability matrix for agent skill matching
- Auto-form teams of 2-5 agents (research-backed optimal size)
- Coordination pattern selection (peer/hub/hierarchical)
- Performance prediction for team composition
- Team caching and reuse for similar tasks
- Role assignment (orchestrator, planner, executor, reviewer)
"""

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Tuple

import logging

logger = logging.getLogger(__name__)


class AgentRole(Enum):
    """Roles an agent can play in a team."""
    ORCHESTRATOR = "orchestrator"  # Coordinates team
    PLANNER = "planner"  # Creates execution plan
    EXECUTOR = "executor"  # Implements work
    REVIEWER = "reviewer"  # Validates output
    SPECIALIST = "specialist"  # Domain expert


class CoordinationPattern(Enum):
    """Team coordination patterns."""
    PEER = "peer"  # All agents equal, consensus-based
    HUB = "hub"  # Central coordinator, spoke executors
    HIERARCHICAL = "hierarchical"  # Multi-level delegation
    PIPELINE = "pipeline"  # Sequential handoff


class AgentCapability(Enum):
    """Agent capability types."""
    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    ARCHITECTURE = "architecture"
    SECURITY = "security"
    PERFORMANCE = "performance"
    DEBUGGING = "debugging"
    REFACTORING = "refactoring"
    API_DESIGN = "api_design"
    DATABASE = "database"
    FRONTEND = "frontend"
    BACKEND = "backend"
    DEVOPS = "devops"
    DATA_SCIENCE = "data_science"


@dataclass
class AgentProfile:
    """Profile of an agent's capabilities."""
    agent_id: str
    name: str
    capabilities: Dict[AgentCapability, float] = field(default_factory=dict)  # 0-1 score
    preferred_roles: List[AgentRole] = field(default_factory=list)
    max_concurrent_tasks: int = 5
    performance_history: Dict[str, float] = field(default_factory=dict)  # task_type -> success_rate
    availability: float = 1.0  # 0-1
    cost_per_task: float = 1.0  # Relative cost

    def get_capability_score(self, capability: AgentCapability) -> float:
        """Get score for a capability (0-1)."""
        return self.capabilities.get(capability, 0.0)

    def get_overall_score(self, required_capabilities: List[AgentCapability]) -> float:
        """Get overall match score for required capabilities."""
        if not required_capabilities:
            return 0.0

        total = sum(self.get_capability_score(cap) for cap in required_capabilities)
        return total / len(required_capabilities)

    def can_fulfill_role(self, role: AgentRole) -> bool:
        """Check if agent can fulfill a role."""
        return role in self.preferred_roles or role == AgentRole.EXECUTOR

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "capabilities": {cap.value: score for cap, score in self.capabilities.items()},
            "preferred_roles": [role.value for role in self.preferred_roles],
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "performance_history": self.performance_history,
            "availability": self.availability,
            "cost_per_task": self.cost_per_task,
        }


@dataclass
class TaskRequirements:
    """Requirements for a task."""
    task_id: str
    description: str
    required_capabilities: List[AgentCapability]
    complexity: int = 1  # 1-5 scale
    urgency: int = 1  # 1-5 scale
    budget: float = 10.0  # Cost budget
    min_team_size: int = 1
    max_team_size: int = 5
    preferred_pattern: Optional[CoordinationPattern] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "task_id": self.task_id,
            "description": self.description,
            "required_capabilities": [cap.value for cap in self.required_capabilities],
            "complexity": self.complexity,
            "urgency": self.urgency,
            "budget": self.budget,
            "min_team_size": self.min_team_size,
            "max_team_size": self.max_team_size,
            "preferred_pattern": self.preferred_pattern.value if self.preferred_pattern else None,
        }


@dataclass
class TeamMember:
    """Member of a team with assigned role."""
    agent: AgentProfile
    role: AgentRole
    workload: float = 0.0  # 0-1

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "agent": self.agent.to_dict(),
            "role": self.role.value,
            "workload": self.workload,
        }


@dataclass
class Team:
    """A team of agents formed for a task."""
    team_id: str
    task_id: str
    members: List[TeamMember]
    pattern: CoordinationPattern
    predicted_performance: float = 0.0  # 0-1
    predicted_duration: int = 0  # seconds
    total_cost: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def get_member_by_role(self, role: AgentRole) -> Optional[TeamMember]:
        """Get team member by role."""
        for member in self.members:
            if member.role == role:
                return member
        return None

    def get_orchestrator(self) -> Optional[TeamMember]:
        """Get team orchestrator."""
        return self.get_member_by_role(AgentRole.ORCHESTRATOR)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "team_id": self.team_id,
            "task_id": self.task_id,
            "members": [member.to_dict() for member in self.members],
            "pattern": self.pattern.value,
            "predicted_performance": self.predicted_performance,
            "predicted_duration": self.predicted_duration,
            "total_cost": self.total_cost,
            "created_at": self.created_at.isoformat(),
        }


class DynamicTeamFormation:
    """Dynamic team formation engine."""

    def __init__(self, state_dir: Optional[Path] = None):
        """Initialize team formation engine."""
        self.state_dir = state_dir or Path.home() / ".cache" / "ai-harness" / "team-formation"
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.agent_profiles: Dict[str, AgentProfile] = {}
        self.team_cache: Dict[str, Team] = {}  # task_signature -> team
        self.team_history: List[Dict[str, Any]] = []

        self._load_state()

    def _load_state(self):
        """Load state from disk."""
        profiles_file = self.state_dir / "agent_profiles.json"
        cache_file = self.state_dir / "team_cache.json"
        history_file = self.state_dir / "team_history.json"

        try:
            if profiles_file.exists():
                with open(profiles_file) as f:
                    data = json.load(f)
                    for profile_data in data.get("profiles", []):
                        profile = self._profile_from_dict(profile_data)
                        self.agent_profiles[profile.agent_id] = profile
        except Exception as e:
            logger.warning(f"Failed to load agent profiles: {e}")

        try:
            if cache_file.exists():
                with open(cache_file) as f:
                    data = json.load(f)
                    for signature, team_data in data.get("cache", {}).items():
                        self.team_cache[signature] = self._team_from_dict(team_data)
        except Exception as e:
            logger.warning(f"Failed to load team cache: {e}")

        try:
            if history_file.exists():
                with open(history_file) as f:
                    data = json.load(f)
                    self.team_history = data.get("history", [])
        except Exception as e:
            logger.warning(f"Failed to load team history: {e}")

    def _save_state(self):
        """Save state to disk."""
        profiles_file = self.state_dir / "agent_profiles.json"
        cache_file = self.state_dir / "team_cache.json"
        history_file = self.state_dir / "team_history.json"

        try:
            with open(profiles_file, 'w') as f:
                json.dump({
                    "profiles": [profile.to_dict() for profile in self.agent_profiles.values()]
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save agent profiles: {e}")

        try:
            with open(cache_file, 'w') as f:
                json.dump({
                    "cache": {sig: team.to_dict() for sig, team in self.team_cache.items()}
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save team cache: {e}")

        try:
            with open(history_file, 'w') as f:
                json.dump({"history": self.team_history}, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save team history: {e}")

    def _profile_from_dict(self, data: Dict[str, Any]) -> AgentProfile:
        """Deserialize agent profile."""
        return AgentProfile(
            agent_id=data["agent_id"],
            name=data["name"],
            capabilities={
                AgentCapability(cap): score
                for cap, score in data.get("capabilities", {}).items()
            },
            preferred_roles=[AgentRole(role) for role in data.get("preferred_roles", [])],
            max_concurrent_tasks=data.get("max_concurrent_tasks", 5),
            performance_history=data.get("performance_history", {}),
            availability=data.get("availability", 1.0),
            cost_per_task=data.get("cost_per_task", 1.0),
        )

    def _team_from_dict(self, data: Dict[str, Any]) -> Team:
        """Deserialize team."""
        members = []
        for member_data in data.get("members", []):
            agent = self._profile_from_dict(member_data["agent"])
            member = TeamMember(
                agent=agent,
                role=AgentRole(member_data["role"]),
                workload=member_data.get("workload", 0.0),
            )
            members.append(member)

        return Team(
            team_id=data["team_id"],
            task_id=data["task_id"],
            members=members,
            pattern=CoordinationPattern(data["pattern"]),
            predicted_performance=data.get("predicted_performance", 0.0),
            predicted_duration=data.get("predicted_duration", 0),
            total_cost=data.get("total_cost", 0.0),
            created_at=datetime.fromisoformat(data["created_at"]),
        )

    def register_agent(self, profile: AgentProfile):
        """Register an agent profile."""
        self.agent_profiles[profile.agent_id] = profile
        self._save_state()

        logger.info("agent_registered",
                   agent_id=profile.agent_id,
                   capabilities=len(profile.capabilities))

    def unregister_agent(self, agent_id: str):
        """Unregister an agent."""
        if agent_id in self.agent_profiles:
            del self.agent_profiles[agent_id]
            self._save_state()
            logger.info("agent_unregistered", agent_id=agent_id)

    def update_agent_performance(self, agent_id: str, task_type: str, success: bool):
        """Update agent performance history."""
        if agent_id not in self.agent_profiles:
            return

        profile = self.agent_profiles[agent_id]
        current = profile.performance_history.get(task_type, {"success": 0, "total": 0})

        current["total"] += 1
        if success:
            current["success"] += 1

        success_rate = current["success"] / current["total"]
        profile.performance_history[task_type] = success_rate

        self._save_state()

    def _compute_task_signature(self, requirements: TaskRequirements) -> str:
        """Compute signature for task requirements (for caching)."""
        key_parts = [
            ",".join(sorted([cap.value for cap in requirements.required_capabilities])),
            str(requirements.complexity),
            str(requirements.min_team_size),
            str(requirements.max_team_size),
        ]
        key = "|".join(key_parts)
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def _select_coordination_pattern(self,
                                    requirements: TaskRequirements,
                                    team_size: int) -> CoordinationPattern:
        """Select coordination pattern based on task and team."""
        if requirements.preferred_pattern:
            return requirements.preferred_pattern

        # Simple heuristics for pattern selection
        if team_size == 1:
            return CoordinationPattern.PEER
        elif team_size == 2:
            return CoordinationPattern.PEER
        elif requirements.complexity >= 4:
            return CoordinationPattern.HIERARCHICAL
        elif team_size <= 3:
            return CoordinationPattern.HUB
        else:
            return CoordinationPattern.PIPELINE

    def _optimize_team_size(self, requirements: TaskRequirements) -> int:
        """Optimize team size based on requirements."""
        # Research shows 2-5 is optimal team size
        # Base on complexity
        if requirements.complexity <= 2:
            size = 1
        elif requirements.complexity == 3:
            size = 2
        elif requirements.complexity == 4:
            size = 3
        else:
            size = 4

        # Adjust based on capability diversity
        size = min(size, len(requirements.required_capabilities))

        # Clamp to limits
        size = max(requirements.min_team_size, min(size, requirements.max_team_size))
        size = max(1, min(size, 5))  # Research-backed optimal range

        return size

    def _score_agent_for_task(self,
                             agent: AgentProfile,
                             requirements: TaskRequirements) -> float:
        """Score how well an agent matches task requirements."""
        # Capability match (50% weight)
        capability_score = agent.get_overall_score(requirements.required_capabilities)

        # Performance history (30% weight)
        perf_scores = [
            agent.performance_history.get(cap.value, 0.5)
            for cap in requirements.required_capabilities
        ]
        performance_score = sum(perf_scores) / len(perf_scores) if perf_scores else 0.5

        # Availability (20% weight)
        availability_score = agent.availability

        total_score = (
            0.5 * capability_score +
            0.3 * performance_score +
            0.2 * availability_score
        )

        return total_score

    def _assign_roles(self,
                     agents: List[AgentProfile],
                     pattern: CoordinationPattern) -> List[Tuple[AgentProfile, AgentRole]]:
        """Assign roles to agents based on pattern."""
        if not agents:
            return []

        assignments: List[Tuple[AgentProfile, AgentRole]] = []

        if pattern == CoordinationPattern.PEER:
            # All peers
            for agent in agents:
                assignments.append((agent, AgentRole.EXECUTOR))

        elif pattern == CoordinationPattern.HUB:
            # First agent is orchestrator, rest are executors
            assignments.append((agents[0], AgentRole.ORCHESTRATOR))
            for agent in agents[1:]:
                assignments.append((agent, AgentRole.EXECUTOR))

        elif pattern == CoordinationPattern.HIERARCHICAL:
            # Orchestrator -> Planner -> Executors -> Reviewer
            if len(agents) >= 1:
                assignments.append((agents[0], AgentRole.ORCHESTRATOR))
            if len(agents) >= 2:
                assignments.append((agents[1], AgentRole.PLANNER))
            if len(agents) >= 3:
                for agent in agents[2:-1]:
                    assignments.append((agent, AgentRole.EXECUTOR))
            if len(agents) >= 4:
                assignments.append((agents[-1], AgentRole.REVIEWER))

        elif pattern == CoordinationPattern.PIPELINE:
            # Sequential handoff
            roles = [AgentRole.PLANNER, AgentRole.EXECUTOR, AgentRole.REVIEWER]
            for i, agent in enumerate(agents):
                role = roles[i % len(roles)]
                assignments.append((agent, role))

        return assignments

    def _predict_team_performance(self,
                                  team_members: List[TeamMember],
                                  requirements: TaskRequirements) -> float:
        """Predict team performance (0-1)."""
        if not team_members:
            return 0.0

        # Average capability match
        capability_scores = [
            member.agent.get_overall_score(requirements.required_capabilities)
            for member in team_members
        ]
        avg_capability = sum(capability_scores) / len(capability_scores)

        # Team diversity bonus (different agents bring different strengths)
        diversity_bonus = min(0.2, 0.05 * len(team_members))

        # Coordination overhead penalty (more agents = more overhead)
        overhead_penalty = 0.05 * (len(team_members) - 1)

        predicted = avg_capability + diversity_bonus - overhead_penalty
        return max(0.0, min(1.0, predicted))

    def _predict_duration(self,
                         team_members: List[TeamMember],
                         requirements: TaskRequirements) -> int:
        """Predict task duration in seconds."""
        # Base duration from complexity
        base_duration = requirements.complexity * 300  # 5 minutes per complexity level

        # Adjust for team size (diminishing returns)
        if len(team_members) > 1:
            parallelization_factor = 1.0 / (1.0 + 0.3 * (len(team_members) - 1))
            base_duration = int(base_duration * parallelization_factor)

        # Add coordination overhead
        coordination_overhead = (len(team_members) - 1) * 60  # 1 minute per additional member

        return base_duration + coordination_overhead

    def _calculate_cost(self, team_members: List[TeamMember]) -> float:
        """Calculate total team cost."""
        return sum(member.agent.cost_per_task for member in team_members)

    async def form_team(self, requirements: TaskRequirements) -> Team:
        """Form optimal team for task requirements."""
        start_time = time.time()

        # Check cache
        signature = self._compute_task_signature(requirements)
        if signature in self.team_cache:
            cached_team = self.team_cache[signature]
            logger.info("team_cache_hit",
                       task_id=requirements.task_id,
                       team_id=cached_team.team_id)
            return cached_team

        # Optimize team size
        optimal_size = self._optimize_team_size(requirements)

        # Score all agents
        agent_scores: List[Tuple[AgentProfile, float]] = []
        for agent in self.agent_profiles.values():
            score = self._score_agent_for_task(agent, requirements)
            agent_scores.append((agent, score))

        # Sort by score and take top N
        agent_scores.sort(key=lambda x: x[1], reverse=True)
        selected_agents = [agent for agent, _ in agent_scores[:optimal_size]]

        if not selected_agents:
            raise ValueError("No suitable agents found for task")

        # Select coordination pattern
        pattern = self._select_coordination_pattern(requirements, len(selected_agents))

        # Assign roles
        role_assignments = self._assign_roles(selected_agents, pattern)

        # Create team members
        team_members = [
            TeamMember(agent=agent, role=role)
            for agent, role in role_assignments
        ]

        # Predict performance and duration
        predicted_performance = self._predict_team_performance(team_members, requirements)
        predicted_duration = self._predict_duration(team_members, requirements)
        total_cost = self._calculate_cost(team_members)

        # Create team
        team_id = f"team-{requirements.task_id}-{int(time.time())}"
        team = Team(
            team_id=team_id,
            task_id=requirements.task_id,
            members=team_members,
            pattern=pattern,
            predicted_performance=predicted_performance,
            predicted_duration=predicted_duration,
            total_cost=total_cost,
        )

        # Cache team
        self.team_cache[signature] = team

        # Record in history
        self.team_history.append({
            "team_id": team_id,
            "task_id": requirements.task_id,
            "team_size": len(team_members),
            "pattern": pattern.value,
            "predicted_performance": predicted_performance,
            "formation_time": time.time() - start_time,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        self._save_state()

        logger.info("team_formed",
                   team_id=team_id,
                   task_id=requirements.task_id,
                   size=len(team_members),
                   pattern=pattern.value,
                   predicted_performance=predicted_performance,
                   formation_time=time.time() - start_time)

        return team

    def get_team_metrics(self) -> Dict[str, Any]:
        """Get team formation metrics."""
        if not self.team_history:
            return {
                "total_teams": 0,
                "avg_team_size": 0,
                "avg_formation_time": 0,
                "pattern_distribution": {},
            }

        total = len(self.team_history)
        avg_size = sum(t["team_size"] for t in self.team_history) / total
        avg_time = sum(t["formation_time"] for t in self.team_history) / total

        patterns = {}
        for team in self.team_history:
            pattern = team["pattern"]
            patterns[pattern] = patterns.get(pattern, 0) + 1

        return {
            "total_teams": total,
            "avg_team_size": round(avg_size, 2),
            "avg_formation_time": round(avg_time, 4),
            "pattern_distribution": patterns,
            "cache_hit_rate": len(self.team_cache) / total if total > 0 else 0,
        }


# Default agent profiles for testing
def create_default_agents() -> List[AgentProfile]:
    """Create default agent profiles for testing."""
    return [
        AgentProfile(
            agent_id="claude-opus",
            name="Claude Opus",
            capabilities={
                AgentCapability.CODE_GENERATION: 0.95,
                AgentCapability.CODE_REVIEW: 0.90,
                AgentCapability.ARCHITECTURE: 0.95,
                AgentCapability.SECURITY: 0.85,
                AgentCapability.DOCUMENTATION: 0.90,
            },
            preferred_roles=[AgentRole.ORCHESTRATOR, AgentRole.PLANNER],
            cost_per_task=5.0,
        ),
        AgentProfile(
            agent_id="qwen-coder",
            name="Qwen Coder",
            capabilities={
                AgentCapability.CODE_GENERATION: 0.85,
                AgentCapability.REFACTORING: 0.80,
                AgentCapability.DEBUGGING: 0.75,
                AgentCapability.TESTING: 0.70,
            },
            preferred_roles=[AgentRole.EXECUTOR],
            cost_per_task=2.0,
        ),
        AgentProfile(
            agent_id="codex",
            name="Codex",
            capabilities={
                AgentCapability.CODE_GENERATION: 0.80,
                AgentCapability.API_DESIGN: 0.75,
                AgentCapability.BACKEND: 0.80,
            },
            preferred_roles=[AgentRole.EXECUTOR],
            cost_per_task=3.0,
        ),
        AgentProfile(
            agent_id="security-specialist",
            name="Security Specialist",
            capabilities={
                AgentCapability.SECURITY: 0.95,
                AgentCapability.CODE_REVIEW: 0.85,
            },
            preferred_roles=[AgentRole.REVIEWER, AgentRole.SPECIALIST],
            cost_per_task=4.0,
        ),
    ]
