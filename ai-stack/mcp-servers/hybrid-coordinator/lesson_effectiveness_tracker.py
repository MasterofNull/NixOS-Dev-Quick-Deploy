"""
lesson_effectiveness_tracker.py — Lesson Effectiveness Tracking & Analytics

Tracks lesson usage across the system:
- Which lessons are being referenced
- Usage frequency and trends
- Success/failure rates when lessons are applied
- Impact on query quality and outcomes
- Provides recommendations for lesson promotion/retirement

Batch 5.1: Lesson Effectiveness Tracking
"""

from __future__ import annotations

import logging
import time
from collections import deque, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lesson Usage Tracking
# ---------------------------------------------------------------------------

@dataclass
class LessonUsageEvent:
    """A single lesson usage/reference event."""
    lesson_key: str
    timestamp: str
    context: str  # Where was it used: "hints", "delegate", "workflow", etc.
    success: bool  # Whether the operation using this lesson succeeded
    agent: str  # Which agent referenced it
    latency_ms: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "lesson_key": self.lesson_key,
            "timestamp": self.timestamp,
            "context": self.context,
            "success": self.success,
            "agent": self.agent,
            "latency_ms": round(self.latency_ms, 2),
            "metadata": self.metadata,
        }


@dataclass
class LessonEffectivenessStats:
    """Aggregated statistics for a lesson."""
    lesson_key: str
    total_uses: int = 0
    successful_uses: int = 0
    failed_uses: int = 0
    avg_latency_ms: float = 0.0
    recent_contexts: deque = field(default_factory=lambda: deque(maxlen=10))
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
            "lesson_key": self.lesson_key,
            "total_uses": self.total_uses,
            "successful_uses": self.successful_uses,
            "failed_uses": self.failed_uses,
            "success_rate": round(self.success_rate, 3),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "recent_contexts": list(self.recent_contexts),
            "last_used": self.last_used,
        }


@dataclass
class LessonTrackerState:
    """Global lesson tracking state."""
    usage_history: deque = field(default_factory=lambda: deque(maxlen=1000))
    lesson_stats: Dict[str, LessonEffectivenessStats] = field(default_factory=dict)
    context_usage_matrix: Dict[str, Dict[str, int]] = field(default_factory=lambda: defaultdict(lambda: defaultdict(int)))


_tracker_state = LessonTrackerState()


def track_lesson_usage(
    lesson_key: str,
    context: str,
    success: bool,
    agent: str = "unknown",
    latency_ms: float = 0.0,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Record a lesson usage event.

    Args:
        lesson_key: Lesson identifier
        context: Where the lesson was used (hints, delegate, workflow, etc.)
        success: Whether the operation succeeded
        agent: Agent that used the lesson
        latency_ms: Execution latency
        metadata: Optional additional context
    """
    global _tracker_state

    event = LessonUsageEvent(
        lesson_key=lesson_key,
        timestamp=datetime.now(tz=timezone.utc).isoformat(),
        context=context,
        success=success,
        agent=agent,
        latency_ms=latency_ms,
        metadata=metadata or {},
    )

    _tracker_state.usage_history.append(event)

    # Update lesson stats
    if lesson_key not in _tracker_state.lesson_stats:
        _tracker_state.lesson_stats[lesson_key] = LessonEffectivenessStats(lesson_key=lesson_key)

    stats = _tracker_state.lesson_stats[lesson_key]
    stats.total_uses += 1
    if success:
        stats.successful_uses += 1
    else:
        stats.failed_uses += 1

    # Update running average latency
    n = stats.total_uses
    stats.avg_latency_ms = ((stats.avg_latency_ms * (n - 1)) + latency_ms) / n

    stats.recent_contexts.append(context)
    stats.last_used = event.timestamp

    # Update context-lesson matrix
    _tracker_state.context_usage_matrix[context][lesson_key] += 1

    logger.debug(
        f"Tracked lesson usage: {lesson_key} in {context}, success={success}, latency={latency_ms:.2f}ms"
    )


def get_lesson_effectiveness_stats() -> Dict[str, Any]:
    """
    Get comprehensive lesson effectiveness statistics.

    Returns:
        Dictionary with usage stats, trends, and recommendations
    """
    stats = _tracker_state.lesson_stats

    # Calculate top lessons by usage
    top_lessons = sorted(
        stats.values(),
        key=lambda s: s.total_uses,
        reverse=True
    )[:10]

    # Calculate underused lessons (defined but rarely used)
    underused_threshold = 5
    underused_lessons = [
        s.lesson_key for s in stats.values()
        if s.total_uses < underused_threshold
    ]

    # Calculate ineffective lessons (success rate < 0.6)
    ineffective_lessons = [
        {
            "lesson_key": s.lesson_key,
            "success_rate": round(s.success_rate, 3),
            "total_uses": s.total_uses,
        }
        for s in stats.values()
        if s.success_rate < 0.6 and s.total_uses >= 3
    ]

    # Calculate highly effective lessons (success rate >= 0.9, usage >= 5)
    highly_effective = [
        {
            "lesson_key": s.lesson_key,
            "success_rate": round(s.success_rate, 3),
            "total_uses": s.total_uses,
        }
        for s in stats.values()
        if s.success_rate >= 0.9 and s.total_uses >= 5
    ]

    # Context preferences
    context_preferences = {}
    for context, lesson_counts in _tracker_state.context_usage_matrix.items():
        top_lesson = max(lesson_counts.items(), key=lambda x: x[1]) if lesson_counts else None
        context_preferences[context] = {
            "total_lessons_used": len(lesson_counts),
            "top_lesson": top_lesson[0] if top_lesson else None,
            "top_lesson_count": top_lesson[1] if top_lesson else 0,
        }

    return {
        "total_events": len(_tracker_state.usage_history),
        "unique_lessons_used": len(stats),
        "top_lessons": [s.to_dict() for s in top_lessons],
        "underused_lessons": underused_lessons,
        "ineffective_lessons": ineffective_lessons,
        "highly_effective_lessons": highly_effective,
        "context_preferences": context_preferences,
        "active": True,
    }


def get_lesson_recommendation(context: str) -> List[str]:
    """
    Recommend lessons for a specific context based on historical effectiveness.

    Args:
        context: Context requesting recommendation (hints, delegate, workflow, etc.)

    Returns:
        List of recommended lesson keys
    """
    # Get lessons that were successful in this context
    successful_lessons = [
        s.lesson_key for s in _tracker_state.lesson_stats.values()
        if s.success_rate >= 0.8 and s.total_uses >= 3
        and context in list(s.recent_contexts)
    ]

    # Sort by total uses (popularity)
    recommended = sorted(
        successful_lessons,
        key=lambda key: _tracker_state.lesson_stats[key].total_uses,
        reverse=True
    )[:5]

    return recommended


def get_recent_lesson_events(limit: int = 20) -> List[Dict[str, Any]]:
    """
    Get recent lesson usage events.

    Args:
        limit: Maximum number of events to return

    Returns:
        List of recent lesson events
    """
    events = list(_tracker_state.usage_history)[-limit:]
    return [e.to_dict() for e in reversed(events)]


def clear_lesson_tracking() -> int:
    """
    Clear all lesson tracking data.

    Returns:
        Number of events cleared
    """
    global _tracker_state

    count = len(_tracker_state.usage_history)
    _tracker_state.usage_history.clear()
    _tracker_state.lesson_stats.clear()
    _tracker_state.context_usage_matrix.clear()

    logger.info(f"Cleared {count} lesson tracking events")
    return count
