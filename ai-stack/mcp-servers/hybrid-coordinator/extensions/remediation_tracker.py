"""
remediation_tracker.py — Gap Remediation Success Rate Tracking

Tracks gap auto-remediation success rates and trends:
- Reads remediation logs from aq-gap-auto-remediate
- Calculates success/failure rates
- Tracks remediation velocity (attempts per day)
- Identifies problem gaps (repeatedly failing remediations)

Batch 6.3: Track Remediation Success Rate
"""

from __future__ import annotations

import json
import logging
import os
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Default log directory
DEFAULT_LOG_DIR = Path(os.getenv(
    "GAP_REMEDIATION_LOG_DIR",
    Path.home() / ".local/state/nixos-ai-stack/gap-remediation"
))


# ---------------------------------------------------------------------------
# Remediation Event
# ---------------------------------------------------------------------------

@dataclass
class RemediationEvent:
    """A single gap remediation attempt."""
    query: str
    timestamp: str
    success: bool
    method: str  # "knowledge_import", "manual", "skipped"
    duration_ms: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> Optional[RemediationEvent]:
        """Parse from JSONL log entry."""
        try:
            return cls(
                query=str(data.get("query", "")).strip(),
                timestamp=str(data.get("timestamp", "")),
                success=bool(data.get("success", False)),
                method=str(data.get("method", "unknown")),
                duration_ms=float(data.get("duration_ms", 0.0)),
                metadata=data.get("metadata", {}),
            )
        except Exception as exc:
            logger.debug(f"Failed to parse remediation event: {exc}")
            return None


# ---------------------------------------------------------------------------
# Remediation Tracking
# ---------------------------------------------------------------------------

@dataclass
class RemediationStats:
    """Aggregated remediation statistics."""
    total_attempts: int = 0
    successful_attempts: int = 0
    failed_attempts: int = 0
    skipped_attempts: int = 0
    avg_duration_ms: float = 0.0
    recent_events: deque = field(default_factory=lambda: deque(maxlen=100))
    problem_gaps: Dict[str, int] = field(default_factory=lambda: defaultdict(int))

    @property
    def success_rate(self) -> float:
        """Calculate overall success rate."""
        if self.total_attempts == 0:
            return 0.0
        return self.successful_attempts / self.total_attempts


def load_remediation_logs(
    log_dir: Optional[Path] = None,
    days_back: int = 7,
) -> List[RemediationEvent]:
    """
    Load remediation events from JSONL logs.

    Args:
        log_dir: Directory containing remediation logs
        days_back: Number of days to look back

    Returns:
        List of remediation events
    """
    if log_dir is None:
        log_dir = DEFAULT_LOG_DIR

    if not log_dir.exists():
        logger.debug(f"Remediation log directory not found: {log_dir}")
        return []

    events = []
    cutoff_date = datetime.now(tz=timezone.utc) - timedelta(days=days_back)

    # Load logs from recent dates
    for log_file in sorted(log_dir.glob("remediation-*.jsonl"))[-days_back:]:
        try:
            for line in log_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)
                    event = RemediationEvent.from_json(data)
                    if event:
                        # Parse timestamp and check if within cutoff
                        try:
                            event_time = datetime.fromisoformat(event.timestamp.replace('Z', '+00:00'))
                            if event_time >= cutoff_date:
                                events.append(event)
                        except ValueError:
                            # If timestamp parsing fails, include anyway
                            events.append(event)
                except json.JSONDecodeError:
                    continue

        except Exception as exc:
            logger.debug(f"Failed to read log file {log_file}: {exc}")
            continue

    logger.info(f"Loaded {len(events)} remediation events from {log_dir}")
    return events


def calculate_remediation_stats(events: List[RemediationEvent]) -> RemediationStats:
    """
    Calculate aggregated statistics from remediation events.

    Args:
        events: List of remediation events

    Returns:
        Aggregated statistics
    """
    stats = RemediationStats()

    if not events:
        return stats

    stats.total_attempts = len(events)
    stats.successful_attempts = sum(1 for e in events if e.success)
    stats.failed_attempts = sum(1 for e in events if not e.success and e.method != "skipped")
    stats.skipped_attempts = sum(1 for e in events if e.method == "skipped")

    # Average duration
    durations = [e.duration_ms for e in events if e.duration_ms > 0]
    if durations:
        stats.avg_duration_ms = sum(durations) / len(durations)

    # Recent events
    for event in events[-100:]:
        stats.recent_events.append(event)

    # Identify problem gaps (repeatedly failing)
    for event in events:
        if not event.success and event.method != "skipped":
            stats.problem_gaps[event.query] += 1

    return stats


