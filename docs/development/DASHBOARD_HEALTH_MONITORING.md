# Dashboard Health and Stale Data Detection

## Dashboard Health Monitoring and Reliability

This document outlines the dashboard health monitoring, stale data detection, and alerting mechanisms for the NixOS AI Stack.

### Dashboard Health Monitoring

#### Health Check Endpoints
The dashboard API provides several health check endpoints:

```
GET  /api/health                      - Overall dashboard health
GET  /api/health/services            - Individual service health
GET  /api/health/containers          - Container health status
GET  /api/health/kubernetes          - Kubernetes connectivity
GET  /api/health/database            - Database connectivity
GET  /api/health/metrics             - Metrics collection status
```

#### Health Response Format
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "websocket_connections": 5,
  "metrics_collector": "running",
  "services": {
    "aidb": "healthy",
    "hybrid_coordinator": "healthy", 
    "ralph_wiggum": "degraded",
    "embeddings": "healthy"
  },
  "kubernetes": {
    "connected": true,
    "namespace": "ai-stack",
    "pods_monitored": 8
  },
  "timestamp": "2026-01-26T10:00:00Z"
}
```

### Stale Data Detection

#### Data Freshness Monitoring
The dashboard monitors data freshness and detects stale information:

1. **Metrics Collection Timestamps**:
   - Last metrics collection time
   - Average collection interval
   - Data age thresholds

2. **Service Status Updates**:
   - Last service health check
   - Container status age
   - Pod status freshness

3. **Telemetry Data Age**:
   - Last telemetry event received
   - Event processing lag
   - Data pipeline status

#### Stale Data Detection Algorithm
```python
import datetime
from typing import Dict, Any

def is_data_stale(last_update: datetime.datetime, max_age_minutes: int = 5) -> bool:
    """Check if data is stale based on last update time"""
    time_diff = datetime.datetime.now(datetime.timezone.utc) - last_update
    return time_diff.total_seconds() > (max_age_minutes * 60)

def check_dashboard_health() -> Dict[str, Any]:
    """Comprehensive dashboard health check"""
    health_status = {
        "overall_status": "healthy",
        "components": {},
        "stale_data_detected": False,
        "last_update": datetime.datetime.now(datetime.timezone.utc)
    }
    
    # Check metrics collection
    metrics_age = get_metrics_age()
    if is_data_stale(metrics_age, max_age_minutes=10):
        health_status["components"]["metrics"] = {"status": "stale", "last_update": metrics_age}
        health_status["stale_data_detected"] = True
        health_status["overall_status"] = "degraded"
    else:
        health_status["components"]["metrics"] = {"status": "fresh", "last_update": metrics_age}
    
    # Check service connectivity
    for service in ["aidb", "hybrid_coordinator", "ralph_wiggum"]:
        service_status = check_service_health(service)
        health_status["components"][service] = service_status
        
        if service_status["status"] == "unreachable":
            health_status["overall_status"] = "critical"
    
    return health_status
```

### Alerting Configuration

#### Prometheus Alert Rules
Add the following alert rules to detect dashboard issues:

```yaml
# File: ai-stack/monitoring/prometheus/rules/dashboard-alerts.yml
groups:
- name: dashboard.rules
  rules:
  - alert: DashboardDataStale
    expr: time() - dashboard_last_update_timestamp > 600  # 10 minutes
    for: 2m
    labels:
      severity: warning
    annotations:
      summary: "Dashboard data is stale"
      description: "Dashboard has not received fresh data for more than 10 minutes"

  - alert: DashboardUnreachable
    expr: dashboard_health_status == 0
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "Dashboard API is unreachable"
      description: "Dashboard API health check is failing"

  - alert: ServiceUnreachable
    expr: service_health_status == 0
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "AI service is unreachable"
      description: "One of the AI services is not responding to health checks"
```

### Dashboard Data Refresh Mechanisms

#### WebSocket Auto-Reconnection
The dashboard frontend implements auto-reconnection for WebSocket data streams:

```javascript
// Dashboard WebSocket client with auto-reconnection
class DashboardWebSocket {
  constructor(url) {
    this.url = url;
    this.reconnectInterval = 5000; // 5 seconds
    this.maxReconnectAttempts = 10;
    this.reconnectAttempts = 0;
    this.connect();
  }

  connect() {
    this.ws = new WebSocket(this.url);
    
    this.ws.onopen = () => {
      console.log('Dashboard WebSocket connected');
      this.reconnectAttempts = 0;
    };

    this.ws.onclose = () => {
      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        console.log(`WebSocket disconnected, reconnecting in ${this.reconnectInterval}ms`);
        setTimeout(() => {
          this.reconnectAttempts++;
          this.connect();
        }, this.reconnectInterval);
      } else {
        console.error('Max reconnection attempts reached');
        this.showConnectionError();
      }
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
  }

