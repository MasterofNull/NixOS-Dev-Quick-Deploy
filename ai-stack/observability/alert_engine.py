"""
Alert Engine - Core alert processing and management system.

Handles alert creation, deduplication, grouping, severity-based routing,
and automated remediation workflow triggers.

Part of Phase 1 (Monitoring & Observability) implementation.
"""

import asyncio
import hashlib
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Set, Callable, Any
from pathlib import Path
import yaml
import json

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels for routing and prioritization."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AlertStatus(Enum):
    """Alert lifecycle states."""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


@dataclass
class Alert:
    """
    Core alert data structure.

    Attributes:
        id: Unique alert identifier (SHA256 of fingerprint)
        title: Short alert title
        message: Detailed alert message
        severity: Alert severity level
        source: Alert source component
        component: Specific component affected
        timestamp: Alert creation time
        status: Current alert status
        auto_remediate: Whether to trigger automated remediation
        remediation_workflow: Workflow ID to execute
        metadata: Additional context data
        fingerprint: Unique alert fingerprint for deduplication
        acknowledged_at: When alert was acknowledged
        resolved_at: When alert was resolved
        occurrence_count: Number of times this alert has occurred
        last_occurrence: Most recent occurrence timestamp
    """
    id: str
    title: str
    message: str
    severity: AlertSeverity
    source: str
    component: str
    timestamp: datetime
    status: AlertStatus = AlertStatus.ACTIVE
    auto_remediate: bool = False
    remediation_workflow: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    fingerprint: str = ""
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    occurrence_count: int = 1
    last_occurrence: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert alert to dictionary for serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "message": self.message,
            "severity": self.severity.value,
            "source": self.source,
            "component": self.component,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status.value,
            "auto_remediate": self.auto_remediate,
            "remediation_workflow": self.remediation_workflow,
            "metadata": self.metadata,
            "fingerprint": self.fingerprint,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "occurrence_count": self.occurrence_count,
            "last_occurrence": self.last_occurrence.isoformat() if self.last_occurrence else None,
        }


@dataclass
class AlertRule:
    """
    Alert rule definition.

    Attributes:
        name: Rule name
        condition: Metric condition to evaluate
        threshold: Threshold value
        severity: Alert severity if triggered
        duration: How long condition must persist
        auto_remediate: Enable automated remediation
        remediation_workflow: Workflow to execute
        enabled: Whether rule is active
    """
    name: str
    condition: str
    threshold: float
    severity: AlertSeverity
    duration: int = 60  # seconds
    auto_remediate: bool = False
    remediation_workflow: Optional[str] = None
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


