"""
AI Insights API Routes
Provides analytics and insights from the AI stack's operational data.
"""

from fastapi import APIRouter, HTTPException
import logging

from api.services.ai_insights import get_insights_service

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Full Report Endpoint
# ============================================================================

@router.get("/report/full")
async def get_full_insights_report():
    """Get the complete aq-report data."""
    try:
        service = get_insights_service()
        report = await service.get_full_report()
        return report
    except Exception as e:
        logger.error(f"Failed to get full insights report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Tool Performance Endpoints
# ============================================================================

@router.get("/tools/performance")
async def get_tool_performance():
    """Get tool performance summary and analytics."""
    try:
        service = get_insights_service()
        performance = await service.get_tool_performance_summary()
        return performance
    except Exception as e:
        logger.error(f"Failed to get tool performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/ai-specific")
async def get_ai_specific_metrics():
    """Get AI-specific operations metrics from the hybrid Prometheus surface."""
    try:
        service = get_insights_service()
        metrics = await service.get_ai_specific_metrics_summary()
        return metrics
    except Exception as e:
        logger.error(f"Failed to get AI-specific metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# LLM Routing and Model Performance Endpoints
# ============================================================================

@router.get("/routing/analytics")
async def get_routing_analytics():
    """Get LLM routing analytics and model performance comparison."""
    try:
        service = get_insights_service()
        analytics = await service.get_routing_analytics()
        return analytics
    except Exception as e:
        logger.error(f"Failed to get routing analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Hint Effectiveness Endpoints
# ============================================================================

@router.get("/hints/effectiveness")
async def get_hint_effectiveness():
    """Get hint adoption and effectiveness metrics."""
    try:
        service = get_insights_service()
        effectiveness = await service.get_hint_effectiveness()
        return effectiveness
    except Exception as e:
        logger.error(f"Failed to get hint effectiveness: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Workflow Compliance Endpoints
# ============================================================================

@router.get("/workflows/compliance")
async def get_workflow_compliance():
    """Get agentic workflow success and compliance metrics."""
    try:
        service = get_insights_service()
        compliance = await service.get_workflow_compliance()
        return compliance
    except Exception as e:
        logger.error(f"Failed to get workflow compliance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workflows/phase-4-acceptance")
async def get_phase_4_acceptance():
    """Get the latest consolidated Phase 4 workflow acceptance report."""
    try:
        service = get_insights_service()
        acceptance = await service.get_phase4_acceptance_summary()
        return acceptance
    except Exception as e:
        logger.error(f"Failed to get Phase 4 acceptance summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workflows/a2a-readiness")
async def get_a2a_readiness():
    """Get A2A compatibility readiness for the hybrid coordinator."""
    try:
        service = get_insights_service()
        readiness = await service.get_a2a_readiness()
        return readiness
    except Exception as e:
        logger.error(f"Failed to get A2A readiness: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/roadmap/readiness")
async def get_roadmap_readiness():
    """Get consolidated readiness for the active next-gen roadmap phases."""
    try:
        service = get_insights_service()
        readiness = await service.get_roadmap_readiness()
        return readiness
    except Exception as e:
        logger.error(f"Failed to get roadmap readiness: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/improvements/candidates")
async def get_improvement_candidates():
    """Get the persisted Phase 3 improvement-candidate summary."""
    try:
        service = get_insights_service()
        candidates = await service.get_improvement_candidates()
        return candidates
    except Exception as e:
        logger.error(f"Failed to get improvement candidates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/improvements/reviews")
async def get_code_review_summary():
    """Get the persisted Phase 3 LLM code-review summary."""
    try:
        service = get_insights_service()
        review = await service.get_code_review_summary()
        return review
    except Exception as e:
        logger.error(f"Failed to get code review summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/testing/readiness")
async def get_testing_validation_readiness():
    """Get the repo-native Phase 3.2 testing and validation readiness summary."""
    try:
        service = get_insights_service()
        readiness = await service.get_testing_validation_readiness()
        return readiness
    except Exception as e:
        logger.error(f"Failed to get testing validation readiness: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/deployments/readiness")
async def get_deployment_pipeline_readiness():
    """Get the repo-native Phase 3.3 autonomous deployment readiness summary."""
    try:
        service = get_insights_service()
        readiness = await service.get_deployment_pipeline_readiness()
        return readiness
    except Exception as e:
        logger.error(f"Failed to get deployment pipeline readiness: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/patterns/readiness")
async def get_agentic_pattern_library_readiness():
    """Get the repo-native Phase 4.1 agentic pattern library readiness summary."""
    try:
        service = get_insights_service()
        readiness = await service.get_agentic_pattern_library_readiness()
        return readiness
    except Exception as e:
        logger.error(f"Failed to get agentic pattern library readiness: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/experiments/readiness")
async def get_experimentation_readiness():
    """Get the repo-native experimentation and A/B readiness summary."""
    try:
        service = get_insights_service()
        readiness = await service.get_experimentation_readiness()
        return readiness
    except Exception as e:
        logger.error(f"Failed to get experimentation readiness: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance/profiling")
async def get_performance_profiling_readiness():
    """Get the repo-native continuous profiling readiness summary."""
    try:
        service = get_insights_service()
        readiness = await service.get_performance_profiling_readiness()
        return readiness
    except Exception as e:
        logger.error(f"Failed to get performance profiling readiness: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/security/compliance")
async def get_security_compliance():
    """Get dashboard/operator security compliance posture summary."""
    try:
        service = get_insights_service()
        compliance = await service.get_security_compliance_summary()
        return compliance
    except Exception as e:
        logger.error(f"Failed to get security compliance summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Query Complexity Analysis Endpoints
# ============================================================================

@router.get("/queries/complexity")
async def get_query_complexity():
    """Get query complexity and gap analysis."""
    try:
        service = get_insights_service()
        complexity = await service.get_query_complexity_analysis()
        return complexity
    except Exception as e:
        logger.error(f"Failed to get query complexity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance/hotspots")
async def get_performance_hotspots():
    """Get the current highest-signal performance hotspots for Phase 5 work."""
    try:
        service = get_insights_service()
        hotspots = await service.get_performance_hotspots()
        return hotspots
    except Exception as e:
        logger.error(f"Failed to get performance hotspots: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Cache Analytics Endpoints
# ============================================================================

@router.get("/cache/analytics")
async def get_cache_analytics():
    """Get cache performance analytics."""
    try:
        service = get_insights_service()
        analytics = await service.get_cache_analytics()
        return analytics
    except Exception as e:
        logger.error(f"Failed to get cache analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# System Health Overview Endpoints
# ============================================================================

@router.get("/system/health")
async def get_system_health():
    """Get high-level system health overview with recommendations."""
    try:
        service = get_insights_service()
        health = await service.get_system_health_overview()
        return health
    except Exception as e:
        logger.error(f"Failed to get system health: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Agent Lessons and Learning Endpoints
# ============================================================================

@router.get("/agents/lessons")
async def get_agent_lessons():
    """Get agent lessons and continuous learning metrics."""
    try:
        service = get_insights_service()
        lessons = await service.get_agent_lessons()
        return lessons
    except Exception as e:
        logger.error(f"Failed to get agent lessons: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Structured Actions Endpoints
# ============================================================================

@router.get("/actions/recommendations")
async def get_structured_actions():
    """Get structured actionable recommendations."""
    try:
        service = get_insights_service()
        actions = await service.get_structured_actions()
        return {"actions": actions, "count": len(actions)}
    except Exception as e:
        logger.error(f"Failed to get structured actions: {e}")
        raise HTTPException(status_code=500, detail=str(e))
