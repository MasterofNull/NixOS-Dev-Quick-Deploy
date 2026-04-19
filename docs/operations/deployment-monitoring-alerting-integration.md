# Phase 4.1: Deployment → Monitoring → Alerting → Remediation Integration

**Status:** Active
**Owner:** Platform Engineering Team
**Last Updated:** 2026-03-20

## Overview

Phase 4.1 implements a complete end-to-end integration that ensures:
- **Automatic monitoring setup** immediately after deployment
- **Alert rules configured** for all deployed services
- **Alerts flow seamlessly** to dashboard and notifications
- **Automated remediation** for common issues
- **Manual escalation** for critical problems
- **Complete visibility** in dashboard timeline

This document describes the integration, configuration, and operational procedures.

## Architecture

### Components

```
┌─────────────────┐
│  Deployment     │
│  Pipeline       │
└────────┬────────┘
         │ triggers
         ▼
┌─────────────────────────────────────────┐
│  Monitoring Integration                 │
│  - Service registration                 │
│  - Metric collection                    │
│  - Health event logging                 │
└────────┬────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  Alert Configuration & Rules            │
│  - Service health alerts                │
│  - Performance alerts                   │
│  - Resource alerts                      │
│  - Threshold management                 │
└────────┬────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  Hybrid Alert Engine                    │
│  - Alert generation                     │
│  - Alert routing                        │
│  - Notification dispatch                │
└────────┬────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  Dashboard Alerting Interface           │
│  - Active alerts display                │
│  - Alert history                        │
│  - Acknowledgment & resolution          │
│  - Remediation triggering               │
└─────────────────────────────────────────┘
         │
         ├─────────────────────────┬──────────────────┐
         ▼                         ▼                  ▼
┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│ Auto-Remediation │   │  Manual Response │   │  Escalation Log  │
│ - Playbooks      │   │  - Operator UI   │   │  - Critical issues│
│ - Execution      │   │  - Manual fixes  │   │  - Notifications │
└──────────────────┘   └──────────────────┘   └──────────────────┘
```

## Core Libraries

### 1. Monitoring Integration (`lib/deploy/monitoring-integration.sh`)

Automatically sets up monitoring after deployment with service registration and metric collection.

**Key Functions:**

```bash
# Setup monitoring for a deployment
setup_monitoring_after_deployment "deployment_id"

# Register services with monitoring
register_services_with_monitoring "deployment_id"

# Collect metrics for a service
collect_deployment_metrics "service_name" "deployment_id"

# Register with dashboard
register_with_dashboard "deployment_id"

# Validate configuration
validate_monitoring_config
```

**Configuration Files:**
- `~/.agent/monitoring/deployment-metrics.json` - Deployment records
- `~/.agent/monitoring/service-health-events.json` - Health events and metrics

**Integration Points:**
- Called automatically after `deploy system` completes
- Metrics collected every 10 seconds
- Services registered with health check endpoints
- Events logged to JSON for searchability

### 2. Alert Configuration (`lib/deploy/alert-config.sh`)

Configures alert rules, thresholds, and notification channels.

**Key Functions:**

```bash
# Setup alert rules for deployment
setup_alert_rules_for_deployment "deployment_id"

# Configure threshold-based alerts
configure_threshold_alert "service" "metric" "threshold" "severity"

# Setup notification channels
setup_notification_channels

# Setup alert suppression
setup_alert_suppression "deployment_id" "duration_seconds"

# Validate configuration
validate_alert_config
```

**Alert Categories:**

| Category | Rules | Suppression | Action |
|----------|-------|-------------|--------|
| Service Health | down, degraded, restart_required | immediate | restart, healthcheck |
| Performance | latency, error_rate, timeout | immediate | check logs, scale |
| Resources | high_cpu, high_memory, low_disk | deferred | cleanup, scale |
| Deployment | failed, slow, post_deploy_health | immediate | alert operator |

**Thresholds (Configurable):**

