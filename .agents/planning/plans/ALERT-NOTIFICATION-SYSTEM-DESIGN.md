# Alert & Notification System Design

**Parent Roadmap:** NEXT-GEN-AGENTIC-ROADMAP-2026-03.md
**Related:** Phase 1 (Monitoring), Phase 3 (Self-Improvement)
**Status:** Design Complete, Ready for Implementation
**Created:** 2026-03-15

---

## Overview

**Objective:** Comprehensive multi-channel alerting system with browser-based pop-ups, automated workflows, and intelligent alert routing.

**Key Features:**
1. Real-time browser notifications with action buttons
2. Multi-channel delivery (desktop, email, Slack, webhook)
3. Automated remediation workflows
4. Alert correlation and grouping
5. Escalation paths with timeouts
6. Smart routing by severity and context
7. One-click remediation from alerts

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Alert Generation                         │
├─────────────────────────────────────────────────────────────┤
│  Prometheus │ Anomaly Detector │ Service Health │ Logs      │
└──────┬──────────────┬───────────────┬──────────────┬─────────┘
       │              │               │              │
       └──────────────┴───────────────┴──────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  Alert Processing Engine                     │
├─────────────────────────────────────────────────────────────┤
│  • Deduplication    • Grouping      • Correlation           │
│  • Severity routing • Context enrichment                    │
│  • Rate limiting    • Alert history                         │
└──────┬──────────────┬───────────────┬──────────────┬────────┘
       │              │               │              │
       ▼              ▼               ▼              ▼
  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐
  │ Browser │  │  Email   │  │  Slack   │  │  Webhook     │
  │ WebSocket│  │  SMTP    │  │ Discord  │  │  HTTP POST   │
  └────┬────┘  └──────────┘  └──────────┘  └──────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│            Browser Alert Dashboard                          │
├─────────────────────────────────────────────────────────────┤
│  • Real-time pop-ups  • Alert history  • Action buttons    │
│  • Remediation UI     • Silence/snooze • Escalate          │
└──────┬──────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│            Automated Remediation Engine                     │
├─────────────────────────────────────────────────────────────┤
│  • Pattern matching    • Workflow execution                 │
│  • Rollback on failure • Success validation                 │
└─────────────────────────────────────────────────────────────┘
```

---

## Alert Severity Levels

| Level | Priority | Auto-Remediate | Notification Channels | Escalate After |
|-------|----------|----------------|----------------------|----------------|
| **Info** | Low | No | Browser only | Never |
| **Warning** | Medium | Optional | Browser + Log | 30 minutes |
| **Critical** | High | Yes (safe actions) | Browser + Email + Slack | 10 minutes |
| **Emergency** | Urgent | Yes (all actions) | All channels + SMS | 2 minutes |

---

## Component 1: Alert Processing Engine

**File:** `ai-stack/observability/alert_engine.py`

```python
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Callable
from enum import Enum
import hashlib
import asyncio

class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"

