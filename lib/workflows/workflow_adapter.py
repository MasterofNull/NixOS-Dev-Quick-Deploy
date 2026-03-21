#!/usr/bin/env python3
"""
Workflow Adapter - Reuse and adapt existing workflows.

This module provides workflow adaptation capabilities including similarity
detection, template matching, parameter binding, and workflow customization.
"""

import re
import logging
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
import difflib

logger = logging.getLogger(__name__)


@dataclass
class AdaptationResult:
    """Result of workflow adaptation."""
    adapted_workflow: Any  # Workflow object
    template_id: Optional[str]
    similarity_score: float
    adaptations_applied: List[str]
    parameter_bindings: Dict[str, Any]
    validation_status: str
    confidence: float


class SimilarityDetector:
    """Detects similarity between goals and workflows."""

    def __init__(self):
        """Initialize similarity detector."""
        pass

    def calculate_goal_similarity(
        self,
        goal1: str,
        goal2: str
    ) -> float:
        """
        Calculate similarity between two goals.

        Args:
            goal1: First goal
            goal2: Second goal

        Returns:
            Similarity score (0-1)
        """
        # Use sequence matcher for basic similarity
        similarity = difflib.SequenceMatcher(
            None,
            goal1.lower(),
            goal2.lower()
        ).ratio()

        # Boost similarity if key words match
        words1 = set(self._extract_keywords(goal1))
        words2 = set(self._extract_keywords(goal2))

        if words1 and words2:
            keyword_overlap = len(words1 & words2) / max(len(words1), len(words2))
            # Weighted combination: 60% sequence, 40% keyword
            similarity = similarity * 0.6 + keyword_overlap * 0.4

        return similarity

    def calculate_workflow_similarity(
        self,
        workflow1: Any,
        workflow2: Any
    ) -> float:
        """
        Calculate similarity between two workflows.

        Args:
            workflow1: First workflow
            workflow2: Second workflow

        Returns:
            Similarity score (0-1)
        """
        # Compare task structure
        tasks1 = [t.task_type.value for t in workflow1.tasks]
        tasks2 = [t.task_type.value for t in workflow2.tasks]

        # Sequence similarity
        seq_similarity = difflib.SequenceMatcher(None, tasks1, tasks2).ratio()

        # Task type overlap
        set1 = set(tasks1)
        set2 = set(tasks2)
        if set1 and set2:
            type_overlap = len(set1 & set2) / max(len(set1), len(set2))
        else:
            type_overlap = 0

        # Weighted combination
        similarity = seq_similarity * 0.7 + type_overlap * 0.3

        return similarity

    def find_similar_workflows(
        self,
        goal: str,
        workflows: List[Any],
        min_similarity: float = 0.5
    ) -> List[Tuple[Any, float]]:
        """
        Find similar workflows for a goal.

        Args:
            goal: Target goal
            workflows: List of existing workflows
            min_similarity: Minimum similarity threshold

        Returns:
            List of (workflow, similarity) tuples
        """
        similar = []

        for workflow in workflows:
            similarity = self.calculate_goal_similarity(goal, workflow.goal)

            if similarity >= min_similarity:
                similar.append((workflow, similarity))

        # Sort by similarity
        similar.sort(key=lambda x: x[1], reverse=True)

        return similar

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text."""
        # Common stop words
        stop_words = {
            "a", "an", "and", "are", "as", "at", "be", "by", "for",
            "from", "has", "he", "in", "is", "it", "its", "of", "on",
            "that", "the", "to", "was", "will", "with"
        }

        words = re.findall(r'\b\w+\b', text.lower())
        return [w for w in words if w not in stop_words and len(w) > 2]


class ParameterBinder:
    """Binds parameters to template workflows."""

    def __init__(self):
        """Initialize parameter binder."""
        pass

    def bind(
        self,
        template: Any,
        goal: str,
        explicit_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Bind parameters from goal to template.

        Args:
            template: Workflow template
            goal: Target goal
            explicit_params: Explicitly provided parameters

        Returns:
            Dictionary of parameter bindings
        """
        bindings = explicit_params.copy() if explicit_params else {}

        # Try to extract parameter values from goal
        for param in template.parameters:
            if param.name in bindings:
                # Already provided explicitly
                continue

            # Try to extract from goal
            value = self._extract_parameter_value(param, goal)

            if value is not None:
                bindings[param.name] = value
            elif param.default_value is not None:
                bindings[param.name] = param.default_value
            elif param.required:
                # Use placeholder for required params without value
                bindings[param.name] = f"<{param.name}>"

        # Validate bindings
        self._validate_bindings(template, bindings)

        return bindings

    def _extract_parameter_value(
        self,
        param: Any,
        goal: str
    ) -> Optional[Any]:
        """Extract parameter value from goal."""
        # Simple heuristic-based extraction
        goal_lower = goal.lower()

        # Try to find parameter name in goal
        param_name_normalized = param.name.replace("_", " ")

        if param_name_normalized in goal_lower:
            # Try to extract value after parameter name
            pattern = rf"{re.escape(param_name_normalized)}\s+(\w+)"
            match = re.search(pattern, goal_lower)
            if match:
                return match.group(1)

        # Special case: service_name
        if param.name == "service_name":
            # Look for "deploy X" or "X service"
            for pattern in [r"deploy\s+(\w+)", r"(\w+)\s+service"]:
                match = re.search(pattern, goal_lower)
                if match:
                    return match.group(1)

        # Special case: feature_name
        if param.name == "feature_name":
            # Look for "add X" or "implement X"
            for pattern in [r"add\s+([\w\s]+?)(?:\s+to|$)", r"implement\s+([\w\s]+?)(?:\s+to|$)"]:
                match = re.search(pattern, goal_lower)
                if match:
                    return match.group(1).strip()

        return None

    def _validate_bindings(
        self,
        template: Any,
        bindings: Dict[str, Any]
    ):
        """
        Validate parameter bindings.

        Raises:
            ValueError: If bindings are invalid
        """
        for param in template.parameters:
            if param.required and param.name not in bindings:
                raise ValueError(f"Required parameter '{param.name}' not provided")

            if param.name in bindings:
                value = bindings[param.name]

                # Check allowed values
                if param.allowed_values and value not in param.allowed_values:
                    raise ValueError(
                        f"Parameter '{param.name}' value '{value}' not in allowed values: "
                        f"{param.allowed_values}"
                    )

                # Check validation pattern
                if param.validation_pattern and isinstance(value, str):
                    if not re.match(param.validation_pattern, value):
                        raise ValueError(
                            f"Parameter '{param.name}' value '{value}' does not match "
                            f"pattern: {param.validation_pattern}"
                        )


