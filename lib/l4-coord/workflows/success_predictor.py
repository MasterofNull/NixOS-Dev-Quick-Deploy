#!/usr/bin/env python3
"""
Success Predictor - Predict workflow success probability.

This module provides ML-based workflow success prediction including feature
extraction, risk identification, and alternative suggestions.
"""

import logging
import pickle
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from pathlib import Path
import statistics

logger = logging.getLogger(__name__)


@dataclass
class WorkflowFeatures:
    """Extracted features from a workflow."""
    total_tasks: int
    max_dependencies: int
    avg_dependencies: float
    critical_path_length: int
    parallelism_ratio: float
    total_estimated_duration: int
    task_type_diversity: float
    has_retry_policies: bool
    has_validation: bool
    resource_intensity: float

    def to_vector(self) -> List[float]:
        """Convert features to vector for ML."""
        return [
            float(self.total_tasks),
            float(self.max_dependencies),
            float(self.avg_dependencies),
            float(self.critical_path_length),
            float(self.parallelism_ratio),
            float(self.total_estimated_duration),
            float(self.task_type_diversity),
            float(self.has_retry_policies),
            float(self.has_validation),
            float(self.resource_intensity),
        ]


@dataclass
class RiskFactor:
    """Represents a risk factor."""
    factor: str
    severity: float  # 0-1
    description: str
    mitigation: str


@dataclass
class PredictionResult:
    """Result of success prediction."""
    success_probability: float
    confidence: float
    risk_factors: List[RiskFactor]
    features: WorkflowFeatures
    recommendations: List[str]
    alternative_suggestions: List[Dict[str, Any]]


class FeatureExtractor:
    """Extracts features from workflows."""

    def __init__(self):
        """Initialize feature extractor."""
        pass

    def extract(self, workflow: Any) -> WorkflowFeatures:
        """
        Extract features from a workflow.

        Args:
            workflow: Workflow object

        Returns:
            Extracted features
        """
        # Task count
        total_tasks = len(workflow.tasks)

        # Dependency metrics
        dep_counts = [len(task.dependencies) for task in workflow.tasks]
        max_dependencies = max(dep_counts) if dep_counts else 0
        avg_dependencies = statistics.mean(dep_counts) if dep_counts else 0

        # Critical path length
        critical_path_length = self._calculate_critical_path_length(workflow)

        # Parallelism ratio
        parallelism_ratio = self._calculate_parallelism_ratio(workflow)

        # Duration
        total_estimated_duration = sum(
            task.estimated_duration for task in workflow.tasks
        )

        # Task type diversity
        task_types = set(task.task_type.value for task in workflow.tasks)
        task_type_diversity = len(task_types) / 14.0  # 14 total task types

        # Retry policies
        has_retry_policies = any(
            task.retry_policy is not None for task in workflow.tasks
        )

        # Validation
        has_validation = any(
            task.validation_criteria for task in workflow.tasks
        )

        # Resource intensity
        resource_intensity = self._calculate_resource_intensity(workflow)

        return WorkflowFeatures(
            total_tasks=total_tasks,
            max_dependencies=max_dependencies,
            avg_dependencies=avg_dependencies,
            critical_path_length=critical_path_length,
            parallelism_ratio=parallelism_ratio,
            total_estimated_duration=total_estimated_duration,
            task_type_diversity=task_type_diversity,
            has_retry_policies=has_retry_policies,
            has_validation=has_validation,
            resource_intensity=resource_intensity,
        )

    def _calculate_critical_path_length(self, workflow: Any) -> int:
        """Calculate critical path length through workflow."""
        graph = workflow.get_task_graph()

        # Calculate longest path
        longest_paths = {}

        def calculate_longest(task_id: str) -> int:
            if task_id in longest_paths:
                return longest_paths[task_id]

            deps = graph.get(task_id, [])
            if not deps:
                longest_paths[task_id] = 1
            else:
                longest_paths[task_id] = 1 + max(
                    calculate_longest(dep) for dep in deps
                )

            return longest_paths[task_id]

        for task_id in graph:
            calculate_longest(task_id)

        return max(longest_paths.values()) if longest_paths else 0

    def _calculate_parallelism_ratio(self, workflow: Any) -> float:
        """Calculate parallelism ratio (0-1)."""
        try:
            batches = workflow.get_execution_order()
            if not batches:
                return 0.0

            total_tasks = len(workflow.tasks)
            avg_parallel = statistics.mean(len(batch) for batch in batches)

            return avg_parallel / total_tasks if total_tasks else 0
        except:
            return 0.0

    def _calculate_resource_intensity(self, workflow: Any) -> float:
        """Calculate resource intensity (0-1)."""
        intensity_scores = []

        for task in workflow.tasks:
            resources = task.required_resources
            score = 0.0

            if resources.get("cpu") == "high":
                score += 0.5
            elif resources.get("cpu") == "medium":
                score += 0.25

            if resources.get("memory") == "high":
                score += 0.5
            elif resources.get("memory") == "medium":
                score += 0.25

            intensity_scores.append(score)

        return statistics.mean(intensity_scores) if intensity_scores else 0.0


