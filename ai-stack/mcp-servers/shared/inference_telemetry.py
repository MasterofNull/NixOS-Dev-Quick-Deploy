#!/usr/bin/env python3
"""
Local Inference SLOs & Telemetry for AI Stack Services

Implements Service Level Objectives (SLOs) for local inference, including
latency, success rate, and resource usage tracking with comprehensive telemetry.
"""

import asyncio
import json
import time
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
import logging
import statistics
import psutil
from collections import deque, defaultdict


logger = logging.getLogger(__name__)


class InferenceOutcome(Enum):
    """Possible outcomes of an inference request"""
    SUCCESS = "success"
    TIMEOUT = "timeout"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    MODEL_ERROR = "model_error"
    INVALID_INPUT = "invalid_input"
    CANCELLED = "cancelled"


class SLOType(Enum):
    """Types of SLOs"""
    LATENCY = "latency"
    SUCCESS_RATE = "success_rate"
    RESOURCE_USAGE = "resource_usage"
    THROUGHPUT = "throughput"


@dataclass
class InferenceRequest:
    """Details of an inference request"""
    request_id: str
    model_name: str
    input_tokens: int
    input_size_bytes: int
    timestamp: datetime
    timeout_seconds: float = 60.0
    priority: int = 1  # Higher number = higher priority


@dataclass
class InferenceResponse:
    """Details of an inference response"""
    request_id: str
    outcome: InferenceOutcome
    output_tokens: Optional[int] = None
    output_size_bytes: Optional[int] = None
    response_time_ms: Optional[float] = None
    timestamp: Optional[datetime] = None
    error_message: Optional[str] = None
    resource_usage: Optional[Dict[str, float]] = None  # CPU%, GPU%, Memory%


@dataclass
class SLOTarget:
    """Target for an SLO"""
    slo_type: SLOType
    target_value: float
    measurement_window_minutes: int = 60
    description: str = ""


@dataclass
class SLOViolation:
    """Record of an SLO violation"""
    slo_type: SLOType
    target_value: float
    observed_value: float
    timestamp: datetime
    severity: str  # "warning", "critical"
    description: str


@dataclass
class InferenceMetrics:
    """Aggregated metrics for inference performance"""
    model_name: str
    window_start: datetime
    window_end: datetime
    total_requests: int
    successful_requests: int
    failed_requests: int
    total_response_time_ms: float
    p50_response_time_ms: float
    p90_response_time_ms: float
    p95_response_time_ms: float
    p99_response_time_ms: float
    avg_tokens_per_second: float
    success_rate: float
    avg_cpu_usage: float
    avg_gpu_usage: float
    avg_memory_usage: float
    violations: List[SLOViolation]


