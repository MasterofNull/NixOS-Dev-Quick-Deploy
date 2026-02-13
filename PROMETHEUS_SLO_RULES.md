# Prometheus Rules for AI Stack SLOs

## Service Level Objectives and Monitoring Rules

This document defines the Prometheus rules for monitoring AI stack Service Level Objectives (SLOs) and ensuring system reliability.

### AI Stack Service Level Indicators (SLIs)

#### 1. Availability SLI
- **Target**: 99.9% availability
- **Measurement**: Percentage of successful health checks
- **Query**: 
  ```
  100 * (sum(rate(health_check_total{status="healthy"}[5m])) / sum(rate(health_check_total[5m])))
  ```

#### 2. Latency SLI
- **Target**: 95th percentile response time < 500ms
- **Measurement**: API response time percentiles
- **Query**:
  ```
  histogram_quantile(0.95, rate(ai_stack_request_duration_seconds_bucket[5m]))
  ```

#### 3. Quality SLI
- **Target**: < 1% error rate
- **Measurement**: Percentage of failed requests
- **Query**:
  ```
  100 * (sum(rate(ai_stack_requests_total{status=~"5.."}[5m])) / sum(rate(ai_stack_requests_total[5m])))
  ```

### Prometheus Rule Groups

#### 1. Availability Rules
```yaml
# File: ai-stack/monitoring/prometheus/rules/availability.yml
groups:
- name: ai-stack.availability
  rules:
  - alert: AIDBUnreachable
    expr: health_check_status{service="aidb"} == 0
    for: 1m
    labels:
      severity: critical
      service: aidb
    annotations:
      summary: "AIDB service is unreachable"
      description: "AIDB service health check has failed for more than 1 minute"

  - alert: HybridCoordinatorUnreachable
    expr: health_check_status{service="hybrid-coordinator"} == 0
    for: 1m
    labels:
      severity: critical
      service: hybrid-coordinator
    annotations:
      summary: "Hybrid Coordinator service is unreachable"
      description: "Hybrid Coordinator service health check has failed for more than 1 minute"

  - alert: RalphWiggumUnreachable
    expr: health_check_status{service="ralph-wiggum"} == 0
    for: 1m
    labels:
      severity: critical
      service: ralph-wiggum
    annotations:
      summary: "Ralph Wiggum service is unreachable"
      description: "Ralph Wiggum service health check has failed for more than 1 minute"

  - alert: EmbeddingsServiceUnreachable
    expr: health_check_status{service="embeddings"} == 0
    for: 1m
    labels:
      severity: critical
      service: embeddings
    annotations:
      summary: "Embeddings service is unreachable"
      description: "Embeddings service health check has failed for more than 1 minute"

  - alert: LowAvailability
    expr: 100 * (sum(rate(health_check_total{status="healthy"}[5m])) / sum(rate(health_check_total[5m]))) < 99.9
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "AI Stack availability below 99.9%"
      description: "AI Stack availability is {{ $value }}%, below the 99.9% target"
```

#### 2. Latency Rules
```yaml
# File: ai-stack/monitoring/prometheus/rules/latency.yml
groups:
- name: ai-stack.latency
  rules:
  - alert: HighAPILatency
    expr: histogram_quantile(0.95, rate(ai_stack_request_duration_seconds_bucket[5m])) > 0.5
    for: 2m
    labels:
      severity: warning
    annotations:
      summary: "API latency above 500ms (95th percentile)"
      description: "95th percentile API response time is {{ $value }}s, above the 500ms target"

  - alert: VeryHighAPILatency
    expr: histogram_quantile(0.99, rate(ai_stack_request_duration_seconds_bucket[5m])) > 2.0
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "API latency above 2s (99th percentile)"
      description: "99th percentile API response time is {{ $value }}s, above the 2s target"

  - alert: AIDBLatencyHigh
    expr: histogram_quantile(0.95, rate(aidb_request_duration_seconds_bucket[5m])) > 1.0
    for: 2m
    labels:
      severity: warning
      service: aidb
    annotations:
      summary: "AIDB service latency high"
      description: "AIDB 95th percentile response time is {{ $value }}s, above the 1s target"

  - alert: RalphWiggumLatencyHigh
    expr: histogram_quantile(0.95, rate(ralph_wiggum_request_duration_seconds_bucket[5m])) > 5.0
    for: 2m
    labels:
      severity: warning
      service: ralph-wiggum
    annotations:
      summary: "Ralph Wiggum service latency high"
      description: "Ralph Wiggum 95th percentile response time is {{ $value }}s, above the 5s target"
```

