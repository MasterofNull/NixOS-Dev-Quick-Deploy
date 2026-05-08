"""
skill_usage_tracker.py — Skill Usage Tracking & Analytics

Tracks skill invocations across the system:
- Which skills are being used
- Usage frequency and trends
- Success/failure rates
- Agent/profile usage patterns
- Provides recommendations for skill adoption

Batch 5.2: Skill Usage Tracking
"""

from __future__ import annotations

import time
import logging
from collections import deque, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Skill Usage Tracking
# ---------------------------------------------------------------------------

@dataclass
class SkillUsageEvent:
    """A single skill usage event."""
    skill_slug: str
    timestamp: str
    agent: str  # Which agent/profile used it
    success: bool
    latency_ms: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "skill_slug": self.skill_slug,
            "timestamp": self.timestamp,
            "agent": self.agent,
            "success": self.success,
            "latency_ms": round(self.latency_ms, 2),
            "metadata": self.metadata,
        }


@dataclass
class SkillUsageStats:
    """Aggregated statistics for a skill."""
    skill_slug: str
    total_uses: int = 0
    successful_uses: int = 0
    failed_uses: int = 0
    avg_latency_ms: float = 0.0
    recent_agents: deque = field(default_factory=lambda: deque(maxlen=10))
    last_used: Optional[str] = None

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_uses == 0:
            return 0.0
        return self.successful_uses / self.total_uses

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "skill_slug": self.skill_slug,
            "total_uses": self.total_uses,
            "successful_uses": self.successful_uses,
            "failed_uses": self.failed_uses,
            "success_rate": round(self.success_rate, 3),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "recent_agents": list(self.recent_agents),
            "last_used": self.last_used,
        }


@dataclass
class SkillTrackerState:
    """Global skill tracking state."""
    usage_history: deque = field(default_factory=lambda: deque(maxlen=1000))
    skill_stats: Dict[str, SkillUsageStats] = field(default_factory=dict)
    agent_skill_matrix: Dict[str, Dict[str, int]] = field(default_factory=lambda: defaultdict(lambda: defaultdict(int)))


_tracker_state = SkillTrackerState()


def track_skill_usage(
    skill_slug: str,
    agent: str,
    success: bool,
    latency_ms: float,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Record a skill usage event.

    Args:
        skill_slug: Skill identifier
        agent: Agent/profile that used the skill
        success: Whether the skill invocation succeeded
        latency_ms: Execution latency
        metadata: Optional additional context
    """
    global _tracker_state

    event = SkillUsageEvent(
        skill_slug=skill_slug,
        timestamp=datetime.now(tz=timezone.utc).isoformat(),
        agent=agent,
        success=success,
        latency_ms=latency_ms,
        metadata=metadata or {},
    )

    _tracker_state.usage_history.append(event)

    # Update skill stats
    if skill_slug not in _tracker_state.skill_stats:
        _tracker_state.skill_stats[skill_slug] = SkillUsageStats(skill_slug=skill_slug)

    stats = _tracker_state.skill_stats[skill_slug]
    stats.total_uses += 1
    if success:
        stats.successful_uses += 1
    else:
        stats.failed_uses += 1

    # Update running average latency
    n = stats.total_uses
    stats.avg_latency_ms = ((stats.avg_latency_ms * (n - 1)) + latency_ms) / n

    stats.recent_agents.append(agent)
    stats.last_used = event.timestamp

    # Update agent-skill matrix
    _tracker_state.agent_skill_matrix[agent][skill_slug] += 1

    logger.debug(
        f"Tracked skill usage: {skill_slug} by {agent}, success={success}, latency={latency_ms:.2f}ms"
    )


def get_skill_usage_stats() -> Dict[str, Any]:
    """
    Get comprehensive skill usage statistics.

    Returns:
        Dictionary with usage stats, trends, and recommendations
    """
    stats = _tracker_state.skill_stats

    # Calculate top skills by usage
    top_skills = sorted(
        stats.values(),
        key=lambda s: s.total_uses,
        reverse=True
    )[:10]

    # Calculate underused skills (defined but rarely used)
    underused_threshold = 5
    underused_skills = [
        s.skill_slug for s in stats.values()
        if s.total_uses < underused_threshold
    ]

    # Calculate failing skills (success rate < 0.7)
    failing_skills = [
        {
            "skill_slug": s.skill_slug,
            "success_rate": round(s.success_rate, 3),
            "total_uses": s.total_uses,
        }
        for s in stats.values()
        if s.success_rate < 0.7 and s.total_uses >= 3
    ]

    # Agent preferences
    agent_preferences = {}
    for agent, skill_counts in _tracker_state.agent_skill_matrix.items():
        top_skill = max(skill_counts.items(), key=lambda x: x[1]) if skill_counts else None
        agent_preferences[agent] = {
            "total_skills_used": len(skill_counts),
            "top_skill": top_skill[0] if top_skill else None,
            "top_skill_count": top_skill[1] if top_skill else 0,
        }

    return {
        "total_events": len(_tracker_state.usage_history),
        "unique_skills_used": len(stats),
        "top_skills": [s.to_dict() for s in top_skills],
        "underused_skills": underused_skills,
        "failing_skills": failing_skills,
        "agent_preferences": agent_preferences,
        "active": True,
    }


def get_skill_recommendation(agent: str, task_type: Optional[str] = None) -> List[str]:
    """
    Recommend skills for an agent based on historical usage patterns.

    Args:
        agent: Agent/profile requesting recommendation
        task_type: Optional task type for context-aware recommendation

    Returns:
        List of recommended skill slugs
    """
    # Get agent's previous skill usage
    agent_skills = _tracker_state.agent_skill_matrix.get(agent, {})

    # Get all successful skills
    successful_skills = [
        s.skill_slug for s in _tracker_state.skill_stats.values()
        if s.success_rate >= 0.8 and s.total_uses >= 3
    ]

    # Recommend skills that:
    # 1. Haven't been used by this agent yet
    # 2. Have high success rates overall
    # 3. Are popular among other agents
    unused_by_agent = [
        slug for slug in successful_skills
        if slug not in agent_skills
    ]

    # Sort by total uses (popularity)
    recommended = sorted(
        unused_by_agent,
        key=lambda slug: _tracker_state.skill_stats[slug].total_uses,
        reverse=True
    )[:5]

    return recommended


def get_recent_skill_events(limit: int = 20) -> List[Dict[str, Any]]:
    """
    Get recent skill usage events.

    Args:
        limit: Maximum number of events to return

    Returns:
        List of recent skill events
    """
    events = list(_tracker_state.usage_history)[-limit:]
    return [e.to_dict() for e in reversed(events)]


def clear_skill_tracking() -> int:
    """
    Clear all skill tracking data.

    Returns:
        Number of events cleared
    """
    global _tracker_state

    count = len(_tracker_state.usage_history)
    _tracker_state.usage_history.clear()
    _tracker_state.skill_stats.clear()
    _tracker_state.agent_skill_matrix.clear()

    logger.info(f"Cleared {count} skill tracking events")
    return count