class InferenceTelemetryCollector:
    """Collects telemetry for inference requests"""
    
    def __init__(self, max_buffer_size: int = 10000):
        self.request_buffer = deque(maxlen=max_buffer_size)
        self.response_buffer = deque(maxlen=max_buffer_size)
        self.metrics_history = deque(maxlen=100)  # Keep last 100 metric windows
        self.slo_targets: List[SLOTarget] = []
        self.violation_buffer = deque(maxlen=1000)
        self.resource_monitoring = True
        self._monitoring_task: Optional[asyncio.Task] = None
    
    def add_slo_target(self, target: SLOTarget):
        """Add an SLO target"""
        self.slo_targets.append(target)
    
    def record_request(self, request: InferenceRequest):
        """Record an incoming inference request"""
        self.request_buffer.append(request)
    
    def record_response(self, response: InferenceResponse):
        """Record an inference response"""
        self.response_buffer.append(response)
    
    async def collect_resource_usage(self) -> Dict[str, float]:
        """Collect current resource usage"""
        if not self.resource_monitoring:
            return {}
        
        usage = {
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory_percent": psutil.virtual_memory().percent,
            "memory_available_gb": psutil.virtual_memory().available / (1024**3),
            "disk_io_reads": psutil.disk_io_counters().read_count if psutil.disk_io_counters() else 0,
            "disk_io_writes": psutil.disk_io_counters().write_count if psutil.disk_io_counters() else 0,
            "network_io_sent": psutil.net_io_counters().bytes_sent if psutil.net_io_counters() else 0,
            "network_io_recv": psutil.net_io_counters().bytes_recv if psutil.net_io_counters() else 0,
        }
        
        # Try to get GPU usage if available
        try:
            import GPUtil
            gpus = GPUtil.getGPUs()
            if gpus:
                gpu = gpus[0]  # Use first GPU
                usage["gpu_percent"] = gpu.load * 100
                usage["gpu_memory_percent"] = gpu.memoryUtil * 100
                usage["gpu_temperature"] = gpu.temperature
        except ImportError:
            # GPUtil not available, skip GPU metrics
            pass
        except Exception:
            # Other GPU errors, skip GPU metrics
            pass
        
        return usage
    
    def calculate_metrics(self, model_name: str, window_minutes: int = 60) -> Optional[InferenceMetrics]:
        """Calculate metrics for a specific model and time window"""
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=window_minutes)
        
        # Filter requests and responses for the model and time window
        relevant_requests = [
            req for req in self.request_buffer
            if req.model_name == model_name and req.timestamp >= window_start
        ]
        
        relevant_responses = [
            resp for resp in self.response_buffer
            if resp.timestamp and resp.timestamp >= window_start
        ]
        
        if not relevant_requests:
            return None
        
        # Match requests with responses
        response_map = {resp.request_id: resp for resp in relevant_responses}
        
        successful_responses = []
        failed_responses = []
        
        for request in relevant_requests:
            response = response_map.get(request.request_id)
            if response:
                if response.outcome == InferenceOutcome.SUCCESS:
                    successful_responses.append(response)
                else:
                    failed_responses.append(response)
        
        # Calculate metrics
        total_requests = len(relevant_requests)
        successful_requests = len(successful_responses)
        failed_requests = len(failed_responses)
        
        success_rate = successful_requests / total_requests if total_requests > 0 else 0.0
        
        # Response time metrics
        response_times = [resp.response_time_ms for resp in successful_responses if resp.response_time_ms is not None]
        total_response_time_ms = sum(response_times) if response_times else 0.0
        
        if response_times:
            p50_response_time_ms = statistics.median(response_times)
            p90_response_time_ms = response_times[int(len(response_times) * 0.9)] if len(response_times) > 0 else 0.0
            p95_response_time_ms = response_times[int(len(response_times) * 0.95)] if len(response_times) > 0 else 0.0
            p99_response_time_ms = response_times[int(len(response_times) * 0.99)] if len(response_times) > 0 else 0.0
        else:
            p50_response_time_ms = p90_response_time_ms = p95_response_time_ms = p99_response_time_ms = 0.0
        
        # Throughput metrics
        avg_tokens_per_second = 0.0
        if successful_responses:
            total_output_tokens = sum(resp.output_tokens or 0 for resp in successful_responses)
            total_response_time_s = sum(resp.response_time_ms or 0 for resp in successful_responses) / 1000.0
            avg_tokens_per_second = total_output_tokens / total_response_time_s if total_response_time_s > 0 else 0.0
        
        # Resource usage metrics (average over successful responses)
        cpu_usages = [resp.resource_usage.get("cpu_percent", 0) for resp in successful_responses 
                      if resp.resource_usage and "cpu_percent" in resp.resource_usage]
        gpu_usages = [resp.resource_usage.get("gpu_percent", 0) for resp in successful_responses 
                      if resp.resource_usage and "gpu_percent" in resp.resource_usage]
        memory_usages = [resp.resource_usage.get("memory_percent", 0) for resp in successful_responses 
                         if resp.resource_usage and "memory_percent" in resp.resource_usage]
        
        avg_cpu_usage = statistics.mean(cpu_usages) if cpu_usages else 0.0
        avg_gpu_usage = statistics.mean(gpu_usages) if gpu_usages else 0.0
        avg_memory_usage = statistics.mean(memory_usages) if memory_usages else 0.0
        
        # Check for SLO violations
        violations = self._check_slo_violations(
            model_name, success_rate, p95_response_time_ms, avg_cpu_usage, avg_memory_usage
        )
        
        return InferenceMetrics(
            model_name=model_name,
            window_start=window_start,
            window_end=now,
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            total_response_time_ms=total_response_time_ms,
            p50_response_time_ms=p50_response_ms,
            p90_response_ms=p90_response_ms,
            p95_response_ms=p95_response_ms,
            p99_response_ms=p99_response_ms,
            avg_tokens_per_second=avg_tokens_per_second,
            success_rate=success_rate,
            avg_cpu_usage=avg_cpu_usage,
            avg_gpu_usage=avg_gpu_usage,
            avg_memory_usage=avg_memory_usage,
            violations=violations
        )
    
    def _check_slo_violations(self, model_name: str, success_rate: float, p95_response_ms: float, 
                              avg_cpu_usage: float, avg_memory_usage: float) -> List[SLOViolation]:
        """Check for SLO violations"""
        violations = []
        
        for target in self.slo_targets:
            violation = None
            
            if target.slo_type == SLOType.SUCCESS_RATE:
                if success_rate < target.target_value:
                    violation = SLOViolation(
                        slo_type=target.slo_type,
                        target_value=target.target_value,
                        observed_value=success_rate,
                        timestamp=datetime.now(timezone.utc),
                        severity="critical" if success_rate < target.target_value * 0.8 else "warning",
                        description=f"Success rate {success_rate:.2%} below target {target.target_value:.2%}"
                    )
            
            elif target.slo_type == SLOType.LATENCY:
                if p95_response_ms > target.target_value:
                    violation = SLOViolation(
                        slo_type=target.slo_type,
                        target_value=target.target_value,
                        observed_value=p95_response_ms,
                        timestamp=datetime.now(timezone.utc),
                        severity="critical" if p95_response_ms > target.target_value * 1.5 else "warning",
                        description=f"P95 latency {p95_response_ms:.2f}ms above target {target.target_value:.2f}ms"
                    )
            
            elif target.slo_type == SLOType.RESOURCE_USAGE:
                # Target value could represent max CPU or memory usage
                if avg_cpu_usage > target.target_value:
                    violation = SLOViolation(
                        slo_type=target.slo_type,
                        target_value=target.target_value,
                        observed_value=avg_cpu_usage,
                        timestamp=datetime.now(timezone.utc),
                        severity="warning",
                        description=f"Average CPU usage {avg_cpu_usage:.2f}% above target {target.target_value:.2f}%"
                    )
            
            if violation:
                violations.append(violation)
                self.violation_buffer.append(violation)
                logger.warning(f"SLO Violation: {violation.description}")
        
        return violations
    
    def get_recent_violations(self, count: int = 10) -> List[SLOViolation]:
        """Get recent SLO violations"""
        return list(self.violation_buffer)[-count:]
    
    def get_model_metrics_history(self, model_name: str, count: int = 10) -> List[InferenceMetrics]:
        """Get historical metrics for a model"""
        # This would normally come from the metrics history
        # For now, return empty list
        return []
    
    def start_resource_monitoring(self, interval_seconds: float = 5.0):
        """Start background resource monitoring"""
        if self._monitoring_task:
            self._monitoring_task.cancel()
        
        self._monitoring_task = asyncio.create_task(
            self._background_resource_monitoring(interval_seconds)
        )
    
    def stop_resource_monitoring(self):
        """Stop background resource monitoring"""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            self._monitoring_task = None
    
    async def _background_resource_monitoring(self, interval_seconds: float):
        """Background task to periodically collect resource usage"""
        while True:
            try:
                await asyncio.sleep(interval_seconds)
                # This would normally store resource usage for trending
                # For now, just collect to keep stats current
                await self.collect_resource_usage()
            except asyncio.CancelledError:
                logger.info("Resource monitoring stopped")
                break
            except Exception as e:
                logger.error(f"Error in resource monitoring: {e}")


