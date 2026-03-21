"""
Workflow Automation Library - Intelligent workflow generation and execution.

This library provides comprehensive workflow automation capabilities including:
- Automatic workflow generation from natural language goals
- Workflow optimization based on telemetry
- Template-based workflow reuse
- Success prediction and risk assessment
- DAG-based workflow execution
"""

# Lazy imports to avoid circular dependencies
def __getattr__(name):
    if name == "WorkflowGenerator":
        from .workflow_generator import WorkflowGenerator
        return WorkflowGenerator
    elif name == "GoalParser":
        from .workflow_generator import GoalParser
        return GoalParser
    elif name == "TaskDecomposer":
        from .workflow_generator import TaskDecomposer
        return TaskDecomposer
    elif name == "Workflow":
        from .workflow_generator import Workflow
        return Workflow
    elif name == "Task":
        from .workflow_generator import Task
        return Task
    elif name == "TaskType":
        from .workflow_generator import TaskType
        return TaskType
    elif name == "AgentRole":
        from .workflow_generator import AgentRole
        return AgentRole
    elif name == "generate_workflow":
        from .workflow_generator import generate_workflow
        return generate_workflow
    elif name == "WorkflowOptimizer":
        from .workflow_optimizer import WorkflowOptimizer
        return WorkflowOptimizer
    elif name == "TelemetryAnalyzer":
        from .workflow_optimizer import TelemetryAnalyzer
        return TelemetryAnalyzer
    elif name == "BottleneckDetector":
        from .workflow_optimizer import BottleneckDetector
        return BottleneckDetector
    elif name == "OptimizationType":
        from .workflow_optimizer import OptimizationType
        return OptimizationType
    elif name == "OptimizationResult":
        from .workflow_optimizer import OptimizationResult
        return OptimizationResult
    elif name == "TemplateManager":
        from .template_manager import TemplateManager
        return TemplateManager
    elif name == "WorkflowTemplate":
        from .template_manager import WorkflowTemplate
        return WorkflowTemplate
    elif name == "TemplateParameter":
        from .template_manager import TemplateParameter
        return TemplateParameter
    elif name == "TemplateMetadata":
        from .template_manager import TemplateMetadata
        return TemplateMetadata
    elif name == "WorkflowAdapter":
        from .workflow_adapter import WorkflowAdapter
        return WorkflowAdapter
    elif name == "SimilarityDetector":
        from .workflow_adapter import SimilarityDetector
        return SimilarityDetector
    elif name == "ParameterBinder":
        from .workflow_adapter import ParameterBinder
        return ParameterBinder
    elif name == "AdaptationResult":
        from .workflow_adapter import AdaptationResult
        return AdaptationResult
    elif name == "SuccessPredictor":
        from .success_predictor import SuccessPredictor
        return SuccessPredictor
    elif name == "PredictionResult":
        from .success_predictor import PredictionResult
        return PredictionResult
    elif name == "WorkflowFeatures":
        from .success_predictor import WorkflowFeatures
        return WorkflowFeatures
    elif name == "RiskFactor":
        from .success_predictor import RiskFactor
        return RiskFactor
    elif name == "WorkflowExecutor":
        from .workflow_executor import WorkflowExecutor
        return WorkflowExecutor
    elif name == "WorkflowExecution":
        from .workflow_executor import WorkflowExecution
        return WorkflowExecution
    elif name == "TaskExecution":
        from .workflow_executor import TaskExecution
        return TaskExecution
    elif name == "ExecutionStatus":
        from .workflow_executor import ExecutionStatus
        return ExecutionStatus
    elif name == "WorkflowStore":
        from .workflow_store import WorkflowStore
        return WorkflowStore
    raise AttributeError(f"module 'workflows' has no attribute '{name}'")

__all__ = [
    # Generator
    "WorkflowGenerator",
    "GoalParser",
    "TaskDecomposer",
    "Workflow",
    "Task",
    "TaskType",
    "AgentRole",
    "generate_workflow",
    # Optimizer
    "WorkflowOptimizer",
    "TelemetryAnalyzer",
    "BottleneckDetector",
    "OptimizationType",
    "OptimizationResult",
    # Template Manager
    "TemplateManager",
    "WorkflowTemplate",
    "TemplateParameter",
    "TemplateMetadata",
    # Adapter
    "WorkflowAdapter",
    "SimilarityDetector",
    "ParameterBinder",
    "AdaptationResult",
    # Predictor
    "SuccessPredictor",
    "PredictionResult",
    "WorkflowFeatures",
    "RiskFactor",
    # Executor
    "WorkflowExecutor",
    "WorkflowExecution",
    "TaskExecution",
    "ExecutionStatus",
    # Store
    "WorkflowStore",
]

__version__ = "1.0.0"
