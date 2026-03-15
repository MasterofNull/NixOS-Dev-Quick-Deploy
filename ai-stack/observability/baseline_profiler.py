#!/usr/bin/env python3
"""
Baseline Profiling and Statistical Anomaly Detection

Tracks normal operational metrics and detects statistical anomalies using:
- Z-score method (standard deviations from mean)
- IQR method (interquartile range outliers)
- Rolling window baseline updates

Integrates with Alert Engine to create alerts for detected anomalies.

Part of Phase 1 Batch 1.2: Automated Anomaly Detection
"""

import asyncio
import json
import logging
import sqlite3
import statistics
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of metrics to track"""
    LATENCY = "latency"  # Response time in ms
    TOKEN_USAGE = "token_usage"  # Tokens consumed
    ERROR_RATE = "error_rate"  # Errors per time window
    QUALITY_SCORE = "quality_score"  # Output quality 0.0-1.0
    THROUGHPUT = "throughput"  # Requests per second
    MEMORY_USAGE = "memory_usage"  # Memory in MB
    CPU_USAGE = "cpu_usage"  # CPU percentage


class AnomalyMethod(Enum):
    """Statistical anomaly detection methods"""
    Z_SCORE = "z_score"  # Standard deviations from mean
    IQR = "iqr"  # Interquartile range
    PERCENTILE = "percentile"  # Percentile-based


@dataclass
class MetricBaseline:
    """Statistical baseline for a metric"""
    metric_type: MetricType
    component: str
    service: str

    # Statistical measures
    mean: float = 0.0
    stddev: float = 0.0
    median: float = 0.0
    q1: float = 0.0  # 25th percentile
    q3: float = 0.0  # 75th percentile
    iqr: float = 0.0  # Interquartile range
    p95: float = 0.0  # 95th percentile
    p99: float = 0.0  # 99th percentile

    # Tracking
    sample_count: int = 0
    last_updated: datetime = field(default_factory=datetime.now)
    samples: deque = field(default_factory=lambda: deque(maxlen=1000))

    def update_statistics(self):
        """Recalculate statistical measures from samples"""
        if len(self.samples) < 2:
            return

        values = list(self.samples)
        self.sample_count = len(values)
        self.mean = statistics.mean(values)
        self.stddev = statistics.stdev(values) if len(values) > 1 else 0.0
        self.median = statistics.median(values)

        sorted_values = sorted(values)
        n = len(sorted_values)
        self.q1 = sorted_values[n // 4]
        self.q3 = sorted_values[(3 * n) // 4]
        self.iqr = self.q3 - self.q1
        self.p95 = sorted_values[int(n * 0.95)]
        self.p99 = sorted_values[int(n * 0.99)]

        self.last_updated = datetime.now()


@dataclass
class Anomaly:
    """Detected anomaly"""
    id: str
    timestamp: datetime
    metric_type: MetricType
    component: str
    service: str

    observed_value: float
    expected_value: float
    deviation: float

    method: AnomalyMethod
    severity_score: float  # 0.0-1.0

    baseline: MetricBaseline
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "metric_type": self.metric_type.value,
            "component": self.component,
            "service": self.service,
            "observed_value": self.observed_value,
            "expected_value": self.expected_value,
            "deviation": self.deviation,
            "method": self.method.value,
            "severity_score": self.severity_score,
            "baseline": {
                "mean": self.baseline.mean,
                "stddev": self.baseline.stddev,
                "median": self.baseline.median,
                "p95": self.baseline.p95,
                "p99": self.baseline.p99,
            },
            "metadata": self.metadata,
        }


class BaselineProfiler:
    """
    Baseline profiling and anomaly detection for AI stack metrics.

    Features:
    - Tracks normal operational baselines per service/component/metric
    - Detects anomalies using multiple statistical methods
    - Rolling window baseline updates
    - Integration with Alert Engine
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        baseline_window_size: int = 1000,
        update_interval_seconds: int = 300,
        z_score_threshold: float = 3.0,
        iqr_multiplier: float = 1.5,
    ):
        self.baseline_window_size = baseline_window_size
        self.update_interval_seconds = update_interval_seconds
        self.z_score_threshold = z_score_threshold
        self.iqr_multiplier = iqr_multiplier

        # In-memory baselines
        # Key: (service, component, metric_type)
        self.baselines: Dict[Tuple[str, str, MetricType], MetricBaseline] = {}

        # Anomaly tracking
        self.detected_anomalies: deque = deque(maxlen=10000)
        self.anomaly_count_by_service: Dict[str, int] = defaultdict(int)

        # Database
        self.db_path = db_path or Path.home() / ".local/share/nixos-ai-stack/observability/baselines.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

        # Background tasks
        self._background_tasks: List[asyncio.Task] = []

        logger.info(f"Baseline profiler initialized: window={baseline_window_size}, "
                   f"z_threshold={z_score_threshold}, iqr_mult={iqr_multiplier}")

    def _init_database(self):
        """Initialize SQLite database for persistent baselines"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Baselines table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS baselines (
                service TEXT NOT NULL,
                component TEXT NOT NULL,
                metric_type TEXT NOT NULL,
                mean REAL,
                stddev REAL,
                median REAL,
                q1 REAL,
                q3 REAL,
                iqr REAL,
                p95 REAL,
                p99 REAL,
                sample_count INTEGER,
                last_updated TIMESTAMP,
                PRIMARY KEY (service, component, metric_type)
            )
        """)

        # Anomalies table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS anomalies (
                id TEXT PRIMARY KEY,
                timestamp TIMESTAMP NOT NULL,
                service TEXT NOT NULL,
                component TEXT NOT NULL,
                metric_type TEXT NOT NULL,
                observed_value REAL,
                expected_value REAL,
                deviation REAL,
                method TEXT,
                severity_score REAL,
                metadata TEXT
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_anomaly_timestamp ON anomalies(timestamp DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_anomaly_service ON anomalies(service)")

        conn.commit()
        conn.close()

        logger.info(f"Baseline database initialized: {self.db_path}")

    def record_metric(
        self,
        service: str,
        component: str,
        metric_type: MetricType,
        value: float,
        metadata: Optional[Dict] = None,
    ):
        """
        Record a metric observation and update baseline.

        Args:
            service: Service name (e.g., "llama-cpp", "hybrid-coordinator")
            component: Component name (e.g., "inference", "hints")
            metric_type: Type of metric
            value: Observed value
            metadata: Optional metadata
        """
        key = (service, component, metric_type)

        # Get or create baseline
        if key not in self.baselines:
            self.baselines[key] = MetricBaseline(
                metric_type=metric_type,
                component=component,
                service=service,
            )

        baseline = self.baselines[key]
        baseline.samples.append(value)

        # Update statistics if we have enough samples
        if len(baseline.samples) >= 10:
            baseline.update_statistics()

            # Check for anomalies
            self._check_for_anomaly(baseline, value, metadata or {})

    def _check_for_anomaly(
        self,
        baseline: MetricBaseline,
        observed_value: float,
        metadata: Dict,
    ):
        """Check if observed value is anomalous"""
        if baseline.sample_count < 30:
            # Need more samples for reliable detection
            return

        anomalies = []

        # Z-score method
        if baseline.stddev > 0:
            z_score = abs((observed_value - baseline.mean) / baseline.stddev)
            if z_score > self.z_score_threshold:
                severity = min(1.0, z_score / (self.z_score_threshold * 2))
                anomalies.append((AnomalyMethod.Z_SCORE, baseline.mean, z_score, severity))

        # IQR method
        if baseline.iqr > 0:
            lower_bound = baseline.q1 - (self.iqr_multiplier * baseline.iqr)
            upper_bound = baseline.q3 + (self.iqr_multiplier * baseline.iqr)

            if observed_value < lower_bound or observed_value > upper_bound:
                deviation = min(
                    abs(observed_value - lower_bound),
                    abs(observed_value - upper_bound)
                ) / baseline.iqr
                severity = min(1.0, deviation / 3.0)
                anomalies.append((AnomalyMethod.IQR, baseline.median, deviation, severity))

        # Record anomalies
        for method, expected, deviation, severity in anomalies:
            anomaly_id = f"{baseline.service}_{baseline.component}_{baseline.metric_type.value}_{int(time.time() * 1000)}"

            anomaly = Anomaly(
                id=anomaly_id,
                timestamp=datetime.now(),
                metric_type=baseline.metric_type,
                component=baseline.component,
                service=baseline.service,
                observed_value=observed_value,
                expected_value=expected,
                deviation=deviation,
                method=method,
                severity_score=severity,
                baseline=baseline,
                metadata=metadata,
            )

            self.detected_anomalies.append(anomaly)
            self.anomaly_count_by_service[baseline.service] += 1

            # Store in database
            self._store_anomaly(anomaly)

            logger.warning(
                f"Anomaly detected [{method.value}]: {baseline.service}/{baseline.component} "
                f"{baseline.metric_type.value}={observed_value:.2f} "
                f"(expected={expected:.2f}, deviation={deviation:.2f}, severity={severity:.2f})"
            )

    def _store_anomaly(self, anomaly: Anomaly):
        """Store anomaly in database"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO anomalies
            (id, timestamp, service, component, metric_type, observed_value,
             expected_value, deviation, method, severity_score, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                anomaly.id,
                anomaly.timestamp,
                anomaly.service,
                anomaly.component,
                anomaly.metric_type.value,
                anomaly.observed_value,
                anomaly.expected_value,
                anomaly.deviation,
                anomaly.method.value,
                anomaly.severity_score,
                json.dumps(anomaly.metadata),
            ),
        )

        conn.commit()
        conn.close()

    def get_baseline(
        self,
        service: str,
        component: str,
        metric_type: MetricType,
    ) -> Optional[MetricBaseline]:
        """Get baseline for a specific metric"""
        key = (service, component, metric_type)
        return self.baselines.get(key)

    def get_anomalies(
        self,
        service: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Anomaly]:
        """Get recent anomalies"""
        anomalies = list(self.detected_anomalies)

        if service:
            anomalies = [a for a in anomalies if a.service == service]

        if since:
            anomalies = [a for a in anomalies if a.timestamp >= since]

        # Sort by timestamp descending
        anomalies.sort(key=lambda a: a.timestamp, reverse=True)

        return anomalies[:limit]

    def get_statistics(self) -> Dict:
        """Get profiler statistics"""
        total_anomalies = len(self.detected_anomalies)
        recent_anomalies = len([a for a in self.detected_anomalies
                               if a.timestamp >= datetime.now() - timedelta(hours=1)])

        return {
            "total_baselines": len(self.baselines),
            "total_anomalies": total_anomalies,
            "recent_anomalies_1h": recent_anomalies,
            "anomalies_by_service": dict(self.anomaly_count_by_service),
            "baselines_by_service": self._count_baselines_by_service(),
        }

    def _count_baselines_by_service(self) -> Dict[str, int]:
        """Count baselines per service"""
        counts = defaultdict(int)
        for (service, _, _) in self.baselines.keys():
            counts[service] += 1
        return dict(counts)

    async def persist_baselines(self):
        """Persist in-memory baselines to database"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        for baseline in self.baselines.values():
            if baseline.sample_count < 10:
                continue  # Skip baselines with insufficient data

            cursor.execute(
                """
                INSERT OR REPLACE INTO baselines
                (service, component, metric_type, mean, stddev, median, q1, q3,
                 iqr, p95, p99, sample_count, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    baseline.service,
                    baseline.component,
                    baseline.metric_type.value,
                    baseline.mean,
                    baseline.stddev,
                    baseline.median,
                    baseline.q1,
                    baseline.q3,
                    baseline.iqr,
                    baseline.p95,
                    baseline.p99,
                    baseline.sample_count,
                    baseline.last_updated,
                ),
            )

        conn.commit()
        conn.close()

        logger.info(f"Persisted {len(self.baselines)} baselines to database")

    async def load_baselines(self):
        """Load baselines from database"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM baselines")
        rows = cursor.fetchall()

        for row in rows:
            service, component, metric_type_str = row[0], row[1], row[2]
            metric_type = MetricType(metric_type_str)

            baseline = MetricBaseline(
                metric_type=metric_type,
                component=component,
                service=service,
                mean=row[3],
                stddev=row[4],
                median=row[5],
                q1=row[6],
                q3=row[7],
                iqr=row[8],
                p95=row[9],
                p99=row[10],
                sample_count=row[11],
                last_updated=datetime.fromisoformat(row[12]) if row[12] else datetime.now(),
            )

            key = (service, component, metric_type)
            self.baselines[key] = baseline

        conn.close()

        logger.info(f"Loaded {len(self.baselines)} baselines from database")

    async def _periodic_persist(self):
        """Background task to periodically persist baselines"""
        while True:
            await asyncio.sleep(self.update_interval_seconds)
            try:
                await self.persist_baselines()
            except Exception as e:
                logger.error(f"Error persisting baselines: {e}")

    async def start(self):
        """Start background tasks"""
        # Load existing baselines
        await self.load_baselines()

        # Start periodic persistence
        task = asyncio.create_task(self._periodic_persist())
        self._background_tasks.append(task)

        logger.info("Baseline profiler started")

    async def stop(self):
        """Stop background tasks and persist state"""
        # Cancel background tasks
        for task in self._background_tasks:
            task.cancel()

        # Wait for cancellation
        await asyncio.gather(*self._background_tasks, return_exceptions=True)

        # Final persistence
        await self.persist_baselines()

        logger.info("Baseline profiler stopped")


# Convenience function for integration
_PROFILER: Optional[BaselineProfiler] = None


def get_profiler() -> BaselineProfiler:
    """Get global profiler instance"""
    global _PROFILER
    if _PROFILER is None:
        _PROFILER = BaselineProfiler()
    return _PROFILER


if __name__ == "__main__":
    # Simple test
    logging.basicConfig(level=logging.INFO)

    profiler = BaselineProfiler()

    # Simulate normal metrics
    for i in range(100):
        profiler.record_metric(
            service="test-service",
            component="test-component",
            metric_type=MetricType.LATENCY,
            value=100 + (i % 20),  # Normal range 100-120
        )

    # Inject anomaly
    profiler.record_metric(
        service="test-service",
        component="test-component",
        metric_type=MetricType.LATENCY,
        value=500,  # Anomalous!
    )

    # Check results
    anomalies = profiler.get_anomalies()
    print(f"\nDetected {len(anomalies)} anomalies:")
    for a in anomalies:
        print(f"  {a.method.value}: {a.observed_value:.2f} vs {a.expected_value:.2f} "
              f"(severity={a.severity_score:.2f})")

    stats = profiler.get_statistics()
    print(f"\nStatistics: {json.dumps(stats, indent=2)}")