class WorkflowCustomizer:
    """Customizes workflows based on requirements."""

    def __init__(self):
        """Initialize workflow customizer."""
        pass

    def customize(
        self,
        base_workflow: Any,
        goal: str,
        customizations: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Customize a workflow.

        Args:
            base_workflow: Base workflow to customize
            goal: Target goal
            customizations: Optional customization directives

        Returns:
            Customized workflow
        """
        from .workflow_generator import Workflow, Task
        import copy

        # Deep copy to avoid modifying original
        customized = copy.deepcopy(base_workflow)

        # Update goal and metadata
        customized.goal = goal
        customized.description = f"Adapted workflow for: {goal}"
        customized.created_at = datetime.utcnow().isoformat()

        if customizations:
            # Apply task additions
            if "add_tasks" in customizations:
                for task_spec in customizations["add_tasks"]:
                    self._add_task(customized, task_spec)

            # Apply task removals
            if "remove_tasks" in customizations:
                for task_id in customizations["remove_tasks"]:
                    self._remove_task(customized, task_id)

            # Apply task modifications
            if "modify_tasks" in customizations:
                for task_id, modifications in customizations["modify_tasks"].items():
                    self._modify_task(customized, task_id, modifications)

        return customized

    def _add_task(self, workflow: Any, task_spec: Dict[str, Any]):
        """Add a task to workflow."""
        from .workflow_generator import Task, TaskType, AgentRole

        task = Task(
            id=task_spec.get("id", f"task_{len(workflow.tasks) + 1}"),
            name=task_spec["name"],
            description=task_spec["description"],
            task_type=TaskType(task_spec.get("task_type", "code")),
            agent_role=AgentRole(task_spec.get("agent_role", "developer")),
            dependencies=task_spec.get("dependencies", []),
            estimated_duration=task_spec.get("estimated_duration", 20),
        )

        workflow.tasks.append(task)

    def _remove_task(self, workflow: Any, task_id: str):
        """Remove a task from workflow."""
        # Remove task
        workflow.tasks = [t for t in workflow.tasks if t.id != task_id]

        # Remove dependencies on this task
        for task in workflow.tasks:
            if task_id in task.dependencies:
                task.dependencies.remove(task_id)

    def _modify_task(
        self,
        workflow: Any,
        task_id: str,
        modifications: Dict[str, Any]
    ):
        """Modify a task in workflow."""
        task = next((t for t in workflow.tasks if t.id == task_id), None)

        if not task:
            logger.warning(f"Task {task_id} not found for modification")
            return

        # Apply modifications
        for key, value in modifications.items():
            if hasattr(task, key):
                setattr(task, key, value)


class WorkflowValidator:
    """Validates adapted workflows."""

    def __init__(self):
        """Initialize workflow validator."""
        pass

    def validate(self, workflow: Any) -> Tuple[bool, List[str]]:
        """
        Validate a workflow.

        Args:
            workflow: Workflow to validate

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        # Check for tasks
        if not workflow.tasks:
            errors.append("Workflow has no tasks")

        # Check for circular dependencies
        try:
            workflow.get_execution_order()
        except ValueError as e:
            errors.append(f"Circular dependency detected: {e}")

        # Check task IDs are unique
        task_ids = [t.id for t in workflow.tasks]
        if len(task_ids) != len(set(task_ids)):
            errors.append("Duplicate task IDs found")

        # Check dependencies reference valid tasks
        for task in workflow.tasks:
            for dep_id in task.dependencies:
                if dep_id not in task_ids:
                    errors.append(
                        f"Task {task.id} has invalid dependency: {dep_id}"
                    )

        # Check for orphaned tasks (tasks with no path to completion)
        execution_order = None
        try:
            execution_order = workflow.get_execution_order()
        except:
            pass

        if execution_order:
            all_scheduled = set()
            for batch in execution_order:
                all_scheduled.update(batch)

            for task in workflow.tasks:
                if task.id not in all_scheduled:
                    errors.append(f"Task {task.id} is orphaned (no execution path)")

        is_valid = len(errors) == 0

        return is_valid, errors


class WorkflowAdapter:
    """Main workflow adapter orchestrator."""

    def __init__(self):
        """Initialize workflow adapter."""
        self.similarity_detector = SimilarityDetector()
        self.parameter_binder = ParameterBinder()
        self.customizer = WorkflowCustomizer()
        self.validator = WorkflowValidator()

    def adapt_from_template(
        self,
        template: Any,
        goal: str,
        parameters: Optional[Dict[str, Any]] = None,
        customizations: Optional[Dict[str, Any]] = None
    ) -> AdaptationResult:
        """
        Adapt a template to a new goal.

        Args:
            template: Workflow template
            goal: Target goal
            parameters: Optional parameter values
            customizations: Optional customization directives

        Returns:
            Adaptation result
        """
        logger.info(f"Adapting template {template.id} for goal: {goal}")

        adaptations = []

        # Bind parameters
        bindings = self.parameter_binder.bind(template, goal, parameters)
        adaptations.append(f"Bound {len(bindings)} parameters")

        # Create workflow from template
        adapted_workflow = self._instantiate_template(template, bindings)
        adaptations.append("Instantiated template")

        # Apply customizations
        if customizations:
            adapted_workflow = self.customizer.customize(
                adapted_workflow,
                goal,
                customizations
            )
            adaptations.append("Applied customizations")

        # Update workflow goal
        adapted_workflow.goal = goal

        # Validate
        is_valid, errors = self.validator.validate(adapted_workflow)

        if not is_valid:
            validation_status = f"Invalid: {'; '.join(errors)}"
            confidence = 0.5
        else:
            validation_status = "Valid"
            confidence = 0.9

        result = AdaptationResult(
            adapted_workflow=adapted_workflow,
            template_id=template.id,
            similarity_score=self.similarity_detector.calculate_goal_similarity(
                goal, template.goal_pattern
            ),
            adaptations_applied=adaptations,
            parameter_bindings=bindings,
            validation_status=validation_status,
            confidence=confidence,
        )

        logger.info(f"Adaptation complete: {validation_status}")

        return result

    def adapt_from_workflow(
        self,
        source_workflow: Any,
        goal: str,
        customizations: Optional[Dict[str, Any]] = None
    ) -> AdaptationResult:
        """
        Adapt an existing workflow to a new goal.

        Args:
            source_workflow: Source workflow
            goal: Target goal
            customizations: Optional customization directives

        Returns:
            Adaptation result
        """
        logger.info(f"Adapting workflow {source_workflow.id} for goal: {goal}")

        adaptations = []

        # Customize workflow
        adapted_workflow = self.customizer.customize(
            source_workflow,
            goal,
            customizations
        )
        adaptations.append("Customized workflow")

        # Validate
        is_valid, errors = self.validator.validate(adapted_workflow)

        if not is_valid:
            validation_status = f"Invalid: {'; '.join(errors)}"
            confidence = 0.5
        else:
            validation_status = "Valid"
            confidence = 0.85

        # Calculate similarity
        similarity = self.similarity_detector.calculate_goal_similarity(
            goal, source_workflow.goal
        )

        result = AdaptationResult(
            adapted_workflow=adapted_workflow,
            template_id=None,
            similarity_score=similarity,
            adaptations_applied=adaptations,
            parameter_bindings={},
            validation_status=validation_status,
            confidence=confidence,
        )

        logger.info(f"Adaptation complete: {validation_status}")

        return result

    def _instantiate_template(
        self,
        template: Any,
        bindings: Dict[str, Any]
    ) -> Any:
        """
        Instantiate a workflow from a template.

        Args:
            template: Workflow template
            bindings: Parameter bindings

        Returns:
            Instantiated workflow
        """
        from .workflow_generator import Workflow, Task, TaskType, AgentRole
        import re

        # Create tasks from template
        tasks = []

        for task_template in template.task_template:
            # Replace parameter placeholders
            task_data = self._replace_placeholders(task_template, bindings)

            # Create task
            task = Task(
                id=task_data["id"],
                name=task_data["name"],
                description=task_data["description"],
                task_type=TaskType(task_data["task_type"]),
                agent_role=AgentRole(task_data["agent_role"]),
                dependencies=task_data.get("dependencies", []),
                estimated_duration=task_data.get("estimated_duration", 20),
                required_resources=task_data.get("required_resources", {}),
                validation_criteria=task_data.get("validation_criteria", []),
            )

            tasks.append(task)

        # Create workflow
        workflow = Workflow(
            id=f"wf_{template.id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            name=template.name,
            description=template.description,
            goal=template.goal_pattern,
            tasks=tasks,
            created_at=datetime.utcnow().isoformat(),
            metadata={"template_id": template.id},
        )

        return workflow

    def _replace_placeholders(
        self,
        data: Any,
        bindings: Dict[str, Any]
    ) -> Any:
        """Replace parameter placeholders in data."""
        if isinstance(data, str):
            # Replace {{ param_name }} with value
            for param_name, value in bindings.items():
                placeholder = f"{{{{ {param_name} }}}}"
                data = data.replace(placeholder, str(value))
            return data
        elif isinstance(data, dict):
            return {
                key: self._replace_placeholders(value, bindings)
                for key, value in data.items()
            }
        elif isinstance(data, list):
            return [
                self._replace_placeholders(item, bindings)
                for item in data
            ]
        else:
            return data


def main():
    """Test workflow adapter."""
    logging.basicConfig(level=logging.INFO)

    adapter = WorkflowAdapter()
    print("Workflow adapter initialized successfully")


if __name__ == "__main__":
    main()
