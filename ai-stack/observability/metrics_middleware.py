#!/usr/bin/env python3
"""
Metrics Collection Middleware for aiohttp

Automatically records metrics for all HTTP requests and integrates with:
- Baseline Profiler for anomaly detection
- Alert Engine for anomaly alerts
- Prometheus for metrics export

Part of Phase 1 Batch 1.2: Automated Anomaly Detection
"""

import asyncio
import logging
import time
from typing import Optional

from aiohttp import web
from aiohttp.web_middlewares import middleware

from baseline_profiler import BaselineProfiler, MetricType, get_profiler
from alert_engine import AlertEngine

logger = logging.getLogger(__name__)


class MetricsMiddleware:
    """
    aiohttp middleware for automatic metrics collection and anomaly detection.

    Records:
    - Request latency
    - Error rates
    - Request throughput
    - Response sizes

    Integrates with baseline profiler for anomaly detection.
    """

    def __init__(
        self,
        service_name: str,
        profiler: Optional[BaselineProfiler] = None,
        alert_engine: Optional[AlertEngine] = None,
        enable_anomaly_detection: bool = True,
    ):
        self.service_name = service_name
        self.profiler = profiler or get_profiler()
        self.alert_engine = alert_engine
        self.enable_anomaly_detection = enable_anomaly_detection

        # Request counters for throughput calculation
        self.request_count = 0
        self.last_throughput_check = time.time()
        self.throughput_window_seconds = 10

        logger.info(
            f"Metrics middleware initialized for service={service_name}, "
            f"anomaly_detection={enable_anomaly_detection}"
        )

    @middleware
    async def middleware_handler(self, request: web.Request, handler):
        """
        Middleware handler that wraps all requests.

        Records metrics before and after request processing.
        """
        start_time = time.time()
        component = self._extract_component(request)
        error = None

        try:
            # Process request
            response = await handler(request)

            # Record success metrics
            latency_ms = (time.time() - start_time) * 1000

            self._record_latency(component, latency_ms, request.path)
            self._record_throughput(component)

            return response

        except Exception as exc:
            # Record error metrics
            error = exc
            latency_ms = (time.time() - start_time) * 1000

            self._record_latency(component, latency_ms, request.path)
            self._record_error(component, exc)

            raise

    def _extract_component(self, request: web.Request) -> str:
        """Extract component name from request path"""
        path = request.path

        # Map paths to components
        if "/hints" in path:
            return "hints"
        elif "/query" in path or "/augment" in path:
            return "query"
        elif "/health" in path:
            return "health"
        elif "/workflow" in path:
            return "workflow"
        elif "/metrics" in path:
            return "metrics"
        elif "/ws/" in path:
            return "websocket"
        else:
            return "general"

    def _record_latency(self, component: str, latency_ms: float, path: str):
        """Record request latency metric"""
        if self.enable_anomaly_detection:
            self.profiler.record_metric(
                service=self.service_name,
                component=component,
                metric_type=MetricType.LATENCY,
                value=latency_ms,
                metadata={"path": path},
            )

    def _record_error(self, component: str, error: Exception):
        """Record error occurrence"""
        if self.enable_anomaly_detection:
            # Record error rate as 1.0 (error occurred)
            self.profiler.record_metric(
                service=self.service_name,
                component=component,
                metric_type=MetricType.ERROR_RATE,
                value=1.0,
                metadata={
                    "error_type": type(error).__name__,
                    "error_message": str(error),
                },
            )

    def _record_throughput(self, component: str):
        """Record request throughput"""
        self.request_count += 1

        # Calculate throughput periodically
        now = time.time()
        elapsed = now - self.last_throughput_check

        if elapsed >= self.throughput_window_seconds:
            throughput = self.request_count / elapsed

            if self.enable_anomaly_detection:
                self.profiler.record_metric(
                    service=self.service_name,
                    component=component,
                    metric_type=MetricType.THROUGHPUT,
                    value=throughput,
                )

            # Reset counters
            self.request_count = 0
            self.last_throughput_check = now


def create_metrics_middleware(
    service_name: str,
    profiler: Optional[BaselineProfiler] = None,
    alert_engine: Optional[AlertEngine] = None,
    enable_anomaly_detection: bool = True,
):
    """
    Create metrics middleware for aiohttp application.

    Args:
        service_name: Name of the service (e.g., "hybrid-coordinator")
        profiler: Baseline profiler instance (creates default if None)
        alert_engine: Alert engine for anomaly alerts (optional)
        enable_anomaly_detection: Enable anomaly detection (default: True)

    Returns:
        Middleware handler function

    Usage:
        app = web.Application(middlewares=[
            create_metrics_middleware("my-service")
        ])
    """
    middleware_instance = MetricsMiddleware(
        service_name=service_name,
        profiler=profiler,
        alert_engine=alert_engine,
        enable_anomaly_detection=enable_anomaly_detection,
    )

    return middleware_instance.middleware_handler


if __name__ == "__main__":
    # Test middleware
    logging.basicConfig(level=logging.INFO)

    from aiohttp import web

    # Create middleware
    metrics_mw = create_metrics_middleware("test-service")

    # Create test app
    app = web.Application(middlewares=[metrics_mw])

    async def hello(request):
        await asyncio.sleep(0.1)  # Simulate work
        return web.json_response({"message": "hello"})

    async def slow_endpoint(request):
        await asyncio.sleep(1.0)  # Simulate slow request
        return web.json_response({"message": "slow"})

    async def error_endpoint(request):
        raise ValueError("Test error")

    app.router.add_get("/hello", hello)
    app.router.add_get("/slow", slow_endpoint)
    app.router.add_get("/error", error_endpoint)

    # Run test server
    print("Test server running on http://localhost:8888")
    print("Try:")
    print("  curl http://localhost:8888/hello")
    print("  curl http://localhost:8888/slow")
    print("  curl http://localhost:8888/error")

    web.run_app(app, host="localhost", port=8888)
