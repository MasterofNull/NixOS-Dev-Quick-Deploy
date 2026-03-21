#!/usr/bin/env python3
"""
Workflow Optimizer - Optimize workflows based on telemetry and performance data.

This module analyzes workflow execution telemetry to identify bottlenecks,
suggest parallelization opportunities, and optimize resource allocation.
"""

import logging
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import statistics

logger = logging.getLogger(__name__)


class OptimizationType(Enum):
    """Types of optimizations."""
    PARALLELIZATION = "parallelization"
    RESOURCE_ALLOCATION = "resource_allocation"
    DEPENDENCY_REMOVAL = "dependency_removal"
    TASK_REORDERING = "task_reordering"
    AGENT_REASSIGNMENT = "agent_reassignment"
    RETRY_POLICY = "retry_policy"
    TIMEOUT_ADJUSTMENT = "timeout_adjustment"


@dataclass
class TaskTelemetry:
    """Telemetry data for a single task execution."""
    task_id: str
    workflow_id: str
    execution_id: str
    start_time: str
    end_time: str
    duration: int  # seconds
    status: str  # success, failure, timeout
    agent_id: str
    resource_usage: Dict[str, float] = field(default_factory=dict)
    retry_count: int = 0
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowTelemetry:
    """Telemetry data for a workflow execution."""
    workflow_id: str
    execution_id: str
    start_time: str
    end_time: str
    total_duration: int  # seconds
    task_telemetry: List[TaskTelemetry]
    success: bool
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Bottleneck:
    """Represents a workflow bottleneck."""
    task_id: str
    task_name: str
    severity: float  # 0-1, higher is worse
    issue_type: str
    description: str
    impact: Dict[str, Any]
    suggestions: List[str]


@dataclass
class OptimizationSuggestion:
    """Represents an optimization suggestion."""
    optimization_type: OptimizationType
    description: str
    expected_improvement: Dict[str, Any]
    confidence: float  # 0-1
    implementation_difficulty: str  # easy, medium, hard
    affected_tasks: List[str]
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OptimizationResult:
    """Result of workflow optimization analysis."""
    workflow_id: str
    analyzed_executions: int
    bottlenecks: List[Bottleneck]
    suggestions: List[OptimizationSuggestion]
    current_metrics: Dict[str, Any]
    projected_metrics: Dict[str, Any]
    optimization_summary: str


