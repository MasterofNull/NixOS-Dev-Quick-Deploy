#!/usr/bin/env python3
"""
Trend Database Module - PostgreSQL integration for metrics aggregation
Feeds time-series data and trend analysis to the autonomous improvement system
Uses local LLM for pattern recognition and anomaly detection
"""

import asyncio
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
from psycopg2.extras import execute_values


@dataclass
class MetricSnapshot:
    """Single metric observation"""
    time: datetime
    metric_name: str
    metric_value: float
    metric_unit: str
    service: str
    component: str
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class TrendAnalysis:
    """Computed trend for a metric over a time window"""
    metric_name: str
    time_window: str
    current_value: float
    baseline_value: float
    change_pct: float
    trend_direction: str  # improving, stable, degrading, volatile, insufficient_data
    volatility: float
    sample_count: int


class TrendDatabase:
    """
    Aggregates metrics from multiple sources and computes trends
    Stores results in PostgreSQL for local LLM analysis
    """

    def __init__(
        self,
        pg_host: str = "127.0.0.1",
        pg_port: int = 5432,
        pg_user: str = "aidb",
        pg_database: str = "aidb",
        pg_password: Optional[str] = None,
    ):
        self.pg_host = pg_host
        self.pg_port = pg_port
        self.pg_user = pg_user
        self.pg_database = pg_database
        self.pg_password = pg_password
        self._conn: Optional[psycopg2.extensions.connection] = None

        # Data source paths
        self.repo_root = Path(__file__).parent.parent.parent
        self.routing_metrics_db = self.repo_root / "routing_metrics.db"
        self.experiments_db = self.repo_root / "ai-stack/autoresearch/experiments.sqlite"

    def connect(self) -> psycopg2.extensions.connection:
        """Get or create PostgreSQL connection"""
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(
                host=self.pg_host,
                port=self.pg_port,
                user=self.pg_user,
                database=self.pg_database,
                password=self.pg_password,
            )
        return self._conn

    def close(self):
        """Close PostgreSQL connection"""
        if self._conn and not self._conn.closed:
            self._conn.close()
            self._conn = None

    # ========================================================================
    # METRIC COLLECTION FROM MULTIPLE SOURCES
    # ========================================================================

    def collect_routing_metrics(self, since_hours: int = 24) -> List[MetricSnapshot]:
        """
        Collect metrics from routing_metrics.db (cache hit rate, local routing %)
        """
        if not self.routing_metrics_db.exists():
            return []

        snapshots = []
        since = datetime.now() - timedelta(hours=since_hours)

        with sqlite3.connect(str(self.routing_metrics_db)) as conn:
            cursor = conn.cursor()

            # Cache metrics
            cursor.execute("""
                SELECT timestamp, cache_hit, cache_miss
                FROM routing_log
                WHERE timestamp >= ?
                ORDER BY timestamp
            """, (since.isoformat(),))

            for row in cursor.fetchall():
                ts = datetime.fromisoformat(row[0])
                cache_hit = bool(row[1])

                snapshots.append(MetricSnapshot(
                    time=ts,
                    metric_name="cache_hit_rate",
                    metric_value=1.0 if cache_hit else 0.0,
                    metric_unit="pct",
                    service="hybrid-coordinator",
                    component="cache",
                ))

            # Local routing percentage
            cursor.execute("""
                SELECT timestamp, used_local
                FROM routing_log
                WHERE timestamp >= ?
                ORDER BY timestamp
            """, (since.isoformat(),))

            for row in cursor.fetchall():
                ts = datetime.fromisoformat(row[0])
                used_local = bool(row[1])

                snapshots.append(MetricSnapshot(
                    time=ts,
                    metric_name="local_routing_pct",
                    metric_value=1.0 if used_local else 0.0,
                    metric_unit="pct",
                    service="hybrid-coordinator",
                    component="routing",
                ))

        return snapshots

    def collect_experiment_metrics(self, since_hours: int = 24) -> List[MetricSnapshot]:
        """
        Collect experiment results from autoresearch experiments.sqlite
        """
        if not self.experiments_db.exists():
            return []

        snapshots = []
        since = datetime.now() - timedelta(hours=since_hours)

        with sqlite3.connect(str(self.experiments_db)) as conn:
            cursor = conn.cursor()

            # Experiment success rate
            cursor.execute("""
                SELECT timestamp, accepted
                FROM experiments
                WHERE timestamp >= ?
                ORDER BY timestamp
            """, (since.isoformat(),))

            for row in cursor.fetchall():
                ts = datetime.fromisoformat(row[0])
                accepted = bool(row[1])

                snapshots.append(MetricSnapshot(
                    time=ts,
                    metric_name="experiment_success_rate",
                    metric_value=1.0 if accepted else 0.0,
                    metric_unit="pct",
                    service="autoresearch",
                    component="experiments",
                ))

        return snapshots

    def collect_baseline_metrics(self) -> List[MetricSnapshot]:
        """
        Collect metrics from baseline profiler
        Currently returns empty list - baseline profiler uses JSONL format
        TODO: Parse baseline profiler JSONL logs
        """
        # Placeholder for baseline profiler integration
        return []

    def collect_all_metrics(self, since_hours: int = 24) -> List[MetricSnapshot]:
        """
        Aggregate metrics from all data sources
        """
        all_metrics = []
        all_metrics.extend(self.collect_routing_metrics(since_hours))
        all_metrics.extend(self.collect_experiment_metrics(since_hours))
        all_metrics.extend(self.collect_baseline_metrics())

        # Sort by time
        all_metrics.sort(key=lambda m: m.time)

        return all_metrics

    # ========================================================================
    # WRITE TO POSTGRESQL TIMESERIES
    # ========================================================================

    def insert_metrics(self, snapshots: List[MetricSnapshot]) -> int:
        """
        Batch insert metrics into system_metrics_timeseries
        Returns number of rows inserted
        """
        if not snapshots:
            return 0

        conn = self.connect()
        cursor = conn.cursor()

        values = [
            (
                s.time,
                s.metric_name,
                s.metric_value,
                s.metric_unit,
                s.service,
                s.component,
                json.dumps(s.metadata) if s.metadata else None,
            )
            for s in snapshots
        ]

        execute_values(
            cursor,
            """
            INSERT INTO system_metrics_timeseries
                (time, metric_name, metric_value, metric_unit, service, component, metadata)
            VALUES %s
            ON CONFLICT (time, metric_name, service, component) DO NOTHING
            """,
            values,
        )

        conn.commit()
        inserted = cursor.rowcount
        cursor.close()

        return inserted

    # ========================================================================
    # TREND ANALYSIS
    # ========================================================================

    def compute_trend(
        self,
        metric_name: str,
        time_window: str = "24h",
    ) -> Optional[TrendAnalysis]:
        """
        Compute trend analysis for a metric over a time window
        Returns TrendAnalysis or None if insufficient data
        """
        conn = self.connect()
        cursor = conn.cursor()

        # Map time window to hours
        window_hours = {
            "1h": 1,
            "6h": 6,
            "24h": 24,
            "7d": 24 * 7,
            "30d": 24 * 30,
            "90d": 24 * 90,
        }.get(time_window, 24)

        since = datetime.now() - timedelta(hours=window_hours)

        # Get all metric values in window
        cursor.execute(
            """
            SELECT metric_value, time
            FROM system_metrics_timeseries
            WHERE metric_name = %s AND time >= %s
            ORDER BY time
            """,
            (metric_name, since),
        )

        rows = cursor.fetchall()
        cursor.close()

        if len(rows) < 2:
            # Insufficient data
            return TrendAnalysis(
                metric_name=metric_name,
                time_window=time_window,
                current_value=0.0,
                baseline_value=0.0,
                change_pct=0.0,
                trend_direction="insufficient_data",
                volatility=0.0,
                sample_count=len(rows),
            )

        values = [float(row[0]) for row in rows]

        # Compute statistics
        current_value = values[-1]
        baseline_value = values[0]
        mean_value = sum(values) / len(values)

        # Change percentage
        if baseline_value != 0:
            change_pct = ((current_value - baseline_value) / baseline_value) * 100
        else:
            change_pct = 0.0

        # Volatility (coefficient of variation)
        if mean_value != 0:
            variance = sum((v - mean_value) ** 2 for v in values) / len(values)
            stddev = variance ** 0.5
            volatility = stddev / mean_value
        else:
            volatility = 0.0

        # Trend direction
        if abs(change_pct) < 2.0:
            trend_direction = "stable"
        elif volatility > 0.3:
            trend_direction = "volatile"
        elif change_pct > 0:
            trend_direction = "improving"  # Assuming higher is better
        else:
            trend_direction = "degrading"

        return TrendAnalysis(
            metric_name=metric_name,
            time_window=time_window,
            current_value=current_value,
            baseline_value=baseline_value,
            change_pct=change_pct,
            trend_direction=trend_direction,
            volatility=volatility,
            sample_count=len(values),
        )

    def update_trend_cache(self, trend: TrendAnalysis):
        """
        Update metric_trends table with computed trend
        """
        conn = self.connect()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO metric_trends
                (metric_name, time_window, current_value, baseline_value,
                 change_pct, trend_direction, volatility, sample_count, last_updated)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (metric_name, time_window)
            DO UPDATE SET
                current_value = EXCLUDED.current_value,
                baseline_value = EXCLUDED.baseline_value,
                change_pct = EXCLUDED.change_pct,
                trend_direction = EXCLUDED.trend_direction,
                volatility = EXCLUDED.volatility,
                sample_count = EXCLUDED.sample_count,
                last_updated = NOW()
            """,
            (
                trend.metric_name,
                trend.time_window,
                trend.current_value,
                trend.baseline_value,
                trend.change_pct,
                trend.trend_direction,
                trend.volatility,
                trend.sample_count,
            ),
        )

        conn.commit()
        cursor.close()

    def refresh_all_trends(
        self,
        time_windows: Optional[List[str]] = None,
    ) -> int:
        """
        Refresh trend cache for all key metrics
        Returns number of trends updated
        """
        if time_windows is None:
            time_windows = ["1h", "24h", "7d"]

        key_metrics = [
            "cache_hit_rate",
            "local_routing_pct",
            "experiment_success_rate",
        ]

        trends_updated = 0

        for metric_name in key_metrics:
            for window in time_windows:
                trend = self.compute_trend(metric_name, window)
                if trend:
                    self.update_trend_cache(trend)
                    trends_updated += 1

        return trends_updated

    # ========================================================================
    # ANOMALY DETECTION (FOR TRIGGER ENGINE)
    # ========================================================================

    def detect_anomalies(self) -> List[Dict[str, Any]]:
        """
        Detect metric anomalies that should trigger improvement cycles
        Returns list of anomaly dicts with severity and context
        """
        conn = self.connect()
        cursor = conn.cursor()

        anomalies = []

        # Check for degrading trends
        cursor.execute(
            """
            SELECT metric_name, time_window, current_value, baseline_value, change_pct
            FROM metric_trends
            WHERE trend_direction = 'degrading' AND change_pct < -10.0
            ORDER BY change_pct
            """
        )

        for row in cursor.fetchall():
            anomalies.append({
                "type": "degrading_trend",
                "metric_name": row[0],
                "time_window": row[1],
                "current_value": float(row[2]),
                "baseline_value": float(row[3]),
                "change_pct": float(row[4]),
                "severity": "high" if row[4] < -20.0 else "medium",
            })

        # Check for volatile metrics
        cursor.execute(
            """
            SELECT metric_name, time_window, volatility, current_value
            FROM metric_trends
            WHERE trend_direction = 'volatile' AND volatility > 0.4
            """
        )

        for row in cursor.fetchall():
            anomalies.append({
                "type": "high_volatility",
                "metric_name": row[0],
                "time_window": row[1],
                "volatility": float(row[2]),
                "current_value": float(row[3]),
                "severity": "medium",
            })

        cursor.close()
        return anomalies

    # ========================================================================
    # SYNC PIPELINE
    # ========================================================================

    async def sync_metrics_pipeline(self, since_hours: int = 24) -> Dict[str, int]:
        """
        Complete sync pipeline: collect -> insert -> analyze -> cache trends
        Returns stats dict
        """
        # Step 1: Collect from all sources
        snapshots = self.collect_all_metrics(since_hours)

        # Step 2: Insert into PostgreSQL
        inserted = self.insert_metrics(snapshots)

        # Step 3: Refresh trend cache
        trends_updated = self.refresh_all_trends()

        # Step 4: Detect anomalies
        anomalies = self.detect_anomalies()

        return {
            "metrics_collected": len(snapshots),
            "metrics_inserted": inserted,
            "trends_updated": trends_updated,
            "anomalies_detected": len(anomalies),
        }


async def main():
    """
    Example usage and testing
    """
    # Read password from secrets if available
    pg_password = None
    secret_path = Path("/run/secrets/postgres_password")
    if secret_path.exists():
        pg_password = secret_path.read_text().strip()

    db = TrendDatabase(pg_password=pg_password)

    try:
        print("🔄 Syncing metrics to trend database...")
        stats = await db.sync_metrics_pipeline(since_hours=24)

        print(f"✅ Sync complete:")
        print(f"   Metrics collected: {stats['metrics_collected']}")
        print(f"   Metrics inserted: {stats['metrics_inserted']}")
        print(f"   Trends updated: {stats['trends_updated']}")
        print(f"   Anomalies detected: {stats['anomalies_detected']}")

        if stats['anomalies_detected'] > 0:
            print("\n⚠️  Anomalies detected:")
            anomalies = db.detect_anomalies()
            for anomaly in anomalies:
                print(f"   - {anomaly['type']}: {anomaly['metric_name']} "
                      f"({anomaly['severity']}) {anomaly.get('change_pct', anomaly.get('volatility')):.1f}")

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
