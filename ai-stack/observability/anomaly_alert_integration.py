#!/usr/bin/env python3
"""
Anomaly Detection → Alert Engine Integration

Connects baseline profiler anomaly detection with the alert engine to:
- Automatically create alerts for detected anomalies
- Map anomaly severity to alert severity
- Trigger auto-remediation for critical anomalies
- Provide anomaly context in alert metadata

Part of Phase 1 Batch 1.2: Automated Anomaly Detection
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional

from baseline_profiler import (
    Anomaly,
    AnomalyMethod,
    BaselineProfiler,
    MetricType,
    get_profiler as get_baseline_profiler,
)
from alert_engine import Alert, AlertEngine, AlertSeverity, AlertStatus

logger = logging.getLogger(__name__)


class AnomalyAlertIntegration:
    """
    Integration between baseline profiler and alert engine.

    Automatically creates alerts for detected anomalies with appropriate
    severity levels and remediation workflows.
    """

    def __init__(
        self,
        profiler: Optional[BaselineProfiler] = None,
        alert_engine: Optional[AlertEngine] = None,
    ):
        self.profiler = profiler or get_baseline_profiler()
        self.alert_engine = alert_engine

        # Severity mapping thresholds
        self.severity_thresholds = {
            "emergency": 0.9,  # Severity score >= 0.9
            "critical": 0.7,   # Severity score >= 0.7
            "warning": 0.5,    # Severity score >= 0.5
            "info": 0.0,       # Any anomaly
        }

        # Remediation workflow mapping
        self.remediation_workflows = {
            MetricType.LATENCY: "restart_service",
            MetricType.ERROR_RATE: "restart_service",
            MetricType.MEMORY_USAGE: "clear_cache",
            MetricType.QUALITY_SCORE: "refresh_models",
        }

        logger.info("Anomaly alert integration initialized")

    def _map_severity(self, anomaly: Anomaly) -> AlertSeverity:
        """Map anomaly severity score to alert severity"""
        score = anomaly.severity_score

        if score >= self.severity_thresholds["emergency"]:
            return AlertSeverity.EMERGENCY
        elif score >= self.severity_thresholds["critical"]:
            return AlertSeverity.CRITICAL
        elif score >= self.severity_thresholds["warning"]:
            return AlertSeverity.WARNING
        else:
            return AlertSeverity.INFO

    def _should_auto_remediate(self, anomaly: Anomaly) -> bool:
        """Determine if anomaly should trigger auto-remediation"""
        # Only remediate critical/emergency anomalies
        if anomaly.severity_score < self.severity_thresholds["critical"]:
            return False

        # Only remediate if we have a workflow for this metric type
        if anomaly.metric_type not in self.remediation_workflows:
            return False

        # Don't remediate quality score anomalies automatically
        # (might be upstream data issue)
        if anomaly.metric_type == MetricType.QUALITY_SCORE:
            return False

        return True

    def _get_remediation_workflow(self, anomaly: Anomaly) -> Optional[str]:
        """Get remediation workflow for anomaly"""
        if not self._should_auto_remediate(anomaly):
            return None
        return self.remediation_workflows.get(anomaly.metric_type)

    def _format_alert_message(self, anomaly: Anomaly) -> str:
        """Format detailed alert message for anomaly"""
        method_name = anomaly.method.value.replace("_", " ").title()

        message = (
            f"Anomaly detected using {method_name} method:\n\n"
            f"Service: {anomaly.service}\n"
            f"Component: {anomaly.component}\n"
            f"Metric: {anomaly.metric_type.value}\n\n"
            f"Observed Value: {anomaly.observed_value:.2f}\n"
            f"Expected Value: {anomaly.expected_value:.2f}\n"
            f"Deviation: {anomaly.deviation:.2f}\n"
            f"Severity Score: {anomaly.severity_score:.2f}\n\n"
            f"Baseline Statistics:\n"
            f"  Mean: {anomaly.baseline.mean:.2f}\n"
            f"  Std Dev: {anomaly.baseline.stddev:.2f}\n"
            f"  Median: {anomaly.baseline.median:.2f}\n"
            f"  P95: {anomaly.baseline.p95:.2f}\n"
            f"  P99: {anomaly.baseline.p99:.2f}\n"
            f"  Sample Count: {anomaly.baseline.sample_count}\n"
        )

        # Add metadata if present
        if anomaly.metadata:
            message += f"\nAdditional Context:\n"
            for key, value in anomaly.metadata.items():
                message += f"  {key}: {value}\n"

        return message

    async def create_alert_for_anomaly(self, anomaly: Anomaly) -> Optional[Alert]:
        """
        Create an alert for a detected anomaly.

        Args:
            anomaly: Detected anomaly

        Returns:
            Created alert, or None if alert engine not available
        """
        if not self.alert_engine:
            logger.warning("Alert engine not available, skipping alert creation")
            return None

        severity = self._map_severity(anomaly)
        remediation_workflow = self._get_remediation_workflow(anomaly)

        title = (
            f"Anomaly: {anomaly.service}/{anomaly.component} "
            f"{anomaly.metric_type.value} = {anomaly.observed_value:.2f}"
        )

        message = self._format_alert_message(anomaly)

        # Create alert
        alert = await self.alert_engine.create_alert(
            title=title,
            message=message,
            severity=severity,
            source="anomaly_detection",
            component=f"{anomaly.service}/{anomaly.component}",
            auto_remediate=self._should_auto_remediate(anomaly),
            remediation_workflow=remediation_workflow,
            metadata={
                "anomaly_id": anomaly.id,
                "metric_type": anomaly.metric_type.value,
                "detection_method": anomaly.method.value,
                "observed_value": anomaly.observed_value,
                "expected_value": anomaly.expected_value,
                "deviation": anomaly.deviation,
                "severity_score": anomaly.severity_score,
                "baseline_mean": anomaly.baseline.mean,
                "baseline_stddev": anomaly.baseline.stddev,
            },
        )

        logger.info(
            f"Created alert {alert.id} for anomaly {anomaly.id} "
            f"(severity={severity.value}, auto_remediate={self._should_auto_remediate(anomaly)})"
        )

        return alert

    async def monitor_anomalies(self, check_interval_seconds: int = 30):
        """
        Background task to monitor for new anomalies and create alerts.

        Args:
            check_interval_seconds: How often to check for new anomalies
        """
        last_check_count = len(self.profiler.detected_anomalies)

        logger.info(f"Starting anomaly monitoring (interval={check_interval_seconds}s)")

        while True:
            await asyncio.sleep(check_interval_seconds)

            try:
                current_count = len(self.profiler.detected_anomalies)

                # Check if new anomalies detected
                if current_count > last_check_count:
                    new_anomalies = list(self.profiler.detected_anomalies)[
                        last_check_count:current_count
                    ]

                    logger.info(f"Detected {len(new_anomalies)} new anomalies")

                    # Create alerts for each new anomaly
                    for anomaly in new_anomalies:
                        await self.create_alert_for_anomaly(anomaly)

                    last_check_count = current_count

            except Exception as e:
                logger.error(f"Error in anomaly monitoring: {e}", exc_info=True)


# Convenience function to record metrics and auto-detect anomalies
async def record_metric_with_alert(
    service: str,
    component: str,
    metric_type: MetricType,
    value: float,
    metadata: Optional[dict] = None,
    profiler: Optional[BaselineProfiler] = None,
    alert_engine: Optional[AlertEngine] = None,
):
    """
    Record a metric and automatically create alert if anomaly detected.

    Convenience wrapper that combines metric recording with immediate
    anomaly checking and alert creation.

    Args:
        service: Service name
        component: Component name
        metric_type: Type of metric
        value: Observed value
        metadata: Optional metadata
        profiler: Baseline profiler (uses global if None)
        alert_engine: Alert engine (optional)
    """
    if profiler is None:
        profiler = get_baseline_profiler()

    # Record metric
    initial_count = len(profiler.detected_anomalies)
    profiler.record_metric(service, component, metric_type, value, metadata)

    # Check if anomaly was detected
    if len(profiler.detected_anomalies) > initial_count:
        # New anomaly detected
        anomaly = list(profiler.detected_anomalies)[-1]

        if alert_engine:
            integration = AnomalyAlertIntegration(profiler, alert_engine)
            await integration.create_alert_for_anomaly(anomaly)


if __name__ == "__main__":
    # Test integration
    import sys
    from pathlib import Path

    # Add parent to path for imports
    sys.path.insert(0, str(Path(__file__).parent))

    logging.basicConfig(level=logging.INFO)

    async def test():
        from alert_engine import AlertEngine

        # Create instances
        profiler = BaselineProfiler()
        alert_engine = AlertEngine(rules_config_path=None)
        integration = AnomalyAlertIntegration(profiler, alert_engine)

        # Record normal metrics
        for i in range(100):
            profiler.record_metric(
                service="test-service",
                component="inference",
                metric_type=MetricType.LATENCY,
                value=100 + (i % 20),
            )

        # Inject anomalies
        anomalies_to_inject = [
            (MetricType.LATENCY, 500, "High latency spike"),
            (MetricType.ERROR_RATE, 0.8, "Error rate spike"),
            (MetricType.MEMORY_USAGE, 8000, "Memory leak detected"),
        ]

        for metric_type, value, description in anomalies_to_inject:
            profiler.record_metric(
                service="test-service",
                component="inference",
                metric_type=metric_type,
                value=value,
                metadata={"description": description},
            )

            # Check if anomaly detected
            if len(profiler.detected_anomalies) > 0:
                anomaly = list(profiler.detected_anomalies)[-1]
                alert = await integration.create_alert_for_anomaly(anomaly)
                if alert:
                    print(f"\n✓ Created alert: {alert.title}")
                    print(f"  Severity: {alert.severity.value}")
                    print(f"  Auto-remediate: {alert.auto_remediate}")
                    print(f"  Workflow: {alert.remediation_workflow}")

        # Show statistics
        stats = profiler.get_statistics()
        alert_stats = alert_engine.get_statistics()

        print(f"\n=== Profiler Statistics ===")
        print(f"Total anomalies: {stats['total_anomalies']}")
        print(f"Recent anomalies (1h): {stats['recent_anomalies_1h']}")

        print(f"\n=== Alert Statistics ===")
        print(f"Total alerts: {alert_stats['total_alerts']}")
        print(f"Active alerts: {alert_stats['active_alerts']}")
        print(f"Alerts by severity: {alert_stats['alerts_by_severity']}")

    asyncio.run(test())