```json
{
  "llama-cpp": {
    "response_time_ms": {"warning": 5000, "critical": 10000},
    "error_rate_percent": {"warning": 5, "critical": 10}
  },
  "system": {
    "cpu_percent": {"warning": 80, "critical": 95},
    "memory_percent": {"warning": 85, "critical": 95},
    "disk_percent": {"warning": 80, "critical": 90}
  }
}
```

**Notification Channels:**
- Dashboard (alerts API)
- Syslog (system journal)
- Webhooks (configurable, disabled by default)

### 3. Auto-Remediation (`lib/deploy/auto-remediation.sh`)

Executes remediation playbooks automatically with escalation for critical issues.

**Key Functions:**

```bash
# Setup remediation playbooks
setup_remediation_playbooks

# Execute remediation for an alert
execute_remediation_for_alert "alert_id" "service" "issue_type"

# Track remediation status
track_remediation_status "remediation_id"

# Escalate alert for manual intervention
escalate_alert "alert_id" "service" "issue_type"

# Validate configuration
validate_remediation_config
```

**Built-in Playbooks:**

| Playbook | Trigger | Action | Mode |
|----------|---------|--------|------|
| Service Restart | service_health (down) | systemctl restart | auto |
| Health Check | service_health (degraded) | run health checks | auto |
| Resource Cleanup | resource_exhaustion | clear cache/temp | auto |
| Deployment Rollback | deployment_failure | rollback command | manual |
| Config Fix | configuration_error | apply known fixes | manual |

**Execution Modes:**
- **auto** - Executes automatically when triggered
- **manual** - Requires operator confirmation
- **escalation** - Escalates to operator for manual intervention

**Configuration Files:**
- `~/.agent/remediation/playbooks.json` - Playbook registry
- `~/.agent/remediation/remediation-log.json` - Execution history
- `~/.agent/remediation/escalation-rules.json` - Escalation policies

## Dashboard API Endpoints

### Alert Management

**GET /api/health/alerts**
List all active alerts with metadata.

```bash
curl http://localhost:8889/api/health/alerts
```

Response:
```json
{
  "alerts": [
    {
      "id": "alert-123",
      "severity": "warning",
      "title": "High CPU usage",
      "message": "CPU exceeds 80%",
      "source": "monitoring",
      "component": "ai-stack",
      "acknowledged": false,
      "resolved": false,
      "created_at": "2026-03-20T12:30:00Z",
      "metadata": {
        "service": "llama-cpp",
        "metric": "cpu_percent",
        "value": 85
      }
    }
  ],
  "summary": {
    "total": 5,
    "by_severity": {
      "critical": 1,
      "warning": 3,
      "info": 1
    },
    "acknowledged": 2
  }
}
```

**GET /api/health/alerts/history?limit=100&offset=0**
Get alert history with pagination.

**GET /api/health/alerts/by-severity/{severity}**
Filter alerts by severity (critical, warning, info).

**POST /api/health/alerts/{alert_id}/acknowledge**
Mark an alert as acknowledged.

```bash
curl -X POST http://localhost:8889/api/health/alerts/alert-123/acknowledge
```

Response:
```json
{
  "alert_id": "alert-123",
  "acknowledged": true,
  "timestamp": 1234567890
}
```

**POST /api/health/alerts/{alert_id}/resolve**
Resolve an alert and remove from active list.

```bash
curl -X POST http://localhost:8889/api/health/alerts/alert-123/resolve
```

**POST /api/health/alerts/{alert_id}/suppress**
Temporarily suppress an alert (e.g., during maintenance).

```bash
curl -X POST http://localhost:8889/api/health/alerts/alert-123/suppress?duration_seconds=600
```

### Configuration & Control

**GET /api/health/alerts/config**
Get current alert configuration.

```bash
curl http://localhost:8889/api/health/alerts/config
```

Response:
```json
{
  "rules": [
    {
      "name": "service_down",
      "severity": "critical",
      "category": "service_health",
      "enabled": true
    }
  ],
  "thresholds": {
    "llama-cpp.response_time_ms.warning": 5000,
    "llama-cpp.response_time_ms.critical": 10000
  },
  "channels": [
    {"name": "dashboard", "status": "enabled"},
    {"name": "syslog", "status": "enabled"},
    {"name": "webhook", "status": "disabled"}
  ],
  "remediation_enabled": true
}
```

