#!/usr/bin/env python3
"""
Model Performance Monitoring for AI Stack Services

Implements comprehensive model performance tracking, drift detection,
and telemetry for local inference services.
"""

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field
import logging
import statistics
from collections import deque

import asyncpg
from qdrant_client import QdrantClient
from redis import asyncio as redis_asyncio


logger = logging.getLogger(__name__)


class ModelQualityMetric(Enum):
    """Types of model quality metrics"""
    ACCURACY = "accuracy"
    PRECISION = "precision"
    RECALL = "recall"
    F1_SCORE = "f1_score"
    BLEU_SCORE = "bleu_score"
    ROUGE_SCORE = "rouge_score"
    PERPLEXITY = "perplexity"
    LATENCY_MS = "latency_ms"
    THROUGHPUT_QPS = "throughput_qps"
    ERROR_RATE = "error_rate"
    TOKEN_PER_SECOND = "tokens_per_second"


class DriftType(Enum):
    """Types of model drift"""
    CONCEPT_DRIFT = "concept_drift"
    DATA_DRIFT = "data_drift"
    PERFORMANCE_DRIFT = "performance_drift"


@dataclass
class ModelPerformanceRecord:
    """Record of model performance at a point in time"""
    model_name: str
    model_version: str
    timestamp: datetime
    metrics: Dict[ModelQualityMetric, float]
    input_distribution: Optional[Dict[str, Any]] = None
    output_distribution: Optional[Dict[str, Any]] = None
    context: Optional[Dict[str, Any]] = None
    hardware_info: Optional[Dict[str, Any]] = None


@dataclass
class ModelDriftAlert:
    """Alert for model drift detection"""
    model_name: str
    drift_type: DriftType
    severity: str  # "low", "medium", "high", "critical"
    timestamp: datetime
    description: str
    threshold_value: float
    observed_value: float
    recommendation: str


@dataclass
class ModelTelemetry:
    """Real-time telemetry for model inference"""
    model_name: str
    request_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    input_size_bytes: Optional[int] = None
    output_size_bytes: Optional[int] = None
    error_occurred: bool = False
    error_message: Optional[str] = None
    hardware_usage: Optional[Dict[str, float]] = None  # CPU%, GPU%, Memory%
    response_time_ms: Optional[float] = None


