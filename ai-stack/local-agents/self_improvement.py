#!/usr/bin/env python3
"""
Self-Improvement Loop - Continuous Agent Optimization

Enables local agents to learn from their actions and improve over time:
- Quality scoring for agent outputs
- Feedback collection from executions
- Performance benchmarking
- Improvement recommendations
- A/B testing framework

Part of Phase 11 Batch 11.5: Self-Improvement Loop
"""

import asyncio
import json
import logging
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from agent_executor import Task, TaskStatus, AgentType
from task_router import AgentTarget

logger = logging.getLogger(__name__)


class QualityDimension(Enum):
    """Quality dimensions for scoring"""
    CORRECTNESS = "correctness"  # Did it solve the task?
    COMPLETENESS = "completeness"  # All requirements met?
    EFFICIENCY = "efficiency"  # Time/resources used
    TOOL_USAGE = "tool_usage"  # Appropriate tool selection
    ERROR_HANDLING = "error_handling"  # Graceful error handling


@dataclass
class QualityScore:
    """Quality score for an agent execution"""
    task_id: str
    agent_type: AgentType
    timestamp: datetime = field(default_factory=datetime.now)

    # Dimension scores (0.0-1.0)
    correctness: float = 0.0
    completeness: float = 0.0
    efficiency: float = 0.0
    tool_usage: float = 0.0
    error_handling: float = 0.0

    # Overall score (weighted average)
    overall: float = 0.0

    # Metadata
    feedback: str = ""
    scored_by: str = "auto"  # auto or human

    def calculate_overall(self):
        """Calculate weighted overall score"""
        weights = {
            "correctness": 0.4,
            "completeness": 0.3,
            "efficiency": 0.1,
            "tool_usage": 0.1,
            "error_handling": 0.1,
        }

        self.overall = (
            weights["correctness"] * self.correctness +
            weights["completeness"] * self.completeness +
            weights["efficiency"] * self.efficiency +
            weights["tool_usage"] * self.tool_usage +
            weights["error_handling"] * self.error_handling
        )

    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "agent_type": self.agent_type.value,
            "timestamp": self.timestamp.isoformat(),
            "correctness": self.correctness,
            "completeness": self.completeness,
            "efficiency": self.efficiency,
            "tool_usage": self.tool_usage,
            "error_handling": self.error_handling,
            "overall": self.overall,
            "feedback": self.feedback,
            "scored_by": self.scored_by,
        }


@dataclass
class ImprovementRecommendation:
    """Recommendation for improving agent performance"""
    category: str
    priority: str  # high, medium, low
    description: str
    evidence: List[str] = field(default_factory=list)
    suggested_actions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "category": self.category,
            "priority": self.priority,
            "description": self.description,
            "evidence": self.evidence,
            "suggested_actions": self.suggested_actions,
        }