class AlertEngine:
    """
    Core alert processing engine.

    Handles alert lifecycle, deduplication, grouping, and routing.
    Integrates with notification handlers and remediation workflows.
    """

    def __init__(
        self,
        rules_config_path: Optional[Path] = None,
        dedup_window_seconds: int = 300,
        grouping_window_seconds: int = 60,
        max_alert_history: int = 10000,
    ):
        """
        Initialize alert engine.

        Args:
            rules_config_path: Path to alert rules YAML
            dedup_window_seconds: Deduplication time window
            grouping_window_seconds: Alert grouping time window
            max_alert_history: Maximum alerts to retain in history
        """
        self.rules: Dict[str, AlertRule] = {}
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self.dedup_window = timedelta(seconds=dedup_window_seconds)
        self.grouping_window = timedelta(seconds=grouping_window_seconds)
        self.max_history = max_alert_history

        # Alert grouping by component and severity
        self.alert_groups: Dict[str, List[Alert]] = defaultdict(list)

        # Notification handlers (channel -> handler function)
        self.notification_handlers: Dict[str, Callable] = {}

        # Remediation workflows (workflow_id -> workflow function)
        self.remediation_workflows: Dict[str, Callable] = {}

        # WebSocket connections for browser notifications
        self.websocket_connections: Set[Any] = set()

        # Load alert rules if config provided
        if rules_config_path and rules_config_path.exists():
            self.load_rules(rules_config_path)

        logger.info(
            f"AlertEngine initialized: dedup_window={dedup_window_seconds}s, "
            f"grouping_window={grouping_window_seconds}s, max_history={max_alert_history}"
        )

    def load_rules(self, config_path: Path) -> None:
        """Load alert rules from YAML configuration."""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)

            for rule_data in config.get('alert_rules', []):
                rule = AlertRule(
                    name=rule_data['name'],
                    condition=rule_data['condition'],
                    threshold=rule_data['threshold'],
                    severity=AlertSeverity(rule_data['severity']),
                    duration=rule_data.get('duration', 60),
                    auto_remediate=rule_data.get('auto_remediate', False),
                    remediation_workflow=rule_data.get('remediation_workflow'),
                    enabled=rule_data.get('enabled', True),
                    metadata=rule_data.get('metadata', {}),
                )
                self.rules[rule.name] = rule

            logger.info(f"Loaded {len(self.rules)} alert rules from {config_path}")
        except Exception as e:
            logger.error(f"Failed to load alert rules: {e}")

    def _generate_fingerprint(self, alert: Alert) -> str:
        """
        Generate unique fingerprint for alert deduplication.

        Fingerprint based on: severity, source, component, title
        """
        fingerprint_data = f"{alert.severity.value}:{alert.source}:{alert.component}:{alert.title}"
        return hashlib.sha256(fingerprint_data.encode()).hexdigest()[:16]

    def _generate_alert_id(self, fingerprint: str, timestamp: datetime) -> str:
        """Generate unique alert ID."""
        id_data = f"{fingerprint}:{timestamp.isoformat()}"
        return hashlib.sha256(id_data.encode()).hexdigest()[:16]

    async def create_alert(
        self,
        title: str,
        message: str,
        severity: AlertSeverity,
        source: str,
        component: str,
        auto_remediate: bool = False,
        remediation_workflow: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Alert:
        """
        Create and process a new alert.

        Handles deduplication, grouping, notification routing, and
        automated remediation triggers.

        Returns:
            Alert: The created or deduplicated alert
        """
        now = datetime.utcnow()

        # Create alert object
        alert = Alert(
            id="",  # Will be set after fingerprinting
            title=title,
            message=message,
            severity=severity,
            source=source,
            component=component,
            timestamp=now,
            auto_remediate=auto_remediate,
            remediation_workflow=remediation_workflow,
            metadata=metadata or {},
        )

        # Generate fingerprint for deduplication
        fingerprint = self._generate_fingerprint(alert)
        alert.fingerprint = fingerprint
        alert.id = self._generate_alert_id(fingerprint, now)

        # Check for deduplication
        existing_alert = self._check_deduplication(alert)
        if existing_alert:
            logger.debug(f"Alert deduplicated: {alert.title} (fingerprint={fingerprint})")
            existing_alert.occurrence_count += 1
            existing_alert.last_occurrence = now
            return existing_alert

        # Add to active alerts
        self.active_alerts[alert.id] = alert

        # Add to alert history
        self.alert_history.append(alert)
        if len(self.alert_history) > self.max_history:
            self.alert_history.pop(0)

        # Add to grouping
        group_key = f"{alert.component}:{alert.severity.value}"
        self.alert_groups[group_key].append(alert)

        logger.info(
            f"Alert created: {alert.title} (severity={severity.value}, "
            f"source={source}, component={component})"
        )

        # Route notifications
        await self._route_notifications(alert)

        # Trigger remediation if enabled
        if alert.auto_remediate and alert.remediation_workflow:
            await self._trigger_remediation(alert)

        return alert

    def _check_deduplication(self, alert: Alert) -> Optional[Alert]:
        """
        Check if alert is duplicate within deduplication window.

        Returns existing alert if found, None otherwise.
        """
        cutoff_time = datetime.utcnow() - self.dedup_window

        for existing_alert in self.active_alerts.values():
            if (
                existing_alert.fingerprint == alert.fingerprint
                and existing_alert.status == AlertStatus.ACTIVE
                and existing_alert.timestamp >= cutoff_time
            ):
                return existing_alert

        return None

    async def _route_notifications(self, alert: Alert) -> None:
        """Route alert to appropriate notification channels based on severity."""
        # Emergency alerts go to all channels
        if alert.severity == AlertSeverity.EMERGENCY:
            channels = list(self.notification_handlers.keys())
        # Critical alerts go to browser + primary channel
        elif alert.severity == AlertSeverity.CRITICAL:
            channels = ['browser', 'primary']
        # Warning alerts go to browser
        elif alert.severity == AlertSeverity.WARNING:
            channels = ['browser']
        # Info alerts only logged
        else:
            channels = []

        # Always send to browser WebSocket if available
        if self.websocket_connections:
            await self._send_browser_notification(alert)

        # Send to configured handlers
        for channel in channels:
            handler = self.notification_handlers.get(channel)
            if handler:
                try:
                    await handler(alert)
                except Exception as e:
                    logger.error(f"Notification handler {channel} failed: {e}")

    async def _send_browser_notification(self, alert: Alert) -> None:
        """Send alert to all connected browser WebSocket clients."""
        if not self.websocket_connections:
            return

        message = json.dumps(alert.to_dict())
        disconnected = set()

        for ws in self.websocket_connections:
            try:
                await ws.send_text(message)
            except Exception as e:
                logger.error(f"Failed to send WebSocket alert: {e}")
                disconnected.add(ws)

        # Clean up disconnected clients
        self.websocket_connections -= disconnected

    async def _trigger_remediation(self, alert: Alert) -> None:
        """Trigger automated remediation workflow for alert."""
        if not alert.remediation_workflow:
            return

        workflow = self.remediation_workflows.get(alert.remediation_workflow)
        if not workflow:
            logger.warning(f"Remediation workflow not found: {alert.remediation_workflow}")
            return

        logger.info(f"Triggering remediation workflow: {alert.remediation_workflow} for alert {alert.id}")

        try:
            result = await workflow(alert)
            if result.get("success"):
                logger.info(f"Remediation successful for alert {alert.id}")
                await self.resolve_alert(alert.id, auto_resolved=True)
            else:
                logger.warning(f"Remediation failed for alert {alert.id}: {result.get('error')}")
        except Exception as e:
            logger.error(f"Remediation workflow error for alert {alert.id}: {e}")

    async def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an active alert."""
        alert = self.active_alerts.get(alert_id)
        if not alert:
            return False

        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_at = datetime.utcnow()
        logger.info(f"Alert acknowledged: {alert_id}")
        return True

    async def resolve_alert(self, alert_id: str, auto_resolved: bool = False) -> bool:
        """Resolve an alert and remove from active alerts."""
        alert = self.active_alerts.get(alert_id)
        if not alert:
            return False

        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = datetime.utcnow()

        # Remove from active alerts
        del self.active_alerts[alert_id]

        # Remove from groups
        group_key = f"{alert.component}:{alert.severity.value}"
        if group_key in self.alert_groups:
            self.alert_groups[group_key] = [
                a for a in self.alert_groups[group_key] if a.id != alert_id
            ]

        resolution_type = "auto-resolved" if auto_resolved else "manually resolved"
        logger.info(f"Alert {resolution_type}: {alert_id}")
        return True

    def get_active_alerts(
        self,
        severity: Optional[AlertSeverity] = None,
        component: Optional[str] = None,
    ) -> List[Alert]:
        """Get active alerts with optional filtering."""
        alerts = list(self.active_alerts.values())

        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        if component:
            alerts = [a for a in alerts if a.component == component]

        return sorted(alerts, key=lambda a: a.timestamp, reverse=True)

    def get_alert_groups(self) -> Dict[str, List[Alert]]:
        """Get alerts grouped by component and severity."""
        return dict(self.alert_groups)

    def register_notification_handler(self, channel: str, handler: Callable) -> None:
        """Register a notification handler for a channel."""
        self.notification_handlers[channel] = handler
        logger.info(f"Registered notification handler: {channel}")

    def register_remediation_workflow(self, workflow_id: str, workflow: Callable) -> None:
        """Register an automated remediation workflow."""
        self.remediation_workflows[workflow_id] = workflow
        logger.info(f"Registered remediation workflow: {workflow_id}")

    def register_websocket(self, ws: Any) -> None:
        """Register a WebSocket connection for browser notifications."""
        self.websocket_connections.add(ws)
        logger.debug(f"WebSocket registered, total connections: {len(self.websocket_connections)}")

    def unregister_websocket(self, ws: Any) -> None:
        """Unregister a WebSocket connection."""
        self.websocket_connections.discard(ws)
        logger.debug(f"WebSocket unregistered, total connections: {len(self.websocket_connections)}")

    def get_stats(self) -> dict:
        """Get alert engine statistics."""
        return {
            "active_alerts": len(self.active_alerts),
            "total_history": len(self.alert_history),
            "websocket_connections": len(self.websocket_connections),
            "alert_groups": len(self.alert_groups),
            "loaded_rules": len(self.rules),
            "notification_handlers": len(self.notification_handlers),
            "remediation_workflows": len(self.remediation_workflows),
            "severity_breakdown": {
                severity.value: len([a for a in self.active_alerts.values() if a.severity == severity])
                for severity in AlertSeverity
            },
        }