#### 3. Error Rate Rules
```yaml
# File: ai-stack/monitoring/prometheus/rules/error-rate.yml
groups:
- name: ai-stack.error-rate
  rules:
  - alert: HighErrorRate
    expr: 100 * (sum(rate(ai_stack_requests_total{status=~"5.."}[5m])) / sum(rate(ai_stack_requests_total[5m]))) > 1
    for: 2m
    labels:
      severity: warning
    annotations:
      summary: "Error rate above 1%"
      description: "Error rate is {{ $value }}%, above the 1% target"

  - alert: AIDBHighErrorRate
    expr: 100 * (sum(rate(aidb_requests_total{status=~"5.."}[5m])) / sum(rate(aidb_requests_total[5m]))) > 5
    for: 2m
    labels:
      severity: warning
      service: aidb
    annotations:
      summary: "AIDB error rate above 5%"
      description: "AIDB error rate is {{ $value }}%, above the 5% target"

  - alert: RalphWiggumHighErrorRate
    expr: 100 * (sum(rate(ralph_wiggum_requests_total{status=~"5.."}[5m])) / sum(rate(ralph_wiggum_requests_total[5m]))) > 10
    for: 2m
    labels:
      severity: warning
      service: ralph-wiggum
    annotations:
      summary: "Ralph Wiggum error rate above 10%"
      description: "Ralph Wiggum error rate is {{ $value }}%, above the 10% target"
```

#### 4. Resource Utilization Rules
```yaml
# File: ai-stack/monitoring/prometheus/rules/resources.yml
groups:
- name: ai-stack.resources
  rules:
  - alert: HighMemoryUsage
    expr: 100 * (container_memory_usage_bytes{container!="",namespace="ai-stack"} / container_spec_memory_limit_bytes) > 85
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High memory usage in AI stack containers"
      description: "Container {{ $labels.container }} in namespace {{ $labels.namespace }} has memory usage {{ $value }}%"

  - alert: HighCPUUsage
    expr: 100 * rate(container_cpu_usage_seconds_total{container!="",namespace="ai-stack"}[5m]) / container_spec_cpu_quota > 90
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High CPU usage in AI stack containers"
      description: "Container {{ $labels.container }} in namespace {{ $labels.namespace }} has CPU usage {{ $value }}%"

  - alert: DiskSpaceLow
    expr: 100 * (1 - node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) > 85
    for: 10m
    labels:
      severity: critical
    annotations:
      summary: "Disk space critically low"
      description: "Disk usage is {{ $value }}%, above the 85% threshold"
```

#### 5. Telemetry Flow Rules
```yaml
# File: ai-stack/monitoring/prometheus/rules/telemetry.yml
groups:
- name: ai-stack.telemetry
  rules:
  - alert: NoTelemetryEvents
    expr: increase(telemetry_events_total[5m]) == 0
    for: 10m
    labels:
      severity: warning
    annotations:
      summary: "No telemetry events in the last 10 minutes"
      description: "No telemetry events have been recorded in the last 10 minutes"

  - alert: RalphToHybridToAIDBFlowBroken
    expr: |
      (
        increase(ralph_wiggum_telemetry_events_total[10m]) > 0
      ) and (
        increase(hybrid_coordinator_telemetry_events_total[10m]) == 0
      )
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "Telemetry flow from Ralph to Hybrid Coordinator broken"
      description: "Ralph is generating telemetry but Hybrid Coordinator is not receiving it"

  - alert: HybridToAIDBFlowBroken
    expr: |
      (
        increase(hybrid_coordinator_telemetry_events_total[10m]) > 0
      ) and (
        increase(aidb_telemetry_events_total[10m]) == 0
      )
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "Telemetry flow from Hybrid Coordinator to AIDB broken"
      description: "Hybrid Coordinator is generating telemetry but AIDB is not receiving it"
```

