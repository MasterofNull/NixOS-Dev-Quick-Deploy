#!/usr/bin/env python3
"""
Agent Communication Protocol

Provides standardized message passing, shared context management,
and conflict resolution for multi-agent collaboration.

Part of Phase 4: Advanced Multi-Agent Collaboration
"""

import asyncio
import json
import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from uuid import uuid4

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent_communication_protocol")


class MessagePriority(Enum):
    """Message priority levels"""
    CRITICAL = 1  # Immediate attention required
    HIGH = 2      # Important, handle soon
    NORMAL = 3    # Standard priority
    LOW = 4       # Background, handle when available


class ConflictResolutionStrategy(Enum):
    """Strategies for resolving conflicts"""
    FIRST_WINS = "first_wins"              # First proposal accepted
    LAST_WINS = "last_wins"                # Most recent wins
    HIGHEST_CONFIDENCE = "highest_confidence"  # Best confidence score
    EXPERT_AUTHORITY = "expert_authority"  # Domain expert decides
    VOTING = "voting"                      # Majority vote
    MERGE = "merge"                        # Attempt to merge proposals


@dataclass
class AgentMessage:
    """Standardized message between agents"""
    message_id: str
    sender_id: str
    recipient_id: str  # or "broadcast" for all agents
    message_type: str
    content: Any
    priority: MessagePriority = MessagePriority.NORMAL
    requires_response: bool = False
    response_deadline: Optional[datetime] = None
    context_snapshot: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['priority'] = self.priority.value
        d['timestamp'] = self.timestamp.isoformat()
        if self.response_deadline:
            d['response_deadline'] = self.response_deadline.isoformat()
        return d


@dataclass
class SharedContext:
    """Shared context accessible to all agents in a collaboration"""
    context_id: str
    collaboration_id: str
    facts: Dict[str, Any] = field(default_factory=dict)  # Agreed-upon facts
    proposals: Dict[str, Any] = field(default_factory=dict)  # Proposed changes
    conflicts: List[Dict[str, Any]] = field(default_factory=list)  # Unresolved conflicts
    decisions: List[Dict[str, Any]] = field(default_factory=list)  # Made decisions
    task_state: Dict[str, Any] = field(default_factory=dict)  # Current task state
    agent_contributions: Dict[str, List[str]] = field(default_factory=dict)  # agent_id -> contributions
    last_updated: datetime = field(default_factory=datetime.now)
    version: int = 1

    def update(self, key: str, value: Any, agent_id: str):
        """Update context with version tracking"""
        self.facts[key] = value
        self.version += 1
        self.last_updated = datetime.now()

        if agent_id not in self.agent_contributions:
            self.agent_contributions[agent_id] = []
        self.agent_contributions[agent_id].append(f"Updated {key}")

    def propose_change(self, key: str, value: Any, agent_id: str, confidence: float):
        """Propose a change without immediately committing"""
        proposal_id = str(uuid4())
        self.proposals[proposal_id] = {
            "key": key,
            "value": value,
            "proposed_by": agent_id,
            "confidence": confidence,
            "proposed_at": datetime.now().isoformat(),
            "status": "pending"
        }
        return proposal_id

    def detect_conflict(self, key: str) -> bool:
        """Check if there are conflicting proposals for a key"""
        proposals_for_key = [
            p for p in self.proposals.values()
            if p["key"] == key and p["status"] == "pending"
        ]
        return len(proposals_for_key) > 1

    def get_conflicts(self) -> List[Dict[str, Any]]:
        """Get all current conflicts"""
        conflict_keys = set()
        for proposal in self.proposals.values():
            if proposal["status"] == "pending":
                key = proposal["key"]
                if self.detect_conflict(key):
                    conflict_keys.add(key)

        conflicts = []
        for key in conflict_keys:
            competing_proposals = [
                p for p in self.proposals.values()
                if p["key"] == key and p["status"] == "pending"
            ]
            conflicts.append({
                "key": key,
                "proposals": competing_proposals,
                "detected_at": datetime.now().isoformat()
            })

        return conflicts