class RiskIdentifier:
    """Identifies risk factors in workflows."""

    def __init__(self):
        """Initialize risk identifier."""
        pass

    def identify(
        self,
        workflow: Any,
        features: WorkflowFeatures
    ) -> List[RiskFactor]:
        """
        Identify risk factors in workflow.

        Args:
            workflow: Workflow object
            features: Extracted features

        Returns:
            List of risk factors
        """
        risks = []

        # Complexity risk
        if features.total_tasks > 20:
            severity = min(1.0, (features.total_tasks - 20) / 30)
            risks.append(RiskFactor(
                factor="high_complexity",
                severity=severity,
                description=f"Workflow has {features.total_tasks} tasks, which may be difficult to manage",
                mitigation="Consider breaking into smaller sub-workflows",
            ))

        # Dependency risk
        if features.max_dependencies > 5:
            severity = min(1.0, (features.max_dependencies - 5) / 10)
            risks.append(RiskFactor(
                factor="high_dependencies",
                severity=severity,
                description=f"Some tasks have {features.max_dependencies} dependencies",
                mitigation="Review dependency graph for potential simplification",
            ))

        # Long critical path risk
        if features.critical_path_length > 10:
            severity = min(1.0, (features.critical_path_length - 10) / 20)
            risks.append(RiskFactor(
                factor="long_critical_path",
                severity=severity,
                description=f"Critical path has {features.critical_path_length} tasks",
                mitigation="Look for opportunities to parallelize tasks",
            ))

        # Low parallelism risk
        if features.parallelism_ratio < 0.3:
            severity = 0.3 - features.parallelism_ratio
            risks.append(RiskFactor(
                factor="low_parallelism",
                severity=severity,
                description=f"Low parallelism ratio ({features.parallelism_ratio:.2f})",
                mitigation="Identify tasks that can run in parallel",
            ))

        # Long duration risk
        if features.total_estimated_duration > 120:  # 2 hours
            severity = min(1.0, (features.total_estimated_duration - 120) / 240)
            risks.append(RiskFactor(
                factor="long_duration",
                severity=severity,
                description=f"Estimated duration is {features.total_estimated_duration} minutes",
                mitigation="Consider optimizing slow tasks or running in parallel",
            ))

        # No retry policy risk
        if not features.has_retry_policies:
            risks.append(RiskFactor(
                factor="no_retry_policy",
                severity=0.4,
                description="No retry policies configured",
                mitigation="Add retry policies for critical tasks",
            ))

        # No validation risk
        if not features.has_validation:
            risks.append(RiskFactor(
                factor="no_validation",
                severity=0.3,
                description="No validation criteria defined",
                mitigation="Add validation criteria for task outputs",
            ))

        # High resource intensity risk
        if features.resource_intensity > 0.7:
            severity = features.resource_intensity - 0.7
            risks.append(RiskFactor(
                factor="high_resource_intensity",
                severity=severity,
                description=f"High resource intensity ({features.resource_intensity:.2f})",
                mitigation="Ensure adequate resources are available",
            ))

        # Sort by severity
        risks.sort(key=lambda r: r.severity, reverse=True)

        return risks


class SuccessModel:
    """Simple ML model for success prediction."""

    def __init__(self):
        """Initialize success model."""
        # Simple heuristic-based model
        # In a real implementation, this would be a trained ML model
        self.weights = {
            "total_tasks": -0.02,  # More tasks = slightly riskier
            "max_dependencies": -0.05,  # More deps = riskier
            "avg_dependencies": -0.03,
            "critical_path_length": -0.03,
            "parallelism_ratio": 0.3,  # More parallelism = better
            "total_estimated_duration": -0.001,
            "task_type_diversity": 0.1,  # Diversity is good
            "has_retry_policies": 0.15,  # Retry policies help
            "has_validation": 0.1,  # Validation helps
            "resource_intensity": -0.05,  # High intensity = risky
        }
        self.bias = 0.85  # Base success rate

    def predict(self, features: WorkflowFeatures) -> Tuple[float, float]:
        """
        Predict success probability.

        Args:
            features: Workflow features

        Returns:
            Tuple of (success_probability, confidence)
        """
        # Calculate weighted sum
        score = self.bias

        feature_vector = features.to_vector()
        feature_names = [
            "total_tasks", "max_dependencies", "avg_dependencies",
            "critical_path_length", "parallelism_ratio",
            "total_estimated_duration", "task_type_diversity",
            "has_retry_policies", "has_validation", "resource_intensity"
        ]

        for name, value in zip(feature_names, feature_vector):
            score += self.weights[name] * value

        # Sigmoid to get probability
        probability = 1 / (1 + pow(2.718281828, -score))

        # Confidence based on feature values
        # Higher complexity = lower confidence
        complexity = (
            features.total_tasks / 50 +
            features.max_dependencies / 20 +
            features.critical_path_length / 30
        )
        confidence = max(0.5, 1.0 - complexity)

        return probability, confidence

    def train(self, training_data: List[Tuple[WorkflowFeatures, bool]]):
        """
        Train the model (placeholder for real ML training).

        Args:
            training_data: List of (features, success) tuples
        """
        # In a real implementation, this would train a classifier
        # For now, we use fixed heuristic weights
        logger.info(f"Training with {len(training_data)} examples (heuristic model)")


