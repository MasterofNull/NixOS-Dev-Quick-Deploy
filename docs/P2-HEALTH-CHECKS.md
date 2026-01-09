# P2 Health Checks - Implementation Complete

**Date**: 2026-01-08
**Feature**: Comprehensive Health Check System
**Status**: Implemented - Ready for Deployment
**Priority**: P2 (Medium - High Impact)

---

## 🎯 Overview

Implemented Kubernetes-style health probes for proactive issue detection and automatic recovery. This system provides three types of health checks:

1. **Liveness Probe** - Is the service alive? (not deadlocked)
2. **Readiness Probe** - Is the service ready to accept traffic?
3. **Startup Probe** - Has the service finished starting up?

---

## 🏗️ Architecture

### Health Check System

```
┌─────────────────────────────────────────────────────────────┐
│                      AIDB Service                            │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────────┐    ┌──────────────────────────┐       │
│  │ HealthChecker   │───▶│  Liveness Probe          │       │
│  │                 │    │  - Simple alive check     │       │
│  │  - Service name │    │  - Fast (<1s)             │       │
│  │  - Dependencies │    │  - No dependency checks   │       │
│  │  - Metrics      │    └──────────────────────────┘       │
│  └─────────────────┘                                         │
│          │                                                    │
│          │         ┌──────────────────────────┐             │
│          ├────────▶│  Readiness Probe         │             │
│          │         │  - Checks dependencies    │             │
│          │         │  - PostgreSQL health      │             │
│          │         │  - Qdrant health          │             │
│          │         │  - Redis health (optional)│             │
│          │         └──────────────────────────┘             │
│          │                                                    │
│          │         ┌──────────────────────────┐             │
│          └────────▶│  Startup Probe           │             │
│                    │  - Checks initialization  │             │
│                    │  - Lenient timeout        │             │
│                    │  - One-time check         │             │
│                    └──────────────────────────┘             │
└─────────────────────────────────────────────────────────────┘
```

### Dependency Health Checks

```
Readiness Probe
    │
    ├──▶ PostgreSQL (Critical)
    │      └──▶ SELECT 1 query
    │
    ├──▶ Qdrant (Critical)
    │      └──▶ Get collections
    │
    └──▶ Redis (Non-Critical)
           └──▶ PING command
```

---

## 📋 Health Check Endpoints

### `/health/live` - Liveness Probe

**Purpose**: Checks if service is alive (not deadlocked)

**Use Case**: Kubernetes uses this to determine if container should be restarted

**Checks**:
- Can execute Python code
- Not in deadlock state

**Response**:
```json
{
  "status": "healthy",
  "check_type": "liveness",
  "message": "aidb is alive",
  "details": {"service": "aidb"},
  "timestamp": "2026-01-08T22:30:00Z",
  "duration_ms": 1.5
}
```

**Status Codes**:
- `200` - Healthy
- `503` - Unhealthy (will be restarted)

---

### `/health/ready` - Readiness Probe

**Purpose**: Checks if service is ready to accept traffic

**Use Case**: Kubernetes uses this to determine if pod should receive traffic

**Checks**:
- All critical dependencies healthy
- PostgreSQL connected and responsive
- Qdrant connected and responsive
- Redis connected (if configured)

**Response** (Healthy):
```json
{
  "status": "healthy",
  "check_type": "readiness",
  "message": "aidb is ready",
  "details": {
    "service": "aidb",
    "dependencies": [
      {
        "name": "postgresql",
        "status": "healthy",
        "critical": true,
        "message": "postgresql is healthy",
        "error": null
      },
      {
        "name": "qdrant",
        "status": "healthy",
        "critical": true,
        "message": "qdrant is healthy",
        "error": null
      }
    ],
    "critical_failures": 0,
    "non_critical_failures": 0
  },
  "timestamp": "2026-01-08T22:30:00Z",
  "duration_ms": 15.3
}
```

**Response** (Degraded):
```json
{
  "status": "degraded",
  "check_type": "readiness",
  "message": "aidb is degraded: 1 non-critical dependencies unhealthy",
  "details": {
    "dependencies": [
      {
        "name": "redis",
        "status": "unhealthy",
        "critical": false,
        "message": "redis check timed out",
        "error": "timeout"
      }
    ],
    "critical_failures": 0,
    "non_critical_failures": 1
  }
}
```

