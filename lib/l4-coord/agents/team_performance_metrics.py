#!/usr/bin/env python3
"""
Phase 4: Team Performance Metrics
Track and analyze team vs individual performance.

Features:
- Team vs individual performance comparison
- Communication overhead measurement
- Collaboration efficiency metrics
- Team composition analysis
- Success rate by configuration
- Cost-benefit analysis
- Performance regression detection
"""

import json
import logging
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

import logging

logger = logging.getLogger(__name__)


@dataclass
class IndividualPerformance:
    """Performance metrics for individual agent."""
    agent_id: str
    tasks_completed: int = 0
    tasks_succeeded: int = 0
    total_duration: int = 0  # seconds
    avg_duration: int = 0
    success_rate: float = 0.0
    avg_quality_score: float = 0.0

    def update(self, task_duration: int, success: bool, quality_score: float = 0.0):
        """Update metrics with new task."""
        self.tasks_completed += 1
        if success:
            self.tasks_succeeded += 1

        self.total_duration += task_duration
        self.avg_duration = self.total_duration // self.tasks_completed
        self.success_rate = self.tasks_succeeded / self.tasks_completed

        # Update quality score (running average)
        prev_total = self.avg_quality_score * (self.tasks_completed - 1)
        self.avg_quality_score = (prev_total + quality_score) / self.tasks_completed

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "agent_id": self.agent_id,
            "tasks_completed": self.tasks_completed,
            "tasks_succeeded": self.tasks_succeeded,
            "avg_duration": self.avg_duration,
            "success_rate": round(self.success_rate, 3),
            "avg_quality_score": round(self.avg_quality_score, 3),
        }


@dataclass
class TeamPerformance:
    """Performance metrics for team."""
    team_id: str
    team_size: int
    coordination_pattern: str
    tasks_completed: int = 0
    tasks_succeeded: int = 0
    total_duration: int = 0  # seconds
    communication_overhead: int = 0  # seconds
    avg_duration: int = 0
    avg_overhead: int = 0
    success_rate: float = 0.0
    avg_quality_score: float = 0.0
    collaboration_efficiency: float = 0.0  # 0-1

    def update(self,
              task_duration: int,
              communication_time: int,
              success: bool,
              quality_score: float = 0.0):
        """Update metrics with new task."""
        self.tasks_completed += 1
        if success:
            self.tasks_succeeded += 1

        self.total_duration += task_duration
        self.communication_overhead += communication_time

        self.avg_duration = self.total_duration // self.tasks_completed
        self.avg_overhead = self.communication_overhead // self.tasks_completed
        self.success_rate = self.tasks_succeeded / self.tasks_completed

        # Update quality score
        prev_total = self.avg_quality_score * (self.tasks_completed - 1)
        self.avg_quality_score = (prev_total + quality_score) / self.tasks_completed

        # Calculate collaboration efficiency
        # Efficiency = (actual_time - overhead) / actual_time
        if self.total_duration > 0:
            self.collaboration_efficiency = 1.0 - (self.communication_overhead / self.total_duration)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "team_id": self.team_id,
            "team_size": self.team_size,
            "coordination_pattern": self.coordination_pattern,
            "tasks_completed": self.tasks_completed,
            "tasks_succeeded": self.tasks_succeeded,
            "avg_duration": self.avg_duration,
            "avg_overhead": self.avg_overhead,
            "success_rate": round(self.success_rate, 3),
            "avg_quality_score": round(self.avg_quality_score, 3),
            "collaboration_efficiency": round(self.collaboration_efficiency, 3),
        }


@dataclass
class ComparisonResult:
    """Comparison between team and individual performance."""
    task_type: str
    team_success_rate: float
    individual_success_rate: float
    team_avg_duration: int
    individual_avg_duration: int
    team_quality: float
    individual_quality: float
    team_advantage: float  # Positive means team is better
    recommendation: str

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "task_type": self.task_type,
            "team_success_rate": round(self.team_success_rate, 3),
            "individual_success_rate": round(self.individual_success_rate, 3),
            "team_avg_duration": self.team_avg_duration,
            "individual_avg_duration": self.individual_avg_duration,
            "team_quality": round(self.team_quality, 3),
            "individual_quality": round(self.individual_quality, 3),
            "team_advantage": round(self.team_advantage, 3),
            "recommendation": self.recommendation,
        }


