"""
quality_monitor.py — Quality Monitoring & Alerting

Tracks quality metrics across all features:
- RAG reflection confidence trends
- Critic evaluation scores
- Cache hit rates and quality
- Overall system quality health

Provides:
- Trend detection (degradation, improvement)
- Alerting thresholds
- Health scoring
- Anomaly detection
"""

from __future__ import annotations

import time
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Alert Levels
# ---------------------------------------------------------------------------

class AlertLevel(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class QualityAlert:
    """A quality alert with context."""
    level: AlertLevel
    metric: str
    message: str
    current_value: float
    threshold: float
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "level": self.level.value,
            "metric": self.metric,
            "message": self.message,
            "current_value": round(self.current_value, 3),
            "threshold": round(self.threshold, 3),
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Quality Thresholds
# ---------------------------------------------------------------------------

# Reflection confidence thresholds
REFLECTION_CONFIDENCE_WARNING = 0.7
REFLECTION_CONFIDENCE_CRITICAL = 0.5

# Critic score thresholds
CRITIC_QUALITY_WARNING = 75.0
CRITIC_QUALITY_CRITICAL = 60.0

# Cache hit rate thresholds
CACHE_HIT_RATE_WARNING = 0.3
CACHE_HIT_RATE_CRITICAL = 0.1

# Intervention rate thresholds (high = problem)
CRITIC_INTERVENTION_WARNING = 0.4
CRITIC_INTERVENTION_CRITICAL = 0.6


# ---------------------------------------------------------------------------
# Quality Monitor
# ---------------------------------------------------------------------------

@dataclass
class QualityMonitorState:
    """Tracks quality monitor state."""
    alerts: deque = field(default_factory=lambda: deque(maxlen=100))
    last_check_time: float = 0.0
    check_count: int = 0

    # Trend tracking
    reflection_trend: deque = field(default_factory=lambda: deque(maxlen=50))
    critic_trend: deque = field(default_factory=lambda: deque(maxlen=50))
    cache_trend: deque = field(default_factory=lambda: deque(maxlen=50))


_monitor_state = QualityMonitorState()


def check_quality_health(
    reflection_stats: Optional[Dict[str, Any]] = None,
    critic_stats: Optional[Dict[str, Any]] = None,
    cache_stats: Optional[Dict[str, Any]] = None,
) -> Tuple[float, List[QualityAlert]]:
    """
    Check overall quality health and generate alerts.

    Args:
        reflection_stats: RAG reflection statistics
        critic_stats: Generator-critic statistics
        cache_stats: Quality cache statistics

    Returns:
        (health_score 0-100, list of alerts)
    """
    global _monitor_state

    _monitor_state.check_count += 1
    _monitor_state.last_check_time = time.time()

    alerts = []
    health_components = []

    # Check reflection confidence
    if reflection_stats and reflection_stats.get("active"):
        avg_conf = reflection_stats.get("avg_final_confidence", 1.0)
        _monitor_state.reflection_trend.append(avg_conf)

        if avg_conf < REFLECTION_CONFIDENCE_CRITICAL:
            alerts.append(QualityAlert(
                level=AlertLevel.CRITICAL,
                metric="reflection_confidence",
                message=f"Reflection confidence critically low: {avg_conf:.2%}",
                current_value=avg_conf,
                threshold=REFLECTION_CONFIDENCE_CRITICAL,
                timestamp=datetime.now(tz=timezone.utc).isoformat(),
            ))
            health_components.append(30.0)  # Critical = 30%
        elif avg_conf < REFLECTION_CONFIDENCE_WARNING:
            alerts.append(QualityAlert(
                level=AlertLevel.WARNING,
                metric="reflection_confidence",
                message=f"Reflection confidence low: {avg_conf:.2%}",
                current_value=avg_conf,
                threshold=REFLECTION_CONFIDENCE_WARNING,
                timestamp=datetime.now(tz=timezone.utc).isoformat(),
            ))
            health_components.append(70.0)  # Warning = 70%
        else:
            health_components.append(100.0)  # Healthy

    # Check critic quality scores
    if critic_stats and critic_stats.get("active"):
        avg_quality = critic_stats.get("avg_quality_score", 100.0)
        intervention_rate = critic_stats.get("intervention_rate", 0.0)

        _monitor_state.critic_trend.append(avg_quality)

        # Check quality score
        if avg_quality > 0 and avg_quality < CRITIC_QUALITY_CRITICAL:
            alerts.append(QualityAlert(
                level=AlertLevel.CRITICAL,
                metric="critic_quality",
                message=f"Critic quality critically low: {avg_quality:.1f}/100",
                current_value=avg_quality,
                threshold=CRITIC_QUALITY_CRITICAL,
                timestamp=datetime.now(tz=timezone.utc).isoformat(),
            ))
            health_components.append(30.0)
        elif avg_quality > 0 and avg_quality < CRITIC_QUALITY_WARNING:
            alerts.append(QualityAlert(
                level=AlertLevel.WARNING,
                metric="critic_quality",
                message=f"Critic quality low: {avg_quality:.1f}/100",
                current_value=avg_quality,
                threshold=CRITIC_QUALITY_WARNING,
                timestamp=datetime.now(tz=timezone.utc).isoformat(),
            ))
            health_components.append(70.0)
        else:
            health_components.append(100.0)

        # Check intervention rate (high = bad)
        if intervention_rate > CRITIC_INTERVENTION_CRITICAL:
            alerts.append(QualityAlert(
                level=AlertLevel.CRITICAL,
                metric="critic_intervention_rate",
                message=f"Critic intervention rate critically high: {intervention_rate:.1%}",
                current_value=intervention_rate,
                threshold=CRITIC_INTERVENTION_CRITICAL,
                timestamp=datetime.now(tz=timezone.utc).isoformat(),
            ))
            health_components.append(30.0)
        elif intervention_rate > CRITIC_INTERVENTION_WARNING:
            alerts.append(QualityAlert(
                level=AlertLevel.WARNING,
                metric="critic_intervention_rate",
                message=f"Critic intervention rate high: {intervention_rate:.1%}",
                current_value=intervention_rate,
                threshold=CRITIC_INTERVENTION_WARNING,
                timestamp=datetime.now(tz=timezone.utc).isoformat(),
            ))
            health_components.append(70.0)

    # Check cache hit rate
    if cache_stats and cache_stats.get("active"):
        hit_rate = cache_stats.get("hit_rate", 0.0)
        avg_quality = cache_stats.get("avg_hit_quality", 100.0)

        _monitor_state.cache_trend.append(hit_rate)

        if hit_rate > 0 and hit_rate < CACHE_HIT_RATE_CRITICAL:
            alerts.append(QualityAlert(
                level=AlertLevel.WARNING,
                metric="cache_hit_rate",
                message=f"Cache hit rate low: {hit_rate:.1%}",
                current_value=hit_rate,
                threshold=CACHE_HIT_RATE_CRITICAL,
                timestamp=datetime.now(tz=timezone.utc).isoformat(),
            ))
            health_components.append(70.0)
        elif hit_rate > 0 and hit_rate < CACHE_HIT_RATE_WARNING:
            alerts.append(QualityAlert(
                level=AlertLevel.INFO,
                metric="cache_hit_rate",
                message=f"Cache hit rate could be improved: {hit_rate:.1%}",
                current_value=hit_rate,
                threshold=CACHE_HIT_RATE_WARNING,
                timestamp=datetime.now(tz=timezone.utc).isoformat(),
            ))
            health_components.append(85.0)
        else:
            health_components.append(100.0)

    # Calculate overall health score
    if health_components:
        health_score = sum(health_components) / len(health_components)
    else:
        health_score = 100.0  # No data = assume healthy

    # Store alerts
    for alert in alerts:
        _monitor_state.alerts.append(alert)

    return (health_score, alerts)


def detect_trends() -> Dict[str, Any]:
    """
    Detect quality trends over time.

    Returns:
        Dictionary with trend analysis
    """
    trends = {}

    # Reflection confidence trend
    if len(_monitor_state.reflection_trend) >= 5:
        recent = list(_monitor_state.reflection_trend)[-5:]
        older = list(_monitor_state.reflection_trend)[:-5]

        if older:
            recent_avg = sum(recent) / len(recent)
            older_avg = sum(older) / len(older)
            change = recent_avg - older_avg

            trends["reflection_confidence"] = {
                "direction": "improving" if change > 0.05 else "degrading" if change < -0.05 else "stable",
                "recent_avg": round(recent_avg, 3),
                "older_avg": round(older_avg, 3),
                "change": round(change, 3),
            }

    # Critic quality trend
    if len(_monitor_state.critic_trend) >= 5:
        recent = list(_monitor_state.critic_trend)[-5:]
        older = list(_monitor_state.critic_trend)[:-5]

        if older and all(x > 0 for x in recent + older):
            recent_avg = sum(recent) / len(recent)
            older_avg = sum(older) / len(older)
            change = recent_avg - older_avg

            trends["critic_quality"] = {
                "direction": "improving" if change > 5.0 else "degrading" if change < -5.0 else "stable",
                "recent_avg": round(recent_avg, 1),
                "older_avg": round(older_avg, 1),
                "change": round(change, 1),
            }

    # Cache hit rate trend
    if len(_monitor_state.cache_trend) >= 5:
        recent = list(_monitor_state.cache_trend)[-5:]
        older = list(_monitor_state.cache_trend)[:-5]

        if older and all(x > 0 for x in recent):
            recent_avg = sum(recent) / len(recent)
            older_avg = sum(older) / len(older)
            change = recent_avg - older_avg

            trends["cache_hit_rate"] = {
                "direction": "improving" if change > 0.1 else "degrading" if change < -0.1 else "stable",
                "recent_avg": round(recent_avg, 3),
                "older_avg": round(older_avg, 3),
                "change": round(change, 3),
            }

    return trends


def get_monitor_stats() -> Dict[str, Any]:
    """Get quality monitor statistics."""
    recent_alerts = list(_monitor_state.alerts)[-10:]  # Last 10 alerts

    # Count alerts by level
    alert_counts = {
        "critical": sum(1 for a in recent_alerts if a.level == AlertLevel.CRITICAL),
        "warning": sum(1 for a in recent_alerts if a.level == AlertLevel.WARNING),
        "info": sum(1 for a in recent_alerts if a.level == AlertLevel.INFO),
    }

    # Get trends
    trends = detect_trends()

    return {
        "check_count": _monitor_state.check_count,
        "last_check_time": datetime.fromtimestamp(
            _monitor_state.last_check_time, tz=timezone.utc
        ).isoformat() if _monitor_state.last_check_time > 0 else None,
        "recent_alerts": [a.to_dict() for a in recent_alerts],
        "alert_counts": alert_counts,
        "trends": trends,
        "active": True,
    }


def get_health_summary(
    reflection_stats: Optional[Dict[str, Any]] = None,
    critic_stats: Optional[Dict[str, Any]] = None,
    cache_stats: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Get comprehensive health summary.

    Args:
        reflection_stats: RAG reflection statistics
        critic_stats: Generator-critic statistics
        cache_stats: Quality cache statistics

    Returns:
        Health summary with score and alerts
    """
    health_score, alerts = check_quality_health(
        reflection_stats, critic_stats, cache_stats
    )

    return {
        "health_score": round(health_score, 1),
        "status": (
            "healthy" if health_score >= 90
            else "degraded" if health_score >= 70
            else "critical"
        ),
        "active_alerts": [a.to_dict() for a in alerts],
        "alert_count": len(alerts),
        "critical_count": sum(1 for a in alerts if a.level == AlertLevel.CRITICAL),
        "warning_count": sum(1 for a in alerts if a.level == AlertLevel.WARNING),
    }