### SLO Dashboard Configuration

#### Grafana Dashboard Panels
Create Grafana panels to visualize SLO compliance:

```json
{
  "dashboard": {
    "title": "AI Stack SLO Dashboard",
    "panels": [
      {
        "id": 1,
        "title": "Availability (Target: 99.9%)",
        "type": "gauge",
        "targets": [
          {
            "expr": "100 * (sum(rate(health_check_total{status=\"healthy\"}[5m])) / sum(rate(health_check_total[5m])))",
            "legendFormat": "Current Availability"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "thresholds": {
              "steps": [
                {"value": 0, "color": "red"},
                {"value": 99.9, "color": "green"}
              ]
            },
            "unit": "percent"
          }
        }
      },
      {
        "id": 2,
        "title": "95th Percentile Latency (Target: <500ms)",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(ai_stack_request_duration_seconds_bucket[5m]))",
            "legendFormat": "{{service}}"
          }
        ],
        "yaxes": [{"format": "s"}]
      },
      {
        "id": 3,
        "title": "Error Rate (Target: <1%)",
        "type": "graph",
        "targets": [
          {
            "expr": "100 * (sum(rate(ai_stack_requests_total{status=~\"5..\"}[5m])) / sum(rate(ai_stack_requests_total[5m])))",
            "legendFormat": "Error Rate"
          }
        ],
        "yaxes": [{"format": "percent"}]
      }
    ]
  }
}
```

### SLO Reporting

#### Monthly SLO Reports
Generate monthly SLO compliance reports:

```bash
#!/bin/bash
# scripts/generate-slo-report.sh

# Calculate availability for the month
AVAILABILITY=$(curl -s "http://prometheus:9090/api/v1/query?query=100%20*%20(sum(rate(health_check_total{status=%22healthy%22}[5m]))%20/%20sum(rate(health_check_total[5m])))&time=$(date%20-d%20'last%20month'%20+%s)")

# Calculate error rate for the month
ERROR_RATE=$(curl -s "http://prometheus:9090/api/v1/query?query=100%20*%20(sum(rate(ai_stack_requests_total{status=~%225..%22}[5m]))%20/%20sum(rate(ai_stack_requests_total[5m])))&time=$(date%20-d%20'last%20month'%20+%s)")

# Calculate latency for the month
LATENCY_95TH=$(curl -s "http://prometheus:9090/api/v1/query?query=histogram_quantile(0.95,%20rate(ai_stack_request_duration_seconds_bucket[5m]))&time=$(date%20-d%20'last%20month'%20+%s)")

echo "AI Stack SLO Report - $(date -d 'last month' +%B\ %Y)"
echo "=================================================="
echo "Availability: $AVAILABILITY% (Target: 99.9%)"
echo "Error Rate: $ERROR_RATE% (Target: <1%)"
echo "95th Percentile Latency: $LATENCY_95TH s (Target: <0.5s)"
```

### Alert Configuration

#### Alertmanager Configuration
Configure Alertmanager to route AI stack alerts appropriately:

```yaml
# File: ai-stack/monitoring/alertmanager/config.yml
route:
  group_by: ['alertname', 'service']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 12h
  receiver: 'default'
  routes:
  - matchers:
    - alertname =~ "High.*|.*Unreachable"
    receiver: 'critical'
    group_wait: 10s
    group_interval: 1m
  - matchers:
    - alertname =~ ".*ErrorRate.*"
    receiver: 'errors'
    group_wait: 30s
    group_interval: 3m

receivers:
- name: 'default'
  webhook_configs:
  - url: 'http://notification-service:8080/webhook'
- name: 'critical'
  webhook_configs:
  - url: 'http://notification-service:8080/webhook/critical'
  email_configs:
  - to: 'oncall@company.com'
- name: 'errors'
  webhook_configs:
  - url: 'http://notification-service:8080/webhook/errors'
```

This provides comprehensive Prometheus rules for monitoring AI stack SLOs.