**Status Codes**:
- `200` - Healthy or Degraded (receives traffic)
- `503` - Unhealthy (no traffic)

---

### `/health/startup` - Startup Probe

**Purpose**: Checks if service has finished starting up

**Use Case**: Kubernetes uses this to know when to start liveness/readiness probes

**Checks**:
- Database schema initialized
- Qdrant collections exist
- All initialization complete

**Response**:
```json
{
  "status": "healthy",
  "check_type": "startup",
  "message": "aidb startup complete",
  "details": {
    "service": "aidb",
    "startup_complete": true
  },
  "timestamp": "2026-01-08T22:30:00Z",
  "duration_ms": 25.7
}
```

**Status Codes**:
- `200` - Startup complete
- `503` - Startup in progress

---

### `/health/detailed` - Comprehensive Status

**Purpose**: Get detailed health status including all probes

**Response**:
```json
{
  "service": "aidb",
  "startup_complete": true,
  "liveness": {
    "status": "healthy",
    "check_type": "liveness",
    "message": "aidb is alive",
    "duration_ms": 1.5
  },
  "readiness": {
    "status": "healthy",
    "check_type": "readiness",
    "message": "aidb is ready",
    "dependencies": [...],
    "duration_ms": 15.3
  },
  "timestamp": "2026-01-08T22:30:00Z"
}
```

---

## 🚀 Deployment

### Docker Compose

Update your docker-compose.yml to include healthchecks:

```yaml
services:
  aidb:
    image: aidb:latest
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8091/health/live"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 30s
```

### Kubernetes

The complete Kubernetes deployment with health probes is at [kubernetes/aidb-deployment.yaml](../ai-stack/kubernetes/aidb-deployment.yaml).

**Key Configuration**:

```yaml
# Startup Probe - Protects slow-starting containers
startupProbe:
  httpGet:
    path: /health/startup
    port: 8091
  initialDelaySeconds: 10
  periodSeconds: 5
  failureThreshold: 30  # 150s max startup time

# Liveness Probe - Restart if unhealthy
livenessProbe:
  httpGet:
    path: /health/live
    port: 8091
  initialDelaySeconds: 30
  periodSeconds: 10
  failureThreshold: 3  # Restart after 30s

# Readiness Probe - Remove from service if unhealthy
readinessProbe:
  httpGet:
    path: /health/ready
    port: 8091
  initialDelaySeconds: 15
  periodSeconds: 5
  failureThreshold: 2  # Stop traffic after 10s
```

---

## 📊 Prometheus Metrics

The health check system exports comprehensive metrics:

### Metrics Exported

```promql
# Total health checks performed
health_check_total{service="aidb", check_type="liveness", status="healthy"}

# Health check duration
health_check_duration_seconds{service="aidb", check_type="readiness"}

# Service health status (1=healthy, 0=unhealthy)
service_health_status{service="aidb", check_type="liveness"}

# Dependency health status
dependency_health_status{dependency="postgresql", check_type="readiness"}
```

### Grafana Queries

**Service Health Status**:
```promql
service_health_status{service="aidb"}
```

**Health Check Success Rate**:
```promql
rate(health_check_total{status="healthy"}[5m]) / rate(health_check_total[5m])
```

**Health Check P95 Latency**:
```promql
histogram_quantile(0.95, rate(health_check_duration_seconds_bucket[5m]))
```

**Dependency Failures**:
```promql
sum by (dependency) (dependency_health_status == 0)
```

---

## 🔧 Custom Dependency Checks

You can register custom dependency checks:

```python
from health_check import HealthChecker

health_checker = HealthChecker(service_name="myservice")

# Register custom check
async def check_external_api():
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.example.com/health")
        return response.status_code == 200

health_checker.register_dependency_check(
    name="external-api",
    check_fn=check_external_api,
    critical=True,  # Service unhealthy if this fails
    timeout=5.0
)
```

---

## 🧪 Testing

### Manual Testing

```bash
# Test liveness
curl http://localhost:8091/health/live

# Test readiness
curl http://localhost:8091/health/ready

# Test startup
curl http://localhost:8091/health/startup

# Get detailed status
curl http://localhost:8091/health/detailed
```

### Automated Testing

```bash
# Run health check tests
pytest ai-stack/tests/test_health_checks.py -v
```