**POST /api/health/alerts/config/threshold**
Update an alert threshold.

```bash
curl -X POST http://localhost:8889/api/health/alerts/config/threshold \
  -H "Content-Type: application/json" \
  -d '{
    "service": "llama-cpp",
    "metric": "response_time_ms",
    "threshold": 5000,
    "severity": "warning"
  }'
```

### Remediation

**GET /api/health/alerts/remediation-status/{alert_id}**
Get remediation status for an alert.

```bash
curl http://localhost:8889/api/health/alerts/remediation-status/alert-123
```

Response:
```json
{
  "alert_id": "alert-123",
  "remediation_status": "success",
  "remediation_details": {
    "playbook": "service_restart",
    "service": "llama-cpp",
    "executed_at": "2026-03-20T12:31:00Z"
  },
  "last_updated": "2026-03-20T12:31:30Z"
}
```

**POST /api/health/alerts/{alert_id}/remediate**
Trigger remediation for an alert.

```bash
curl -X POST http://localhost:8889/api/health/alerts/alert-123/remediate \
  -H "Content-Type: application/json" \
  -d '{"playbook": "auto"}'
```

Response:
```json
{
  "alert_id": "alert-123",
  "remediation_triggered": true,
  "playbook": "auto",
  "started_at": 1234567890
}
```

## Testing & Validation

### Smoke Tests

**Enhanced Smoke Test** (`scripts/testing/smoke-deployment-monitoring-alerting.sh`)
Quick validation of the basic flow:
- Deployment triggers monitoring
- Alert API responses
- Alert acknowledgment/resolution

```bash
bash scripts/testing/smoke-deployment-monitoring-alerting.sh
```

**Comprehensive Validator** (`scripts/testing/validate-deployment-monitoring-alerting.sh`)
Full end-to-end validation with multiple scenarios:

1. **Happy Path** - Normal deployment with monitoring
2. **Alert Trigger** - Synthetic alert creation and visibility
3. **Auto Remediation** - Automated fix execution
4. **Manual Escalation** - Critical alert handling
5. **Rollback Safety** - Failed deployment detection

```bash
bash scripts/testing/validate-deployment-monitoring-alerting.sh
```

Output: JSON report at `~/.reports/phase-4.1-validation-report.json`

### Manual Testing

**1. Deploy and Monitor**

```bash
# Start deployment
./deploy system --dry-run

# In another terminal, check monitoring
curl http://localhost:8889/api/health/alerts
```

**2. Trigger Alert**

```bash
# Stop a service to trigger alert
systemctl stop llama-cpp

# Check dashboard
curl http://localhost:8889/api/health/alerts

# Restart service
systemctl start llama-cpp

# Verify remediation/recovery
curl http://localhost:8889/api/health/services/llama-cpp
```

**3. Test Suppression**

```bash
# During maintenance, suppress alerts
curl -X POST http://localhost:8889/api/health/alerts/alert-123/suppress?duration_seconds=3600

# Alerts won't trigger for 1 hour
```

## Best Practices

### 1. Alert Configuration

- **Don't be too sensitive** - Set thresholds that avoid alert fatigue
- **Use severity levels** - Match severity to impact (critical = immediate response)
- **Group related alerts** - Avoid duplicate alerts for same issue
- **Document custom rules** - Comment why thresholds are set

### 2. Remediation

- **Start simple** - Auto-remediation for obvious fixes (restart, cleanup)
- **Test playbooks** - Verify remediation works before production
- **Log all actions** - Record what remediation executed and why
- **Escalate cautiously** - Escalate to operator for any destructive actions

### 3. Dashboard Usage

- **Review alert history** - Identify patterns and systemic issues
- **Tune thresholds** - Adjust based on actual performance patterns
- **Monitor remediation success** - Track which playbooks work
- **Plan capacity** - Use alert trends to plan scaling

### 4. Operations

