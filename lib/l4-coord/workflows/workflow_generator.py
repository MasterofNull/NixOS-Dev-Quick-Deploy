#!/usr/bin/env python3
"""
Workflow Generator - Automatic workflow generation from goals.

This module provides intelligent workflow generation from natural language goals,
including task decomposition, dependency analysis, and agent assignment.
"""

import re
import json
import logging
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import hashlib
from datetime import datetime

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """Types of workflow tasks."""
    CODE = "code"
    TEST = "test"
    BUILD = "build"
    DEPLOY = "deploy"
    MONITOR = "monitor"
    ANALYZE = "analyze"
    DOCUMENT = "document"
    REVIEW = "review"
    VALIDATE = "validate"
    CONFIGURE = "configure"
    INVESTIGATE = "investigate"
    FIX = "fix"
    OPTIMIZE = "optimize"
    PLAN = "plan"


class AgentRole(Enum):
    """Agent roles for task assignment."""
    ORCHESTRATOR = "orchestrator"
    DEVELOPER = "developer"
    TESTER = "tester"
    DEPLOYER = "deployer"
    MONITOR = "monitor"
    ANALYST = "analyst"
    REVIEWER = "reviewer"
    DOCUMENTER = "documenter"


@dataclass
class Task:
    """Represents a single task in a workflow."""
    id: str
    name: str
    description: str
    task_type: TaskType
    agent_role: AgentRole
    dependencies: List[str] = field(default_factory=list)
    estimated_duration: int = 0  # minutes
    required_resources: Dict[str, Any] = field(default_factory=dict)
    validation_criteria: List[str] = field(default_factory=list)
    retry_policy: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "task_type": self.task_type.value,
            "agent_role": self.agent_role.value,
            "dependencies": self.dependencies,
            "estimated_duration": self.estimated_duration,
            "required_resources": self.required_resources,
            "validation_criteria": self.validation_criteria,
            "retry_policy": self.retry_policy,
            "metadata": self.metadata,
        }


@dataclass
class Workflow:
    """Represents a complete workflow."""
    id: str
    name: str
    description: str
    goal: str
    tasks: List[Task]
    created_at: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert workflow to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "goal": self.goal,
            "tasks": [task.to_dict() for task in self.tasks],
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    def get_task_graph(self) -> Dict[str, List[str]]:
        """Get task dependency graph."""
        graph = {}
        for task in self.tasks:
            graph[task.id] = task.dependencies
        return graph

    def get_execution_order(self) -> List[List[str]]:
        """Get topological execution order (batches of parallelizable tasks)."""
        graph = self.get_task_graph()
        in_degree = {task_id: 0 for task_id in graph}

        for task_id, deps in graph.items():
            for dep in deps:
                if dep in in_degree:
                    in_degree[task_id] += 1

        batches = []
        remaining = set(graph.keys())

        while remaining:
            ready = [task_id for task_id in remaining if in_degree[task_id] == 0]
            if not ready:
                raise ValueError("Circular dependency detected in workflow")

            batches.append(ready)
            for task_id in ready:
                remaining.remove(task_id)
                for other_id in remaining:
                    if task_id in graph[other_id]:
                        in_degree[other_id] -= 1

        return batches