def get_remediation_success_rate(
    log_dir: Optional[Path] = None,
    days_back: int = 7,
) -> Dict[str, Any]:
    """
    Get remediation success rate statistics.

    Args:
        log_dir: Directory containing remediation logs
        days_back: Number of days to look back

    Returns:
        Statistics dictionary
    """
    events = load_remediation_logs(log_dir, days_back)
    stats = calculate_remediation_stats(events)

    # Identify top problem gaps
    problem_gaps = sorted(
        stats.problem_gaps.items(),
        key=lambda x: x[1],
        reverse=True
    )[:5]

    # Calculate daily velocity
    if events:
        first_event_time = datetime.fromisoformat(events[0].timestamp.replace('Z', '+00:00'))
        last_event_time = datetime.fromisoformat(events[-1].timestamp.replace('Z', '+00:00'))
        time_span_days = max(1, (last_event_time - first_event_time).total_seconds() / 86400)
        daily_velocity = stats.total_attempts / time_span_days
    else:
        daily_velocity = 0.0

    return {
        "total_attempts": stats.total_attempts,
        "successful_attempts": stats.successful_attempts,
        "failed_attempts": stats.failed_attempts,
        "skipped_attempts": stats.skipped_attempts,
        "success_rate": round(stats.success_rate, 3),
        "avg_duration_ms": round(stats.avg_duration_ms, 1),
        "daily_velocity": round(daily_velocity, 1),
        "problem_gaps": [
            {"query": query, "failure_count": count}
            for query, count in problem_gaps
        ],
        "days_analyzed": days_back,
        "active": stats.total_attempts > 0,
    }


def get_remediation_trend(
    log_dir: Optional[Path] = None,
    days_back: int = 30,
) -> Dict[str, Any]:
    """
    Get remediation trend over time.

    Args:
        log_dir: Directory containing remediation logs
        days_back: Number of days to analyze

    Returns:
        Trend data with daily breakdowns
    """
    events = load_remediation_logs(log_dir, days_back)

    if not events:
        return {
            "daily_breakdown": [],
            "trend": "stable",
            "active": False,
        }

    # Group by date
    daily_stats: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {"total": 0, "success": 0, "failed": 0}
    )

    for event in events:
        try:
            event_date = datetime.fromisoformat(event.timestamp.replace('Z', '+00:00')).date()
            date_key = event_date.isoformat()

            daily_stats[date_key]["total"] += 1
            if event.success:
                daily_stats[date_key]["success"] += 1
            else:
                daily_stats[date_key]["failed"] += 1
        except ValueError:
            continue

    # Calculate trend
    dates = sorted(daily_stats.keys())
    if len(dates) >= 3:
        recent_success_rate = sum(daily_stats[d]["success"] for d in dates[-3:]) / max(1, sum(daily_stats[d]["total"] for d in dates[-3:]))
        older_success_rate = sum(daily_stats[d]["success"] for d in dates[:-3]) / max(1, sum(daily_stats[d]["total"] for d in dates[:-3]))

        if recent_success_rate > older_success_rate + 0.1:
            trend = "improving"
        elif recent_success_rate < older_success_rate - 0.1:
            trend = "degrading"
        else:
            trend = "stable"
    else:
        trend = "insufficient_data"

    # Build daily breakdown
    daily_breakdown = [
        {
            "date": date,
            "total": daily_stats[date]["total"],
            "success": daily_stats[date]["success"],
            "failed": daily_stats[date]["failed"],
            "success_rate": round(daily_stats[date]["success"] / max(1, daily_stats[date]["total"]), 3),
        }
        for date in dates[-7:]  # Last 7 days
    ]

    return {
        "daily_breakdown": daily_breakdown,
        "trend": trend,
        "active": True,
    }
