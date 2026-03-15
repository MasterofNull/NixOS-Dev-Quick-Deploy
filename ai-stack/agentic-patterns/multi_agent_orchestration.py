#!/usr/bin/env python3
"""
Multi-Agent Orchestration Framework

Implements dynamic team formation, inter-agent communication, and consensus mechanisms.
Part of Phase 4 Batch 4.2: Multi-Agent Orchestration

Key Features:
- Dynamic role assignment based on agent capabilities
- Inter-agent communication protocol with message passing
- Agent collaboration patterns (delegation, voting, consensus)
- Consensus mechanisms for collective decisions
- Agent performance evaluation and selection

Reference: "AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation"
https://arxiv.org/abs/2308.08155
"""

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class AgentRole(Enum):
    """Agent roles in multi-agent system"""
    ORCHESTRATOR = "orchestrator"  # Coordinates other agents
    PLANNER = "planner"  # Creates plans
    EXECUTOR = "executor"  # Executes tasks
    REVIEWER = "reviewer"  # Reviews outputs
    RESEARCHER = "researcher"  # Gathers information
    SPECIALIST = "specialist"  # Domain expert


class MessageType(Enum):
    """Types of inter-agent messages"""
    TASK_ASSIGNMENT = "task_assignment"
    TASK_RESULT = "task_result"
    QUESTION = "question"
    ANSWER = "answer"
    PROPOSAL = "proposal"
    VOTE = "vote"
    CONSENSUS_REACHED = "consensus_reached"
    STATUS_UPDATE = "status_update"


class ConsensusStrategy(Enum):
    """Consensus decision strategies"""
    UNANIMOUS = "unanimous"  # All agents must agree
    MAJORITY = "majority"  # >50% must agree
    SUPERMAJORITY = "supermajority"  # >=2/3 must agree
    WEIGHTED = "weighted"  # Weighted by agent performance
    EXPERT_OVERRIDE = "expert_override"  # Specialist can override


@dataclass
class Message:
    """Inter-agent message"""
    message_id: str
    sender: str
    recipient: str  # or "broadcast"
    message_type: MessageType
    content: Any
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict = field(default_factory=dict)


@dataclass
class AgentCapability:
    """Agent capability definition"""
    name: str
    proficiency: float  # 0.0 to 1.0
    cost: float  # Execution cost
    latency_ms: float  # Expected latency


@dataclass
class Agent:
    """Agent in multi-agent system"""
    agent_id: str
    name: str
    roles: List[AgentRole]
    capabilities: List[AgentCapability]
    performance_score: float = 1.0
    availability: bool = True

    # Statistics
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_latency_ms: float = 0.0

    def success_rate(self) -> float:
        """Calculate agent success rate"""
        total = self.tasks_completed + self.tasks_failed
        if total == 0:
            return 1.0
        return self.tasks_completed / total

    def avg_latency_ms(self) -> float:
        """Calculate average latency"""
        if self.tasks_completed == 0:
            return 0.0
        return self.total_latency_ms / self.tasks_completed

    def has_capability(self, capability_name: str) -> bool:
        """Check if agent has capability"""
        return any(c.name == capability_name for c in self.capabilities)

    def get_capability_proficiency(self, capability_name: str) -> float:
        """Get proficiency for capability"""
        for cap in self.capabilities:
            if cap.name == capability_name:
                return cap.proficiency
        return 0.0


@dataclass
class Task:
    """Task to be executed"""
    task_id: str
    description: str
    required_capabilities: List[str]
    assigned_agent: Optional[str] = None
    result: Optional[Any] = None
    status: str = "pending"  # pending, in_progress, completed, failed
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class TeamFormation:
    """Team formation result"""
    team_id: str
    objective: str
    agents: List[Agent]
    role_assignments: Dict[str, AgentRole]  # agent_id -> role
    coordination_pattern: str
    estimated_performance: float


