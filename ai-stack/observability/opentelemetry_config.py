#!/usr/bin/env python3
"""
OpenTelemetry Configuration and Instrumentation

Provides unified metrics, traces, and logs for all AI stack services.
Part of Phase 1 Batch 1.1: Unified Metrics Pipeline

Features:
- Auto-instrumentation for FastAPI, HTTP clients, Redis, PostgreSQL
- Custom metrics for AI operations (token usage, latency, quality)
- Distributed tracing with context propagation
- Structured logging integration
- Prometheus metrics export
"""

import logging
import os
from contextlib import contextmanager
from typing import Dict, Optional

# Optional dependencies - gracefully handle missing packages
try:
    from opentelemetry import metrics, trace
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    logger.warning("OpenTelemetry not available - monitoring will be limited")

try:
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    OTLP_AVAILABLE = True
except ImportError:
    OTLP_AVAILABLE = False

try:
    from opentelemetry.exporter.prometheus import PrometheusMetricReader
    from prometheus_client import start_http_server
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

try:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor
    from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
    INSTRUMENTATION_AVAILABLE = True
except ImportError:
    INSTRUMENTATION_AVAILABLE = False

logger = logging.getLogger(__name__)


class OpenTelemetryConfig:
    """OpenTelemetry configuration for AI stack services"""

    def __init__(
        self,
        service_name: str,
        service_version: str = "1.0.0",
        environment: str = "production",
        otlp_endpoint: Optional[str] = None,
        prometheus_port: int = 9090,
        enable_console_export: bool = False,
    ):
        if not OTEL_AVAILABLE:
            logger.warning("OpenTelemetry not available - install opentelemetry-api")
            return

        self.service_name = service_name
        self.service_version = service_version
        self.environment = environment
        self.otlp_endpoint = otlp_endpoint or os.getenv(
            "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"
        )
        self.prometheus_port = prometheus_port
        self.enable_console_export = enable_console_export

        # Create resource
        self.resource = Resource.create(
            {
                "service.name": service_name,
                "service.version": service_version,
                "deployment.environment": environment,
                "service.namespace": "ai-stack",
            }
        )

        # Initialize providers
        self._setup_tracing()
        self._setup_metrics()

        logger.info(
            f"OpenTelemetry initialized for {service_name} "
            f"(env={environment}, otlp={self.otlp_endpoint})"
        )

    def _setup_tracing(self):
        """Setup distributed tracing"""
        # Create trace provider
        trace_provider = TracerProvider(resource=self.resource)

        # Add OTLP exporter
        otlp_exporter = OTLPSpanExporter(endpoint=self.otlp_endpoint)
        trace_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

        # Console exporter for debugging
        if self.enable_console_export:
            from opentelemetry.sdk.trace.export import ConsoleSpanExporter

            console_exporter = ConsoleSpanExporter()
            trace_provider.add_span_processor(BatchSpanProcessor(console_exporter))

        # Set global tracer provider
        trace.set_tracer_provider(trace_provider)

        logger.info("Distributed tracing initialized")

    def _setup_metrics(self):
        """Setup metrics collection"""
        # Create Prometheus reader
        prometheus_reader = PrometheusMetricReader()

        # Create meter provider
        meter_provider = MeterProvider(
            resource=self.resource,
            metric_readers=[prometheus_reader],
        )

        # Set global meter provider
        metrics.set_meter_provider(meter_provider)

        # Start Prometheus HTTP server
        try:
            start_http_server(port=self.prometheus_port, addr="0.0.0.0")
            logger.info(f"Prometheus metrics server started on port {self.prometheus_port}")
        except OSError as e:
            logger.warning(f"Prometheus server already running or port in use: {e}")

    def instrument_fastapi(self, app):
        """Auto-instrument FastAPI application"""
        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI instrumented")
        return app

    def instrument_all(self):
        """Auto-instrument common libraries"""
        # HTTP clients
        HTTPXClientInstrumentor().instrument()

        # Redis
        try:
            RedisInstrumentor().instrument()
            logger.info("Redis instrumented")
        except Exception as e:
            logger.warning(f"Redis instrumentation failed: {e}")

        # PostgreSQL
        try:
            Psycopg2Instrumentor().instrument()
            logger.info("PostgreSQL instrumented")
        except Exception as e:
            logger.warning(f"PostgreSQL instrumentation failed: {e}")

        logger.info("Common libraries instrumented")

    def get_tracer(self, name: str):
        """Get tracer for manual instrumentation"""
        return trace.get_tracer(name, self.service_version)

    def get_meter(self, name: str):
        """Get meter for custom metrics"""
        return metrics.get_meter(name, self.service_version)