class TelemetryAnalyzer:
    """Analyzes workflow telemetry data."""

    def __init__(self):
        """Initialize telemetry analyzer."""
        pass

    def analyze_task_performance(
        self,
        task_telemetry: List[TaskTelemetry]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Analyze performance of tasks across executions.

        Args:
            task_telemetry: List of task telemetry records

        Returns:
            Dictionary mapping task_id to performance metrics
        """
        task_metrics = {}

        # Group by task ID
        by_task = {}
        for record in task_telemetry:
            if record.task_id not in by_task:
                by_task[record.task_id] = []
            by_task[record.task_id].append(record)

        # Calculate metrics for each task
        for task_id, records in by_task.items():
            durations = [r.duration for r in records]
            success_count = sum(1 for r in records if r.status == "success")
            failure_count = sum(1 for r in records if r.status == "failure")
            timeout_count = sum(1 for r in records if r.status == "timeout")
            total_retries = sum(r.retry_count for r in records)

            task_metrics[task_id] = {
                "executions": len(records),
                "avg_duration": statistics.mean(durations) if durations else 0,
                "median_duration": statistics.median(durations) if durations else 0,
                "std_duration": statistics.stdev(durations) if len(durations) > 1 else 0,
                "min_duration": min(durations) if durations else 0,
                "max_duration": max(durations) if durations else 0,
                "success_rate": success_count / len(records) if records else 0,
                "failure_count": failure_count,
                "timeout_count": timeout_count,
                "avg_retries": total_retries / len(records) if records else 0,
            }

        return task_metrics

    def identify_critical_path(
        self,
        workflow: Any,
        task_metrics: Dict[str, Dict[str, Any]]
    ) -> Tuple[List[str], int]:
        """
        Identify critical path through workflow.

        Args:
            workflow: Workflow object
            task_metrics: Task performance metrics

        Returns:
            Tuple of (critical_path_task_ids, total_duration)
        """
        # Build dependency graph
        graph = workflow.get_task_graph()

        # Calculate earliest start times
        earliest_start = {}
        earliest_finish = {}

        def calculate_earliest(task_id: str) -> int:
            if task_id in earliest_finish:
                return earliest_finish[task_id]

            deps = graph.get(task_id, [])
            if not deps:
                earliest_start[task_id] = 0
            else:
                earliest_start[task_id] = max(
                    calculate_earliest(dep) for dep in deps
                )

            duration = task_metrics.get(task_id, {}).get("avg_duration", 0)
            earliest_finish[task_id] = earliest_start[task_id] + duration

            return earliest_finish[task_id]

        # Calculate for all tasks
        for task_id in graph:
            calculate_earliest(task_id)

        # Find critical path (backwards from tasks with no successors)
        successors = {task_id: [] for task_id in graph}
        for task_id, deps in graph.items():
            for dep in deps:
                successors[dep].append(task_id)

        end_tasks = [
            task_id for task_id in graph
            if not successors.get(task_id)
        ]

        if not end_tasks:
            return [], 0

        # Start from task with latest finish
        current = max(end_tasks, key=lambda t: earliest_finish.get(t, 0))
        critical_path = [current]
        total_duration = earliest_finish.get(current, 0)

        # Trace back through dependencies
        while graph.get(current):
            deps = graph[current]
            # Find dep with latest finish time
            next_task = max(deps, key=lambda t: earliest_finish.get(t, 0))
            critical_path.insert(0, next_task)
            current = next_task

        return critical_path, int(total_duration)

    def calculate_parallelism(
        self,
        workflow: Any
    ) -> Dict[str, Any]:
        """
        Calculate current parallelism metrics.

        Args:
            workflow: Workflow object

        Returns:
            Parallelism metrics
        """
        batches = workflow.get_execution_order()

        total_tasks = len(workflow.tasks)
        max_parallel = max(len(batch) for batch in batches) if batches else 0
        avg_parallel = statistics.mean(len(batch) for batch in batches) if batches else 0

        return {
            "total_batches": len(batches),
            "max_parallel_tasks": max_parallel,
            "avg_parallel_tasks": avg_parallel,
            "total_tasks": total_tasks,
            "parallelism_ratio": avg_parallel / total_tasks if total_tasks else 0,
        }


class BottleneckDetector:
    """Detects bottlenecks in workflows."""

    def __init__(self):
        """Initialize bottleneck detector."""
        self.analyzer = TelemetryAnalyzer()

    def detect(
        self,
        workflow: Any,
        telemetry: List[WorkflowTelemetry]
    ) -> List[Bottleneck]:
        """
        Detect bottlenecks in workflow.

        Args:
            workflow: Workflow object
            telemetry: List of workflow telemetry records

        Returns:
            List of detected bottlenecks
        """
        bottlenecks = []

        # Collect all task telemetry
        all_task_telemetry = []
        for wf_telemetry in telemetry:
            all_task_telemetry.extend(wf_telemetry.task_telemetry)

        if not all_task_telemetry:
            return bottlenecks

        # Analyze task performance
        task_metrics = self.analyzer.analyze_task_performance(all_task_telemetry)

        # Identify critical path
        critical_path, critical_duration = self.analyzer.identify_critical_path(
            workflow, task_metrics
        )

        # Check for slow tasks
        avg_duration = statistics.mean(
            m["avg_duration"] for m in task_metrics.values()
        )

        for task_id, metrics in task_metrics.items():
            # Slow task bottleneck
            if metrics["avg_duration"] > avg_duration * 2:
                severity = min(1.0, metrics["avg_duration"] / (avg_duration * 4))
                task = next((t for t in workflow.tasks if t.id == task_id), None)

                bottlenecks.append(Bottleneck(
                    task_id=task_id,
                    task_name=task.name if task else task_id,
                    severity=severity,
                    issue_type="slow_execution",
                    description=f"Task takes {metrics['avg_duration']:.1f}s on average, "
                               f"{metrics['avg_duration']/avg_duration:.1f}x longer than average",
                    impact={
                        "duration": metrics["avg_duration"],
                        "relative_slowdown": metrics["avg_duration"] / avg_duration,
                        "on_critical_path": task_id in critical_path,
                    },
                    suggestions=[
                        "Optimize task implementation",
                        "Increase resource allocation",
                        "Break into smaller parallel tasks",
                    ]
                ))

            # High failure rate bottleneck
            if metrics["failure_count"] > 0 and metrics["success_rate"] < 0.8:
                severity = 1.0 - metrics["success_rate"]
                task = next((t for t in workflow.tasks if t.id == task_id), None)

                bottlenecks.append(Bottleneck(
                    task_id=task_id,
                    task_name=task.name if task else task_id,
                    severity=severity,
                    issue_type="high_failure_rate",
                    description=f"Task fails {(1-metrics['success_rate'])*100:.1f}% of the time",
                    impact={
                        "success_rate": metrics["success_rate"],
                        "failure_count": metrics["failure_count"],
                    },
                    suggestions=[
                        "Add retry logic with exponential backoff",
                        "Improve error handling",
                        "Add validation before task execution",
                        "Increase timeout threshold",
                    ]
                ))

            # High retry rate bottleneck
            if metrics["avg_retries"] > 1.0:
                severity = min(1.0, metrics["avg_retries"] / 5.0)
                task = next((t for t in workflow.tasks if t.id == task_id), None)

                bottlenecks.append(Bottleneck(
                    task_id=task_id,
                    task_name=task.name if task else task_id,
                    severity=severity,
                    issue_type="high_retry_rate",
                    description=f"Task requires {metrics['avg_retries']:.1f} retries on average",
                    impact={
                        "avg_retries": metrics["avg_retries"],
                    },
                    suggestions=[
                        "Investigate root cause of failures",
                        "Add pre-execution validation",
                        "Improve task idempotency",
                    ]
                ))

        # Sort by severity
        bottlenecks.sort(key=lambda b: b.severity, reverse=True)

        return bottlenecks


class ParallelizationAnalyzer:
    """Analyzes parallelization opportunities."""

    def __init__(self):
        """Initialize parallelization analyzer."""
        pass

    def find_opportunities(
        self,
        workflow: Any,
        task_metrics: Dict[str, Dict[str, Any]]
    ) -> List[OptimizationSuggestion]:
        """
        Find parallelization opportunities.

        Args:
            workflow: Workflow object
            task_metrics: Task performance metrics

        Returns:
            List of parallelization suggestions
        """
        suggestions = []

        # Check if any tasks have unnecessary dependencies
        graph = workflow.get_task_graph()

        for task in workflow.tasks:
            if not task.dependencies:
                continue

            # Check if all dependencies are actually necessary
            # (In a real implementation, this would use data flow analysis)
            # For now, we'll look for dependencies that could be removed

            # Check for transitive dependencies
            direct_deps = set(task.dependencies)
            transitive_deps = set()

            for dep in task.dependencies:
                # Get dependencies of dependencies
                if dep in graph:
                    for trans_dep in graph[dep]:
                        transitive_deps.add(trans_dep)

            # If a task depends on both X and Y, and Y depends on X,
            # the dependency on X is redundant
            redundant = direct_deps & transitive_deps

            if redundant:
                suggestions.append(OptimizationSuggestion(
                    optimization_type=OptimizationType.DEPENDENCY_REMOVAL,
                    description=f"Remove redundant dependencies from {task.id}",
                    expected_improvement={
                        "parallelism_increase": len(redundant),
                        "redundant_deps": list(redundant),
                    },
                    confidence=0.9,
                    implementation_difficulty="easy",
                    affected_tasks=[task.id],
                    details={
                        "task_id": task.id,
                        "redundant_dependencies": list(redundant),
                    }
                ))

        return suggestions


class ResourceOptimizer:
    """Optimizes resource allocation."""

    def __init__(self):
        """Initialize resource optimizer."""
        pass

    def optimize(
        self,
        workflow: Any,
        task_metrics: Dict[str, Dict[str, Any]]
    ) -> List[OptimizationSuggestion]:
        """
        Optimize resource allocation.

        Args:
            workflow: Workflow object
            task_metrics: Task performance metrics

        Returns:
            List of resource optimization suggestions
        """
        suggestions = []

        for task in workflow.tasks:
            if task.id not in task_metrics:
                continue

            metrics = task_metrics[task.id]

            # Check for timeout issues
            if metrics["timeout_count"] > 0:
                suggestions.append(OptimizationSuggestion(
                    optimization_type=OptimizationType.TIMEOUT_ADJUSTMENT,
                    description=f"Increase timeout for {task.name}",
                    expected_improvement={
                        "reduced_timeouts": metrics["timeout_count"],
                        "current_timeout_rate": metrics["timeout_count"] / metrics["executions"],
                    },
                    confidence=0.8,
                    implementation_difficulty="easy",
                    affected_tasks=[task.id],
                    details={
                        "task_id": task.id,
                        "timeout_count": metrics["timeout_count"],
                        "suggested_timeout": int(metrics["max_duration"] * 1.5),
                    }
                ))

            # Check for high variance in duration (might need more resources)
            if metrics["std_duration"] > metrics["avg_duration"] * 0.5:
                suggestions.append(OptimizationSuggestion(
                    optimization_type=OptimizationType.RESOURCE_ALLOCATION,
                    description=f"Increase resource allocation for {task.name}",
                    expected_improvement={
                        "reduced_variance": metrics["std_duration"],
                        "more_consistent_performance": True,
                    },
                    confidence=0.6,
                    implementation_difficulty="medium",
                    affected_tasks=[task.id],
                    details={
                        "task_id": task.id,
                        "current_variance": metrics["std_duration"],
                        "avg_duration": metrics["avg_duration"],
                    }
                ))

        return suggestions


class WorkflowOptimizer:
    """Main workflow optimizer orchestrator."""

    def __init__(self):
        """Initialize workflow optimizer."""
        self.telemetry_analyzer = TelemetryAnalyzer()
        self.bottleneck_detector = BottleneckDetector()
        self.parallelization_analyzer = ParallelizationAnalyzer()
        self.resource_optimizer = ResourceOptimizer()

    def optimize(
        self,
        workflow: Any,
        telemetry: List[WorkflowTelemetry]
    ) -> OptimizationResult:
        """
        Optimize a workflow based on telemetry.

        Args:
            workflow: Workflow object
            telemetry: List of workflow telemetry records

        Returns:
            Optimization result with suggestions
        """
        logger.info(f"Optimizing workflow {workflow.id} based on {len(telemetry)} executions")

        # Collect all task telemetry
        all_task_telemetry = []
        for wf_telemetry in telemetry:
            all_task_telemetry.extend(wf_telemetry.task_telemetry)

        # Analyze task performance
        task_metrics = self.telemetry_analyzer.analyze_task_performance(
            all_task_telemetry
        )

        # Detect bottlenecks
        bottlenecks = self.bottleneck_detector.detect(workflow, telemetry)

        # Find optimization suggestions
        suggestions = []

        # Parallelization opportunities
        suggestions.extend(
            self.parallelization_analyzer.find_opportunities(workflow, task_metrics)
        )

        # Resource optimization
        suggestions.extend(
            self.resource_optimizer.optimize(workflow, task_metrics)
        )

        # Calculate current metrics
        critical_path, critical_duration = self.telemetry_analyzer.identify_critical_path(
            workflow, task_metrics
        )
        parallelism = self.telemetry_analyzer.calculate_parallelism(workflow)

        avg_duration = statistics.mean(
            wf.total_duration for wf in telemetry
        ) if telemetry else 0

        success_rate = sum(
            1 for wf in telemetry if wf.success
        ) / len(telemetry) if telemetry else 0

        current_metrics = {
            "avg_duration": avg_duration,
            "critical_path_duration": critical_duration,
            "success_rate": success_rate,
            "total_tasks": len(workflow.tasks),
            "parallelism": parallelism,
            "critical_path": critical_path,
        }

        # Calculate projected metrics (estimate improvement)
        projected_improvement = self._calculate_projected_improvement(
            current_metrics,
            suggestions,
            bottlenecks
        )

        projected_metrics = {
            "avg_duration": current_metrics["avg_duration"] * (1 - projected_improvement["duration"]),
            "success_rate": min(1.0, current_metrics["success_rate"] + projected_improvement["success_rate"]),
            "improvement_percentage": projected_improvement["duration"] * 100,
        }

        # Generate summary
        summary = self._generate_summary(
            len(telemetry),
            bottlenecks,
            suggestions,
            projected_improvement
        )

        result = OptimizationResult(
            workflow_id=workflow.id,
            analyzed_executions=len(telemetry),
            bottlenecks=bottlenecks,
            suggestions=suggestions,
            current_metrics=current_metrics,
            projected_metrics=projected_metrics,
            optimization_summary=summary,
        )

        logger.info(f"Optimization complete: {len(bottlenecks)} bottlenecks, "
                   f"{len(suggestions)} suggestions, "
                   f"{projected_improvement['duration']*100:.1f}% projected improvement")

        return result

    def _calculate_projected_improvement(
        self,
        current_metrics: Dict[str, Any],
        suggestions: List[OptimizationSuggestion],
        bottlenecks: List[Bottleneck]
    ) -> Dict[str, float]:
        """Calculate projected improvement from suggestions."""
        # Simple heuristic-based estimation
        duration_improvement = 0.0
        success_rate_improvement = 0.0

        # Each bottleneck if fixed contributes to improvement
        for bottleneck in bottlenecks:
            if bottleneck.issue_type == "slow_execution":
                duration_improvement += bottleneck.severity * 0.1  # Up to 10% per bottleneck
            elif bottleneck.issue_type == "high_failure_rate":
                success_rate_improvement += (1 - bottleneck.impact["success_rate"]) * 0.5

        # Parallelization suggestions
        parallel_suggestions = [
            s for s in suggestions
            if s.optimization_type == OptimizationType.PARALLELIZATION
        ]
        if parallel_suggestions:
            duration_improvement += 0.15  # 15% improvement from parallelization

        # Cap improvements
        duration_improvement = min(0.5, duration_improvement)  # Max 50% improvement
        success_rate_improvement = min(0.2, success_rate_improvement)  # Max 20% improvement

        return {
            "duration": duration_improvement,
            "success_rate": success_rate_improvement,
        }

    def _generate_summary(
        self,
        executions: int,
        bottlenecks: List[Bottleneck],
        suggestions: List[OptimizationSuggestion],
        projected_improvement: Dict[str, float]
    ) -> str:
        """Generate optimization summary."""
        lines = [
            f"Analyzed {executions} workflow executions.",
            f"Found {len(bottlenecks)} bottlenecks and {len(suggestions)} optimization opportunities.",
        ]

        if bottlenecks:
            lines.append(f"\nTop bottleneck: {bottlenecks[0].description}")

        if suggestions:
            lines.append(f"\nTop suggestion: {suggestions[0].description}")

        lines.append(
            f"\nProjected improvement: {projected_improvement['duration']*100:.1f}% faster, "
            f"{projected_improvement['success_rate']*100:.1f}% higher success rate."
        )

        return "\n".join(lines)


def main():
    """Test workflow optimizer."""
    logging.basicConfig(level=logging.INFO)

    # This would normally use real telemetry data
    print("Workflow Optimizer initialized successfully")


if __name__ == "__main__":
    main()