class MultiAgentOrchestrator:
    """Multi-agent orchestration system"""

    def __init__(self):
        self.agents: Dict[str, Agent] = {}
        self.message_queue: List[Message] = []
        self.teams: Dict[str, TeamFormation] = {}

        logger.info("Multi-Agent Orchestrator initialized")

    def register_agent(self, agent: Agent):
        """Register an agent"""
        self.agents[agent.agent_id] = agent
        logger.info(f"Registered agent: {agent.name} (roles: {[r.value for r in agent.roles]})")

    def form_team(
        self,
        objective: str,
        required_capabilities: List[str],
        team_size: Optional[int] = None,
    ) -> TeamFormation:
        """Form a team dynamically based on objective"""
        logger.info(f"Forming team for: {objective}")

        # Score agents for this objective
        agent_scores = []
        for agent_id, agent in self.agents.items():
            if not agent.availability:
                continue

            score = self._score_agent_for_task(agent, required_capabilities)
            if score > 0:
                agent_scores.append((score, agent))

        # Sort by score (descending)
        agent_scores.sort(reverse=True, key=lambda x: x[0])

        # Select top agents
        if team_size:
            selected_agents = [a for _, a in agent_scores[:team_size]]
        else:
            # Auto-size team based on capabilities
            selected_agents = self._auto_select_team(agent_scores, required_capabilities)

        # Assign roles
        role_assignments = self._assign_roles(selected_agents, objective)

        # Determine coordination pattern
        coordination_pattern = self._select_coordination_pattern(selected_agents, objective)

        # Estimate team performance
        estimated_performance = self._estimate_team_performance(selected_agents, required_capabilities)

        team = TeamFormation(
            team_id=f"team_{len(self.teams)}",
            objective=objective,
            agents=selected_agents,
            role_assignments=role_assignments,
            coordination_pattern=coordination_pattern,
            estimated_performance=estimated_performance,
        )

        self.teams[team.team_id] = team

        logger.info(
            f"Team formed: {len(selected_agents)} agents, "
            f"pattern={coordination_pattern}, "
            f"estimated_performance={estimated_performance:.2f}"
        )

        return team

    def _score_agent_for_task(self, agent: Agent, required_capabilities: List[str]) -> float:
        """Score agent suitability for task"""
        if not required_capabilities:
            return agent.performance_score

        # Calculate capability match
        capability_scores = []
        for req_cap in required_capabilities:
            proficiency = agent.get_capability_proficiency(req_cap)
            capability_scores.append(proficiency)

        if not capability_scores:
            return 0.0

        # Combine capability match with performance score
        avg_capability = sum(capability_scores) / len(capability_scores)
        return avg_capability * agent.performance_score * agent.success_rate()

    def _auto_select_team(
        self,
        agent_scores: List[tuple],
        required_capabilities: List[str],
    ) -> List[Agent]:
        """Auto-select optimal team size"""
        # Ensure all required capabilities are covered
        covered_capabilities = set()
        selected_agents = []

        for score, agent in agent_scores:
            selected_agents.append(agent)

            # Track covered capabilities
            for cap in agent.capabilities:
                if cap.name in required_capabilities:
                    covered_capabilities.add(cap.name)

            # Stop if all capabilities covered and we have at least 2 agents
            if covered_capabilities >= set(required_capabilities) and len(selected_agents) >= 2:
                break

            # Don't exceed 5 agents
            if len(selected_agents) >= 5:
                break

        return selected_agents

    def _assign_roles(self, agents: List[Agent], objective: str) -> Dict[str, AgentRole]:
        """Assign roles to team members"""
        assignments = {}

        # Assign orchestrator (highest performing agent)
        if agents:
            best_agent = max(agents, key=lambda a: a.performance_score)
            if AgentRole.ORCHESTRATOR in best_agent.roles:
                assignments[best_agent.agent_id] = AgentRole.ORCHESTRATOR

        # Assign other roles based on agent capabilities
        for agent in agents:
            if agent.agent_id in assignments:
                continue

            # Prefer agent's primary role
            if agent.roles:
                assignments[agent.agent_id] = agent.roles[0]
            else:
                assignments[agent.agent_id] = AgentRole.EXECUTOR

        return assignments

    def _select_coordination_pattern(self, agents: List[Agent], objective: str) -> str:
        """Select coordination pattern for team"""
        team_size = len(agents)

        if team_size <= 2:
            return "peer_to_peer"
        elif team_size <= 4:
            return "hub_and_spoke"  # Orchestrator coordinates
        else:
            return "hierarchical"  # Multi-level coordination

    def _estimate_team_performance(
        self,
        agents: List[Agent],
        required_capabilities: List[str],
    ) -> float:
        """Estimate team performance score"""
        if not agents:
            return 0.0

        # Average agent performance
        avg_performance = sum(a.performance_score for a in agents) / len(agents)

        # Capability coverage
        covered_caps = set()
        for agent in agents:
            for cap in agent.capabilities:
                if cap.name in required_capabilities:
                    covered_caps.add(cap.name)

        coverage = len(covered_caps) / len(required_capabilities) if required_capabilities else 1.0

        # Combine factors
        return avg_performance * coverage * 0.9  # 10% penalty for coordination overhead

    async def send_message(self, message: Message):
        """Send a message to agent(s)"""
        self.message_queue.append(message)

        logger.info(
            f"Message sent: {message.sender} -> {message.recipient} "
            f"({message.message_type.value})"
        )

    async def broadcast_message(
        self,
        sender: str,
        message_type: MessageType,
        content: Any,
    ):
        """Broadcast message to all agents"""
        message = Message(
            message_id=f"msg_{len(self.message_queue)}",
            sender=sender,
            recipient="broadcast",
            message_type=message_type,
            content=content,
        )
        await self.send_message(message)

    async def reach_consensus(
        self,
        team_id: str,
        proposal: str,
        strategy: ConsensusStrategy = ConsensusStrategy.MAJORITY,
    ) -> tuple[bool, Dict[str, bool]]:
        """Reach consensus on a proposal"""
        team = self.teams.get(team_id)
        if not team:
            return False, {}

        logger.info(f"Seeking consensus: {proposal} (strategy={strategy.value})")

        # Collect votes (simulated for now)
        votes = {}
        for agent in team.agents:
            # In production, would query actual agent
            vote = await self._get_agent_vote(agent, proposal)
            votes[agent.agent_id] = vote

        # Apply consensus strategy
        consensus_reached = self._evaluate_consensus(votes, team, strategy)

        logger.info(
            f"Consensus {'reached' if consensus_reached else 'NOT reached'}: "
            f"{sum(votes.values())}/{len(votes)} votes in favor"
        )

        return consensus_reached, votes

    async def _get_agent_vote(self, agent: Agent, proposal: str) -> bool:
        """Get agent's vote on proposal (simulated)"""
        # In production, would query actual agent LLM
        # For now, simulate based on agent performance
        import random
        return random.random() < agent.performance_score

    def _evaluate_consensus(
        self,
        votes: Dict[str, bool],
        team: TeamFormation,
        strategy: ConsensusStrategy,
    ) -> bool:
        """Evaluate if consensus reached"""
        yes_votes = sum(votes.values())
        total_votes = len(votes)

        if strategy == ConsensusStrategy.UNANIMOUS:
            return yes_votes == total_votes

        elif strategy == ConsensusStrategy.MAJORITY:
            return yes_votes > total_votes / 2

        elif strategy == ConsensusStrategy.SUPERMAJORITY:
            return yes_votes >= (total_votes * 2 / 3)

        elif strategy == ConsensusStrategy.WEIGHTED:
            # Weight votes by agent performance
            weighted_yes = sum(
                self.agents[agent_id].performance_score
                for agent_id, vote in votes.items()
                if vote
            )
            total_weight = sum(
                self.agents[agent_id].performance_score
                for agent_id in votes.keys()
            )
            return weighted_yes > total_weight / 2

        elif strategy == ConsensusStrategy.EXPERT_OVERRIDE:
            # If any specialist votes yes, consensus reached
            for agent_id, vote in votes.items():
                agent = self.agents[agent_id]
                if AgentRole.SPECIALIST in agent.roles and vote:
                    return True
            # Otherwise, fall back to majority
            return yes_votes > total_votes / 2

        return False

    async def execute_collaborative_task(
        self,
        team_id: str,
        task: Task,
    ) -> Any:
        """Execute task with team collaboration"""
        team = self.teams.get(team_id)
        if not team:
            raise ValueError(f"Team {team_id} not found")

        logger.info(f"Team {team_id} executing: {task.description}")

        # Select coordination pattern
        if team.coordination_pattern == "peer_to_peer":
            result = await self._peer_to_peer_execution(team, task)
        elif team.coordination_pattern == "hub_and_spoke":
            result = await self._hub_and_spoke_execution(team, task)
        else:  # hierarchical
            result = await self._hierarchical_execution(team, task)

        logger.info(f"Task completed: {task.task_id}")
        return result

    async def _peer_to_peer_execution(self, team: TeamFormation, task: Task) -> Any:
        """Peer-to-peer task execution"""
        # Each agent contributes, results are merged
        results = []

        for agent in team.agents:
            # In production, would call actual agent
            agent_result = await self._execute_on_agent(agent, task)
            results.append(agent_result)

        # Merge results (simple concatenation for now)
        return {"results": results, "pattern": "peer_to_peer"}

    async def _hub_and_spoke_execution(self, team: TeamFormation, task: Task) -> Any:
        """Hub-and-spoke task execution"""
        # Orchestrator delegates to others
        orchestrator_id = next(
            (aid for aid, role in team.role_assignments.items()
             if role == AgentRole.ORCHESTRATOR),
            None
        )

        if not orchestrator_id:
            return await self._peer_to_peer_execution(team, task)

        # Orchestrator breaks down task and delegates
        subtasks = self._decompose_task(task)
        results = []

        for subtask in subtasks:
            # Find best agent for subtask
            agent = self._select_agent_for_subtask(team, subtask)
            result = await self._execute_on_agent(agent, subtask)
            results.append(result)

        return {"results": results, "pattern": "hub_and_spoke", "orchestrator": orchestrator_id}

    async def _hierarchical_execution(self, team: TeamFormation, task: Task) -> Any:
        """Hierarchical task execution"""
        # Multi-level delegation
        return await self._hub_and_spoke_execution(team, task)  # Simplified

    def _decompose_task(self, task: Task) -> List[Task]:
        """Decompose task into subtasks"""
        # Simplified: create 2-3 subtasks
        subtasks = []
        for i in range(2):
            subtasks.append(Task(
                task_id=f"{task.task_id}_sub{i}",
                description=f"Subtask {i+1} of {task.description}",
                required_capabilities=task.required_capabilities,
            ))
        return subtasks

    def _select_agent_for_subtask(self, team: TeamFormation, subtask: Task) -> Agent:
        """Select best agent for subtask"""
        scores = [
            (self._score_agent_for_task(agent, subtask.required_capabilities), agent)
            for agent in team.agents
        ]
        scores.sort(reverse=True)
        return scores[0][1] if scores else team.agents[0]

    async def _execute_on_agent(self, agent: Agent, task: Task) -> Any:
        """Execute task on specific agent (simulated)"""
        # In production, would call actual agent
        await asyncio.sleep(0.01)  # Simulate work
        return f"Result from {agent.name} for {task.description}"

    def update_agent_performance(
        self,
        agent_id: str,
        success: bool,
        latency_ms: float,
    ):
        """Update agent performance metrics"""
        agent = self.agents.get(agent_id)
        if not agent:
            return

        if success:
            agent.tasks_completed += 1
        else:
            agent.tasks_failed += 1

        agent.total_latency_ms += latency_ms

        # Update performance score (exponential moving average)
        new_score = 1.0 if success else 0.0
        agent.performance_score = 0.9 * agent.performance_score + 0.1 * new_score