class ModelPerformanceStorage:
    """Storage backend for model performance data"""
    
    def __init__(self, db_pool: Optional[asyncpg.Pool] = None, redis_client: Optional[redis_asyncio.Redis] = None):
        self.db_pool = db_pool
        self.redis = redis_client
        self.performance_buffer = deque(maxlen=1000)  # In-memory buffer for recent records
    
    async def save_performance_record(self, record: ModelPerformanceRecord):
        """Save model performance record"""
        # Add to in-memory buffer
        self.performance_buffer.append(record)
        
        if self.redis:
            # Store in Redis for quick access
            key = f"model_perf:{record.model_name}:{record.model_version}"
            await self.redis.lpush(
                key,
                json.dumps({
                    "timestamp": record.timestamp.isoformat(),
                    "metrics": {k.value: v for k, v in record.metrics.items()},
                    "input_distribution": record.input_distribution,
                    "output_distribution": record.output_distribution,
                    "context": record.context,
                    "hardware_info": record.hardware_info
                })
            )
            # Keep only recent records
            await self.redis.ltrim(key, 0, 99)  # Keep last 100 records
        
        if self.db_pool:
            # Store in database for long-term retention
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO model_performance 
                    (model_name, model_version, timestamp, metrics, input_distribution, output_distribution, context, hardware_info)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    record.model_name,
                    record.model_version,
                    record.timestamp,
                    json.dumps({k.value: v for k, v in record.metrics.items()}),
                    json.dumps(record.input_distribution) if record.input_distribution else None,
                    json.dumps(record.output_distribution) if record.output_distribution else None,
                    json.dumps(record.context) if record.context else None,
                    json.dumps(record.hardware_info) if record.hardware_info else None
                )
    
    async def save_telemetry(self, telemetry: ModelTelemetry):
        """Save model telemetry"""
        if self.redis:
            # Store in Redis for real-time monitoring
            key = f"model_telemetry:{telemetry.model_name}"
            await self.redis.lpush(
                key,
                json.dumps({
                    "request_id": telemetry.request_id,
                    "start_time": telemetry.start_time.isoformat(),
                    "end_time": telemetry.end_time.isoformat() if telemetry.end_time else None,
                    "input_tokens": telemetry.input_tokens,
                    "output_tokens": telemetry.output_tokens,
                    "input_size_bytes": telemetry.input_size_bytes,
                    "output_size_bytes": telemetry.output_size_bytes,
                    "error_occurred": telemetry.error_occurred,
                    "error_message": telemetry.error_message,
                    "hardware_usage": telemetry.hardware_usage,
                    "response_time_ms": telemetry.response_time_ms
                })
            )
            # Keep only recent records
            await self.redis.ltrim(key, 0, 999)  # Keep last 1000 records
        
        if self.db_pool:
            # Store in database for long-term analysis
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO model_telemetry 
                    (model_name, request_id, start_time, end_time, input_tokens, output_tokens, 
                     input_size_bytes, output_size_bytes, error_occurred, error_message, 
                     hardware_usage, response_time_ms)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                    """,
                    telemetry.model_name,
                    telemetry.request_id,
                    telemetry.start_time,
                    telemetry.end_time,
                    telemetry.input_tokens,
                    telemetry.output_tokens,
                    telemetry.input_size_bytes,
                    telemetry.output_size_bytes,
                    telemetry.error_occurred,
                    telemetry.error_message,
                    json.dumps(telemetry.hardware_usage) if telemetry.hardware_usage else None,
                    telemetry.response_time_ms
                )
    
    async def get_recent_performance(self, model_name: str, hours: int = 24) -> List[ModelPerformanceRecord]:
        """Get recent performance records for a model"""
        records = []
        
        # Check in-memory buffer first
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        for record in self.performance_buffer:
            if record.model_name == model_name and record.timestamp >= cutoff_time:
                records.append(record)
        
        if self.db_pool:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT model_version, timestamp, metrics, input_distribution, output_distribution, context, hardware_info
                    FROM model_performance
                    WHERE model_name = $1 AND timestamp >= $2
                    ORDER BY timestamp DESC
                    LIMIT 100
                    """,
                    model_name,
                    cutoff_time
                )
                for row in rows:
                    metrics = {ModelQualityMetric(k): v for k, v in json.loads(row["metrics"]).items()}
                    records.append(ModelPerformanceRecord(
                        model_name=model_name,
                        model_version=row["model_version"],
                        timestamp=row["timestamp"],
                        metrics=metrics,
                        input_distribution=json.loads(row["input_distribution"]) if row["input_distribution"] else None,
                        output_distribution=json.loads(row["output_distribution"]) if row["output_distribution"] else None,
                        context=json.loads(row["context"]) if row["context"] else None,
                        hardware_info=json.loads(row["hardware_info"]) if row["hardware_info"] else None
                    ))
        
        return sorted(records, key=lambda r: r.timestamp, reverse=True)
    
    async def get_model_telemetry(self, model_name: str, hours: int = 1) -> List[ModelTelemetry]:
        """Get recent telemetry for a model"""
        telemetries = []
        
        if self.db_pool:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT request_id, start_time, end_time, input_tokens, output_tokens,
                           input_size_bytes, output_size_bytes, error_occurred, error_message,
                           hardware_usage, response_time_ms
                    FROM model_telemetry
                    WHERE model_name = $1 AND start_time >= $2
                    ORDER BY start_time DESC
                    LIMIT 1000
                    """,
                    model_name,
                    datetime.now(timezone.utc) - timedelta(hours=hours)
                )
                for row in rows:
                    telemetries.append(ModelTelemetry(
                        model_name=model_name,
                        request_id=row["request_id"],
                        start_time=row["start_time"],
                        end_time=row["end_time"],
                        input_tokens=row["input_tokens"],
                        output_tokens=row["output_tokens"],
                        input_size_bytes=row["input_size_bytes"],
                        output_size_bytes=row["output_size_bytes"],
                        error_occurred=row["error_occurred"],
                        error_message=row["error_message"],
                        hardware_usage=json.loads(row["hardware_usage"]) if row["hardware_usage"] else None,
                        response_time_ms=row["response_time_ms"]
                    ))
        
        return telemetries


class ModelDriftDetector:
    """Detects various types of model drift"""
    
    def __init__(self, storage: ModelPerformanceStorage):
        self.storage = storage
        self.drift_thresholds = {
            DriftType.CONCEPT_DRIFT: 0.05,  # 5% change in accuracy
            DriftType.DATA_DRIFT: 0.10,     # 10% change in input distribution
            DriftType.PERFORMANCE_DRIFT: 0.20  # 20% change in performance
        }
        self.alert_buffer = deque(maxlen=100)
    
    async def detect_drift(self, model_name: str) -> List[ModelDriftAlert]:
        """Detect drift for a model"""
        alerts = []
        
        # Get recent performance data
        recent_records = await self.storage.get_recent_performance(model_name, hours=24)
        if len(recent_records) < 10:  # Need sufficient data
            return alerts
        
        # Calculate baseline from historical data (older records)
        historical_records = await self.storage.get_recent_performance(model_name, hours=168)  # 1 week
        if len(historical_records) < 20:  # Need sufficient historical data
            return alerts
        
        # Split into baseline and recent
        baseline_records = historical_records[len(recent_records):]  # Older records
        recent_records = historical_records[:len(recent_records)]   # Most recent
        
        if not baseline_records:
            return alerts
        
        # Calculate baseline metrics
        baseline_metrics = self._calculate_average_metrics(baseline_records)
        recent_metrics = self._calculate_average_metrics(recent_records)
        
        # Check for concept drift (accuracy/performance changes)
        if ModelQualityMetric.ACCURACY in baseline_metrics and ModelQualityMetric.ACCURACY in recent_metrics:
            baseline_acc = baseline_metrics[ModelQualityMetric.ACCURACY]
            recent_acc = recent_metrics[ModelQualityMetric.ACCURACY]
            change = abs(baseline_acc - recent_acc)
            
            if change > self.drift_thresholds[DriftType.CONCEPT_DRIFT]:
                severity = self._determine_severity(change, self.drift_thresholds[DriftType.CONCEPT_DRIFT])
                alert = ModelDriftAlert(
                    model_name=model_name,
                    drift_type=DriftType.CONCEPT_DRIFT,
                    severity=severity,
                    timestamp=datetime.now(timezone.utc),
                    description=f"Accuracy changed from {baseline_acc:.4f} to {recent_acc:.4f} ({change:.4f})",
                    threshold_value=self.drift_thresholds[DriftType.CONCEPT_DRIFT],
                    observed_value=change,
                    recommendation="Investigate data quality or retrain model"
                )
                alerts.append(alert)
                self.alert_buffer.append(alert)
        
        # Check for performance drift (latency, throughput changes)
        if ModelQualityMetric.LATENCY_MS in baseline_metrics and ModelQualityMetric.LATENCY_MS in recent_metrics:
            baseline_lat = baseline_metrics[ModelQualityMetric.LATENCY_MS]
            recent_lat = recent_metrics[ModelQualityMetric.LATENCY_MS]
            change = abs(recent_lat - baseline_lat) / baseline_lat if baseline_lat > 0 else 0
            
            if change > self.drift_thresholds[DriftType.PERFORMANCE_DRIFT]:
                severity = self._determine_severity(change, self.drift_thresholds[DriftType.PERFORMANCE_DRIFT])
                alert = ModelDriftAlert(
                    model_name=model_name,
                    drift_type=DriftType.PERFORMANCE_DRIFT,
                    severity=severity,
                    timestamp=datetime.now(timezone.utc),
                    description=f"Latency changed from {baseline_lat:.2f}ms to {recent_lat:.2f}ms ({change:.2%})",
                    threshold_value=self.drift_thresholds[DriftType.PERFORMANCE_DRIFT],
                    observed_value=change,
                    recommendation="Check hardware resources or optimize model"
                )
                alerts.append(alert)
                self.alert_buffer.append(alert)
        
        return alerts
    
    def _calculate_average_metrics(self, records: List[ModelPerformanceRecord]) -> Dict[ModelQualityMetric, float]:
        """Calculate average metrics from a list of records"""
        if not records:
            return {}
        
        # Group metrics by type
        metric_values = {}
        for record in records:
            for metric, value in record.metrics.items():
                if metric not in metric_values:
                    metric_values[metric] = []
                metric_values[metric].append(value)
        
        # Calculate averages
        averages = {}
        for metric, values in metric_values.items():
            averages[metric] = statistics.mean(values)
        
        return averages
    
    def _determine_severity(self, change: float, threshold: float) -> str:
        """Determine alert severity based on change magnitude"""
        ratio = change / threshold
        if ratio >= 2.0:
            return "critical"
        elif ratio >= 1.5:
            return "high"
        elif ratio >= 1.0:
            return "medium"
        else:
            return "low"


class ModelPerformanceMonitor:
    """Main model performance monitoring system"""
    
    def __init__(self, storage: ModelPerformanceStorage, qdrant_client: Optional[QdrantClient] = None):
        self.storage = storage
        self.qdrant = qdrant_client
        self.drift_detector = ModelDriftDetector(storage)
        self.monitoring_tasks: Dict[str, asyncio.Task] = {}
        self.model_configs: Dict[str, Dict[str, Any]] = {}
    
    def register_model(self, model_name: str, config: Dict[str, Any]):
        """Register a model for monitoring"""
        self.model_configs[model_name] = config
    
    async def record_performance(self, record: ModelPerformanceRecord):
        """Record model performance"""
        await self.storage.save_performance_record(record)
        
        # Store in Qdrant if available for similarity search
        if self.qdrant:
            try:
                from qdrant_client.models import PointStruct
                
                # Create a simple embedding from the performance metrics
                metrics_str = " ".join([f"{k.value}:{v}" for k, v in record.metrics.items()])
                perf_embedding = [float(ord(c) % 100) for c in metrics_str[:100]]
                perf_embedding = (perf_embedding + [0.0] * 100)[:100]  # Pad to 100 dimensions
                
                self.qdrant.upsert(
                    collection_name="model_performance",
                    points=[
                        PointStruct(
                            id=f"{record.model_name}_{int(record.timestamp.timestamp())}",
                            vector=perf_embedding,
                            payload={
                                "model_name": record.model_name,
                                "model_version": record.model_version,
                                "timestamp": record.timestamp.isoformat(),
                                "metrics": {k.value: v for k, v in record.metrics.items()},
                                "input_distribution": record.input_distribution,
                                "output_distribution": record.output_distribution,
                                "context": record.context,
                                "hardware_info": record.hardware_info
                            }
                        )
                    ]
                )
            except Exception as e:
                logger.warning(f"Failed to store performance in Qdrant: {e}")
    
    async def record_telemetry(self, telemetry: ModelTelemetry):
        """Record model telemetry"""
        await self.storage.save_telemetry(telemetry)
    
    async def start_monitoring(self, model_name: str, interval_seconds: int = 300):
        """Start monitoring a model"""
        if model_name in self.monitoring_tasks:
            self.monitoring_tasks[model_name].cancel()
        
        task = asyncio.create_task(self._monitor_model(model_name, interval_seconds))
        self.monitoring_tasks[model_name] = task
        return task
    
    async def stop_monitoring(self, model_name: str):
        """Stop monitoring a model"""
        if model_name in self.monitoring_tasks:
            task = self.monitoring_tasks[model_name]
            task.cancel()
            del self.monitoring_tasks[model_name]
    
    async def _monitor_model(self, model_name: str, interval_seconds: int):
        """Monitor a model for performance and drift"""
        while True:
            try:
                # Check for drift
                alerts = await self.drift_detector.detect_drift(model_name)
                for alert in alerts:
                    logger.warning(f"Drift alert for {model_name}: {alert.description}")
                
                # Could add more monitoring checks here
                # e.g., resource usage, error rates, etc.
                
                await asyncio.sleep(interval_seconds)
                
            except asyncio.CancelledError:
                logger.info(f"Monitoring stopped for {model_name}")
                break
            except Exception as e:
                logger.error(f"Error monitoring {model_name}: {e}")
                await asyncio.sleep(interval_seconds)
    
    async def get_model_report(self, model_name: str) -> Dict[str, Any]:
        """Generate a comprehensive report for a model"""
        recent_performance = await self.storage.get_recent_performance(model_name, hours=24)
        telemetry = await self.storage.get_model_telemetry(model_name, hours=1)
        alerts = [a for a in self.drift_detector.alert_buffer if a.model_name == model_name]
        
        if not recent_performance:
            return {"error": f"No performance data found for {model_name}"}
        
        # Calculate summary statistics
        metrics_summary = {}
        for metric in ModelQualityMetric:
            values = [r.metrics[metric] for r in recent_performance if metric in r.metrics]
            if values:
                metrics_summary[metric.value] = {
                    "mean": statistics.mean(values),
                    "median": statistics.median(values),
                    "std_dev": statistics.stdev(values) if len(values) > 1 else 0,
                    "min": min(values),
                    "max": max(values),
                    "count": len(values)
                }
        
        # Calculate recent trends
        recent_count = len(recent_performance)
        if recent_count >= 10:
            recent_slice = recent_performance[:10]
            older_slice = recent_performance[10:20] if len(recent_performance) >= 20 else []
            
            trend_analysis = {}
            for metric in ModelQualityMetric:
                recent_vals = [r.metrics[metric] for r in recent_slice if metric in r.metrics]
                older_vals = [r.metrics[metric] for r in older_slice if metric in r.metrics]
                
                if recent_vals and older_vals:
                    recent_avg = statistics.mean(recent_vals)
                    older_avg = statistics.mean(older_vals)
                    change = recent_avg - older_avg
                    trend_analysis[metric.value] = {
                        "recent_avg": recent_avg,
                        "older_avg": older_avg,
                        "change": change,
                        "change_pct": (change / older_avg) * 100 if older_avg != 0 else 0
                    }
        else:
            trend_analysis = {}
        
        return {
            "model_name": model_name,
            "report_timestamp": datetime.now(timezone.utc).isoformat(),
            "performance_summary": metrics_summary,
            "trend_analysis": trend_analysis,
            "recent_alerts": [a.__dict__ for a in alerts[-5:]],  # Last 5 alerts
            "telemetry_summary": {
                "recent_requests": len(telemetry),
                "avg_response_time_ms": statistics.mean([t.response_time_ms for t in telemetry if t.response_time_ms]) if telemetry else None,
                "error_rate": sum(1 for t in telemetry if t.error_occurred) / len(telemetry) if telemetry else 0
            },
            "data_points_analyzed": len(recent_performance)
        }
    
    async def get_all_models_report(self) -> Dict[str, Any]:
        """Get reports for all monitored models"""
        reports = {}
        for model_name in self.model_configs.keys():
            reports[model_name] = await self.get_model_report(model_name)
        return reports


# Example usage
async def example_usage():
    """Example of how to use the model performance monitoring system"""
    
    # This would typically be connected to your actual database/redis/qdrant
    # For this example, we'll use mock objects
    storage = ModelPerformanceStorage()
    
    # Create monitor
    monitor = ModelPerformanceMonitor(storage)
    
    # Register models
    monitor.register_model("qwen2.5-coder-7b", {
        "vram_required_gb": 16,
        "expected_latency_ms": 2000,
        "supported_tasks": ["code_generation", "explanation"]
    })
    
    monitor.register_model("deepseek-coder-v2-lite", {
        "vram_required_gb": 20,
        "expected_latency_ms": 3000,
        "supported_tasks": ["algorithmic_problems", "code_optimization"]
    })
    
    # Simulate recording performance
    for i in range(50):
        record = ModelPerformanceRecord(
            model_name="qwen2.5-coder-7b",
            model_version="v1.0.0",
            timestamp=datetime.now(timezone.utc),
            metrics={
                ModelQualityMetric.ACCURACY: 0.85 + (random.random() * 0.1 - 0.05),  # 0.8 to 0.9
                ModelQualityMetric.LATENCY_MS: 1800 + (random.random() * 400),  # 1800-2200ms
                ModelQualityMetric.TOKEN_PER_SECOND: 40 + (random.random() * 10),  # 40-50 t/s
                ModelQualityMetric.ERROR_RATE: random.random() * 0.05  # 0-5% error rate
            },
            context={"task_type": "code_generation", "input_complexity": random.choice(["simple", "medium", "complex"])},
            hardware_info={"gpu_utilization": random.random() * 80, "vram_used_gb": 12.5}
        )
        await monitor.record_performance(record)
        
        # Simulate telemetry
        telemetry = ModelTelemetry(
            model_name="qwen2.5-coder-7b",
            request_id=f"req_{i}",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
            input_tokens=random.randint(100, 500),
            output_tokens=random.randint(50, 300),
            response_time_ms=record.metrics[ModelQualityMetric.LATENCY_MS],
            hardware_usage={
                "cpu_percent": random.random() * 50,
                "gpu_percent": random.random() * 80,
                "gpu_memory_percent": random.random() * 70
            }
        )
        await monitor.record_telemetry(telemetry)
        
        await asyncio.sleep(0.1)  # Brief pause
    
    # Start monitoring
    await monitor.start_monitoring("qwen2.5-coder-7b", interval_seconds=60)
    
    # Get report
    report = await monitor.get_model_report("qwen2.5-coder-7b")
    print("Model Performance Report:")
    print(json.dumps(report, indent=2, default=str))
    
    # Stop monitoring
    await monitor.stop_monitoring("qwen2.5-coder-7b")


if __name__ == "__main__":
    import random
    from datetime import timedelta
    asyncio.run(example_usage())