class GoalParser:
    """Parses natural language goals into structured components."""

    # Patterns for goal parsing
    DEPLOYMENT_PATTERNS = [
        r"deploy\s+(?P<target>[\w\s]+?)(?:\s+with\s+(?P<features>.+))?",
        r"rollout\s+(?P<target>[\w\s]+)",
        r"launch\s+(?P<target>[\w\s]+)",
    ]

    FEATURE_PATTERNS = [
        r"add\s+(?P<feature>[\w\s]+?)(?:\s+to\s+(?P<target>.+))?",
        r"implement\s+(?P<feature>[\w\s]+)",
        r"create\s+(?P<feature>[\w\s]+)",
    ]

    FIX_PATTERNS = [
        r"fix\s+(?P<issue>[\w\s]+)",
        r"resolve\s+(?P<issue>[\w\s]+)",
        r"repair\s+(?P<issue>[\w\s]+)",
    ]

    INVESTIGATE_PATTERNS = [
        r"investigate\s+(?P<issue>[\w\s]+)",
        r"analyze\s+(?P<issue>[\w\s]+)",
        r"diagnose\s+(?P<issue>[\w\s]+)",
    ]

    OPTIMIZE_PATTERNS = [
        r"optimize\s+(?P<target>[\w\s]+)",
        r"improve\s+(?P<target>[\w\s]+)",
        r"enhance\s+(?P<target>[\w\s]+)",
    ]

    def __init__(self):
        """Initialize goal parser."""
        self.patterns = {
            "deployment": self.DEPLOYMENT_PATTERNS,
            "feature": self.FEATURE_PATTERNS,
            "fix": self.FIX_PATTERNS,
            "investigate": self.INVESTIGATE_PATTERNS,
            "optimize": self.OPTIMIZE_PATTERNS,
        }

    def parse(self, goal: str) -> Dict[str, Any]:
        """
        Parse a natural language goal.

        Args:
            goal: Natural language goal description

        Returns:
            Structured goal components
        """
        goal_lower = goal.lower()

        # Try each pattern category
        for category, patterns in self.patterns.items():
            for pattern in patterns:
                match = re.search(pattern, goal_lower)
                if match:
                    return {
                        "category": category,
                        "raw_goal": goal,
                        "components": match.groupdict(),
                        "keywords": self._extract_keywords(goal),
                    }

        # Fallback: generic parsing
        return {
            "category": "generic",
            "raw_goal": goal,
            "components": {},
            "keywords": self._extract_keywords(goal),
        }

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text."""
        # Common stop words to filter
        stop_words = {
            "a", "an", "and", "are", "as", "at", "be", "by", "for",
            "from", "has", "he", "in", "is", "it", "its", "of", "on",
            "that", "the", "to", "was", "will", "with"
        }

        words = re.findall(r'\b\w+\b', text.lower())
        return [w for w in words if w not in stop_words and len(w) > 2]


class TaskDecomposer:
    """Decomposes goals into tasks."""

    # Standard task templates by category
    DEPLOYMENT_TASKS = [
        ("validate_code", TaskType.VALIDATE, "Validate code quality and tests"),
        ("build", TaskType.BUILD, "Build deployment artifacts"),
        ("test_integration", TaskType.TEST, "Run integration tests"),
        ("deploy", TaskType.DEPLOY, "Deploy to target environment"),
        ("health_check", TaskType.VALIDATE, "Verify deployment health"),
        ("monitor", TaskType.MONITOR, "Set up monitoring"),
    ]

    FEATURE_TASKS = [
        ("design", TaskType.PLAN, "Design feature architecture"),
        ("implement", TaskType.CODE, "Implement feature code"),
        ("unit_test", TaskType.TEST, "Write unit tests"),
        ("integration_test", TaskType.TEST, "Write integration tests"),
        ("review", TaskType.REVIEW, "Code review"),
        ("document", TaskType.DOCUMENT, "Document feature"),
    ]

    FIX_TASKS = [
        ("investigate", TaskType.INVESTIGATE, "Investigate issue"),
        ("analyze", TaskType.ANALYZE, "Analyze root cause"),
        ("fix", TaskType.FIX, "Implement fix"),
        ("test", TaskType.TEST, "Test fix"),
        ("verify", TaskType.VALIDATE, "Verify fix in production"),
        ("document", TaskType.DOCUMENT, "Document fix"),
    ]

    INVESTIGATE_TASKS = [
        ("gather_data", TaskType.INVESTIGATE, "Gather relevant data"),
        ("analyze", TaskType.ANALYZE, "Analyze data"),
        ("identify_cause", TaskType.INVESTIGATE, "Identify root cause"),
        ("document", TaskType.DOCUMENT, "Document findings"),
    ]

    OPTIMIZE_TASKS = [
        ("analyze_current", TaskType.ANALYZE, "Analyze current performance"),
        ("identify_bottlenecks", TaskType.INVESTIGATE, "Identify bottlenecks"),
        ("plan_improvements", TaskType.PLAN, "Plan improvements"),
        ("implement", TaskType.CODE, "Implement optimizations"),
        ("test", TaskType.TEST, "Test improvements"),
        ("validate", TaskType.VALIDATE, "Validate performance gains"),
    ]

    def __init__(self):
        """Initialize task decomposer."""
        self.task_templates = {
            "deployment": self.DEPLOYMENT_TASKS,
            "feature": self.FEATURE_TASKS,
            "fix": self.FIX_TASKS,
            "investigate": self.INVESTIGATE_TASKS,
            "optimize": self.OPTIMIZE_TASKS,
        }

    def decompose(self, parsed_goal: Dict[str, Any]) -> List[Tuple[str, TaskType, str]]:
        """
        Decompose parsed goal into tasks.

        Args:
            parsed_goal: Parsed goal from GoalParser

        Returns:
            List of (task_name, task_type, description) tuples
        """
        category = parsed_goal["category"]

        if category in self.task_templates:
            return self.task_templates[category]

        # Generic fallback
        return [
            ("analyze", TaskType.ANALYZE, "Analyze requirements"),
            ("plan", TaskType.PLAN, "Create execution plan"),
            ("execute", TaskType.CODE, "Execute plan"),
            ("validate", TaskType.VALIDATE, "Validate results"),
        ]


class DependencyAnalyzer:
    """Analyzes task dependencies."""

    # Dependency rules: task_type -> list of prerequisite task_types
    DEPENDENCY_RULES = {
        TaskType.BUILD: [TaskType.CODE, TaskType.VALIDATE],
        TaskType.DEPLOY: [TaskType.BUILD, TaskType.TEST],
        TaskType.TEST: [TaskType.CODE],
        TaskType.MONITOR: [TaskType.DEPLOY],
        TaskType.REVIEW: [TaskType.CODE],
        TaskType.DOCUMENT: [TaskType.CODE, TaskType.TEST],
        TaskType.FIX: [TaskType.INVESTIGATE, TaskType.ANALYZE],
        TaskType.VALIDATE: [TaskType.CODE, TaskType.FIX],
    }

    def analyze(self, tasks: List[Task]) -> None:
        """
        Analyze and set task dependencies in place.

        Args:
            tasks: List of tasks to analyze
        """
        # Build task type to task ID mapping
        type_to_ids = {}
        for task in tasks:
            if task.task_type not in type_to_ids:
                type_to_ids[task.task_type] = []
            type_to_ids[task.task_type].append(task.id)

        # Set dependencies based on rules
        for task in tasks:
            if task.task_type in self.DEPENDENCY_RULES:
                prereq_types = self.DEPENDENCY_RULES[task.task_type]
                for prereq_type in prereq_types:
                    if prereq_type in type_to_ids:
                        # Add all tasks of prerequisite type as dependencies
                        task.dependencies.extend(type_to_ids[prereq_type])


class AgentAssigner:
    """Assigns agents to tasks based on task type."""

    # Task type to agent role mapping
    ROLE_MAPPING = {
        TaskType.CODE: AgentRole.DEVELOPER,
        TaskType.TEST: AgentRole.TESTER,
        TaskType.BUILD: AgentRole.DEVELOPER,
        TaskType.DEPLOY: AgentRole.DEPLOYER,
        TaskType.MONITOR: AgentRole.MONITOR,
        TaskType.ANALYZE: AgentRole.ANALYST,
        TaskType.DOCUMENT: AgentRole.DOCUMENTER,
        TaskType.REVIEW: AgentRole.REVIEWER,
        TaskType.VALIDATE: AgentRole.TESTER,
        TaskType.CONFIGURE: AgentRole.DEPLOYER,
        TaskType.INVESTIGATE: AgentRole.ANALYST,
        TaskType.FIX: AgentRole.DEVELOPER,
        TaskType.OPTIMIZE: AgentRole.DEVELOPER,
        TaskType.PLAN: AgentRole.ORCHESTRATOR,
    }

    def assign(self, task: Task) -> AgentRole:
        """
        Assign agent role to task.

        Args:
            task: Task to assign agent to

        Returns:
            Assigned agent role
        """
        return self.ROLE_MAPPING.get(task.task_type, AgentRole.ORCHESTRATOR)


class ResourceEstimator:
    """Estimates resource requirements for tasks."""

    # Base duration estimates in minutes
    DURATION_ESTIMATES = {
        TaskType.CODE: 30,
        TaskType.TEST: 15,
        TaskType.BUILD: 10,
        TaskType.DEPLOY: 20,
        TaskType.MONITOR: 5,
        TaskType.ANALYZE: 25,
        TaskType.DOCUMENT: 20,
        TaskType.REVIEW: 15,
        TaskType.VALIDATE: 10,
        TaskType.CONFIGURE: 15,
        TaskType.INVESTIGATE: 30,
        TaskType.FIX: 25,
        TaskType.OPTIMIZE: 40,
        TaskType.PLAN: 20,
    }

    def estimate(self, task: Task) -> None:
        """
        Estimate and set resource requirements in place.

        Args:
            task: Task to estimate resources for
        """
        # Set duration estimate
        task.estimated_duration = self.DURATION_ESTIMATES.get(
            task.task_type, 20
        )

        # Set resource requirements based on task type
        if task.task_type in [TaskType.BUILD, TaskType.DEPLOY]:
            task.required_resources["cpu"] = "medium"
            task.required_resources["memory"] = "medium"
        elif task.task_type in [TaskType.TEST, TaskType.ANALYZE]:
            task.required_resources["cpu"] = "high"
            task.required_resources["memory"] = "high"
        else:
            task.required_resources["cpu"] = "low"
            task.required_resources["memory"] = "low"

        # Add validation criteria
        if task.task_type == TaskType.CODE:
            task.validation_criteria.extend([
                "Code passes linting",
                "Code follows style guide",
                "No critical issues",
            ])
        elif task.task_type == TaskType.TEST:
            task.validation_criteria.extend([
                "All tests pass",
                "Coverage >= 80%",
            ])
        elif task.task_type == TaskType.DEPLOY:
            task.validation_criteria.extend([
                "Deployment successful",
                "Health checks pass",
                "No errors in logs",
            ])


class WorkflowGenerator:
    """Main workflow generator orchestrator."""

    def __init__(self):
        """Initialize workflow generator."""
        self.goal_parser = GoalParser()
        self.task_decomposer = TaskDecomposer()
        self.dependency_analyzer = DependencyAnalyzer()
        self.agent_assigner = AgentAssigner()
        self.resource_estimator = ResourceEstimator()

    def generate(self, goal: str, name: Optional[str] = None) -> Workflow:
        """
        Generate a workflow from a goal.

        Args:
            goal: Natural language goal description
            name: Optional workflow name (auto-generated if not provided)

        Returns:
            Generated workflow
        """
        logger.info(f"Generating workflow for goal: {goal}")

        # Parse goal
        parsed_goal = self.goal_parser.parse(goal)
        logger.debug(f"Parsed goal: {parsed_goal}")

        # Decompose into tasks
        task_specs = self.task_decomposer.decompose(parsed_goal)

        # Create task objects
        tasks = []
        for i, (task_name, task_type, description) in enumerate(task_specs):
            task = Task(
                id=f"task_{i+1}",
                name=task_name,
                description=description,
                task_type=task_type,
                agent_role=AgentRole.ORCHESTRATOR,  # Will be assigned later
            )
            tasks.append(task)

        # Analyze dependencies
        self.dependency_analyzer.analyze(tasks)

        # Assign agents
        for task in tasks:
            task.agent_role = self.agent_assigner.assign(task)

        # Estimate resources
        for task in tasks:
            self.resource_estimator.estimate(task)

        # Create workflow
        workflow_id = self._generate_workflow_id(goal)
        workflow_name = name or f"Workflow for: {goal[:50]}"

        workflow = Workflow(
            id=workflow_id,
            name=workflow_name,
            description=f"Auto-generated workflow for: {goal}",
            goal=goal,
            tasks=tasks,
            created_at=datetime.utcnow().isoformat(),
            metadata={
                "parsed_goal": parsed_goal,
                "total_tasks": len(tasks),
                "estimated_duration": sum(t.estimated_duration for t in tasks),
            }
        )

        # Validate workflow
        self.validate(workflow)

        logger.info(f"Generated workflow {workflow.id} with {len(tasks)} tasks")
        return workflow

    def validate(self, workflow: Workflow) -> bool:
        """
        Validate a workflow.

        Args:
            workflow: Workflow to validate

        Returns:
            True if valid

        Raises:
            ValueError: If workflow is invalid
        """
        # Check for tasks
        if not workflow.tasks:
            raise ValueError("Workflow has no tasks")

        # Check for circular dependencies
        try:
            workflow.get_execution_order()
        except ValueError as e:
            raise ValueError(f"Invalid workflow: {e}")

        # Check task IDs are unique
        task_ids = [t.id for t in workflow.tasks]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("Duplicate task IDs found")

        # Check dependencies reference valid tasks
        for task in workflow.tasks:
            for dep_id in task.dependencies:
                if dep_id not in task_ids:
                    raise ValueError(
                        f"Task {task.id} has invalid dependency: {dep_id}"
                    )

        return True

    def _generate_workflow_id(self, goal: str) -> str:
        """Generate unique workflow ID from goal."""
        hash_input = f"{goal}_{datetime.utcnow().isoformat()}"
        hash_digest = hashlib.sha256(hash_input.encode()).hexdigest()
        return f"wf_{hash_digest[:12]}"


# Convenience functions
def generate_workflow(goal: str, name: Optional[str] = None) -> Workflow:
    """Generate a workflow from a goal."""
    generator = WorkflowGenerator()
    return generator.generate(goal, name)


def main():
    """Test workflow generation."""
    logging.basicConfig(level=logging.INFO)

    # Test goals
    test_goals = [
        "Deploy authentication service with health checks and monitoring",
        "Add rate limiting to API endpoints",
        "Investigate and fix high memory usage in production",
        "Optimize database query performance",
    ]

    generator = WorkflowGenerator()

    for goal in test_goals:
        print(f"\n{'='*80}")
        print(f"Goal: {goal}")
        print('='*80)

        workflow = generator.generate(goal)

        print(f"\nWorkflow ID: {workflow.id}")
        print(f"Tasks: {len(workflow.tasks)}")
        print(f"Estimated Duration: {workflow.metadata['estimated_duration']} minutes")

        print("\nExecution Order:")
        batches = workflow.get_execution_order()
        for i, batch in enumerate(batches):
            print(f"  Batch {i+1}: {', '.join(batch)}")

        print("\nTasks:")
        for task in workflow.tasks:
            print(f"  {task.id}: {task.name} ({task.task_type.value})")
            print(f"    Agent: {task.agent_role.value}")
            print(f"    Duration: {task.estimated_duration} min")
            print(f"    Dependencies: {', '.join(task.dependencies) or 'None'}")


if __name__ == "__main__":
    main()
