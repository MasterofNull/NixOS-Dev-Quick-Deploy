#!/usr/bin/env python3
"""
Monitoring Integration Helper

Integrates OpenTelemetry and AI metrics into existing services.
Part of Phase 1 Batch 1.1: Unified Metrics Pipeline

Usage:
    # In your service startup:
    from observability.integrate_monitoring import setup_service_monitoring

    app = setup_service_monitoring(
        app,
        service_name="hybrid-coordinator",
        prometheus_port=9103,
    )
"""

import logging
from typing import Optional

from opentelemetry_config import (
    OpenTelemetryConfig,
    AIMetrics,
    get_ai_metrics,
    init_observability,
)

logger = logging.getLogger(__name__)


def setup_service_monitoring(
    app,
    service_name: str,
    service_version: str = "1.0.0",
    prometheus_port: int = 9090,
    enable_auto_instrumentation: bool = True,
) -> any:
    """
    Setup comprehensive monitoring for a service.

    Args:
        app: FastAPI or aiohttp application
        service_name: Service identifier
        service_version: Service version
        prometheus_port: Port for Prometheus metrics
        enable_auto_instrumentation: Auto-instrument FastAPI/HTTP clients

    Returns:
        Instrumented application
    """
    logger.info(f"Setting up monitoring for {service_name}")

    # Initialize OpenTelemetry
    config = init_observability(
        service_name=service_name,
        service_version=service_version,
        prometheus_port=prometheus_port,
    )

    # Auto-instrument if FastAPI
    if enable_auto_instrumentation and hasattr(app, "routes"):
        try:
            config.instrument_fastapi(app)
        except Exception as e:
            logger.warning(f"FastAPI instrumentation failed: {e}")

    logger.info(f"Monitoring setup complete for {service_name}")
    logger.info(f"Prometheus metrics: http://localhost:{prometheus_port}/metrics")

    return app


def get_service_metrics() -> AIMetrics:
    """Get AI metrics instance for the current service"""
    return get_ai_metrics()


# Service-specific metric recording helpers

def record_hint_query(
    tokens: int,
    latency_ms: float,
    quality_score: float,
    model: str = "qwen-4b",
    cached: bool = False,
):
    """Record hint query metrics"""
    metrics = get_ai_metrics()

    metrics.record_token_usage(
        tokens=tokens,
        operation="hint_query",
        model=model,
        cached=cached,
    )

    metrics.record_latency(
        latency_ms=latency_ms,
        operation="hint_query",
        model=model,
    )

    if quality_score > 0:
        metrics.record_quality_score(
            score=quality_score,
            operation="hint_query",
            model=model,
        )


def record_delegation(
    tokens: int,
    latency_ms: float,
    success: bool,
    agent: str,
    model: str,
    cost_usd: float = 0.0,
):
    """Record delegation metrics"""
    metrics = get_ai_metrics()

    metrics.record_token_usage(
        tokens=tokens,
        operation="delegation",
        model=model,
        cached=False,
    )

    metrics.record_latency(
        latency_ms=latency_ms,
        operation="delegation",
        model=model,
    )

    metrics.record_task_completion(
        success=success,
        task_type="delegation",
        agent=agent,
    )

    if cost_usd > 0:
        # Extract provider from agent name
        provider = agent.split("-")[0] if "-" in agent else "unknown"
        metrics.record_api_cost(
            cost_usd=cost_usd,
            provider=provider,
            model=model,
        )


def record_workflow_execution(
    latency_ms: float,
    success: bool,
    workflow_type: str,
    agent: str = "local",
):
    """Record workflow execution metrics"""
    metrics = get_ai_metrics()

    metrics.record_latency(
        latency_ms=latency_ms,
        operation=f"workflow_{workflow_type}",
    )

    metrics.record_task_completion(
        success=success,
        task_type=workflow_type,
        agent=agent,
    )


def record_memory_operation(
    operation: str,
    latency_ms: float,
    success: bool,
):
    """Record memory store operation metrics"""
    metrics = get_ai_metrics()

    metrics.record_latency(
        latency_ms=latency_ms,
        operation=f"memory_{operation}",
    )

    metrics.record_task_completion(
        success=success,
        task_type=f"memory_{operation}",
        agent="local",
    )


if __name__ == "__main__":
    # Test monitoring integration
    logging.basicConfig(level=logging.INFO)

    # Simulate FastAPI app
    class MockApp:
        routes = []

    app = MockApp()

    # Setup monitoring
    app = setup_service_monitoring(
        app,
        service_name="test-service",
        prometheus_port=9091,
    )

    # Record some metrics
    record_hint_query(
        tokens=150,
        latency_ms=120.5,
        quality_score=0.89,
        model="qwen-4b",
        cached=False,
    )

    record_delegation(
        tokens=500,
        latency_ms=1500.0,
        success=True,
        agent="claude-sonnet",
        model="claude-sonnet-4",
        cost_usd=0.05,
    )

    logger.info("Monitoring integration test complete")
    logger.info("Check http://localhost:9091/metrics for Prometheus metrics")
