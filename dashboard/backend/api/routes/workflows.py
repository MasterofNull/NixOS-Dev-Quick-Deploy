"""
Workflow Automation API Routes.

This module provides FastAPI routes for workflow automation including
generation, optimization, templates, adaptation, prediction, and execution.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

# Import workflow automation library
import sys
from pathlib import Path

# Add lib to path
lib_path = Path(__file__).parent.parent.parent.parent.parent / "lib"
sys.path.insert(0, str(lib_path))

from workflows import (
    WorkflowGenerator,
    WorkflowOptimizer,
    TemplateManager,
    WorkflowAdapter,
    SuccessPredictor,
    WorkflowExecutor,
    WorkflowStore,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workflows", tags=["workflows"])

# Initialize components
workflow_generator = WorkflowGenerator()
workflow_optimizer = WorkflowOptimizer()
template_manager = TemplateManager()
workflow_adapter = WorkflowAdapter()
success_predictor = SuccessPredictor()
workflow_executor = WorkflowExecutor()
workflow_store = WorkflowStore()


# Pydantic models for API
class GenerateWorkflowRequest(BaseModel):
    """Request to generate workflow."""
    goal: str = Field(..., description="Natural language goal")
    name: Optional[str] = Field(None, description="Optional workflow name")


class GenerateWorkflowResponse(BaseModel):
    """Response from workflow generation."""
    workflow: Dict[str, Any]
    message: str


class OptimizeWorkflowRequest(BaseModel):
    """Request to optimize workflow."""
    workflow_id: str = Field(..., description="Workflow ID to optimize")


class OptimizeWorkflowResponse(BaseModel):
    """Response from workflow optimization."""
    optimization_result: Dict[str, Any]
    message: str


class TemplateListResponse(BaseModel):
    """Response with template list."""
    templates: List[Dict[str, Any]]
    total: int


class TemplateDetailResponse(BaseModel):
    """Response with template details."""
    template: Dict[str, Any]


class AdaptWorkflowRequest(BaseModel):
    """Request to adapt workflow."""
    template_id: Optional[str] = Field(None, description="Template ID to use")
    workflow_id: Optional[str] = Field(None, description="Workflow ID to adapt")
    goal: str = Field(..., description="New goal")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Parameter values")
    customizations: Optional[Dict[str, Any]] = Field(None, description="Customizations")


class AdaptWorkflowResponse(BaseModel):
    """Response from workflow adaptation."""
    adapted_workflow: Dict[str, Any]
    adaptation_result: Dict[str, Any]
    message: str


class PredictSuccessRequest(BaseModel):
    """Request to predict workflow success."""
    workflow_id: str = Field(..., description="Workflow ID")


class PredictSuccessResponse(BaseModel):
    """Response from success prediction."""
    prediction: Dict[str, Any]
    message: str


class ExecuteWorkflowRequest(BaseModel):
    """Request to execute workflow."""
    workflow_id: str = Field(..., description="Workflow ID")


class ExecuteWorkflowResponse(BaseModel):
    """Response from workflow execution."""
    execution_id: str
    status: str
    message: str


class ExecutionStatusResponse(BaseModel):
    """Response with execution status."""
    execution: Dict[str, Any]


class WorkflowHistoryResponse(BaseModel):
    """Response with workflow history."""
    executions: List[Dict[str, Any]]
    total: int


# Routes

@router.post("/generate", response_model=GenerateWorkflowResponse)
async def generate_workflow(request: GenerateWorkflowRequest):
    """
    Generate a workflow from a natural language goal.

    This endpoint uses AI to parse the goal, decompose it into tasks,
    and generate a complete executable workflow.
    """
    try:
        logger.info(f"Generating workflow for goal: {request.goal}")

        # Generate workflow
        workflow = workflow_generator.generate(request.goal, request.name)

        # Save workflow
        workflow_store.save_workflow(workflow)

        return GenerateWorkflowResponse(
            workflow=workflow.to_dict(),
            message=f"Generated workflow with {len(workflow.tasks)} tasks"
        )

    except Exception as e:
        logger.error(f"Error generating workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/optimize", response_model=OptimizeWorkflowResponse)
async def optimize_workflow(request: OptimizeWorkflowRequest):
    """
    Optimize a workflow based on execution telemetry.

    This endpoint analyzes workflow execution history to identify
    bottlenecks and suggest optimizations.
    """
    try:
        logger.info(f"Optimizing workflow {request.workflow_id}")

        # Load workflow
        workflow_data = workflow_store.get_workflow(request.workflow_id)
        if not workflow_data:
            raise HTTPException(status_code=404, detail="Workflow not found")

        # Reconstruct workflow object (simplified)
        from workflows.workflow_generator import Workflow
        workflow = Workflow.from_dict(workflow_data) if hasattr(Workflow, 'from_dict') else None

        if not workflow:
            # Create minimal workflow for optimization
            workflow = type('Workflow', (), workflow_data)()

        # Get execution history
        executions = workflow_store.get_workflow_history(request.workflow_id)

        if not executions:
            raise HTTPException(
                status_code=400,
                detail="No execution history available for optimization"
            )

        # Convert to telemetry objects (simplified)
        from workflows.workflow_optimizer import WorkflowTelemetry, TaskTelemetry

        telemetry = []
        for exec_data in executions:
            task_telemetry = []
            for task_id, task_exec in exec_data.get("task_executions", {}).items():
                task_telemetry.append(TaskTelemetry(
                    task_id=task_exec["task_id"],
                    workflow_id=exec_data["workflow_id"],
                    execution_id=task_exec["execution_id"],
                    start_time=task_exec.get("start_time", ""),
                    end_time=task_exec.get("end_time", ""),
                    duration=task_exec.get("duration", 0),
                    status=task_exec.get("status", "unknown"),
                    agent_id=task_exec.get("agent_id", ""),
                ))

            telemetry.append(WorkflowTelemetry(
                workflow_id=exec_data["workflow_id"],
                execution_id=exec_data["execution_id"],
                start_time=exec_data.get("start_time", ""),
                end_time=exec_data.get("end_time", ""),
                total_duration=exec_data.get("total_duration", 0),
                task_telemetry=task_telemetry,
                success=exec_data.get("status") == "success",
            ))

        # Optimize
        result = workflow_optimizer.optimize(workflow, telemetry)

        return OptimizeWorkflowResponse(
            optimization_result={
                "workflow_id": result.workflow_id,
                "analyzed_executions": result.analyzed_executions,
                "bottlenecks": [
                    {
                        "task_id": b.task_id,
                        "severity": b.severity,
                        "description": b.description,
                        "suggestions": b.suggestions,
                    }
                    for b in result.bottlenecks
                ],
                "suggestions": [
                    {
                        "type": s.optimization_type.value,
                        "description": s.description,
                        "confidence": s.confidence,
                        "expected_improvement": s.expected_improvement,
                    }
                    for s in result.suggestions
                ],
                "current_metrics": result.current_metrics,
                "projected_metrics": result.projected_metrics,
                "summary": result.optimization_summary,
            },
            message=f"Analyzed {result.analyzed_executions} executions, "
                   f"found {len(result.bottlenecks)} bottlenecks"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error optimizing workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/templates", response_model=TemplateListResponse)
async def list_templates(
    category: Optional[str] = Query(None, description="Filter by category"),
    min_quality: float = Query(0.0, description="Minimum quality score"),
    limit: int = Query(50, description="Maximum results"),
):
    """
    List available workflow templates.

    Templates are created from successful workflows and can be
    reused for similar tasks.
    """
    try:
        templates = template_manager.list_templates(
            category=category,
            min_quality=min_quality
        )

        # Limit results
        templates = templates[:limit]

        return TemplateListResponse(
            templates=[t.to_dict() for t in templates],
            total=len(templates)
        )

    except Exception as e:
        logger.error(f"Error listing templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/templates/{template_id}", response_model=TemplateDetailResponse)
async def get_template(template_id: str):
    """Get template details by ID."""
    try:
        template = template_manager.get_template(template_id)

        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        return TemplateDetailResponse(
            template=template.to_dict()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/adapt", response_model=AdaptWorkflowResponse)
async def adapt_workflow(request: AdaptWorkflowRequest):
    """
    Adapt an existing workflow or template for a new goal.

    This endpoint allows reusing successful workflows by adapting
    them to similar but different goals.
    """
    try:
        logger.info(f"Adapting workflow for goal: {request.goal}")

        if request.template_id:
            # Adapt from template
            template = template_manager.get_template(request.template_id)
            if not template:
                raise HTTPException(status_code=404, detail="Template not found")

            result = workflow_adapter.adapt_from_template(
                template,
                request.goal,
                request.parameters,
                request.customizations
            )

        elif request.workflow_id:
            # Adapt from workflow
            workflow_data = workflow_store.get_workflow(request.workflow_id)
            if not workflow_data:
                raise HTTPException(status_code=404, detail="Workflow not found")

            # Reconstruct workflow (simplified)
            from workflows.workflow_generator import Workflow
            workflow = Workflow.from_dict(workflow_data) if hasattr(Workflow, 'from_dict') else None

            if not workflow:
                raise HTTPException(status_code=400, detail="Cannot adapt workflow")

            result = workflow_adapter.adapt_from_workflow(
                workflow,
                request.goal,
                request.customizations
            )

        else:
            raise HTTPException(
                status_code=400,
                detail="Either template_id or workflow_id must be provided"
            )

        # Save adapted workflow
        workflow_store.save_workflow(result.adapted_workflow)

        return AdaptWorkflowResponse(
            adapted_workflow=result.adapted_workflow.to_dict(),
            adaptation_result={
                "template_id": result.template_id,
                "similarity_score": result.similarity_score,
                "adaptations_applied": result.adaptations_applied,
                "parameter_bindings": result.parameter_bindings,
                "validation_status": result.validation_status,
                "confidence": result.confidence,
            },
            message=f"Adapted workflow with {len(result.adaptations_applied)} adaptations"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adapting workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/predict", response_model=PredictSuccessResponse)
async def predict_success(request: PredictSuccessRequest):
    """
    Predict success probability for a workflow.

    This endpoint analyzes workflow characteristics to predict
    likelihood of success and identify risk factors.
    """
    try:
        logger.info(f"Predicting success for workflow {request.workflow_id}")

        # Load workflow
        workflow_data = workflow_store.get_workflow(request.workflow_id)
        if not workflow_data:
            raise HTTPException(status_code=404, detail="Workflow not found")

        # Reconstruct workflow
        from workflows.workflow_generator import Workflow
        workflow = Workflow.from_dict(workflow_data) if hasattr(Workflow, 'from_dict') else None

        if not workflow:
            raise HTTPException(status_code=400, detail="Cannot predict for workflow")

        # Predict
        prediction = success_predictor.predict(workflow)

        return PredictSuccessResponse(
            prediction={
                "success_probability": prediction.success_probability,
                "confidence": prediction.confidence,
                "risk_factors": [
                    {
                        "factor": r.factor,
                        "severity": r.severity,
                        "description": r.description,
                        "mitigation": r.mitigation,
                    }
                    for r in prediction.risk_factors
                ],
                "features": {
                    "total_tasks": prediction.features.total_tasks,
                    "critical_path_length": prediction.features.critical_path_length,
                    "parallelism_ratio": prediction.features.parallelism_ratio,
                    "estimated_duration": prediction.features.total_estimated_duration,
                },
                "recommendations": prediction.recommendations,
                "alternatives": prediction.alternative_suggestions,
            },
            message=f"Predicted {prediction.success_probability:.1%} success probability"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error predicting success: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute", response_model=ExecuteWorkflowResponse)
async def execute_workflow(request: ExecuteWorkflowRequest):
    """
    Execute a workflow asynchronously.

    This endpoint starts workflow execution and returns immediately.
    Use GET /executions/{execution_id} to check status.
    """
    try:
        logger.info(f"Executing workflow {request.workflow_id}")

        # Load workflow
        workflow_data = workflow_store.get_workflow(request.workflow_id)
        if not workflow_data:
            raise HTTPException(status_code=404, detail="Workflow not found")

        # Reconstruct workflow
        from workflows.workflow_generator import Workflow, Task, TaskType, AgentRole

        tasks = []
        for task_data in workflow_data["tasks"]:
            task = Task(
                id=task_data["id"],
                name=task_data["name"],
                description=task_data["description"],
                task_type=TaskType(task_data["task_type"]),
                agent_role=AgentRole(task_data["agent_role"]),
                dependencies=task_data.get("dependencies", []),
                estimated_duration=task_data.get("estimated_duration", 20),
            )
            tasks.append(task)

        workflow = Workflow(
            id=workflow_data["id"],
            name=workflow_data["name"],
            description=workflow_data["description"],
            goal=workflow_data["goal"],
            tasks=tasks,
            created_at=workflow_data["created_at"],
            metadata=workflow_data.get("metadata", {}),
        )

        # Start execution asynchronously
        async def run_workflow():
            execution = await workflow_executor.execute(workflow)
            workflow_store.save_execution(execution)
            workflow_store.save_telemetry(workflow_executor.get_telemetry())

        # Run in background
        asyncio.create_task(run_workflow())

        # Generate execution ID
        execution_id = workflow_executor._generate_execution_id(workflow.id)

        return ExecuteWorkflowResponse(
            execution_id=execution_id,
            status="running",
            message=f"Started execution of workflow {request.workflow_id}"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/executions/{execution_id}", response_model=ExecutionStatusResponse)
async def get_execution_status(execution_id: str):
    """Get workflow execution status."""
    try:
        execution = workflow_executor.get_execution(execution_id)

        if not execution:
            # Try to load from store
            execution = workflow_store.get_execution(execution_id)

        if not execution:
            raise HTTPException(status_code=404, detail="Execution not found")

        return ExecutionStatusResponse(
            execution=execution if isinstance(execution, dict) else execution.to_dict()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting execution status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history", response_model=WorkflowHistoryResponse)
async def get_workflow_history(
    workflow_id: Optional[str] = Query(None, description="Filter by workflow ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, description="Maximum results"),
    offset: int = Query(0, description="Offset for pagination"),
):
    """Get workflow execution history."""
    try:
        executions = workflow_store.list_executions(
            workflow_id=workflow_id,
            status=status,
            limit=limit,
            offset=offset
        )

        return WorkflowHistoryResponse(
            executions=executions,
            total=len(executions)
        )

    except Exception as e:
        logger.error(f"Error getting workflow history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics")
async def get_statistics():
    """Get workflow automation statistics."""
    try:
        stats = workflow_store.get_statistics()
        return stats

    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))