- **Setup on-call** - Ensure escalations reach operators
- **Runbooks for critical alerts** - Document response procedures
- **Maintenance windows** - Use suppression during planned work
- **Post-incident review** - Learn from alert-response cycles

## Configuration Files

### Monitoring Configuration

**`~/.agent/monitoring/deployment-metrics.json`**
```json
{
  "deployments": [
    {
      "deployment_id": "phase4-smoke-1234567890",
      "timestamp": "2026-03-20T12:30:00Z",
      "monitoring_enabled": true,
      "metrics_collection_started": "2026-03-20T12:30:01Z",
      "services_registered": ["llama-cpp", "ai-aidb", "redis"]
    }
  ]
}
```

### Alert Rules

**`~/.agent/alerts/alert-rules.json`**
```json
{
  "rules": [
    {
      "name": "service_down",
      "category": "service_health",
      "severity": "critical",
      "description": "Service is not responding",
      "suppression_policy": "immediate",
      "deployment_id": "phase4-smoke-1234567890",
      "enabled": true,
      "created_at": "2026-03-20T12:30:00Z"
    }
  ]
}
```

### Remediation Playbooks

**`~/.agent/remediation/playbooks.json`**
```json
{
  "playbooks": [
    {
      "name": "service_restart",
      "description": "Restart unresponsive service",
      "issue_type": "service_health",
      "execution_mode": "auto",
      "action": "restart_service",
      "enabled": true,
      "registered_at": "2026-03-20T12:30:00Z"
    }
  ]
}
```

## Troubleshooting

### Alerts Not Appearing

1. Check dashboard is running: `curl http://localhost:8889/api/health/aggregate`
2. Check hybrid coordinator: `curl http://localhost:8003/health`
3. Verify alert configuration: `curl http://localhost:8889/api/health/alerts/config`
4. Check alert rules exist: `jq .rules ~/.agent/alerts/alert-rules.json`

### Remediation Not Executing

1. Verify auto-remediation enabled: `echo $AUTO_REMEDIATION_ENABLED`
2. Check playbook registry: `jq .playbooks ~/.agent/remediation/playbooks.json`
3. Check remediation logs: `cat ~/.agent/remediation/remediation-log.json`
4. Verify required commands available: `which systemctl`

### High Alert Fatigue

1. Review current thresholds: `curl http://localhost:8889/api/health/alerts/config`
2. Check alert history for patterns: `curl http://localhost:8889/api/health/alerts/history`
3. Adjust thresholds upward: Use `/api/health/alerts/config/threshold` endpoint
4. Suppress known noisy alerts: Use `/api/health/alerts/{id}/suppress`

### Dashboard Connection Issues

1. Check dashboard is accessible: `curl http://localhost:8889/api/health/aggregate`
2. Check CORS configuration if using remote access
3. Verify API authentication if required
4. Check firewall rules for port 8889

## Integration with Deployment Pipeline

The integration is automatic:

```bash
./deploy system
│
├─ Deployment begins
├─ Services updated
├─ **Monitoring auto-setup** ← Phase 4.1
├─ Alert rules auto-configured ← Phase 4.1
├─ Metrics collection starts ← Phase 4.1
├─ Health checks run
├─ Deployment succeeds/fails
└─ Dashboard updated with timeline
```

No manual configuration needed - monitoring and alerting are enabled by default.

## Disabling Features

To temporarily disable specific components:

```bash
# Disable auto-remediation
export AUTO_REMEDIATION_ENABLED=false

# Disable alert suppression (not recommended)
export ALERT_SUPPRESSION_ENABLED=false

# Disable monitoring (not recommended)
# Requires commenting out in deploy system command
```

## Future Enhancements

- AI-driven alert threshold optimization
- Predictive remediation (fix issues before alerts fire)
- Cross-service correlation (detect cascading failures)
- Custom remediation playbooks
- Integration with external incident management systems

## See Also

- [System Excellence Roadmap](../../.agents/planning/plans/SYSTEM-EXCELLENCE-ROADMAP-2026-Q2.md)