class SelfImprovementEngine:
    """
    Continuous improvement engine for local agents.

    Features:
    - Quality scoring for all executions
    - Feedback collection
    - Performance benchmarking
    - Improvement recommendations
    - A/B testing support
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path.home() / ".local/share/nixos-ai-stack/local-agents/improvement.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

        # In-memory tracking
        self.quality_scores: List[QualityScore] = []
        self.benchmarks: Dict[str, List[float]] = defaultdict(list)

        logger.info(f"Self-improvement engine initialized: {self.db_path}")

    def _init_database(self):
        """Initialize SQLite database"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Quality scores table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quality_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                agent_type TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                correctness REAL,
                completeness REAL,
                efficiency REAL,
                tool_usage REAL,
                error_handling REAL,
                overall REAL,
                feedback TEXT,
                scored_by TEXT
            )
        """)

        # Benchmarks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS benchmarks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                benchmark_name TEXT NOT NULL,
                agent_type TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                score REAL NOT NULL,
                metadata TEXT
            )
        """)

        # A/B test results table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ab_tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_name TEXT NOT NULL,
                variant_a TEXT NOT NULL,
                variant_b TEXT NOT NULL,
                start_date TIMESTAMP NOT NULL,
                end_date TIMESTAMP,
                winner TEXT,
                confidence REAL,
                results TEXT
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_quality_task ON quality_scores(task_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_quality_agent ON quality_scores(agent_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_benchmark_name ON benchmarks(benchmark_name)")

        conn.commit()
        conn.close()

    def score_task_execution(self, task: Task, compare_to_remote: bool = False) -> QualityScore:
        """
        Score a completed task execution.

        Args:
            task: Completed task
            compare_to_remote: Whether to compare with remote agent baseline

        Returns:
            Quality score
        """
        score = QualityScore(
            task_id=task.id,
            agent_type=AgentType.AGENT,  # Default
        )

        # Correctness: Did it complete successfully?
        if task.status == TaskStatus.COMPLETED:
            score.correctness = 1.0
        elif task.status == TaskStatus.FALLBACK:
            score.correctness = 0.5  # Fell back but got result
        else:
            score.correctness = 0.0

        # Completeness: Did it use expected tools?
        expected_tool_calls = self._estimate_expected_tool_calls(task)
        actual_tool_calls = len(task.tool_calls_made)

        if expected_tool_calls > 0:
            score.completeness = min(1.0, actual_tool_calls / expected_tool_calls)
        else:
            score.completeness = 1.0 if task.status == TaskStatus.COMPLETED else 0.0

        # Efficiency: How fast was it?
        if task.execution_time_ms > 0:
            # Lower is better; normalize to 0-1 (assume 10s is baseline)
            baseline_ms = 10000
            score.efficiency = max(0.0, 1.0 - (task.execution_time_ms / baseline_ms))
        else:
            score.efficiency = 0.5

        # Tool usage: Successful tool calls
        if actual_tool_calls > 0:
            successful = len([tc for tc in task.tool_calls_made if tc.status == "completed"])
            score.tool_usage = successful / actual_tool_calls
        else:
            score.tool_usage = 1.0 if task.status == TaskStatus.COMPLETED else 0.0

        # Error handling: Clean errors vs crashes
        if task.error:
            # Has error message = handled gracefully
            score.error_handling = 0.5
        else:
            score.error_handling = 1.0

        # Calculate overall
        score.calculate_overall()

        # Store
        self._store_quality_score(score)
        self.quality_scores.append(score)

        logger.info(
            f"Scored task {task.id}: overall={score.overall:.2f}, "
            f"correctness={score.correctness:.2f}, completeness={score.completeness:.2f}"
        )

        return score

    def _estimate_expected_tool_calls(self, task: Task) -> int:
        """Estimate expected number of tool calls for a task"""
        # Simple heuristic based on complexity
        if task.complexity < 0.3:
            return 1  # Simple task, 1 tool call
        elif task.complexity < 0.6:
            return 3  # Medium task, 3 tool calls
        else:
            return 5  # Complex task, 5+ tool calls

    def _store_quality_score(self, score: QualityScore):
        """Store quality score in database"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO quality_scores
            (task_id, agent_type, timestamp, correctness, completeness, efficiency,
             tool_usage, error_handling, overall, feedback, scored_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                score.task_id,
                score.agent_type.value,
                score.timestamp,
                score.correctness,
                score.completeness,
                score.efficiency,
                score.tool_usage,
                score.error_handling,
                score.overall,
                score.feedback,
                score.scored_by,
            ),
        )

        conn.commit()
        conn.close()

    def collect_feedback(self, task_id: str, feedback: str, scores: Optional[Dict[str, float]] = None):
        """
        Collect human feedback for a task.

        Args:
            task_id: Task ID
            feedback: Textual feedback
            scores: Optional dimension scores
        """
        # Find existing score or create new
        existing = next((s for s in self.quality_scores if s.task_id == task_id), None)

        if existing:
            existing.feedback = feedback
            existing.scored_by = "human"

            if scores:
                existing.correctness = scores.get("correctness", existing.correctness)
                existing.completeness = scores.get("completeness", existing.completeness)
                existing.efficiency = scores.get("efficiency", existing.efficiency)
                existing.tool_usage = scores.get("tool_usage", existing.tool_usage)
                existing.error_handling = scores.get("error_handling", existing.error_handling)
                existing.calculate_overall()

            # Update in database
            self._store_quality_score(existing)

        logger.info(f"Collected feedback for task {task_id}")

    def analyze_performance(self, agent_type: AgentType, time_window_days: int = 7) -> Dict[str, Any]:
        """
        Analyze agent performance over time window.

        Args:
            agent_type: Agent type to analyze
            time_window_days: Days to look back

        Returns:
            Performance analysis
        """
        cutoff = datetime.now() - timedelta(days=time_window_days)

        recent_scores = [
            s for s in self.quality_scores
            if s.agent_type == agent_type and s.timestamp >= cutoff
        ]

        if not recent_scores:
            return {
                "agent_type": agent_type.value,
                "sample_count": 0,
                "message": "No data in time window",
            }

        # Calculate averages
        avg_correctness = sum(s.correctness for s in recent_scores) / len(recent_scores)
        avg_completeness = sum(s.completeness for s in recent_scores) / len(recent_scores)
        avg_efficiency = sum(s.efficiency for s in recent_scores) / len(recent_scores)
        avg_tool_usage = sum(s.tool_usage for s in recent_scores) / len(recent_scores)
        avg_error_handling = sum(s.error_handling for s in recent_scores) / len(recent_scores)
        avg_overall = sum(s.overall for s in recent_scores) / len(recent_scores)

        return {
            "agent_type": agent_type.value,
            "time_window_days": time_window_days,
            "sample_count": len(recent_scores),
            "avg_correctness": avg_correctness,
            "avg_completeness": avg_completeness,
            "avg_efficiency": avg_efficiency,
            "avg_tool_usage": avg_tool_usage,
            "avg_error_handling": avg_error_handling,
            "avg_overall": avg_overall,
        }

    def generate_improvement_recommendations(
        self,
        agent_type: AgentType,
        time_window_days: int = 7,
    ) -> List[ImprovementRecommendation]:
        """
        Generate recommendations for improving agent performance.

        Args:
            agent_type: Agent type to analyze
            time_window_days: Days to analyze

        Returns:
            List of improvement recommendations
        """
        analysis = self.analyze_performance(agent_type, time_window_days)

        if analysis.get("sample_count", 0) == 0:
            return []

        recommendations = []

        # Check correctness
        if analysis["avg_correctness"] < 0.7:
            recommendations.append(ImprovementRecommendation(
                category="correctness",
                priority="high",
                description=f"Low correctness rate ({analysis['avg_correctness']:.1%})",
                evidence=[
                    f"{analysis['sample_count']} tasks analyzed",
                    f"Average correctness: {analysis['avg_correctness']:.1%}",
                ],
                suggested_actions=[
                    "Review failed tasks for patterns",
                    "Consider increasing model size or quality",
                    "Add more tool training examples",
                    "Fallback to remote agents for complex tasks",
                ],
            ))

        # Check completeness
        if analysis["avg_completeness"] < 0.7:
            recommendations.append(ImprovementRecommendation(
                category="completeness",
                priority="medium",
                description=f"Incomplete task execution ({analysis['avg_completeness']:.1%})",
                evidence=[
                    f"Average completeness: {analysis['avg_completeness']:.1%}",
                ],
                suggested_actions=[
                    "Improve tool call prompting",
                    "Add missing tools to registry",
                    "Train on multi-step task examples",
                ],
            ))

        # Check efficiency
        if analysis["avg_efficiency"] < 0.5:
            recommendations.append(ImprovementRecommendation(
                category="efficiency",
                priority="low",
                description=f"Slow execution ({analysis['avg_efficiency']:.1%})",
                evidence=[
                    f"Average efficiency: {analysis['avg_efficiency']:.1%}",
                ],
                suggested_actions=[
                    "Optimize model inference speed",
                    "Reduce tool call overhead",
                    "Cache frequent operations",
                ],
            ))

        # Check tool usage
        if analysis["avg_tool_usage"] < 0.8:
            recommendations.append(ImprovementRecommendation(
                category="tool_usage",
                priority="medium",
                description=f"Tool call failures ({analysis['avg_tool_usage']:.1%})",
                evidence=[
                    f"Tool success rate: {analysis['avg_tool_usage']:.1%}",
                ],
                suggested_actions=[
                    "Improve tool error handling",
                    "Add tool usage examples",
                    "Validate tool inputs more strictly",
                ],
            ))

        return recommendations

    def run_benchmark(self, benchmark_name: str, agent_type: AgentType, score: float, metadata: Optional[Dict] = None):
        """
        Record benchmark result.

        Args:
            benchmark_name: Name of benchmark
            agent_type: Agent being benchmarked
            score: Benchmark score (0.0-1.0)
            metadata: Optional metadata
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO benchmarks
            (benchmark_name, agent_type, timestamp, score, metadata)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                benchmark_name,
                agent_type.value,
                datetime.now(),
                score,
                json.dumps(metadata or {}),
            ),
        )

        conn.commit()
        conn.close()

        self.benchmarks[benchmark_name].append(score)

        logger.info(f"Benchmark {benchmark_name} for {agent_type.value}: {score:.3f}")

    def get_statistics(self) -> Dict[str, Any]:
        """Get self-improvement statistics"""
        total_scores = len(self.quality_scores)
        if total_scores == 0:
            return {"total_scores": 0, "message": "No data yet"}

        recent = self.quality_scores[-100:]

        avg_overall = sum(s.overall for s in recent) / len(recent)
        human_scored = len([s for s in recent if s.scored_by == "human"])

        return {
            "total_scores": total_scores,
            "recent_samples": len(recent),
            "avg_overall_quality": avg_overall,
            "human_scored_count": human_scored,
            "total_benchmarks": len(self.benchmarks),
        }


