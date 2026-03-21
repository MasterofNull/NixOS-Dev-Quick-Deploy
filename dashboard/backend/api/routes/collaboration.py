"""
Multi-Agent Collaboration API Routes.

This module provides FastAPI routes for multi-agent collaboration including
team formation, communication, planning, consensus, patterns, and metrics.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

# Import collaboration library
import sys
from pathlib import Path

# Add lib to path
lib_path = Path(__file__).parent.parent.parent.parent.parent / "lib"
sys.path.insert(0, str(lib_path))

from agents import (
    DynamicTeamFormation,
    AgentCommunicationProtocol,
    CollaborativePlanning,
    QualityConsensus,
    CollaborationPatterns,
    TeamPerformanceMetrics,
    AgentProfile,
    AgentCapability,
    AgentRole,
    TaskRequirements,
    MessageType,
    MessagePriority,
    PlanningMode,
    ConsensusThreshold,
    VoteType,
    TaskCharacteristic,
    CollaborationPatternType,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/collaboration", tags=["collaboration"])

# Initialize components
team_formation = DynamicTeamFormation()
communication = AgentCommunicationProtocol()
planning = CollaborativePlanning()
consensus = QualityConsensus()
patterns = CollaborationPatterns()
metrics = TeamPerformanceMetrics()


# Pydantic models for API
class RegisterAgentRequest(BaseModel):
    """Request to register agent."""
    agent_id: str
    name: str
    capabilities: Dict[str, float]  # capability -> score
    preferred_roles: List[str]
    max_concurrent_tasks: int = 5
    cost_per_task: float = 1.0


class FormTeamRequest(BaseModel):
    """Request to form team."""
    task_id: str
    description: str
    required_capabilities: List[str]
    complexity: int = Field(1, ge=1, le=5)
    urgency: int = Field(1, ge=1, le=5)
    min_team_size: int = 1
    max_team_size: int = 5


class FormTeamResponse(BaseModel):
    """Response from team formation."""
    team: Dict[str, Any]
    message: str


class SendMessageRequest(BaseModel):
    """Request to send message."""
    from_agent: str
    to_agent: Optional[str]  # None for broadcast
    team_id: str
    message_type: str
    content: Dict[str, Any]
    priority: str = "normal"
    requires_response: bool = False
    timeout: int = 300


class SendMessageResponse(BaseModel):
    """Response from send message."""
    message_id: str
    message: str


class ReceiveMessageResponse(BaseModel):
    """Response with received message."""
    message: Optional[Dict[str, Any]]


class UpdateContextRequest(BaseModel):
    """Request to update shared context."""
    team_id: str
    agent_id: str
    updates: Dict[str, Any]
    broadcast: bool = True


class UpdateContextResponse(BaseModel):
    """Response from context update."""
    conflicts: List[Dict[str, Any]]
    version: int
    message: str


class CreatePlanRequest(BaseModel):
    """Request to create collaborative plan."""
    task_id: str
    team_id: str
    mode: str = "parallel"


class CreatePlanResponse(BaseModel):
    """Response from plan creation."""
    plan_id: str
    message: str


class AddContributionRequest(BaseModel):
    """Request to add plan contribution."""
    plan_id: str
    agent_id: str
    content: str
    suggested_phases: Optional[List[Dict[str, Any]]] = None
    dependencies: Optional[List[str]] = None
    risks: Optional[List[str]] = None
    confidence: float = 0.5


class AddContributionResponse(BaseModel):
    """Response from adding contribution."""
    contribution_id: str
    message: str


class SynthesizePlanRequest(BaseModel):
    """Request to synthesize plan."""
    plan_id: str
    agent_capabilities: Optional[Dict[str, List[str]]] = None


class SynthesizePlanResponse(BaseModel):
    """Response from plan synthesis."""
    plan: Dict[str, Any]
    message: str


class CreateConsensusRequest(BaseModel):
    """Request to create consensus session."""
    artifact_id: str
    team_id: str
    threshold: str = "simple_majority"
    required_reviewers: int = 3
    timeout: int = 300


class CreateConsensusResponse(BaseModel):
    """Response from consensus creation."""
    session_id: str
    message: str


class SubmitReviewRequest(BaseModel):
    """Request to submit review."""
    session_id: str
    reviewer_id: str
    vote: str
    confidence: float = 0.5
    reasoning: str = ""
    issues: Optional[List[str]] = None
    suggestions: Optional[List[str]] = None


class SubmitReviewResponse(BaseModel):
    """Response from review submission."""
    review_id: str
    message: str


class EvaluateConsensusResponse(BaseModel):
    """Response from consensus evaluation."""
    result: Dict[str, Any]
    message: str


class ExecutePatternRequest(BaseModel):
    """Request to execute collaboration pattern."""
    pattern_type: str
    task_id: str
    team_id: str
    agents: List[str]
    task_data: Dict[str, Any]


class ExecutePatternResponse(BaseModel):
    """Response from pattern execution."""
    execution: Dict[str, Any]
    message: str


class RecordTaskRequest(BaseModel):
    """Request to record task completion."""
    task_type: str
    duration: int
    success: bool
    quality_score: float = 0.0
    # For individual tasks
    agent_id: Optional[str] = None
    # For team tasks
    team_id: Optional[str] = None
    team_size: Optional[int] = None
    coordination_pattern: Optional[str] = None
    communication_time: Optional[int] = None


class RecordTaskResponse(BaseModel):
    """Response from task recording."""
    message: str


# API Routes

@router.post("/agents/register", response_model=SendMessageResponse)
async def register_agent(request: RegisterAgentRequest):
    """Register an agent with the system."""
    try:
        # Convert capability strings to enum
        capabilities = {}
        for cap_str, score in request.capabilities.items():
            try:
                cap = AgentCapability(cap_str)
                capabilities[cap] = score
            except ValueError:
                logger.warning(f"Unknown capability: {cap_str}")

        # Convert role strings to enum
        roles = []
        for role_str in request.preferred_roles:
            try:
                role = AgentRole(role_str)
                roles.append(role)
            except ValueError:
                logger.warning(f"Unknown role: {role_str}")

        profile = AgentProfile(
            agent_id=request.agent_id,
            name=request.name,
            capabilities=capabilities,
            preferred_roles=roles,
            max_concurrent_tasks=request.max_concurrent_tasks,
            cost_per_task=request.cost_per_task,
        )

        team_formation.register_agent(profile)
        communication.register_agent(request.agent_id)

        return SendMessageResponse(
            message_id=request.agent_id,
            message=f"Agent {request.agent_id} registered successfully",
        )

    except Exception as e:
        logger.error(f"Failed to register agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/teams/form", response_model=FormTeamResponse)
async def form_team(request: FormTeamRequest):
    """Form optimal team for task."""
    try:
        # Convert capability strings to enum
        capabilities = []
        for cap_str in request.required_capabilities:
            try:
                cap = AgentCapability(cap_str)
                capabilities.append(cap)
            except ValueError:
                logger.warning(f"Unknown capability: {cap_str}")

        requirements = TaskRequirements(
            task_id=request.task_id,
            description=request.description,
            required_capabilities=capabilities,
            complexity=request.complexity,
            urgency=request.urgency,
            min_team_size=request.min_team_size,
            max_team_size=request.max_team_size,
        )

        team = await team_formation.form_team(requirements)

        return FormTeamResponse(
            team=team.to_dict(),
            message=f"Team formed with {len(team.members)} members",
        )

    except Exception as e:
        logger.error(f"Failed to form team: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/teams/{team_id}")
async def get_team(team_id: str):
    """Get team details."""
    # This would need team storage in a real implementation
    return {"team_id": team_id, "message": "Team details"}


@router.post("/messages/send", response_model=SendMessageResponse)
async def send_message(request: SendMessageRequest):
    """Send message between agents."""
    try:
        msg_type = MessageType(request.message_type)
        priority = MessagePriority[request.priority.upper()]

        message_id = await communication.send_message(
            from_agent=request.from_agent,
            to_agent=request.to_agent,
            team_id=request.team_id,
            message_type=msg_type,
            content=request.content,
            priority=priority,
            requires_response=request.requires_response,
            timeout=request.timeout,
        )

        return SendMessageResponse(
            message_id=message_id,
            message="Message sent successfully",
        )

    except Exception as e:
        logger.error(f"Failed to send message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/messages/receive/{agent_id}", response_model=ReceiveMessageResponse)
async def receive_message(agent_id: str, timeout: float = 1.0):
    """Receive next message for agent."""
    try:
        message = await communication.receive_message(agent_id, timeout)

        return ReceiveMessageResponse(
            message=message.to_dict() if message else None,
        )

    except Exception as e:
        logger.error(f"Failed to receive message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/messages/queue/{agent_id}")
async def get_queue_status(agent_id: str):
    """Get message queue status for agent."""
    try:
        status = communication.get_queue_status(agent_id)
        return status

    except Exception as e:
        logger.error(f"Failed to get queue status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/context/update", response_model=UpdateContextResponse)
async def update_context(request: UpdateContextRequest):
    """Update shared context."""
    try:
        conflicts = await communication.update_shared_context(
            team_id=request.team_id,
            agent_id=request.agent_id,
            updates=request.updates,
            broadcast=request.broadcast,
        )

        context = communication.get_shared_context(request.team_id)
        version = context.version if context else 0

        return UpdateContextResponse(
            conflicts=conflicts,
            version=version,
            message=f"Context updated to version {version}",
        )

    except Exception as e:
        logger.error(f"Failed to update context: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/context/{team_id}")
async def get_context(team_id: str):
    """Get shared context for team."""
    try:
        context = communication.get_shared_context(team_id)
        if not context:
            raise HTTPException(status_code=404, detail="Context not found")

        return context.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get context: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/plans/create", response_model=CreatePlanResponse)
async def create_plan(request: CreatePlanRequest):
    """Create collaborative plan."""
    try:
        mode = PlanningMode(request.mode)
        plan_id = planning.create_plan(request.task_id, request.team_id, mode)

        return CreatePlanResponse(
            plan_id=plan_id,
            message="Plan created successfully",
        )

    except Exception as e:
        logger.error(f"Failed to create plan: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/plans/contribute", response_model=AddContributionResponse)
async def add_contribution(request: AddContributionRequest):
    """Add contribution to plan."""
    try:
        contribution_id = planning.add_contribution(
            plan_id=request.plan_id,
            agent_id=request.agent_id,
            content=request.content,
            suggested_phases=request.suggested_phases,
            dependencies=request.dependencies,
            risks=request.risks,
            confidence=request.confidence,
        )

        return AddContributionResponse(
            contribution_id=contribution_id,
            message="Contribution added successfully",
        )

    except Exception as e:
        logger.error(f"Failed to add contribution: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/plans/synthesize", response_model=SynthesizePlanResponse)
async def synthesize_plan(request: SynthesizePlanRequest):
    """Synthesize plan from contributions."""
    try:
        plan = await planning.synthesize_plan(
            plan_id=request.plan_id,
            agent_capabilities=request.agent_capabilities,
        )

        return SynthesizePlanResponse(
            plan=plan.to_dict(),
            message="Plan synthesized successfully",
        )

    except Exception as e:
        logger.error(f"Failed to synthesize plan: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/plans/{plan_id}")
async def get_plan(plan_id: str):
    """Get plan details."""
    try:
        plan = planning.get_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")

        return plan.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get plan: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/consensus/create", response_model=CreateConsensusResponse)
async def create_consensus(request: CreateConsensusRequest):
    """Create consensus session."""
    try:
        threshold = ConsensusThreshold(request.threshold)

        session_id = consensus.create_session(
            artifact_id=request.artifact_id,
            team_id=request.team_id,
            threshold=threshold,
            required_reviewers=request.required_reviewers,
            timeout=request.timeout,
        )

        return CreateConsensusResponse(
            session_id=session_id,
            message="Consensus session created",
        )

    except Exception as e:
        logger.error(f"Failed to create consensus: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/consensus/review", response_model=SubmitReviewResponse)
async def submit_review(request: SubmitReviewRequest):
    """Submit review for consensus."""
    try:
        vote = VoteType(request.vote)

        review_id = consensus.submit_review(
            session_id=request.session_id,
            reviewer_id=request.reviewer_id,
            vote=vote,
            confidence=request.confidence,
            reasoning=request.reasoning,
            issues=request.issues,
            suggestions=request.suggestions,
        )

        return SubmitReviewResponse(
            review_id=review_id,
            message="Review submitted successfully",
        )

    except Exception as e:
        logger.error(f"Failed to submit review: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/consensus/evaluate/{session_id}", response_model=EvaluateConsensusResponse)
async def evaluate_consensus(session_id: str, expert_reviewers: Optional[List[str]] = None):
    """Evaluate consensus."""
    try:
        result = await consensus.evaluate_consensus(
            session_id=session_id,
            expert_reviewers=expert_reviewers,
        )

        return EvaluateConsensusResponse(
            result=result.to_dict(),
            message="Consensus evaluated",
        )

    except Exception as e:
        logger.error(f"Failed to evaluate consensus: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/consensus/{session_id}")
async def get_consensus_session(session_id: str):
    """Get consensus session details."""
    try:
        session = consensus.active_sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        return session.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get consensus session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/patterns/execute", response_model=ExecutePatternResponse)
async def execute_pattern(request: ExecutePatternRequest):
    """Execute collaboration pattern."""
    try:
        pattern_type = CollaborationPatternType(request.pattern_type)

        # Placeholder executor callback
        async def executor_callback(*args, **kwargs):
            await asyncio.sleep(0.1)
            return {"success": True, "result": "placeholder"}

        execution = await patterns.execute_pattern(
            pattern_type=pattern_type,
            task_id=request.task_id,
            team_id=request.team_id,
            agents=request.agents,
            task_data=request.task_data,
            executor_callback=executor_callback,
        )

        return ExecutePatternResponse(
            execution=execution.to_dict(),
            message=f"Pattern {pattern_type.value} executed",
        )

    except Exception as e:
        logger.error(f"Failed to execute pattern: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/patterns")
async def get_patterns():
    """Get available collaboration patterns."""
    try:
        pattern_metrics = patterns.get_pattern_metrics()
        return {
            "patterns": pattern_metrics,
            "total": len(pattern_metrics),
        }

    except Exception as e:
        logger.error(f"Failed to get patterns: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/metrics/record", response_model=RecordTaskResponse)
async def record_task(request: RecordTaskRequest):
    """Record task completion metrics."""
    try:
        if request.agent_id:
            # Individual task
            metrics.record_individual_task(
                agent_id=request.agent_id,
                task_type=request.task_type,
                duration=request.duration,
                success=request.success,
                quality_score=request.quality_score,
            )
            return RecordTaskResponse(message="Individual task recorded")

        elif request.team_id:
            # Team task
            if not request.team_size or not request.coordination_pattern:
                raise HTTPException(
                    status_code=400,
                    detail="team_size and coordination_pattern required for team tasks"
                )

            metrics.record_team_task(
                team_id=request.team_id,
                team_size=request.team_size,
                coordination_pattern=request.coordination_pattern,
                task_type=request.task_type,
                duration=request.duration,
                communication_time=request.communication_time or 0,
                success=request.success,
                quality_score=request.quality_score,
            )
            return RecordTaskResponse(message="Team task recorded")

        else:
            raise HTTPException(
                status_code=400,
                detail="Either agent_id or team_id must be provided"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to record task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/comparison")
async def get_performance_comparison(task_type: Optional[str] = None):
    """Get team vs individual performance comparison."""
    try:
        comparison = metrics.compare_performance(task_type)
        return comparison.to_dict()

    except Exception as e:
        logger.error(f"Failed to get comparison: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/composition")
async def get_composition_analysis():
    """Get team composition analysis."""
    try:
        analysis = metrics.analyze_team_composition()
        return analysis

    except Exception as e:
        logger.error(f"Failed to get composition analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/cost-benefit")
async def get_cost_benefit():
    """Get cost-benefit analysis."""
    try:
        analysis = metrics.calculate_cost_benefit()
        return analysis

    except Exception as e:
        logger.error(f"Failed to get cost-benefit: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/summary")
async def get_metrics_summary():
    """Get overall metrics summary."""
    try:
        summary = metrics.get_summary()

        # Add other system metrics
        summary["communication"] = communication.get_communication_metrics()
        summary["team_formation"] = team_formation.get_team_metrics()
        summary["planning"] = planning.get_planning_metrics()
        summary["consensus"] = consensus.get_consensus_metrics()
        summary["patterns"] = patterns.get_pattern_metrics()

        return summary

    except Exception as e:
        logger.error(f"Failed to get metrics summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))