### Expected Test Results

```
test_liveness_probe_healthy PASSED
test_readiness_probe_no_dependencies PASSED
test_startup_probe_not_complete PASSED
test_startup_probe_complete PASSED
test_postgresql_dependency_check PASSED
test_qdrant_dependency_check PASSED
test_readiness_degraded_with_non_critical_failure PASSED
test_readiness_unhealthy_with_critical_failure PASSED
test_dependency_check_timeout PASSED
test_health_check_result_serialization PASSED
test_liveness_endpoint PASSED
test_readiness_endpoint PASSED
test_startup_endpoint PASSED
test_detailed_health_endpoint PASSED

========================= 14 passed in 3.45s =========================
```

---

## 🛠️ Troubleshooting

### Liveness Probe Failing

**Symptoms**: Container restarting frequently

**Possible Causes**:
- Application deadlocked
- High CPU usage preventing response
- Network issues

**Debug**:
```bash
# Check logs
kubectl logs -f aidb-pod-name

# Check if endpoint responds
kubectl exec aidb-pod-name -- curl http://localhost:8091/health/live
```

### Readiness Probe Failing

**Symptoms**: Pod not receiving traffic

**Possible Causes**:
- Database connection failed
- Qdrant unavailable
- Redis unavailable (if critical)

**Debug**:
```bash
# Check detailed health
kubectl exec aidb-pod-name -- curl http://localhost:8091/health/detailed

# Check dependency status
kubectl exec aidb-pod-name -- curl http://localhost:8091/health/ready | jq '.details.dependencies'

# Test database connection
kubectl exec aidb-pod-name -- psql $DATABASE_URL -c "SELECT 1"
```

### Startup Probe Failing

**Symptoms**: Container killed during startup

**Possible Causes**:
- Startup taking longer than configured
- Dependencies not available during startup
- Initialization errors

**Debug**:
```bash
# Increase failureThreshold in deployment
# Allow more time: failureThreshold * periodSeconds

# Check startup logs
kubectl logs aidb-pod-name --previous
```

---

## 🎯 Best Practices

### Probe Configuration

1. **Startup Probe**:
   - Use for slow-starting applications
   - Set failureThreshold high enough for worst-case startup
   - Only needed if startup > 30s

2. **Liveness Probe**:
   - Keep it simple and fast
   - Don't check dependencies
   - Set failureThreshold to tolerate transient issues
   - Avoid false positives (too sensitive = restart loop)

3. **Readiness Probe**:
   - Check all critical dependencies
   - More frequent than liveness (faster traffic removal)
   - Lower failureThreshold than liveness
   - Distinguish critical vs non-critical dependencies

### Timing Recommendations

```yaml
# Startup: Allow 150s max
startupProbe:
  periodSeconds: 5
  failureThreshold: 30

# Liveness: Check every 10s, restart after 30s
livenessProbe:
  periodSeconds: 10
  failureThreshold: 3

# Readiness: Check every 5s, remove traffic after 10s
readinessProbe:
  periodSeconds: 5
  failureThreshold: 2
```

---

## 📈 Benefits

### Automatic Recovery
- Deadlocked containers automatically restarted
- Unhealthy pods removed from load balancer
- Slow-starting containers protected from premature restart

### Proactive Detection
- Issues detected before users affected
- Dependency failures caught early
- Graceful degradation for non-critical failures

### Improved Reliability
- Reduced MTTR (Mean Time To Recovery)
- Better handling of transient failures
- Prevents cascading failures

### Operational Visibility
- Prometheus metrics for health status
- Grafana dashboards for visualization
- Alerts for persistent failures

---

## 🔗 Related Documentation

- **Kubernetes Health Probes**: https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/
- **Health Check Source**: [../ai-stack/mcp-servers/aidb/health_check.py](../ai-stack/mcp-servers/aidb/health_check.py)
- **Kubernetes Deployment**: [../ai-stack/kubernetes/aidb-deployment.yaml](../ai-stack/kubernetes/aidb-deployment.yaml)
- **Test Suite**: [../ai-stack/tests/test_health_checks.py](../ai-stack/tests/test_health_checks.py)

---

**Implementation Complete**: 2026-01-08
**Ready for Production**: ✅ Yes
**Testing Status**: ✅ Comprehensive test suite
**Documentation Status**: ✅ Complete