if __name__ == "__main__":
    # Test self-improvement engine
    logging.basicConfig(level=logging.INFO)

    async def test():
        engine = SelfImprovementEngine()

        # Create test task
        from agent_executor import Task

        task = Task(
            id="test-123",
            objective="Test task",
            complexity=0.5,
            status=TaskStatus.COMPLETED,
            execution_time_ms=5000,
        )

        # Mock tool calls
        from tool_registry import ToolCall
        task.tool_calls_made = [
            ToolCall(id="1", tool_name="test", arguments={}, status="completed"),
            ToolCall(id="2", tool_name="test2", arguments={}, status="completed"),
        ]

        # Score task
        score = engine.score_task_execution(task)
        print(f"\nQuality Score:")
        print(f"  Overall: {score.overall:.2f}")
        print(f"  Correctness: {score.correctness:.2f}")
        print(f"  Completeness: {score.completeness:.2f}")
        print(f"  Efficiency: {score.efficiency:.2f}")

        # Analyze performance
        analysis = engine.analyze_performance(AgentType.AGENT, time_window_days=30)
        print(f"\nPerformance Analysis:")
        print(json.dumps(analysis, indent=2))

        # Get recommendations
        recommendations = engine.generate_improvement_recommendations(AgentType.AGENT)
        print(f"\nImprovement Recommendations: {len(recommendations)}")
        for rec in recommendations:
            print(f"\n  {rec.category} ({rec.priority}):")
            print(f"    {rec.description}")

        # Statistics
        stats = engine.get_statistics()
        print(f"\nStatistics:")
        print(json.dumps(stats, indent=2))

    asyncio.run(test())