class MessageBus:
    """Message bus for inter-agent communication"""

    def __init__(self, max_history: int = 1000):
        self.queues: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self.broadcast_queue: deque = deque(maxlen=100)
        self.message_history: deque = deque(maxlen=max_history)
        self.subscriptions: Dict[str, Set[str]] = defaultdict(set)  # message_type -> agent_ids
        self.handlers: Dict[str, List[Callable]] = defaultdict(list)

        logger.info("MessageBus initialized")

    async def send(self, message: AgentMessage):
        """Send message to recipient(s)"""
        self.message_history.append(message)

        if message.recipient_id == "broadcast":
            self.broadcast_queue.append(message)
            # Notify all agents subscribed to this message type
            for agent_id in self.subscriptions.get(message.message_type, set()):
                self.queues[agent_id].append(message)
        else:
            self.queues[message.recipient_id].append(message)

        # Call registered handlers
        for handler in self.handlers.get(message.message_type, []):
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
            except Exception as exc:
                logger.error(f"Handler error for {message.message_type}: {exc}")

        logger.debug(
            f"Message sent: {message.sender_id} → {message.recipient_id} "
            f"({message.message_type}, priority={message.priority.name})"
        )

    async def receive(self, agent_id: str, timeout: float = 1.0) -> Optional[AgentMessage]:
        """Receive next message for agent"""
        if not self.queues[agent_id]:
            # Wait for message with timeout
            start = asyncio.get_event_loop().time()
            while asyncio.get_event_loop().time() - start < timeout:
                if self.queues[agent_id]:
                    break
                await asyncio.sleep(0.1)

        if self.queues[agent_id]:
            return self.queues[agent_id].popleft()
        return None

    def subscribe(self, agent_id: str, message_type: str):
        """Subscribe agent to message type"""
        self.subscriptions[message_type].add(agent_id)
        logger.debug(f"Agent {agent_id} subscribed to {message_type}")

    def register_handler(self, message_type: str, handler: Callable):
        """Register handler for message type"""
        self.handlers[message_type].append(handler)
        logger.debug(f"Handler registered for {message_type}")

    def get_pending_count(self, agent_id: str) -> int:
        """Get number of pending messages for agent"""
        return len(self.queues[agent_id])

    def get_message_stats(self) -> Dict[str, Any]:
        """Get message bus statistics"""
        return {
            "total_messages": len(self.message_history),
            "agents_with_messages": len([q for q in self.queues.values() if q]),
            "broadcast_queue_size": len(self.broadcast_queue),
            "message_types": len(self.subscriptions),
            "registered_handlers": sum(len(h) for h in self.handlers.values()),
        }


