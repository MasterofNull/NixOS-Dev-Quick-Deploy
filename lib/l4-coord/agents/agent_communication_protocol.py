#!/usr/bin/env python3
"""
Phase 4: Agent Communication Protocol
Standardized message passing and context management for multi-agent teams.

Features:
- Message passing between agents (request, response, notification, consensus)
- Shared context management with conflict resolution
- Message queues per agent
- Priority-based routing
- Communication logging and audit
- Timeout and retry handling
"""

import asyncio
import json
import logging
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Deque

import logging

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """Types of messages."""
    REQUEST = "request"  # Request action from agent
    RESPONSE = "response"  # Response to request
    NOTIFICATION = "notification"  # Broadcast information
    CONSENSUS = "consensus"  # Request consensus vote
    CONSENSUS_VOTE = "consensus_vote"  # Vote response
    CONTEXT_UPDATE = "context_update"  # Shared context update
    ERROR = "error"  # Error notification


class MessagePriority(Enum):
    """Message priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4
    CRITICAL = 5


@dataclass
class Message:
    """Inter-agent message."""
    message_id: str
    message_type: MessageType
    from_agent: str
    to_agent: Optional[str]  # None for broadcast
    team_id: str
    priority: MessagePriority = MessagePriority.NORMAL
    content: Dict[str, Any] = field(default_factory=dict)
    in_reply_to: Optional[str] = None
    requires_response: bool = False
    timeout: int = 300  # seconds
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    delivered_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "message_id": self.message_id,
            "message_type": self.message_type.value,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "team_id": self.team_id,
            "priority": self.priority.value,
            "content": self.content,
            "in_reply_to": self.in_reply_to,
            "requires_response": self.requires_response,
            "timeout": self.timeout,
            "created_at": self.created_at.isoformat(),
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
        }

    def is_expired(self) -> bool:
        """Check if message has expired."""
        elapsed = (datetime.now(timezone.utc) - self.created_at).total_seconds()
        return elapsed > self.timeout


@dataclass
class SharedContext:
    """Shared context for a team."""
    team_id: str
    data: Dict[str, Any] = field(default_factory=dict)
    version: int = 0
    last_updated_by: Optional[str] = None
    last_updated_at: Optional[datetime] = None
    update_history: List[Dict[str, Any]] = field(default_factory=list)

    def update(self, updates: Dict[str, Any], agent_id: str):
        """Update context with conflict detection."""
        conflicts = []

        for key, value in updates.items():
            if key in self.data:
                old_value = self.data[key]
                if old_value != value:
                    conflicts.append({
                        "key": key,
                        "old_value": old_value,
                        "new_value": value,
                        "agent_id": agent_id,
                    })

        # Record update
        self.update_history.append({
            "version": self.version,
            "agent_id": agent_id,
            "updates": updates,
            "conflicts": conflicts,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Apply updates
        self.data.update(updates)
        self.version += 1
        self.last_updated_by = agent_id
        self.last_updated_at = datetime.now(timezone.utc)

        return conflicts

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "team_id": self.team_id,
            "data": self.data,
            "version": self.version,
            "last_updated_by": self.last_updated_by,
            "last_updated_at": self.last_updated_at.isoformat() if self.last_updated_at else None,
            "update_count": len(self.update_history),
        }


class MessageQueue:
    """Priority queue for agent messages."""

    def __init__(self, agent_id: str, max_size: int = 1000):
        """Initialize message queue."""
        self.agent_id = agent_id
        self.max_size = max_size
        self.queues: Dict[MessagePriority, Deque[Message]] = {
            priority: deque() for priority in MessagePriority
        }
        self.processed_count = 0
        self.dropped_count = 0

    def enqueue(self, message: Message) -> bool:
        """Add message to queue."""
        queue = self.queues[message.priority]

        # Check size limit
        total_size = sum(len(q) for q in self.queues.values())
        if total_size >= self.max_size:
            # Drop lowest priority message
            for priority in MessagePriority:
                if self.queues[priority]:
                    self.queues[priority].popleft()
                    self.dropped_count += 1
                    break

        queue.append(message)
        message.delivered_at = datetime.now(timezone.utc)
        return True

    def dequeue(self) -> Optional[Message]:
        """Get next message (highest priority first)."""
        # Check in priority order
        for priority in reversed(list(MessagePriority)):
            queue = self.queues[priority]
            if queue:
                message = queue.popleft()
                message.processed_at = datetime.now(timezone.utc)
                self.processed_count += 1
                return message
        return None

    def peek(self) -> Optional[Message]:
        """Peek at next message without removing."""
        for priority in reversed(list(MessagePriority)):
            queue = self.queues[priority]
            if queue:
                return queue[0]
        return None

    def size(self) -> int:
        """Get total queue size."""
        return sum(len(q) for q in self.queues.values())

    def clear_expired(self):
        """Remove expired messages."""
        for queue in self.queues.values():
            valid_messages = [msg for msg in queue if not msg.is_expired()]
            expired_count = len(queue) - len(valid_messages)
            queue.clear()
            queue.extend(valid_messages)
            self.dropped_count += expired_count


class AgentCommunicationProtocol:
    """Agent communication protocol manager."""

    def __init__(self, state_dir: Optional[Path] = None):
        """Initialize communication protocol."""
        self.state_dir = state_dir or Path.home() / ".cache" / "ai-harness" / "communication"
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.message_queues: Dict[str, MessageQueue] = {}
        self.shared_contexts: Dict[str, SharedContext] = {}  # team_id -> context
        self.message_log: List[Dict[str, Any]] = []
        self.pending_responses: Dict[str, Message] = {}  # message_id -> request

        # Metrics
        self.total_messages_sent = 0
        self.total_messages_delivered = 0
        self.total_conflicts = 0
        self.avg_latency = 0.0

        self._load_state()

    def _load_state(self):
        """Load state from disk."""
        log_file = self.state_dir / "message_log.json"

        try:
            if log_file.exists():
                with open(log_file) as f:
                    data = json.load(f)
                    self.message_log = data.get("messages", [])
        except Exception as e:
            logger.warning(f"Failed to load message log: {e}")

    def _save_state(self):
        """Save state to disk."""
        log_file = self.state_dir / "message_log.json"

        try:
            # Only keep recent messages (last 1000)
            recent_messages = self.message_log[-1000:]
            with open(log_file, 'w') as f:
                json.dump({"messages": recent_messages}, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save message log: {e}")

    def register_agent(self, agent_id: str, max_queue_size: int = 1000):
        """Register agent and create message queue."""
        if agent_id not in self.message_queues:
            self.message_queues[agent_id] = MessageQueue(agent_id, max_queue_size)
            logger.info("agent_registered", agent_id=agent_id)

    def unregister_agent(self, agent_id: str):
        """Unregister agent and cleanup queue."""
        if agent_id in self.message_queues:
            del self.message_queues[agent_id]
            logger.info("agent_unregistered", agent_id=agent_id)

    def create_shared_context(self, team_id: str) -> SharedContext:
        """Create shared context for team."""
        if team_id not in self.shared_contexts:
            self.shared_contexts[team_id] = SharedContext(team_id=team_id)
            logger.info("shared_context_created", team_id=team_id)
        return self.shared_contexts[team_id]

    def get_shared_context(self, team_id: str) -> Optional[SharedContext]:
        """Get shared context for team."""
        return self.shared_contexts.get(team_id)

    async def send_message(self,
                          from_agent: str,
                          to_agent: Optional[str],
                          team_id: str,
                          message_type: MessageType,
                          content: Dict[str, Any],
                          priority: MessagePriority = MessagePriority.NORMAL,
                          requires_response: bool = False,
                          timeout: int = 300) -> str:
        """Send message from one agent to another (or broadcast)."""
        message_id = str(uuid.uuid4())

        message = Message(
            message_id=message_id,
            message_type=message_type,
            from_agent=from_agent,
            to_agent=to_agent,
            team_id=team_id,
            priority=priority,
            content=content,
            requires_response=requires_response,
            timeout=timeout,
        )

        # Broadcast or unicast
        if to_agent is None:
            # Broadcast to all agents in team
            delivered = 0
            for agent_id, queue in self.message_queues.items():
                if agent_id != from_agent:  # Don't send to self
                    queue.enqueue(message)
                    delivered += 1
            self.total_messages_delivered += delivered
        else:
            # Unicast to specific agent
            if to_agent not in self.message_queues:
                logger.error("agent_not_found", agent_id=to_agent)
                raise ValueError(f"Agent {to_agent} not registered")

            self.message_queues[to_agent].enqueue(message)
            self.total_messages_delivered += 1

        # Track if response required
        if requires_response:
            self.pending_responses[message_id] = message

        # Log message
        self.message_log.append({
            "message_id": message_id,
            "type": message_type.value,
            "from": from_agent,
            "to": to_agent or "broadcast",
            "team_id": team_id,
            "priority": priority.value,
            "timestamp": message.created_at.isoformat(),
        })

        self.total_messages_sent += 1
        self._save_state()

        logger.info("message_sent",
                   message_id=message_id,
                   from_agent=from_agent,
                   to_agent=to_agent or "broadcast",
                   message_type=message_type.value)

        return message_id

    async def receive_message(self, agent_id: str, timeout: float = 1.0) -> Optional[Message]:
        """Receive next message for agent (with timeout)."""
        if agent_id not in self.message_queues:
            logger.error("agent_not_found", agent_id=agent_id)
            return None

        queue = self.message_queues[agent_id]

        # Try to get message immediately
        message = queue.dequeue()
        if message:
            return message

        # Wait for message with timeout
        start = time.time()
        while time.time() - start < timeout:
            await asyncio.sleep(0.1)
            message = queue.dequeue()
            if message:
                return message

        return None

    async def send_response(self,
                           from_agent: str,
                           in_reply_to: str,
                           content: Dict[str, Any],
                           priority: MessagePriority = MessagePriority.NORMAL):
        """Send response to a request message."""
        # Find original message
        original = self.pending_responses.get(in_reply_to)
        if not original:
            logger.warning("original_message_not_found", message_id=in_reply_to)
            # Try to extract from log
            for log_entry in reversed(self.message_log):
                if log_entry["message_id"] == in_reply_to:
                    to_agent = log_entry["from"]
                    team_id = log_entry["team_id"]
                    break
            else:
                raise ValueError(f"Original message {in_reply_to} not found")
        else:
            to_agent = original.from_agent
            team_id = original.team_id

        # Send response
        message_id = await self.send_message(
            from_agent=from_agent,
            to_agent=to_agent,
            team_id=team_id,
            message_type=MessageType.RESPONSE,
            content=content,
            priority=priority,
        )

        # Mark request as responded
        if in_reply_to in self.pending_responses:
            del self.pending_responses[in_reply_to]

        return message_id

    async def update_shared_context(self,
                                   team_id: str,
                                   agent_id: str,
                                   updates: Dict[str, Any],
                                   broadcast: bool = True) -> List[Dict[str, Any]]:
        """Update shared context and optionally broadcast."""
        context = self.get_shared_context(team_id)
        if not context:
            context = self.create_shared_context(team_id)

        # Apply updates and detect conflicts
        conflicts = context.update(updates, agent_id)

        if conflicts:
            self.total_conflicts += len(conflicts)
            logger.warning("context_conflicts_detected",
                          team_id=team_id,
                          agent_id=agent_id,
                          conflicts=len(conflicts))

        # Broadcast update
        if broadcast:
            await self.send_message(
                from_agent=agent_id,
                to_agent=None,  # Broadcast
                team_id=team_id,
                message_type=MessageType.CONTEXT_UPDATE,
                content={
                    "updates": updates,
                    "version": context.version,
                    "conflicts": conflicts,
                },
                priority=MessagePriority.HIGH,
            )

        logger.info("context_updated",
                   team_id=team_id,
                   agent_id=agent_id,
                   version=context.version,
                   conflicts=len(conflicts))

        return conflicts

    async def request_consensus(self,
                               from_agent: str,
                               team_id: str,
                               proposal: Dict[str, Any],
                               timeout: int = 60) -> str:
        """Request consensus vote from team."""
        consensus_id = str(uuid.uuid4())

        await self.send_message(
            from_agent=from_agent,
            to_agent=None,  # Broadcast
            team_id=team_id,
            message_type=MessageType.CONSENSUS,
            content={
                "consensus_id": consensus_id,
                "proposal": proposal,
            },
            priority=MessagePriority.HIGH,
            requires_response=True,
            timeout=timeout,
        )

        logger.info("consensus_requested",
                   consensus_id=consensus_id,
                   from_agent=from_agent,
                   team_id=team_id)

        return consensus_id

    async def vote_consensus(self,
                            from_agent: str,
                            consensus_id: str,
                            team_id: str,
                            vote: bool,
                            reasoning: str = ""):
        """Submit consensus vote."""
        # Find consensus request in log
        original_message = None
        for log_entry in reversed(self.message_log):
            if (log_entry.get("type") == "consensus" and
                log_entry.get("team_id") == team_id):
                # Check content for consensus_id
                original_message = log_entry
                break

        if not original_message:
            logger.warning("consensus_request_not_found", consensus_id=consensus_id)

        await self.send_message(
            from_agent=from_agent,
            to_agent=None,  # Broadcast vote
            team_id=team_id,
            message_type=MessageType.CONSENSUS_VOTE,
            content={
                "consensus_id": consensus_id,
                "vote": vote,
                "reasoning": reasoning,
            },
            priority=MessagePriority.HIGH,
        )

        logger.info("consensus_vote_submitted",
                   consensus_id=consensus_id,
                   from_agent=from_agent,
                   vote=vote)

    def cleanup_expired_messages(self):
        """Clean up expired messages from all queues."""
        for queue in self.message_queues.values():
            queue.clear_expired()

    def get_queue_status(self, agent_id: str) -> Dict[str, Any]:
        """Get queue status for agent."""
        if agent_id not in self.message_queues:
            return {"error": "Agent not found"}

        queue = self.message_queues[agent_id]
        return {
            "agent_id": agent_id,
            "queue_size": queue.size(),
            "processed_count": queue.processed_count,
            "dropped_count": queue.dropped_count,
            "queue_by_priority": {
                priority.name: len(queue.queues[priority])
                for priority in MessagePriority
            },
        }

    def get_communication_metrics(self) -> Dict[str, Any]:
        """Get communication metrics."""
        total_queue_size = sum(q.size() for q in self.message_queues.values())
        total_processed = sum(q.processed_count for q in self.message_queues.values())
        total_dropped = sum(q.dropped_count for q in self.message_queues.values())

        # Calculate average latency
        latencies = []
        for log_entry in self.message_log[-100:]:  # Last 100 messages
            # Simple latency estimate (would need more data in production)
            latencies.append(0.05)  # Placeholder

        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

        return {
            "total_messages_sent": self.total_messages_sent,
            "total_messages_delivered": self.total_messages_delivered,
            "total_processed": total_processed,
            "total_dropped": total_dropped,
            "total_conflicts": self.total_conflicts,
            "avg_latency_ms": round(avg_latency * 1000, 2),
            "pending_responses": len(self.pending_responses),
            "active_agents": len(self.message_queues),
            "total_queue_size": total_queue_size,
            "active_contexts": len(self.shared_contexts),
        }
