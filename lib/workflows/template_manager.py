#!/usr/bin/env python3
"""
Template Manager - Workflow template library management.

This module manages workflow templates including creation, storage,
search, versioning, and quality tracking.
"""

import json
import logging
import os
import re
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class TemplateParameter:
    """Represents a template parameter."""
    name: str
    description: str
    parameter_type: str  # string, int, bool, list, etc.
    default_value: Optional[Any] = None
    required: bool = True
    validation_pattern: Optional[str] = None
    allowed_values: Optional[List[Any]] = None


@dataclass
class TemplateMetadata:
    """Metadata for a workflow template."""
    category: str
    tags: List[str]
    author: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    version: str = "1.0.0"
    success_rate: float = 0.0
    avg_duration: float = 0.0
    usage_count: int = 0
    quality_score: float = 0.0


@dataclass
class WorkflowTemplate:
    """Represents a reusable workflow template."""
    id: str
    name: str
    description: str
    goal_pattern: str  # Regex pattern for matching goals
    parameters: List[TemplateParameter]
    task_template: List[Dict[str, Any]]  # Template for tasks
    metadata: TemplateMetadata
    examples: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert template to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "goal_pattern": self.goal_pattern,
            "parameters": [asdict(p) for p in self.parameters],
            "task_template": self.task_template,
            "metadata": asdict(self.metadata),
            "examples": self.examples,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkflowTemplate':
        """Create template from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            goal_pattern=data["goal_pattern"],
            parameters=[
                TemplateParameter(**p) for p in data.get("parameters", [])
            ],
            task_template=data.get("task_template", []),
            metadata=TemplateMetadata(**data.get("metadata", {})),
            examples=data.get("examples", []),
        )


class TemplateExtractor:
    """Extracts templates from successful workflows."""

    def __init__(self):
        """Initialize template extractor."""
        pass

    def extract(
        self,
        workflow: Any,
        telemetry: Optional[List[Any]] = None
    ) -> WorkflowTemplate:
        """
        Extract a template from a workflow.

        Args:
            workflow: Workflow object
            telemetry: Optional telemetry data for quality scoring

        Returns:
            Extracted workflow template
        """
        logger.info(f"Extracting template from workflow {workflow.id}")

        # Parameterize the workflow
        parameters = self._identify_parameters(workflow)

        # Create task template
        task_template = self._create_task_template(workflow, parameters)

        # Generate goal pattern
        goal_pattern = self._generate_goal_pattern(workflow.goal)

        # Calculate metadata
        metadata = self._calculate_metadata(workflow, telemetry)

        # Create template
        template_id = f"template_{workflow.id}"

        template = WorkflowTemplate(
            id=template_id,
            name=f"Template: {workflow.name}",
            description=f"Template extracted from workflow: {workflow.description}",
            goal_pattern=goal_pattern,
            parameters=parameters,
            task_template=task_template,
            metadata=metadata,
            examples=[{
                "goal": workflow.goal,
                "workflow_id": workflow.id,
            }]
        )

        logger.info(f"Extracted template {template.id} with {len(parameters)} parameters")
        return template

    def _identify_parameters(self, workflow: Any) -> List[TemplateParameter]:
        """Identify parameterizable parts of workflow."""
        parameters = []

        # Look for common parameterizable patterns in goal
        goal = workflow.goal.lower()

        # Service/component name
        if "service" in goal or "component" in goal or "api" in goal:
            parameters.append(TemplateParameter(
                name="service_name",
                description="Name of the service or component",
                parameter_type="string",
                required=True,
            ))

        # Environment
        if "environment" in goal or "deploy" in goal:
            parameters.append(TemplateParameter(
                name="environment",
                description="Target environment",
                parameter_type="string",
                default_value="staging",
                allowed_values=["development", "staging", "production"],
            ))

        # Feature name
        if "feature" in goal or "add" in goal or "implement" in goal:
            parameters.append(TemplateParameter(
                name="feature_name",
                description="Name of the feature",
                parameter_type="string",
                required=True,
            ))

        # Add generic parameters if none found
        if not parameters:
            parameters.append(TemplateParameter(
                name="target",
                description="Target of the workflow",
                parameter_type="string",
                required=True,
            ))

        return parameters

    def _create_task_template(
        self,
        workflow: Any,
        parameters: List[TemplateParameter]
    ) -> List[Dict[str, Any]]:
        """Create task template with parameter placeholders."""
        task_template = []

        for task in workflow.tasks:
            task_dict = task.to_dict()

            # Replace specific values with parameter placeholders
            task_dict = self._parameterize_dict(task_dict, parameters)

            task_template.append(task_dict)

        return task_template

    def _parameterize_dict(
        self,
        data: Dict[str, Any],
        parameters: List[TemplateParameter]
    ) -> Dict[str, Any]:
        """Replace values with parameter placeholders."""
        result = {}

        for key, value in data.items():
            if isinstance(value, str):
                # Replace with parameter placeholders
                for param in parameters:
                    placeholder = f"{{{{ {param.name} }}}}"
                    # Simple heuristic: if parameter name appears in value, parameterize
                    if param.name.replace("_", " ") in value.lower():
                        value = value  # Keep as is for now, real impl would be smarter
            elif isinstance(value, dict):
                value = self._parameterize_dict(value, parameters)
            elif isinstance(value, list):
                value = [
                    self._parameterize_dict(item, parameters) if isinstance(item, dict) else item
                    for item in value
                ]

            result[key] = value

        return result

    def _generate_goal_pattern(self, goal: str) -> str:
        """Generate regex pattern from goal."""
        # Extract key action and objects
        words = goal.lower().split()

        if not words:
            return ".*"

        # Create flexible pattern
        # Example: "Deploy service X" -> "deploy.*service"
        key_words = [w for w in words if len(w) > 3][:3]  # First 3 significant words

        if not key_words:
            return ".*"

        pattern = ".*".join(re.escape(w) for w in key_words)
        return pattern

    def _calculate_metadata(
        self,
        workflow: Any,
        telemetry: Optional[List[Any]]
    ) -> TemplateMetadata:
        """Calculate template metadata."""
        # Determine category based on task types
        task_types = [task.task_type.value for task in workflow.tasks]

        if "deploy" in task_types:
            category = "deployment"
        elif "test" in task_types and "code" in task_types:
            category = "development"
        elif "investigate" in task_types or "analyze" in task_types:
            category = "operations"
        else:
            category = "general"

        # Extract tags from goal
        tags = self._extract_tags(workflow.goal)

        # Calculate quality metrics from telemetry
        success_rate = 0.0
        avg_duration = 0.0

        if telemetry:
            success_count = sum(1 for t in telemetry if t.success)
            success_rate = success_count / len(telemetry) if telemetry else 0.0
            avg_duration = sum(t.total_duration for t in telemetry) / len(telemetry)

        quality_score = self._calculate_quality_score(success_rate, avg_duration)

        return TemplateMetadata(
            category=category,
            tags=tags,
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
            version="1.0.0",
            success_rate=success_rate,
            avg_duration=avg_duration,
            usage_count=0,
            quality_score=quality_score,
        )

    def _extract_tags(self, text: str) -> List[str]:
        """Extract tags from text."""
        tags = []

        text_lower = text.lower()

        # Technology tags
        tech_keywords = ["docker", "kubernetes", "api", "database", "service", "auth"]
        for keyword in tech_keywords:
            if keyword in text_lower:
                tags.append(keyword)

        # Action tags
        action_keywords = ["deploy", "test", "monitor", "fix", "optimize", "analyze"]
        for keyword in action_keywords:
            if keyword in text_lower:
                tags.append(keyword)

        return tags

    def _calculate_quality_score(
        self,
        success_rate: float,
        avg_duration: float
    ) -> float:
        """
        Calculate quality score for template.

        Score is 0-100 based on success rate and duration.
        """
        # Success rate is primary factor (70% weight)
        success_component = success_rate * 70

        # Duration factor (30% weight, favor faster workflows)
        # Normalize to reasonable range (0-60 minutes)
        duration_minutes = avg_duration / 60
        duration_normalized = max(0, min(1, 1 - (duration_minutes / 60)))
        duration_component = duration_normalized * 30

        return success_component + duration_component


class TemplateStore:
    """Stores and retrieves templates."""

    def __init__(self, storage_path: str):
        """
        Initialize template store.

        Args:
            storage_path: Path to template storage directory
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.templates_file = self.storage_path / "templates.json"
        self.templates: Dict[str, WorkflowTemplate] = {}

        self._load()

    def _load(self):
        """Load templates from storage."""
        if self.templates_file.exists():
            try:
                with open(self.templates_file, 'r') as f:
                    data = json.load(f)
                    for template_data in data:
                        template = WorkflowTemplate.from_dict(template_data)
                        self.templates[template.id] = template
                logger.info(f"Loaded {len(self.templates)} templates")
            except Exception as e:
                logger.error(f"Error loading templates: {e}")

    def _save(self):
        """Save templates to storage."""
        try:
            data = [template.to_dict() for template in self.templates.values()]
            with open(self.templates_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Saved {len(self.templates)} templates")
        except Exception as e:
            logger.error(f"Error saving templates: {e}")

    def add(self, template: WorkflowTemplate):
        """Add a template."""
        self.templates[template.id] = template
        self._save()
        logger.info(f"Added template {template.id}")

    def get(self, template_id: str) -> Optional[WorkflowTemplate]:
        """Get a template by ID."""
        return self.templates.get(template_id)

    def list_all(self) -> List[WorkflowTemplate]:
        """List all templates."""
        return list(self.templates.values())

    def search(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        min_quality: float = 0.0
    ) -> List[WorkflowTemplate]:
        """
        Search templates.

        Args:
            query: Search query for name/description
            category: Filter by category
            tags: Filter by tags
            min_quality: Minimum quality score

        Returns:
            List of matching templates
        """
        results = list(self.templates.values())

        # Filter by quality
        results = [t for t in results if t.metadata.quality_score >= min_quality]

        # Filter by category
        if category:
            results = [t for t in results if t.metadata.category == category]

        # Filter by tags
        if tags:
            results = [
                t for t in results
                if any(tag in t.metadata.tags for tag in tags)
            ]

        # Filter by query
        if query:
            query_lower = query.lower()
            results = [
                t for t in results
                if query_lower in t.name.lower() or query_lower in t.description.lower()
            ]

        # Sort by quality score
        results.sort(key=lambda t: t.metadata.quality_score, reverse=True)

        return results

    def update_usage(self, template_id: str, success: bool, duration: float):
        """
        Update template usage statistics.

        Args:
            template_id: Template ID
            success: Whether usage was successful
            duration: Duration in seconds
        """
        template = self.templates.get(template_id)
        if not template:
            return

        # Update usage count
        template.metadata.usage_count += 1

        # Update success rate (moving average)
        old_success_rate = template.metadata.success_rate
        old_count = template.metadata.usage_count - 1

        if old_count > 0:
            new_success_rate = (
                (old_success_rate * old_count + (1.0 if success else 0.0))
                / template.metadata.usage_count
            )
        else:
            new_success_rate = 1.0 if success else 0.0

        template.metadata.success_rate = new_success_rate

        # Update average duration (moving average)
        old_avg_duration = template.metadata.avg_duration

        if old_count > 0:
            new_avg_duration = (
                (old_avg_duration * old_count + duration)
                / template.metadata.usage_count
            )
        else:
            new_avg_duration = duration

        template.metadata.avg_duration = new_avg_duration

        # Recalculate quality score
        template.metadata.quality_score = TemplateExtractor()._calculate_quality_score(
            new_success_rate,
            new_avg_duration
        )

        # Update timestamp
        template.metadata.updated_at = datetime.utcnow().isoformat()

        self._save()
        logger.info(f"Updated template {template_id} usage statistics")


class TemplateRecommender:
    """Recommends templates based on goals."""

    def __init__(self, template_store: TemplateStore):
        """
        Initialize template recommender.

        Args:
            template_store: Template store instance
        """
        self.template_store = template_store

    def recommend(
        self,
        goal: str,
        max_recommendations: int = 5
    ) -> List[Tuple[WorkflowTemplate, float]]:
        """
        Recommend templates for a goal.

        Args:
            goal: Goal description
            max_recommendations: Maximum number of recommendations

        Returns:
            List of (template, similarity_score) tuples
        """
        all_templates = self.template_store.list_all()

        if not all_templates:
            return []

        # Calculate similarity scores
        scored_templates = []

        for template in all_templates:
            score = self._calculate_similarity(goal, template)
            scored_templates.append((template, score))

        # Sort by score
        scored_templates.sort(key=lambda x: x[1], reverse=True)

        # Return top N
        return scored_templates[:max_recommendations]

    def _calculate_similarity(
        self,
        goal: str,
        template: WorkflowTemplate
    ) -> float:
        """Calculate similarity between goal and template."""
        score = 0.0

        # Pattern match (40% weight)
        if re.search(template.goal_pattern, goal.lower()):
            score += 0.4

        # Keyword overlap (30% weight)
        goal_words = set(goal.lower().split())
        template_words = set(template.description.lower().split())
        if goal_words and template_words:
            overlap = len(goal_words & template_words) / len(goal_words)
            score += overlap * 0.3

        # Quality score (30% weight)
        score += (template.metadata.quality_score / 100) * 0.3

        return score


class TemplateManager:
    """Main template manager orchestrator."""

    def __init__(self, storage_path: str = "/tmp/workflow-templates"):
        """
        Initialize template manager.

        Args:
            storage_path: Path to template storage
        """
        self.extractor = TemplateExtractor()
        self.store = TemplateStore(storage_path)
        self.recommender = TemplateRecommender(self.store)

    def create_template(
        self,
        workflow: Any,
        telemetry: Optional[List[Any]] = None
    ) -> WorkflowTemplate:
        """
        Create a template from a workflow.

        Args:
            workflow: Workflow object
            telemetry: Optional telemetry data

        Returns:
            Created template
        """
        template = self.extractor.extract(workflow, telemetry)
        self.store.add(template)
        return template

    def get_template(self, template_id: str) -> Optional[WorkflowTemplate]:
        """Get a template by ID."""
        return self.store.get(template_id)

    def list_templates(
        self,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        min_quality: float = 0.0
    ) -> List[WorkflowTemplate]:
        """List templates with optional filters."""
        return self.store.search(
            category=category,
            tags=tags,
            min_quality=min_quality
        )

    def search_templates(self, query: str) -> List[WorkflowTemplate]:
        """Search templates by query."""
        return self.store.search(query=query)

    def recommend_templates(
        self,
        goal: str,
        max_recommendations: int = 5
    ) -> List[Tuple[WorkflowTemplate, float]]:
        """Recommend templates for a goal."""
        return self.recommender.recommend(goal, max_recommendations)

    def update_template_usage(
        self,
        template_id: str,
        success: bool,
        duration: float
    ):
        """Update template usage statistics."""
        self.store.update_usage(template_id, success, duration)


def main():
    """Test template manager."""
    logging.basicConfig(level=logging.INFO)

    manager = TemplateManager()
    print(f"Template manager initialized with {len(manager.store.list_all())} templates")


if __name__ == "__main__":
    main()
