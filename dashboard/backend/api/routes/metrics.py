"""Metrics API endpoints"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import logging

from api.services.metrics_collector import MetricsCollector

router = APIRouter()
logger = logging.getLogger(__name__)
metrics_collector = MetricsCollector()


@router.get("/system")
async def get_system_metrics() -> Dict[str, Any]:
    """Get current system metrics (CPU, memory, disk, network)"""
    try:
        metrics = await metrics_collector.get_system_metrics()
        return metrics
    except Exception as e:
        logger.error(f"Error getting system metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{metric}")
async def get_metric_history(metric: str, limit: int = 100) -> Dict[str, Any]:
    """Get historical data for a specific metric"""
    try:
        history = await metrics_collector.get_metric_history(metric, limit)
        return {
            "metric": metric,
            "data": history
        }
    except Exception as e:
        logger.error(f"Error getting metric history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health-score")
async def get_health_score() -> Dict[str, Any]:
    """Calculate overall system health score"""
    try:
        score = await metrics_collector.calculate_health_score()
        return {
            "score": score,
            "status": "healthy" if score >= 80 else "warning" if score >= 60 else "critical"
        }
    except Exception as e:
        logger.error(f"Error calculating health score: {e}")
        raise HTTPException(status_code=500, detail=str(e))