  showConnectionError() {
    // Show stale data indicator to user
    document.getElementById('data-status').textContent = 'Data may be stale - reconnecting...';
    document.getElementById('data-status').className = 'stale-warning';
  }
}
```

#### Polling Fallback
Implement polling fallback when WebSocket is unavailable:

```javascript
// Fallback polling mechanism
class DashboardPolling {
  constructor(interval = 30000) { // 30 seconds
    this.interval = interval;
    this.polling = false;
  }

  start() {
    this.polling = setInterval(async () => {
      try {
        const response = await fetch('/api/metrics/system');
        const data = await response.json();
        this.updateDashboard(data);
        
        // Update data freshness timestamp
        this.lastUpdate = new Date();
      } catch (error) {
        console.error('Polling failed:', error);
        this.showStaleDataIndicator();
      }
    }, this.interval);
  }

  showStaleDataIndicator() {
    const timeDiff = (new Date() - this.lastUpdate) / 1000; // seconds
    if (timeDiff > 120) { // 2 minutes
      document.getElementById('stale-data-warning').style.display = 'block';
    }
  }
}
```

### Dashboard Configuration for Health Monitoring

#### Environment Variables
Configure dashboard health monitoring with environment variables:

```bash
# Dashboard health monitoring settings
DASHBOARD_HEALTH_CHECK_INTERVAL=30      # Health check interval in seconds
DASHBOARD_STALE_DATA_THRESHOLD=300      # Data considered stale after 5 minutes
DASHBOARD_WEBSOCKET_TIMEOUT=60000       # WebSocket timeout in milliseconds
DASHBOARD_METRICS_RETENTION=3600        # Metrics retention in seconds
DASHBOARD_ALERT_WEBHOOK=""              # Optional webhook for alerts
```

#### Dashboard API Configuration
```python
# Configuration for dashboard health monitoring
DASHBOARD_CONFIG = {
    "health_check_interval": int(os.getenv("DASHBOARD_HEALTH_CHECK_INTERVAL", "30")),
    "stale_data_threshold": int(os.getenv("DASHBOARD_STALE_DATA_THRESHOLD", "300")),  # 5 minutes
    "websocket_timeout": int(os.getenv("DASHBOARD_WEBSOCKET_TIMEOUT", "60000")),  # 60 seconds
    "metrics_retention": int(os.getenv("DASHBOARD_METRICS_RETENTION", "3600")),  # 1 hour
    "alert_webhook": os.getenv("DASHBOARD_ALERT_WEBHOOK", ""),
    "kubernetes_namespace": os.getenv("AI_STACK_NAMESPACE", "ai-stack")
}
```

### Monitoring Dashboard SLOs

#### Service Level Objectives
Define SLOs for dashboard reliability:

1. **Availability**: 99.9% uptime for dashboard API
2. **Freshness**: Data updated within 30 seconds
3. **Latency**: API responses under 500ms
4. **Connectivity**: WebSocket connections maintained

#### SLO Monitoring Queries
```promql
# Dashboard availability
100 * (sum(rate(dashboard_requests_total{status!="5xx"}[5m])) / sum(rate(dashboard_requests_total[5m])))

# Data freshness
avg(time() - dashboard_last_update_timestamp)

# API latency
histogram_quantile(0.95, rate(dashboard_request_duration_seconds_bucket[5m]))

# WebSocket connections
dashboard_websocket_connections
```

### Troubleshooting Dashboard Issues

#### Common Issues and Solutions

1. **Stale Data Display**:
   - Check WebSocket connectivity
   - Verify metrics collection service is running
   - Check network connectivity to services

2. **Health Check Failures**:
   - Verify service endpoints are accessible
   - Check authentication credentials
   - Review service logs

3. **Performance Issues**:
   - Monitor resource usage
   - Check database connection pool
   - Review metrics collection frequency

#### Diagnostic Commands
```bash
# Check dashboard health
curl http://localhost:8889/api/health

# Check WebSocket connection
wscat -c ws://localhost:8889/ws/metrics

# View dashboard logs
kubectl logs -f deployment/dashboard-api -n ai-stack

# Check metrics collection
curl http://localhost:8889/api/metrics/system

# Verify service connectivity
kubectl get pods -n ai-stack
kubectl get svc -n ai-stack
```

This provides comprehensive dashboard health monitoring and stale data detection capabilities.