class AlternativeSuggester:
    """Suggests alternative workflows."""

    def __init__(self):
        """Initialize alternative suggester."""
        pass

    def suggest(
        self,
        workflow: Any,
        risk_factors: List[RiskFactor]
    ) -> List[Dict[str, Any]]:
        """
        Suggest alternative workflow approaches.

        Args:
            workflow: Workflow object
            risk_factors: Identified risk factors

        Returns:
            List of alternative suggestions
        """
        suggestions = []

        # Check risk factors for suggestions
        for risk in risk_factors:
            if risk.factor == "high_complexity" and risk.severity > 0.5:
                suggestions.append({
                    "type": "simplify",
                    "description": "Simplify workflow by breaking into phases",
                    "expected_improvement": 0.15,
                    "implementation": "Split into 2-3 smaller workflows",
                })

            if risk.factor == "low_parallelism" and risk.severity > 0.3:
                suggestions.append({
                    "type": "parallelize",
                    "description": "Increase parallelism by removing unnecessary dependencies",
                    "expected_improvement": 0.2,
                    "implementation": "Review and remove transitive dependencies",
                })

            if risk.factor == "long_duration" and risk.severity > 0.5:
                suggestions.append({
                    "type": "optimize_duration",
                    "description": "Optimize slow tasks or increase resources",
                    "expected_improvement": 0.25,
                    "implementation": "Profile and optimize bottleneck tasks",
                })

        return suggestions


class SuccessPredictor:
    """Main success predictor orchestrator."""

    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize success predictor.

        Args:
            model_path: Optional path to trained model
        """
        self.feature_extractor = FeatureExtractor()
        self.risk_identifier = RiskIdentifier()
        self.model = SuccessModel()
        self.alternative_suggester = AlternativeSuggester()

        # Load trained model if available
        if model_path and Path(model_path).exists():
            self._load_model(model_path)

    def predict(self, workflow: Any) -> PredictionResult:
        """
        Predict workflow success probability.

        Args:
            workflow: Workflow object

        Returns:
            Prediction result
        """
        logger.info(f"Predicting success for workflow {workflow.id}")

        # Extract features
        features = self.feature_extractor.extract(workflow)

        # Identify risk factors
        risks = self.risk_identifier.identify(workflow, features)

        # Predict success
        success_prob, confidence = self.model.predict(features)

        # Generate recommendations
        recommendations = self._generate_recommendations(risks)

        # Suggest alternatives if low probability
        alternatives = []
        if success_prob < 0.7:
            alternatives = self.alternative_suggester.suggest(workflow, risks)

        result = PredictionResult(
            success_probability=success_prob,
            confidence=confidence,
            risk_factors=risks,
            features=features,
            recommendations=recommendations,
            alternative_suggestions=alternatives,
        )

        logger.info(
            f"Prediction complete: {success_prob:.1%} success probability, "
            f"{len(risks)} risk factors"
        )

        return result

    def train(self, training_data: List[Tuple[Any, bool]]):
        """
        Train the predictor on historical data.

        Args:
            training_data: List of (workflow, success) tuples
        """
        # Extract features from workflows
        feature_data = []

        for workflow, success in training_data:
            features = self.feature_extractor.extract(workflow)
            feature_data.append((features, success))

        # Train model
        self.model.train(feature_data)

        logger.info(f"Trained on {len(training_data)} workflows")

    def save_model(self, model_path: str):
        """Save trained model."""
        Path(model_path).parent.mkdir(parents=True, exist_ok=True)

        with open(model_path, 'wb') as f:
            pickle.dump(self.model, f)

        logger.info(f"Saved model to {model_path}")

    def _load_model(self, model_path: str):
        """Load trained model."""
        try:
            with open(model_path, 'rb') as f:
                self.model = pickle.load(f)
            logger.info(f"Loaded model from {model_path}")
        except Exception as e:
            logger.error(f"Error loading model: {e}")

    def _generate_recommendations(
        self,
        risks: List[RiskFactor]
    ) -> List[str]:
        """Generate recommendations from risk factors."""
        recommendations = []

        # Add top 3 risk mitigations as recommendations
        for risk in risks[:3]:
            recommendations.append(
                f"{risk.factor}: {risk.mitigation}"
            )

        return recommendations


def main():
    """Test success predictor."""
    logging.basicConfig(level=logging.INFO)

    predictor = SuccessPredictor()
    print("Success predictor initialized successfully")


if __name__ == "__main__":
    main()