class AIMetrics:
    """Custom metrics for AI operations"""

    def __init__(self, meter_name: str = "ai-stack"):
        self.meter = metrics.get_meter(meter_name)

        # Token usage metrics
        self.tokens_used = self.meter.create_counter(
            name="ai.tokens.used",
            description="Total tokens used",
            unit="tokens",
        )

        self.tokens_cached = self.meter.create_counter(
            name="ai.tokens.cached",
            description="Tokens served from cache",
            unit="tokens",
        )

        # Latency metrics
        self.request_latency = self.meter.create_histogram(
            name="ai.request.latency",
            description="AI request latency",
            unit="ms",
        )

        self.model_latency = self.meter.create_histogram(
            name="ai.model.latency",
            description="Model inference latency",
            unit="ms",
        )

        # Quality metrics
        self.quality_score = self.meter.create_histogram(
            name="ai.quality.score",
            description="AI response quality score",
            unit="score",
        )

        # Task metrics
        self.tasks_completed = self.meter.create_counter(
            name="ai.tasks.completed",
            description="Completed AI tasks",
            unit="tasks",
        )

        self.tasks_failed = self.meter.create_counter(
            name="ai.tasks.failed",
            description="Failed AI tasks",
            unit="tasks",
        )

        # Cost metrics
        self.api_cost = self.meter.create_counter(
            name="ai.api.cost",
            description="API call cost",
            unit="USD",
        )

        logger.info("AI metrics initialized")

    def record_token_usage(
        self,
        tokens: int,
        operation: str,
        model: str,
        cached: bool = False,
    ):
        """Record token usage"""
        attributes = {
            "operation": operation,
            "model": model,
        }

        if cached:
            self.tokens_cached.add(tokens, attributes)
        else:
            self.tokens_used.add(tokens, attributes)

    def record_latency(
        self,
        latency_ms: float,
        operation: str,
        model: Optional[str] = None,
    ):
        """Record operation latency"""
        attributes = {"operation": operation}
        if model:
            attributes["model"] = model

        self.request_latency.record(latency_ms, attributes)

    def record_quality_score(
        self,
        score: float,
        operation: str,
        model: str,
    ):
        """Record quality score (0.0-1.0)"""
        self.quality_score.record(
            score,
            {"operation": operation, "model": model},
        )

    def record_task_completion(
        self,
        success: bool,
        task_type: str,
        agent: str,
    ):
        """Record task completion or failure"""
        attributes = {
            "task_type": task_type,
            "agent": agent,
        }

        if success:
            self.tasks_completed.add(1, attributes)
        else:
            self.tasks_failed.add(1, attributes)

    def record_api_cost(
        self,
        cost_usd: float,
        provider: str,
        model: str,
    ):
        """Record API call cost"""
        self.api_cost.add(
            cost_usd,
            {"provider": provider, "model": model},
        )


@contextmanager
def trace_operation(
    operation_name: str,
    attributes: Optional[Dict] = None,
    tracer_name: str = "ai-stack",
):
    """
    Context manager for tracing operations.

    Usage:
        with trace_operation("query_hints", {"query": "example"}):
            # Your code here
            pass
    """
    tracer = trace.get_tracer(tracer_name)
    with tracer.start_as_current_span(operation_name) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, str(value))
        try:
            yield span
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            raise


# Global instances (initialized by services)
_ai_metrics: Optional[AIMetrics] = None


def get_ai_metrics() -> AIMetrics:
    """Get global AI metrics instance"""
    global _ai_metrics
    if _ai_metrics is None:
        _ai_metrics = AIMetrics()
    return _ai_metrics


def init_observability(
    service_name: str,
    service_version: str = "1.0.0",
    environment: str = "production",
    prometheus_port: int = 9090,
) -> OpenTelemetryConfig:
    """
    Initialize observability for a service.

    Args:
        service_name: Service identifier
        service_version: Service version
        environment: Deployment environment
        prometheus_port: Port for Prometheus metrics

    Returns:
        OpenTelemetryConfig instance
    """
    config = OpenTelemetryConfig(
        service_name=service_name,
        service_version=service_version,
        environment=environment,
        prometheus_port=prometheus_port,
    )

    # Auto-instrument common libraries
    config.instrument_all()

    # Initialize AI metrics
    global _ai_metrics
    _ai_metrics = AIMetrics()

    return config


if __name__ == "__main__":
    # Test observability setup
    logging.basicConfig(level=logging.INFO)

    # Initialize
    config = init_observability(
        service_name="test-service",
        prometheus_port=9091,
    )

    # Get metrics
    metrics_instance = get_ai_metrics()

    # Record some test data
    metrics_instance.record_token_usage(
        tokens=100,
        operation="test_query",
        model="qwen-4b",
        cached=False,
    )

    metrics_instance.record_latency(
        latency_ms=250.5,
        operation="test_query",
        model="qwen-4b",
    )

    metrics_instance.record_quality_score(
        score=0.85,
        operation="test_query",
        model="qwen-4b",
    )

    # Test tracing
    with trace_operation("test_operation", {"test_attr": "value"}):
        import time

        time.sleep(0.1)

    logger.info("Observability test complete")
    logger.info(f"Prometheus metrics available at http://localhost:9091/metrics")