class ConflictResolver:
    """Resolves conflicts in shared context"""

    def __init__(self, strategy: ConflictResolutionStrategy = ConflictResolutionStrategy.HIGHEST_CONFIDENCE):
        self.strategy = strategy
        self.expert_registry: Dict[str, Set[str]] = defaultdict(set)  # domain -> expert_agent_ids

        logger.info(f"ConflictResolver initialized with strategy: {strategy.value}")

    def register_expert(self, domain: str, agent_id: str):
        """Register agent as expert in domain"""
        self.expert_registry[domain].add(agent_id)
        logger.info(f"Registered {agent_id} as expert in {domain}")

    def resolve_conflict(
        self,
        conflict: Dict[str, Any],
        context: SharedContext,
        agent_capabilities: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """Resolve a conflict using configured strategy"""
        proposals = conflict["proposals"]

        if self.strategy == ConflictResolutionStrategy.FIRST_WINS:
            winner = min(proposals, key=lambda p: p["proposed_at"])

        elif self.strategy == ConflictResolutionStrategy.LAST_WINS:
            winner = max(proposals, key=lambda p: p["proposed_at"])

        elif self.strategy == ConflictResolutionStrategy.HIGHEST_CONFIDENCE:
            winner = max(proposals, key=lambda p: p["confidence"])

        elif self.strategy == ConflictResolutionStrategy.EXPERT_AUTHORITY:
            # Find if any proposal is from an expert
            expert_proposals = [
                p for p in proposals
                if any(p["proposed_by"] in experts for experts in self.expert_registry.values())
            ]
            if expert_proposals:
                winner = max(expert_proposals, key=lambda p: p["confidence"])
            else:
                # Fallback to highest confidence
                winner = max(proposals, key=lambda p: p["confidence"])

        elif self.strategy == ConflictResolutionStrategy.VOTING:
            # Weighted voting based on agent capabilities
            if agent_capabilities:
                weighted_proposals = [
                    (p, agent_capabilities.get(p["proposed_by"], 0.5))
                    for p in proposals
                ]
                winner = max(weighted_proposals, key=lambda x: x[1])[0]
            else:
                # Unweighted - just count
                winner = proposals[0]  # Would need voting mechanism

        elif self.strategy == ConflictResolutionStrategy.MERGE:
            # Attempt to merge proposals (domain-specific logic needed)
            winner = self._attempt_merge(proposals)

        else:
            winner = proposals[0]

        logger.info(
            f"Conflict resolved: {conflict['key']} "
            f"(strategy={self.strategy.value}, winner={winner['proposed_by']})"
        )

        return {
            "winning_proposal": winner,
            "strategy_used": self.strategy.value,
            "resolved_at": datetime.now().isoformat(),
            "rejected_proposals": [p for p in proposals if p != winner]
        }

    def _attempt_merge(self, proposals: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Attempt to merge conflicting proposals"""
        # Simple merge: average numeric values, concatenate strings
        # Domain-specific logic would go here

        values = [p["value"] for p in proposals]

        if all(isinstance(v, (int, float)) for v in values):
            # Average numeric values
            merged_value = sum(values) / len(values)
        elif all(isinstance(v, str) for v in values):
            # Concatenate strings
            merged_value = " | ".join(values)
        elif all(isinstance(v, list) for v in values):
            # Combine lists
            merged_value = list(set(sum(values, [])))
        else:
            # Can't merge - use highest confidence
            return max(proposals, key=lambda p: p["confidence"])

        # Create merged proposal
        return {
            "key": proposals[0]["key"],
            "value": merged_value,
            "proposed_by": "merged",
            "confidence": sum(p["confidence"] for p in proposals) / len(proposals),
            "proposed_at": datetime.now().isoformat(),
            "status": "merged"
        }


class CommunicationProtocol:
    """Main protocol orchestrator"""

    def __init__(self):
        self.message_bus = MessageBus()
        self.contexts: Dict[str, SharedContext] = {}
        self.conflict_resolver = ConflictResolver()
        self.active_collaborations: Dict[str, Set[str]] = {}  # collaboration_id -> agent_ids

        logger.info("CommunicationProtocol initialized")

    def create_collaboration(self, collaboration_id: str, agent_ids: List[str]) -> SharedContext:
        """Create new collaboration context"""
        context = SharedContext(
            context_id=str(uuid4()),
            collaboration_id=collaboration_id
        )
        self.contexts[collaboration_id] = context
        self.active_collaborations[collaboration_id] = set(agent_ids)

        logger.info(f"Created collaboration: {collaboration_id} with {len(agent_ids)} agents")
        return context

    async def broadcast_to_collaboration(
        self,
        collaboration_id: str,
        sender_id: str,
        message_type: str,
        content: Any,
        priority: MessagePriority = MessagePriority.NORMAL
    ):
        """Broadcast message to all agents in collaboration"""
        if collaboration_id not in self.active_collaborations:
            logger.warning(f"Unknown collaboration: {collaboration_id}")
            return

        context = self.contexts.get(collaboration_id)

        for agent_id in self.active_collaborations[collaboration_id]:
            if agent_id == sender_id:
                continue  # Don't send to self

            message = AgentMessage(
                message_id=str(uuid4()),
                sender_id=sender_id,
                recipient_id=agent_id,
                message_type=message_type,
                content=content,
                priority=priority,
                context_snapshot=context.facts if context else None
            )

            await self.message_bus.send(message)

    async def resolve_all_conflicts(
        self,
        collaboration_id: str,
        agent_capabilities: Optional[Dict[str, float]] = None
    ) -> List[Dict[str, Any]]:
        """Resolve all conflicts in collaboration context"""
        context = self.contexts.get(collaboration_id)
        if not context:
            return []

        conflicts = context.get_conflicts()
        resolutions = []

        for conflict in conflicts:
            resolution = self.conflict_resolver.resolve_conflict(
                conflict, context, agent_capabilities
            )

            # Apply winning proposal to context
            winner = resolution["winning_proposal"]
            context.update(winner["key"], winner["value"], winner["proposed_by"])

            # Mark proposals as resolved
            for proposal_id, proposal in context.proposals.items():
                if proposal["key"] == conflict["key"]:
                    proposal["status"] = "resolved" if proposal == winner else "rejected"

            resolutions.append(resolution)

            # Record decision
            context.decisions.append({
                "key": conflict["key"],
                "chosen_value": winner["value"],
                "chosen_by": winner["proposed_by"],
                "alternatives_count": len(conflict["proposals"]) - 1,
                "decided_at": datetime.now().isoformat()
            })

        logger.info(f"Resolved {len(resolutions)} conflicts in {collaboration_id}")
        return resolutions

    def get_collaboration_summary(self, collaboration_id: str) -> Dict[str, Any]:
        """Get summary of collaboration state"""
        context = self.contexts.get(collaboration_id)
        if not context:
            return {"error": "Collaboration not found"}

        return {
            "collaboration_id": collaboration_id,
            "active_agents": len(self.active_collaborations.get(collaboration_id, set())),
            "facts_count": len(context.facts),
            "pending_proposals": len([p for p in context.proposals.values() if p["status"] == "pending"]),
            "conflicts_count": len(context.get_conflicts()),
            "decisions_count": len(context.decisions),
            "context_version": context.version,
            "last_updated": context.last_updated.isoformat(),
            "top_contributors": sorted(
                context.agent_contributions.items(),
                key=lambda x: len(x[1]),
                reverse=True
            )[:3]
        }


async def main():
    """Example usage"""
    protocol = CommunicationProtocol()

    # Create collaboration
    collaboration_id = "test_collab_1"
    context = protocol.create_collaboration(collaboration_id, ["agent1", "agent2", "agent3"])

    # Agents propose changes
    context.propose_change("task_approach", "use_parallel_execution", "agent1", confidence=0.8)
    context.propose_change("task_approach", "use_sequential_execution", "agent2", confidence=0.9)

    # Detect and resolve conflicts
    conflicts = context.get_conflicts()
    print(f"\nDetected {len(conflicts)} conflicts:")
    for conflict in conflicts:
        print(f"  - {conflict['key']}: {len(conflict['proposals'])} competing proposals")

    # Resolve conflicts
    resolutions = await protocol.resolve_all_conflicts(collaboration_id)
    print(f"\nResolved {len(resolutions)} conflicts")

    # Get summary
    summary = protocol.get_collaboration_summary(collaboration_id)
    print(f"\nCollaboration summary:")
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