class TeamPerformanceMetrics:
    """Team performance metrics tracker."""

    def __init__(self, state_dir: Optional[Path] = None):
        """Initialize metrics tracker."""
        self.state_dir = state_dir or Path.home() / ".cache" / "ai-harness" / "team-metrics"
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.individual_metrics: Dict[str, IndividualPerformance] = {}
        self.team_metrics: Dict[str, TeamPerformance] = {}
        self.task_history: List[Dict[str, Any]] = []

        self._load_state()

    def _load_state(self):
        """Load state from disk."""
        individual_file = self.state_dir / "individual_metrics.json"
        team_file = self.state_dir / "team_metrics.json"
        history_file = self.state_dir / "task_history.json"

        try:
            if individual_file.exists():
                with open(individual_file) as f:
                    data = json.load(f)
                    for agent_id, metrics in data.get("metrics", {}).items():
                        perf = IndividualPerformance(agent_id=agent_id)
                        perf.tasks_completed = metrics.get("tasks_completed", 0)
                        perf.tasks_succeeded = metrics.get("tasks_succeeded", 0)
                        perf.total_duration = metrics.get("total_duration", 0)
                        perf.avg_duration = metrics.get("avg_duration", 0)
                        perf.success_rate = metrics.get("success_rate", 0.0)
                        perf.avg_quality_score = metrics.get("avg_quality_score", 0.0)
                        self.individual_metrics[agent_id] = perf
        except Exception as e:
            logger.warning(f"Failed to load individual metrics: {e}")

        try:
            if team_file.exists():
                with open(team_file) as f:
                    data = json.load(f)
                    for team_id, metrics in data.get("metrics", {}).items():
                        perf = TeamPerformance(
                            team_id=team_id,
                            team_size=metrics.get("team_size", 1),
                            coordination_pattern=metrics.get("coordination_pattern", "unknown"),
                        )
                        perf.tasks_completed = metrics.get("tasks_completed", 0)
                        perf.tasks_succeeded = metrics.get("tasks_succeeded", 0)
                        perf.total_duration = metrics.get("total_duration", 0)
                        perf.communication_overhead = metrics.get("communication_overhead", 0)
                        perf.avg_duration = metrics.get("avg_duration", 0)
                        perf.avg_overhead = metrics.get("avg_overhead", 0)
                        perf.success_rate = metrics.get("success_rate", 0.0)
                        perf.avg_quality_score = metrics.get("avg_quality_score", 0.0)
                        perf.collaboration_efficiency = metrics.get("collaboration_efficiency", 0.0)
                        self.team_metrics[team_id] = perf
        except Exception as e:
            logger.warning(f"Failed to load team metrics: {e}")

        try:
            if history_file.exists():
                with open(history_file) as f:
                    data = json.load(f)
                    self.task_history = data.get("history", [])
        except Exception as e:
            logger.warning(f"Failed to load task history: {e}")

    def _save_state(self):
        """Save state to disk."""
        individual_file = self.state_dir / "individual_metrics.json"
        team_file = self.state_dir / "team_metrics.json"
        history_file = self.state_dir / "task_history.json"

        try:
            with open(individual_file, 'w') as f:
                metrics_dict = {
                    agent_id: {
                        **perf.to_dict(),
                        "total_duration": perf.total_duration,
                    }
                    for agent_id, perf in self.individual_metrics.items()
                }
                json.dump({"metrics": metrics_dict}, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save individual metrics: {e}")

        try:
            with open(team_file, 'w') as f:
                metrics_dict = {
                    team_id: {
                        **perf.to_dict(),
                        "total_duration": perf.total_duration,
                        "communication_overhead": perf.communication_overhead,
                    }
                    for team_id, perf in self.team_metrics.items()
                }
                json.dump({"metrics": metrics_dict}, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save team metrics: {e}")

        try:
            # Keep last 1000 tasks
            recent_history = self.task_history[-1000:]
            with open(history_file, 'w') as f:
                json.dump({"history": recent_history}, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save task history: {e}")

    def record_individual_task(self,
                              agent_id: str,
                              task_type: str,
                              duration: int,
                              success: bool,
                              quality_score: float = 0.0):
        """Record individual agent task completion."""
        if agent_id not in self.individual_metrics:
            self.individual_metrics[agent_id] = IndividualPerformance(agent_id=agent_id)

        perf = self.individual_metrics[agent_id]
        perf.update(duration, success, quality_score)

        # Record in history
        self.task_history.append({
            "type": "individual",
            "agent_id": agent_id,
            "task_type": task_type,
            "duration": duration,
            "success": success,
            "quality_score": quality_score,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        self._save_state()

        logger.info("individual_task_recorded",
                   agent_id=agent_id,
                   task_type=task_type,
                   success=success)

    def record_team_task(self,
                        team_id: str,
                        team_size: int,
                        coordination_pattern: str,
                        task_type: str,
                        duration: int,
                        communication_time: int,
                        success: bool,
                        quality_score: float = 0.0):
        """Record team task completion."""
        if team_id not in self.team_metrics:
            self.team_metrics[team_id] = TeamPerformance(
                team_id=team_id,
                team_size=team_size,
                coordination_pattern=coordination_pattern,
            )

        perf = self.team_metrics[team_id]
        perf.update(duration, communication_time, success, quality_score)

        # Record in history
        self.task_history.append({
            "type": "team",
            "team_id": team_id,
            "team_size": team_size,
            "coordination_pattern": coordination_pattern,
            "task_type": task_type,
            "duration": duration,
            "communication_time": communication_time,
            "success": success,
            "quality_score": quality_score,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        self._save_state()

        logger.info("team_task_recorded",
                   team_id=team_id,
                   task_type=task_type,
                   success=success)

    def compare_performance(self, task_type: Optional[str] = None) -> ComparisonResult:
        """Compare team vs individual performance."""
        # Filter history by task type if specified
        if task_type:
            history = [h for h in self.task_history if h.get("task_type") == task_type]
        else:
            history = self.task_history
            task_type = "all"

        if not history:
            return ComparisonResult(
                task_type=task_type,
                team_success_rate=0.0,
                individual_success_rate=0.0,
                team_avg_duration=0,
                individual_avg_duration=0,
                team_quality=0.0,
                individual_quality=0.0,
                team_advantage=0.0,
                recommendation="Insufficient data",
            )

        # Separate team and individual tasks
        team_tasks = [h for h in history if h.get("type") == "team"]
        individual_tasks = [h for h in history if h.get("type") == "individual"]

        # Calculate team metrics
        if team_tasks:
            team_success_rate = sum(1 for t in team_tasks if t.get("success")) / len(team_tasks)
            team_avg_duration = int(statistics.mean([t.get("duration", 0) for t in team_tasks]))
            team_quality = statistics.mean([t.get("quality_score", 0) for t in team_tasks])
        else:
            team_success_rate = 0.0
            team_avg_duration = 0
            team_quality = 0.0

        # Calculate individual metrics
        if individual_tasks:
            individual_success_rate = sum(1 for t in individual_tasks if t.get("success")) / len(individual_tasks)
            individual_avg_duration = int(statistics.mean([t.get("duration", 0) for t in individual_tasks]))
            individual_quality = statistics.mean([t.get("quality_score", 0) for t in individual_tasks])
        else:
            individual_success_rate = 0.0
            individual_avg_duration = 0
            individual_quality = 0.0

        # Calculate team advantage (weighted composite score)
        success_diff = team_success_rate - individual_success_rate
        quality_diff = team_quality - individual_quality

        # Duration diff (negative is better for team)
        if individual_avg_duration > 0:
            duration_ratio = team_avg_duration / individual_avg_duration
            duration_diff = 1.0 - duration_ratio  # Positive if team is faster
        else:
            duration_diff = 0.0

        # Weighted advantage: 50% success, 30% quality, 20% speed
        team_advantage = (0.5 * success_diff) + (0.3 * quality_diff) + (0.2 * duration_diff)

        # Generate recommendation
        if team_advantage > 0.1:
            recommendation = "Team collaboration recommended"
        elif team_advantage < -0.1:
            recommendation = "Individual execution recommended"
        else:
            recommendation = "No clear advantage"

        return ComparisonResult(
            task_type=task_type,
            team_success_rate=team_success_rate,
            individual_success_rate=individual_success_rate,
            team_avg_duration=team_avg_duration,
            individual_avg_duration=individual_avg_duration,
            team_quality=team_quality,
            individual_quality=individual_quality,
            team_advantage=team_advantage,
            recommendation=recommendation,
        )

    def analyze_team_composition(self) -> Dict[str, Any]:
        """Analyze performance by team size and pattern."""
        team_tasks = [h for h in self.task_history if h.get("type") == "team"]

        if not team_tasks:
            return {"error": "No team tasks recorded"}

        # Group by team size
        by_size = {}
        for task in team_tasks:
            size = task.get("team_size", 1)
            if size not in by_size:
                by_size[size] = []
            by_size[size].append(task)

        size_analysis = {}
        for size, tasks in by_size.items():
            success_rate = sum(1 for t in tasks if t.get("success")) / len(tasks)
            avg_duration = int(statistics.mean([t.get("duration", 0) for t in tasks]))
            avg_quality = statistics.mean([t.get("quality_score", 0) for t in tasks])

            size_analysis[size] = {
                "task_count": len(tasks),
                "success_rate": round(success_rate, 3),
                "avg_duration": avg_duration,
                "avg_quality": round(avg_quality, 3),
            }

        # Group by coordination pattern
        by_pattern = {}
        for task in team_tasks:
            pattern = task.get("coordination_pattern", "unknown")
            if pattern not in by_pattern:
                by_pattern[pattern] = []
            by_pattern[pattern].append(task)

        pattern_analysis = {}
        for pattern, tasks in by_pattern.items():
            success_rate = sum(1 for t in tasks if t.get("success")) / len(tasks)
            avg_duration = int(statistics.mean([t.get("duration", 0) for t in tasks]))
            avg_quality = statistics.mean([t.get("quality_score", 0) for t in tasks])

            pattern_analysis[pattern] = {
                "task_count": len(tasks),
                "success_rate": round(success_rate, 3),
                "avg_duration": avg_duration,
                "avg_quality": round(avg_quality, 3),
            }

        return {
            "by_team_size": size_analysis,
            "by_coordination_pattern": pattern_analysis,
        }

    def calculate_cost_benefit(self) -> Dict[str, Any]:
        """Calculate cost-benefit of team vs individual."""
        comparison = self.compare_performance()

        # Assume team cost is sum of individual costs plus coordination overhead
        # This is a simplified model
        individual_cost = 1.0  # Base cost unit
        coordination_overhead_cost = 0.2  # Per additional team member

        # Calculate average team size
        team_tasks = [h for h in self.task_history if h.get("type") == "team"]
        if team_tasks:
            avg_team_size = statistics.mean([t.get("team_size", 1) for t in team_tasks])
            team_cost = avg_team_size * individual_cost + (avg_team_size - 1) * coordination_overhead_cost
        else:
            avg_team_size = 0
            team_cost = 0

        # Benefit = (success_rate * quality) - cost
        team_benefit = (comparison.team_success_rate * comparison.team_quality) - team_cost
        individual_benefit = (comparison.individual_success_rate * comparison.individual_quality) - individual_cost

        roi = team_benefit - individual_benefit

        return {
            "avg_team_size": round(avg_team_size, 2),
            "team_cost": round(team_cost, 2),
            "individual_cost": individual_cost,
            "team_benefit": round(team_benefit, 3),
            "individual_benefit": round(individual_benefit, 3),
            "roi": round(roi, 3),
            "recommendation": "Team" if roi > 0 else "Individual",
        }

    def detect_performance_regression(self, window_days: int = 7) -> Dict[str, Any]:
        """Detect performance regressions over time."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)

        recent_tasks = [
            h for h in self.task_history
            if datetime.fromisoformat(h.get("timestamp", "")) > cutoff
        ]

        if len(recent_tasks) < 10:
            return {"error": "Insufficient recent data"}

        # Split into two halves
        mid = len(recent_tasks) // 2
        first_half = recent_tasks[:mid]
        second_half = recent_tasks[mid:]

        # Compare metrics
        first_success = sum(1 for t in first_half if t.get("success")) / len(first_half)
        second_success = sum(1 for t in second_half if t.get("success")) / len(second_half)

        first_quality = statistics.mean([t.get("quality_score", 0) for t in first_half])
        second_quality = statistics.mean([t.get("quality_score", 0) for t in second_half])

        # Detect regression (>5% drop)
        success_regression = (first_success - second_success) > 0.05
        quality_regression = (first_quality - second_quality) > 0.05

        return {
            "window_days": window_days,
            "total_tasks": len(recent_tasks),
            "first_half_success_rate": round(first_success, 3),
            "second_half_success_rate": round(second_success, 3),
            "first_half_quality": round(first_quality, 3),
            "second_half_quality": round(second_quality, 3),
            "success_regression_detected": success_regression,
            "quality_regression_detected": quality_regression,
            "regression_detected": success_regression or quality_regression,
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all metrics."""
        return {
            "individual_agents": len(self.individual_metrics),
            "teams_tracked": len(self.team_metrics),
            "total_tasks": len(self.task_history),
            "comparison": self.compare_performance().to_dict(),
            "composition": self.analyze_team_composition(),
            "cost_benefit": self.calculate_cost_benefit(),
        }