class InferenceSLOMonitor:
    """Monitors SLOs for inference services"""
    
    def __init__(self, telemetry_collector: InferenceTelemetryCollector):
        self.collector = telemetry_collector
        self._monitoring_tasks: Dict[str, asyncio.Task] = {}
        self._reporting_callbacks: List[Callable] = []
    
    def add_reporting_callback(self, callback: Callable):
        """Add a callback to be called when metrics are calculated"""
        self._reporting_callbacks.append(callback)
    
    def start_monitoring(self, model_name: str, interval_seconds: int = 60):
        """Start monitoring SLOs for a specific model"""
        if model_name in self._monitoring_tasks:
            self._monitoring_tasks[model_name].cancel()
        
        task = asyncio.create_task(
            self._monitor_model_slos(model_name, interval_seconds)
        )
        self._monitoring_tasks[model_name] = task
        return task
    
    def stop_monitoring(self, model_name: str):
        """Stop monitoring SLOs for a specific model"""
        if model_name in self._monitoring_tasks:
            task = self._monitoring_tasks[model_name]
            task.cancel()
            del self._monitoring_tasks[model_name]
    
    async def _monitor_model_slos(self, model_name: str, interval_seconds: int):
        """Monitor SLOs for a specific model"""
        while True:
            try:
                # Calculate metrics for the model
                metrics = self.collector.calculate_metrics(model_name)
                if metrics:
                    # Call reporting callbacks
                    for callback in self._reporting_callbacks:
                        try:
                            await callback(metrics) if asyncio.iscoroutinefunction(callback) else callback(metrics)
                        except Exception as e:
                            logger.error(f"Error in reporting callback: {e}")
                
                await asyncio.sleep(interval_seconds)
                
            except asyncio.CancelledError:
                logger.info(f"SLO monitoring stopped for {model_name}")
                break
            except Exception as e:
                logger.error(f"Error monitoring SLOs for {model_name}: {e}")
                await asyncio.sleep(interval_seconds)
    
    async def get_slo_report(self, model_name: str) -> Dict[str, Any]:
        """Generate a comprehensive SLO report for a model"""
        metrics = self.collector.calculate_metrics(model_name)
        
        if not metrics:
            return {
                "error": f"No metrics available for model {model_name}",
                "model_name": model_name,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        # Calculate SLO compliance
        slo_compliance = {}
        for target in self.collector.slo_targets:
            if target.slo_type == SLOType.SUCCESS_RATE:
                compliant = metrics.success_rate >= target.target_value
                slo_compliance[target.slo_type.value] = {
                    "target": target.target_value,
                    "actual": metrics.success_rate,
                    "compliant": compliant
                }
            elif target.slo_type == SLOType.LATENCY:
                compliant = metrics.p95_response_time_ms <= target.target_value
                slo_compliance[target.slo_type.value] = {
                    "target_ms": target.target_value,
                    "actual_ms": metrics.p95_response_time_ms,
                    "compliant": compliant
                }
            elif target.slo_type == SLOType.RESOURCE_USAGE:
                compliant = metrics.avg_cpu_usage <= target.target_value
                slo_compliance[target.slo_type.value] = {
                    "target_percent": target.target_value,
                    "actual_percent": metrics.avg_cpu_usage,
                    "compliant": compliant
                }
        
        return {
            "model_name": model_name,
            "report_period": {
                "start": metrics.window_start.isoformat(),
                "end": metrics.window_end.isoformat()
            },
            "slo_compliance": slo_compliance,
            "performance_metrics": {
                "total_requests": metrics.total_requests,
                "successful_requests": metrics.successful_requests,
                "failed_requests": metrics.failed_requests,
                "success_rate": metrics.success_rate,
                "latency_percentiles_ms": {
                    "p50": metrics.p50_response_time_ms,
                    "p90": metrics.p90_response_time_ms,
                    "p95": metrics.p95_response_time_ms,
                    "p99": metrics.p99_response_time_ms
                },
                "throughput": {
                    "avg_tokens_per_second": metrics.avg_tokens_per_second
                },
                "resource_usage": {
                    "avg_cpu_percent": metrics.avg_cpu_usage,
                    "avg_gpu_percent": metrics.avg_gpu_usage,
                    "avg_memory_percent": metrics.avg_memory_usage
                }
            },
            "violations": [
                {
                    "type": v.slo_type.value,
                    "severity": v.severity,
                    "description": v.description,
                    "timestamp": v.timestamp.isoformat()
                }
                for v in metrics.violations
            ],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    async def get_all_models_slo_report(self) -> Dict[str, Any]:
        """Get SLO reports for all models"""
        # Get unique model names from recent requests
        model_names = set(req.model_name for req in list(self.collector.request_buffer)[-100:])
        
        reports = {}
        for model_name in model_names:
            reports[model_name] = await self.get_slo_report(model_name)
        
        return {
            "reports": reports,
            "summary": {
                "models_monitored": len(reports),
                "total_violations": sum(len(rep.get("violations", [])) for rep in reports.values()),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }


class LocalInferenceTelemetry:
    """Main class for local inference telemetry and SLOs"""
    
    def __init__(self):
        self.collector = InferenceTelemetryCollector()
        self.monitor = InferenceSLOMonitor(self.collector)
        self._setup_default_slos()
    
    def _setup_default_slos(self):
        """Setup default SLO targets"""
        # 99% success rate
        self.collector.add_slo_target(SLOTarget(
            slo_type=SLOType.SUCCESS_RATE,
            target_value=0.99,
            measurement_window_minutes=60,
            description="99% of inference requests should succeed"
        ))
        
        # P95 latency under 5 seconds
        self.collector.add_slo_target(SLOTarget(
            slo_type=SLOType.LATENCY,
            target_value=5000.0,  # 5 seconds in ms
            measurement_window_minutes=60,
            description="95% of inference requests should complete within 5 seconds"
        ))
        
        # CPU usage under 80%
        self.collector.add_slo_target(SLOTarget(
            slo_type=SLOType.RESOURCE_USAGE,
            target_value=80.0,  # 80% CPU
            measurement_window_minutes=60,
            description="Average CPU usage should stay below 80%"
        ))
    
    def record_inference_request(self, request: InferenceRequest):
        """Record an inference request"""
        self.collector.record_request(request)
    
    async def record_inference_response(self, response: InferenceResponse):
        """Record an inference response"""
        # Add resource usage if not already included
        if not response.resource_usage:
            response.resource_usage = await self.collector.collect_resource_usage()
        
        if not response.timestamp:
            response.timestamp = datetime.now(timezone.utc)
        
        self.collector.record_response(response)
    
    def start_monitoring_model(self, model_name: str, interval_seconds: int = 60):
        """Start monitoring SLOs for a model"""
        return self.monitor.start_monitoring(model_name, interval_seconds)
    
    def stop_monitoring_model(self, model_name: str):
        """Stop monitoring SLOs for a model"""
        self.monitor.stop_monitoring(model_name)
    
    async def get_model_slo_report(self, model_name: str) -> Dict[str, Any]:
        """Get SLO report for a specific model"""
        return await self.monitor.get_slo_report(model_name)
    
    async def get_all_models_slo_report(self) -> Dict[str, Any]:
        """Get SLO reports for all models"""
        return await self.monitor.get_all_models_slo_report()
    
    def get_recent_violations(self, count: int = 10) -> List[SLOViolation]:
        """Get recent SLO violations"""
        return self.collector.get_recent_violations(count)
    
    def start_resource_monitoring(self, interval_seconds: float = 5.0):
        """Start background resource monitoring"""
        self.collector.start_resource_monitoring(interval_seconds)
    
    def stop_resource_monitoring(self):
        """Stop background resource monitoring"""
        self.collector.stop_resource_monitoring()


# Example usage
async def example_usage():
    """Example of how to use the local inference SLOs and telemetry"""
    
    # Create the telemetry system
    telemetry = LocalInferenceTelemetry()
    
    # Start resource monitoring
    telemetry.start_resource_monitoring(interval_seconds=2.0)
    
    # Simulate some inference requests
    for i in range(20):
        request = InferenceRequest(
            request_id=f"req_{i}",
            model_name="qwen2.5-coder-7b",
            input_tokens=256,
            input_size_bytes=1024,
            timestamp=datetime.now(timezone.utc)
        )
        telemetry.record_inference_request(request)
        
        # Simulate response after some delay
        await asyncio.sleep(0.1)
        
        # Randomly simulate different outcomes
        import random
        if random.random() < 0.95:  # 95% success rate
            response = InferenceResponse(
                request_id=f"req_{i}",
                outcome=InferenceOutcome.SUCCESS,
                output_tokens=random.randint(100, 300),
                response_time_ms=random.uniform(1000, 4000),  # 1-4 seconds
                resource_usage=await telemetry.collector.collect_resource_usage()
            )
        else:
            response = InferenceResponse(
                request_id=f"req_{i}",
                outcome=InferenceOutcome.TIMEOUT,
                response_time_ms=60000,  # 60 seconds (timeout)
                error_message="Request timed out"
            )
        
        await telemetry.record_inference_response(response)
    
    # Start monitoring for the model
    telemetry.start_monitoring_model("qwen2.5-coder-7b", interval_seconds=10)
    
    # Wait a bit for metrics to accumulate
    await asyncio.sleep(2)
    
    # Get SLO report
    report = await telemetry.get_model_slo_report("qwen2.5-coder-7b")
    print("SLO Report for qwen2.5-coder-7b:")
    print(json.dumps(report, indent=2, default=str))
    
    # Get recent violations
    violations = telemetry.get_recent_violations()
    print(f"\nRecent SLO Violations ({len(violations)}):")
    for violation in violations:
        print(f"  - {violation.description} [{violation.severity}]")
    
    # Stop monitoring
    telemetry.stop_monitoring_model("qwen2.5-coder-7b")
    telemetry.stop_resource_monitoring()


if __name__ == "__main__":
    asyncio.run(example_usage())