class AlertStatus(Enum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SILENCED = "silenced"

@dataclass
class Alert:
    """Represents a system alert."""
    id: str
    title: str
    message: str
    severity: AlertSeverity
    source: str  # "prometheus", "anomaly_detector", "service_health", etc.
    component: str  # "hybrid-coordinator", "llama-cpp", "redis", etc.
    timestamp: datetime
    status: AlertStatus = AlertStatus.ACTIVE
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Remediation
    auto_remediate: bool = False
    remediation_workflow: Optional[str] = None

    # Escalation
    escalate_after: Optional[timedelta] = None
    escalated: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None

    # Grouping
    fingerprint: str = ""
    group_key: Optional[str] = None

    def __post_init__(self):
        """Generate fingerprint for deduplication."""
        if not self.fingerprint:
            key = f"{self.source}:{self.component}:{self.title}"
            self.fingerprint = hashlib.sha256(key.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API/WebSocket."""
        return {
            "id": self.id,
            "title": self.title,
            "message": self.message,
            "severity": self.severity.value,
            "source": self.source,
            "component": self.component,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status.value,
            "metadata": self.metadata,
            "auto_remediate": self.auto_remediate,
            "remediation_workflow": self.remediation_workflow,
            "escalated": self.escalated,
            "acknowledged_by": self.acknowledged_by,
            "fingerprint": self.fingerprint,
        }


class AlertEngine:
    """Central alert processing and routing engine."""

    def __init__(self):
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self.notification_handlers: Dict[str, Callable] = {}
        self.remediation_handlers: Dict[str, Callable] = {}

        # Deduplication window (don't re-send same alert within 5 minutes)
        self.dedup_window = timedelta(minutes=5)

        # Alert grouping (group similar alerts together)
        self.group_window = timedelta(minutes=2)
        self.alert_groups: Dict[str, List[Alert]] = {}

    def register_notification_handler(self, name: str, handler: Callable):
        """Register a notification channel handler."""
        self.notification_handlers[name] = handler

    def register_remediation_handler(self, workflow: str, handler: Callable):
        """Register an automated remediation workflow."""
        self.remediation_handlers[workflow] = handler

    async def process_alert(self, alert: Alert) -> bool:
        """Process incoming alert with deduplication, grouping, and routing."""

        # 1. Deduplication
        if self._is_duplicate(alert):
            return False

        # 2. Context enrichment
        await self._enrich_alert(alert)

        # 3. Grouping
        self._group_alert(alert)

        # 4. Store alert
        self.active_alerts[alert.id] = alert
        self.alert_history.append(alert)

        # 5. Route notifications
        await self._route_notifications(alert)

        # 6. Auto-remediation
        if alert.auto_remediate and alert.remediation_workflow:
            await self._trigger_remediation(alert)

        # 7. Schedule escalation
        if alert.escalate_after:
            asyncio.create_task(self._schedule_escalation(alert))

        return True

    def _is_duplicate(self, alert: Alert) -> bool:
        """Check if alert is a duplicate within dedup window."""
        cutoff = datetime.now(tz=timezone.utc) - self.dedup_window

        for existing in self.active_alerts.values():
            if existing.fingerprint == alert.fingerprint:
                if existing.timestamp > cutoff:
                    return True

        return False

    async def _enrich_alert(self, alert: Alert):
        """Add context to alert (recent metrics, logs, etc.)."""
        # Example: Add recent error count
        if alert.component == "hybrid-coordinator":
            # Query Prometheus for recent error rate
            alert.metadata["recent_errors"] = 42  # Placeholder
            alert.metadata["p95_latency"] = 1.2  # Placeholder

    def _group_alert(self, alert: Alert):
        """Group similar alerts together."""
        # Group by component + severity
        group_key = f"{alert.component}:{alert.severity.value}"

        if group_key not in self.alert_groups:
            self.alert_groups[group_key] = []

        self.alert_groups[group_key].append(alert)
        alert.group_key = group_key

    async def _route_notifications(self, alert: Alert):
        """Route alert to appropriate notification channels based on severity."""
        channels = self._get_channels_for_severity(alert.severity)

        for channel in channels:
            handler = self.notification_handlers.get(channel)
            if handler:
                await handler(alert)

    def _get_channels_for_severity(self, severity: AlertSeverity) -> List[str]:
        """Determine which channels to notify based on severity."""
        if severity == AlertSeverity.INFO:
            return ["browser"]
        elif severity == AlertSeverity.WARNING:
            return ["browser", "log"]
        elif severity == AlertSeverity.CRITICAL:
            return ["browser", "email", "slack"]
        elif severity == AlertSeverity.EMERGENCY:
            return ["browser", "email", "slack", "webhook", "sms"]
        return []

    async def _trigger_remediation(self, alert: Alert):
        """Execute automated remediation workflow."""
        workflow = alert.remediation_workflow
        handler = self.remediation_handlers.get(workflow)

        if not handler:
            return

        try:
            success = await handler(alert)

            if success:
                alert.status = AlertStatus.RESOLVED
                alert.metadata["remediation_result"] = "success"

                # Send success notification
                await self._notify_remediation_success(alert)
            else:
                alert.metadata["remediation_result"] = "failed"

                # Escalate on failure
                alert.escalated = True
                await self._escalate_alert(alert)

        except Exception as e:
            alert.metadata["remediation_error"] = str(e)
            alert.escalated = True
            await self._escalate_alert(alert)

    async def _schedule_escalation(self, alert: Alert):
        """Schedule alert escalation if not acknowledged."""
        await asyncio.sleep(alert.escalate_after.total_seconds())

        # Check if alert is still active and unacknowledged
        if alert.id in self.active_alerts:
            if alert.status == AlertStatus.ACTIVE:
                alert.escalated = True
                await self._escalate_alert(alert)

    async def _escalate_alert(self, alert: Alert):
        """Escalate alert to higher notification tier."""
        # Upgrade severity by one level
        if alert.severity == AlertSeverity.INFO:
            alert.severity = AlertSeverity.WARNING
        elif alert.severity == AlertSeverity.WARNING:
            alert.severity = AlertSeverity.CRITICAL
        elif alert.severity == AlertSeverity.CRITICAL:
            alert.severity = AlertSeverity.EMERGENCY

        # Re-route with higher severity
        await self._route_notifications(alert)

    async def _notify_remediation_success(self, alert: Alert):
        """Send notification that remediation succeeded."""
        success_alert = Alert(
            id=f"{alert.id}-resolved",
            title=f"Resolved: {alert.title}",
            message=f"Automatic remediation successful for: {alert.message}",
            severity=AlertSeverity.INFO,
            source="remediation_engine",
            component=alert.component,
            timestamp=datetime.now(tz=timezone.utc),
            status=AlertStatus.RESOLVED,
        )

        await self.process_alert(success_alert)

    def acknowledge_alert(self, alert_id: str, user: str):
        """Mark alert as acknowledged."""
        alert = self.active_alerts.get(alert_id)
        if alert:
            alert.status = AlertStatus.ACKNOWLEDGED
            alert.acknowledged_by = user
            alert.acknowledged_at = datetime.now(tz=timezone.utc)

    def silence_alert(self, alert_id: str, duration: timedelta):
        """Silence alert for specified duration."""
        alert = self.active_alerts.get(alert_id)
        if alert:
            alert.status = AlertStatus.SILENCED

            # Schedule un-silence
            asyncio.create_task(self._unsilence_after(alert_id, duration))

    async def _unsilence_after(self, alert_id: str, duration: timedelta):
        """Un-silence alert after duration."""
        await asyncio.sleep(duration.total_seconds())

        alert = self.active_alerts.get(alert_id)
        if alert and alert.status == AlertStatus.SILENCED:
            alert.status = AlertStatus.ACTIVE
```

---

## Component 2: Browser Notification System

**File:** `dashboard/backend/api/routes/alerts.py`

```python
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List, Dict
import asyncio
import json

router = APIRouter()

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast_alert(self, alert: Dict):
        """Send alert to all connected browsers."""
        message = json.dumps({
            "type": "alert",
            "data": alert
        })

        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                # Connection closed, will be removed on disconnect
                pass

manager = ConnectionManager()

@router.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    """WebSocket endpoint for real-time alerts."""
    await manager.connect(websocket)

    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()

            # Handle client messages (acknowledge, silence, etc.)
            message = json.loads(data)

            if message.get("action") == "acknowledge":
                alert_id = message.get("alert_id")
                user = message.get("user", "unknown")
                # Call alert engine to acknowledge
                # alert_engine.acknowledge_alert(alert_id, user)

            elif message.get("action") == "silence":
                alert_id = message.get("alert_id")
                duration = message.get("duration", 3600)  # seconds
                # alert_engine.silence_alert(alert_id, timedelta(seconds=duration))

    except WebSocketDisconnect:
        manager.disconnect(websocket)

@router.get("/alerts/active")
async def get_active_alerts():
    """Get list of active alerts."""
    # Return from alert engine
    return {"alerts": []}

@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str):
    """Acknowledge an alert."""
    # Call alert engine
    return {"status": "acknowledged"}

@router.post("/alerts/{alert_id}/silence")
async def silence_alert(alert_id: str, duration: int = 3600):
    """Silence an alert for duration (seconds)."""
    return {"status": "silenced", "duration": duration}

@router.post("/alerts/{alert_id}/remediate")
async def trigger_remediation(alert_id: str):
    """Manually trigger remediation workflow."""
    return {"status": "triggered"}
```

**File:** `dashboard/frontend/src/components/AlertNotification.tsx`

```typescript
import React, { useEffect, useState } from 'react';
import { Toast, ToastContainer } from 'react-bootstrap';

interface Alert {
  id: string;
  title: string;
  message: string;
  severity: 'info' | 'warning' | 'critical' | 'emergency';
  timestamp: string;
  remediation_workflow?: string;
  auto_remediate: boolean;
}

export const AlertNotificationSystem: React.FC = () => {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [ws, setWs] = useState<WebSocket | null>(null);

  useEffect(() => {
    // Connect to WebSocket
    const websocket = new WebSocket('ws://localhost:8003/ws/alerts');

    websocket.onmessage = (event) => {
      const message = JSON.parse(event.data);

      if (message.type === 'alert') {
        const alert = message.data;

        // Add to alert list
        setAlerts(prev => [alert, ...prev].slice(0, 10));  // Keep last 10

        // Show browser notification (if permission granted)
        if (Notification.permission === 'granted') {
          new Notification(alert.title, {
            body: alert.message,
            icon: getSeverityIcon(alert.severity),
            tag: alert.id,
            requireInteraction: alert.severity === 'critical' || alert.severity === 'emergency',
          });
        }

        // Play sound for critical/emergency
        if (alert.severity === 'critical' || alert.severity === 'emergency') {
          playAlertSound();
        }
      }
    };

    setWs(websocket);

    // Request notification permission
    if (Notification.permission === 'default') {
      Notification.requestPermission();
    }

    return () => {
      websocket.close();
    };
  }, []);

  const acknowledgeAlert = (alertId: string) => {
    fetch(`/api/alerts/${alertId}/acknowledge`, { method: 'POST' })
      .then(() => {
        setAlerts(prev => prev.filter(a => a.id !== alertId));
      });
  };

  const silenceAlert = (alertId: string, duration: number = 3600) => {
    fetch(`/api/alerts/${alertId}/silence`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ duration })
    }).then(() => {
      setAlerts(prev => prev.filter(a => a.id !== alertId));
    });
  };

  const triggerRemediation = (alertId: string) => {
    fetch(`/api/alerts/${alertId}/remediate`, { method: 'POST' })
      .then(() => {
        // Show remediation in progress
      });
  };

  return (
    <div className="alert-notification-system">
      <ToastContainer position="top-end" className="p-3">
        {alerts.map(alert => (
          <Toast
            key={alert.id}
            bg={getSeverityBg(alert.severity)}
            onClose={() => acknowledgeAlert(alert.id)}
          >
            <Toast.Header>
              <strong className="me-auto">{alert.title}</strong>
              <small>{new Date(alert.timestamp).toLocaleTimeString()}</small>
            </Toast.Header>
            <Toast.Body>
              <p>{alert.message}</p>
              <div className="alert-actions">
                <button
                  className="btn btn-sm btn-primary"
                  onClick={() => acknowledgeAlert(alert.id)}
                >
                  Acknowledge
                </button>

                <button
                  className="btn btn-sm btn-secondary"
                  onClick={() => silenceAlert(alert.id, 3600)}
                >
                  Silence (1h)
                </button>

                {alert.remediation_workflow && (
                  <button
                    className="btn btn-sm btn-success"
                    onClick={() => triggerRemediation(alert.id)}
                  >
                    Fix Now
                  </button>
                )}
              </div>
            </Toast.Body>
          </Toast>
        ))}
      </ToastContainer>
    </div>
  );
};

function getSeverityBg(severity: string): string {
  switch (severity) {
    case 'info': return 'info';
    case 'warning': return 'warning';
    case 'critical': return 'danger';
    case 'emergency': return 'dark';
    default: return 'secondary';
  }
}

function getSeverityIcon(severity: string): string {
  switch (severity) {
    case 'info': return '/icons/info.png';
    case 'warning': return '/icons/warning.png';
    case 'critical': return '/icons/critical.png';
    case 'emergency': return '/icons/emergency.png';
    default: return '/icons/alert.png';
  }
}

function playAlertSound() {
  const audio = new Audio('/sounds/alert.mp3');
  audio.play().catch(() => {
    // Autoplay blocked, user needs to interact first
  });
}
```

---

## Component 3: Automated Remediation Workflows

**File:** `ai-stack/observability/remediation_workflows.py`

```python
from typing import Dict, Any
import asyncio
import subprocess

async def restart_service_workflow(alert: Any) -> bool:
    """Restart a failed service."""
    component = alert.component

    if component == "hybrid-coordinator":
        result = subprocess.run(
            ["sudo", "systemctl", "restart", "ai-hybrid-coordinator.service"],
            capture_output=True
        )

        # Wait for service to start
        await asyncio.sleep(5)

        # Verify service is running
        check = subprocess.run(
            ["systemctl", "is-active", "ai-hybrid-coordinator.service"],
            capture_output=True,
            text=True
        )

        return check.stdout.strip() == "active"

    return False

async def clear_cache_workflow(alert: Any) -> bool:
    """Clear Redis cache."""
    result = subprocess.run(
        ["redis-cli", "FLUSHDB"],
        capture_output=True
    )

    return result.returncode == 0

async def scale_resources_workflow(alert: Any) -> bool:
    """Scale resources (increase memory limit, etc.)."""
    # Example: Increase memory limit for hybrid-coordinator
    # In production, this would modify systemd service or container limits
    return True

async def refresh_models_workflow(alert: Any) -> bool:
    """Refresh quality models and patterns."""
    result = subprocess.run(
        ["scripts/ai/aq-patterns", "extract", "--min-occurrences", "5"],
        capture_output=True
    )

    if result.returncode == 0:
        # Reload service
        subprocess.run(["sudo", "systemctl", "reload", "ai-hybrid-coordinator.service"])
        return True

    return False

async def rotate_logs_workflow(alert: Any) -> bool:
    """Rotate logs if disk is full."""
    result = subprocess.run(
        ["scripts/data/rotate-telemetry.sh"],
        capture_output=True
    )

    return result.returncode == 0

# Workflow registry
REMEDIATION_WORKFLOWS = {
    "restart_service": restart_service_workflow,
    "clear_cache": clear_cache_workflow,
    "scale_resources": scale_resources_workflow,
    "refresh_models": refresh_models_workflow,
    "rotate_logs": rotate_logs_workflow,
}
```

---

## Component 4: Alert Rules Configuration

**File:** `config/alert-rules.yaml`

```yaml
# Alert rules with remediation workflows

rules:
  - name: high_error_rate
    condition:
      metric: rate(hybrid_request_errors_total[5m])
      operator: ">"
      threshold: 0.05
      duration: 2m
    alert:
      title: "High Error Rate Detected"
      message: "Error rate is {{ value }} errors/sec (threshold: 0.05)"
      severity: warning
      component: hybrid-coordinator
      auto_remediate: true
      remediation_workflow: clear_cache
      escalate_after: 30m

  - name: service_down
    condition:
      metric: up{job="hybrid-coordinator"}
      operator: "=="
      threshold: 0
      duration: 1m
    alert:
      title: "Service Down"
      message: "Hybrid coordinator is not responding"
      severity: critical
      component: hybrid-coordinator
      auto_remediate: true
      remediation_workflow: restart_service
      escalate_after: 5m

  - name: high_memory
    condition:
      metric: hybrid_process_memory_bytes
      operator: ">"
      threshold: 4000000000  # 4GB
      duration: 5m
    alert:
      title: "High Memory Usage"
      message: "Memory usage is {{ value | humanize }}B (threshold: 4GB)"
      severity: warning
      component: hybrid-coordinator
      auto_remediate: true
      remediation_workflow: restart_service
      escalate_after: 15m

  - name: low_quality
    condition:
      metric: avg_over_time(hybrid_hint_quality_score[10m])
      operator: "<"
      threshold: 0.6
      duration: 5m
    alert:
      title: "Low Hint Quality"
      message: "Average hint quality is {{ value }} (threshold: 0.6)"
      severity: warning
      component: hints-engine
      auto_remediate: true
      remediation_workflow: refresh_models
      escalate_after: 20m

  - name: high_token_cost
    condition:
      metric: rate(hybrid_token_cost_usd_total[1h])
      operator: ">"
      threshold: 1.0
      duration: 10m
    alert:
      title: "High Token Cost"
      message: "Token cost is ${{ value }}/hour (threshold: $1.00/hour)"
      severity: critical
      component: cost-tracker
      auto_remediate: false
      escalate_after: 10m

  - name: disk_full
    condition:
      metric: 100 * (1 - (node_filesystem_avail_bytes / node_filesystem_size_bytes))
      operator: ">"
      threshold: 90
      duration: 5m
    alert:
      title: "Disk Space Critical"
      message: "Disk usage is {{ value }}% (threshold: 90%)"
      severity: emergency
      component: system
      auto_remediate: true
      remediation_workflow: rotate_logs
      escalate_after: 2m
```

---

## Component 5: Multi-Channel Notification Handlers

**File:** `ai-stack/observability/notification_handlers.py`

```python
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
import json
from typing import Any

# Email notification
async def email_handler(alert: Any):
    """Send alert via email."""
    sender = "alerts@ai-stack.local"
    recipient = "admin@example.com"

    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = recipient
    msg['Subject'] = f"[{alert.severity.value.upper()}] {alert.title}"

    body = f"""
Alert: {alert.title}

Message: {alert.message}

Severity: {alert.severity.value}
Component: {alert.component}
Time: {alert.timestamp}

View details: http://localhost:3001/alerts/{alert.id}
"""

    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP('localhost', 25)
        server.send_message(msg)
        server.quit()
    except Exception as e:
        print(f"Failed to send email: {e}")

# Slack notification
async def slack_handler(alert: Any):
    """Send alert to Slack."""
    webhook_url = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

    color = {
        "info": "#36a64f",
        "warning": "#ff9900",
        "critical": "#ff0000",
        "emergency": "#000000"
    }.get(alert.severity.value, "#808080")

    payload = {
        "attachments": [{
            "color": color,
            "title": alert.title,
            "text": alert.message,
            "fields": [
                {"title": "Severity", "value": alert.severity.value, "short": True},
                {"title": "Component", "value": alert.component, "short": True},
            ],
            "footer": f"AI Stack Alerts",
            "ts": int(alert.timestamp.timestamp())
        }]
    }

    try:
        requests.post(webhook_url, json=payload)
    except Exception as e:
        print(f"Failed to send Slack notification: {e}")

# Discord notification
async def discord_handler(alert: Any):
    """Send alert to Discord."""
    webhook_url = "https://discord.com/api/webhooks/YOUR/WEBHOOK"

    embed_color = {
        "info": 0x36a64f,
        "warning": 0xff9900,
        "critical": 0xff0000,
        "emergency": 0x000000
    }.get(alert.severity.value, 0x808080)

    payload = {
        "embeds": [{
            "title": alert.title,
            "description": alert.message,
            "color": embed_color,
            "fields": [
                {"name": "Severity", "value": alert.severity.value, "inline": True},
                {"name": "Component", "value": alert.component, "inline": True},
            ],
            "timestamp": alert.timestamp.isoformat()
        }]
    }

    try:
        requests.post(webhook_url, json=payload)
    except Exception as e:
        print(f"Failed to send Discord notification: {e}")

# Generic webhook
async def webhook_handler(alert: Any):
    """Send alert to generic webhook."""
    webhook_url = "http://your-webhook-endpoint.com/alerts"

    payload = alert.to_dict()

    try:
        requests.post(webhook_url, json=payload)
    except Exception as e:
        print(f"Failed to send webhook: {e}")

# Log notification (for low-priority alerts)
async def log_handler(alert: Any):
    """Log alert to file."""
    import logging
    logger = logging.getLogger("alerts")
    logger.warning(f"[{alert.severity.value}] {alert.title}: {alert.message}")

# Browser notification (handled via WebSocket)
async def browser_handler(alert: Any):
    """Send alert to browser via WebSocket."""
    from dashboard.backend.api.routes.alerts import manager
    await manager.broadcast_alert(alert.to_dict())
```

---

## Implementation Checklist

### Phase 1: Core Infrastructure
- [ ] Implement Alert class and AlertEngine
- [ ] Add alert processing with deduplication
- [ ] Implement alert grouping and correlation
- [ ] Add alert history storage

### Phase 2: Browser Integration
- [ ] Create WebSocket endpoint for real-time alerts
- [ ] Implement React AlertNotification component
- [ ] Add browser notification permission request
- [ ] Add alert sound for critical alerts
- [ ] Create alert dashboard page

### Phase 3: Automated Remediation
- [ ] Implement remediation workflow registry
- [ ] Add restart_service workflow
- [ ] Add clear_cache workflow
- [ ] Add refresh_models workflow
- [ ] Add rotate_logs workflow
- [ ] Test each workflow in isolation

### Phase 4: Multi-Channel Notifications
- [ ] Implement email handler (SMTP)
- [ ] Implement Slack handler
- [ ] Implement Discord handler
- [ ] Implement generic webhook handler
- [ ] Configure notification routing by severity

### Phase 5: Alert Rules
- [ ] Parse alert-rules.yaml configuration
- [ ] Integrate with Prometheus alerts
- [ ] Connect to anomaly detector
- [ ] Add service health checks
- [ ] Test each alert rule

### Phase 6: Testing & Validation
- [ ] Test browser notifications
- [ ] Test email delivery
- [ ] Test Slack/Discord webhooks
- [ ] Test automated remediation
- [ ] Test alert escalation
- [ ] Test alert acknowledgment/silence
- [ ] Load test (100+ simultaneous alerts)

---

## Configuration

**File:** `config/notifications.yaml`

```yaml
# Notification configuration

email:
  enabled: true
  smtp_host: localhost
  smtp_port: 25
  from: "alerts@ai-stack.local"
  to: ["admin@example.com"]

slack:
  enabled: true
  webhook_url: "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
  channel: "#ai-stack-alerts"

discord:
  enabled: false
  webhook_url: ""

webhook:
  enabled: false
  url: ""
  headers:
    Authorization: "Bearer YOUR_TOKEN"

browser:
  enabled: true
  sound_enabled: true
  sound_path: "/sounds/alert.mp3"
  require_interaction:
    critical: true
    emergency: true

# Notification routing
routing:
  info:
    - browser
  warning:
    - browser
    - log
  critical:
    - browser
    - email
    - slack
  emergency:
    - browser
    - email
    - slack
    - webhook

# Rate limiting (prevent alert fatigue)
rate_limiting:
  enabled: true
  max_alerts_per_minute: 10
  max_alerts_per_hour: 100
  grouping_window_seconds: 120
```

---

## Usage Examples

### Example 1: Generate Alert from Code

```python
from ai_stack.observability.alert_engine import Alert, AlertSeverity, AlertEngine
from datetime import datetime, timedelta, timezone

alert_engine = AlertEngine()

# Create alert
alert = Alert(
    id="alert-123",
    title="High Error Rate",
    message="Request error rate exceeded 5% threshold",
    severity=AlertSeverity.WARNING,
    source="prometheus",
    component="hybrid-coordinator",
    timestamp=datetime.now(tz=timezone.utc),
    auto_remediate=True,
    remediation_workflow="clear_cache",
    escalate_after=timedelta(minutes=30)
)

# Process alert
await alert_engine.process_alert(alert)
```

### Example 2: Acknowledge Alert from Browser

```typescript
// User clicks "Acknowledge" button
const acknowledgeAlert = async (alertId: string) => {
  await fetch(`/api/alerts/${alertId}/acknowledge`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' }
  });
};
```

### Example 3: Silence Alert

```python
# Silence alert for 1 hour
from datetime import timedelta

alert_engine.silence_alert("alert-123", duration=timedelta(hours=1))
```

---

## Next Steps

1. **Immediate:** Implement Phase 1-2 (Core + Browser)
2. **Week 1:** Add Phase 3-4 (Remediation + Notifications)
3. **Week 2:** Configure Phase 5-6 (Rules + Testing)
4. **Production:** Deploy with monitoring

**Ready to begin implementation?**