async def main():
    """Test multi-agent orchestration"""
    logging.basicConfig(level=logging.INFO)

    logger.info("Multi-Agent Orchestration Test")
    logger.info("=" * 60)

    orchestrator = MultiAgentOrchestrator()

    # Register agents
    agents = [
        Agent(
            agent_id="agent_1",
            name="Planner Agent",
            roles=[AgentRole.PLANNER, AgentRole.ORCHESTRATOR],
            capabilities=[
                AgentCapability("planning", 0.9, 0.1, 100),
                AgentCapability("reasoning", 0.8, 0.1, 150),
            ],
        ),
        Agent(
            agent_id="agent_2",
            name="Executor Agent",
            roles=[AgentRole.EXECUTOR],
            capabilities=[
                AgentCapability("coding", 0.85, 0.05, 200),
                AgentCapability("testing", 0.7, 0.05, 180),
            ],
        ),
        Agent(
            agent_id="agent_3",
            name="Reviewer Agent",
            roles=[AgentRole.REVIEWER, AgentRole.SPECIALIST],
            capabilities=[
                AgentCapability("code_review", 0.95, 0.15, 120),
                AgentCapability("quality_assurance", 0.9, 0.1, 100),
            ],
        ),
    ]

    for agent in agents:
        orchestrator.register_agent(agent)

    # Form a team
    team = orchestrator.form_team(
        objective="Build a new feature",
        required_capabilities=["planning", "coding", "code_review"],
    )

    logger.info(f"\nTeam formation:")
    logger.info(f"  Team ID: {team.team_id}")
    logger.info(f"  Agents: {[a.name for a in team.agents]}")
    logger.info(f"  Pattern: {team.coordination_pattern}")
    logger.info(f"  Estimated performance: {team.estimated_performance:.2f}")

    # Test consensus
    consensus, votes = await orchestrator.reach_consensus(
        team.team_id,
        "Should we use TypeScript for this feature?",
        strategy=ConsensusStrategy.MAJORITY,
    )

    logger.info(f"\nConsensus result: {consensus}")
    logger.info(f"  Votes: {votes}")

    # Execute collaborative task
    task = Task(
        task_id="task_1",
        description="Implement user authentication",
        required_capabilities=["planning", "coding", "code_review"],
    )

    result = await orchestrator.execute_collaborative_task(team.team_id, task)

    logger.info(f"\nTask execution result:")
    logger.info(f"  Pattern: {result.get('pattern')}")
    logger.info(f"  Results count: {len(result.get('results', []))}")


if __name__ == "__main__":
    asyncio.run(main())
