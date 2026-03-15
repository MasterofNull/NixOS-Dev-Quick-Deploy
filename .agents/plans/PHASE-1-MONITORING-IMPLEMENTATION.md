# Phase 1: Comprehensive Monitoring Implementation

**Parent Roadmap:** NEXT-GEN-AGENTIC-ROADMAP-2026-03.md
**Status:** In Progress
**Created:** 2026-03-15
**Target Completion:** Week 1-2

---

## Current State Assessment

### ✅ Already Implemented

**Metrics Collection:**
- Prometheus metrics in hybrid-coordinator ([metrics.py](ai-stack/mcp-servers/hybrid-coordinator/metrics.py))
- Counters: requests, errors, route decisions, backend selections
- Histograms: request latency, backend latency
- Gauges: memory usage, cache size

**Visualization:**
- Grafana dashboards configured ([monitoring.nix](nix/modules/services/monitoring.nix))
- GPU utilization, VRAM usage, system RAM
- Embedding cache hit rate
- LLM routing split

**Distributed Tracing:**
- Tempo configured for OTLP ingestion
- Trace storage with local backend
- Metrics generator integration

**System Metrics:**
- Node exporter for system-level metrics
- Textfile collector for custom metrics

### ❌ Gaps Identified

**AI-Specific Metrics:**
- No token usage tracking per endpoint
- No quality score metrics (hint quality, delegation success)
- No cost tracking (API calls, token costs)
- No user interaction metrics

**Logging:**
- No centralized log aggregation
- No structured logging across services
- No log-based alerting

**Alerting:**
- No automated alert rules
- No anomaly detection
- No degraded performance alerts
- No quality regression alerts

**Request Tracing:**
- No request ID propagation
- No cross-service trace correlation
- No trace visualization UI

**Dashboards:**
- Missing: Token usage dashboard
- Missing: Quality metrics dashboard
- Missing: Cost tracking dashboard
- Missing: Real-time health dashboard

---

## Batch 1.1: Unified Metrics Pipeline

**Objective:** Complete AI-specific metric instrumentation and create comprehensive dashboards.

**Status:** pending

### Tasks

#### 1.1.1: AI-Specific Metrics Instrumentation

**File:** `ai-stack/mcp-servers/hybrid-coordinator/metrics.py`

Add metrics:
```python
# Token usage tracking
TOKEN_USAGE_TOTAL = Counter(
    "hybrid_token_usage_total",
    "Total tokens used by endpoint",
    ["endpoint", "model", "direction"]  # direction: input/output
)

TOKEN_COST_USD = Counter(
    "hybrid_token_cost_usd_total",
    "Total token cost in USD",
    ["endpoint", "model"]
)

# Quality metrics
HINT_QUALITY_SCORE = Histogram(
    "hybrid_hint_quality_score",
    "Hint quality score distribution",
    ["hint_id"],
    buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
)

DELEGATION_SUCCESS_RATE = Gauge(
    "hybrid_delegation_success_rate",
    "Delegation success rate (rolling window)",
    ["provider"]
)

QUERY_COMPLETION_QUALITY = Histogram(
    "hybrid_query_completion_quality",
    "Query completion quality score",
    buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
)

# User interaction metrics
USER_FEEDBACK_SCORE = Histogram(
    "hybrid_user_feedback_score",
    "User feedback scores",
    ["endpoint"],
    buckets=[-1.0, -0.5, 0.0, 0.5, 1.0]
)

HINT_ADOPTION_RATE = Gauge(
    "hybrid_hint_adoption_rate",
    "Hint adoption rate (rolling window)"
)

# Cost tracking
API_CALL_COST_USD = Counter(
    "hybrid_api_call_cost_usd_total",
    "Total API call cost in USD",
    ["provider", "model"]
)

FREE_AGENT_USAGE_PCT = Gauge(
    "hybrid_free_agent_usage_percentage",
    "Percentage of requests routed to free agents"
)
```

**Integration Points:**
- [ ] Add token counting to query handler
- [ ] Instrument hint quality scoring
- [ ] Track delegation success/failure
- [ ] Record API call costs
- [ ] Track free vs. paid agent routing

**Files to Modify:**
- `ai-stack/mcp-servers/hybrid-coordinator/http_server.py` (query handling)
- `ai-stack/mcp-servers/hybrid-coordinator/hints_engine.py` (quality tracking)
- `ai-stack/mcp-servers/hybrid-coordinator/delegation.py` (if exists)

#### 1.1.2: Grafana Dashboard Creation

**Create Dashboard:** `ai-stack-ai-metrics.json`

**Panels:**

1. **Token Usage (Top Row)**
   - Total tokens/hour (input vs output)
   - Token cost/hour by model
   - Tokens per endpoint

2. **Quality Metrics (Second Row)**
   - Average hint quality score
   - Delegation success rate by provider
   - Query completion quality histogram

3. **Cost Tracking (Third Row)**
   - Total cost/day
   - Cost breakdown by provider
   - Free agent usage percentage

4. **User Experience (Fourth Row)**
   - User feedback scores
   - Hint adoption rate
   - Average response latency by quality tier

5. **System Health (Fifth Row)**
   - Request success rate
   - Error rate by endpoint
   - P95/P99 latency

**Implementation:**
```bash
# Create dashboard JSON
cat > nix/modules/services/dashboards/ai-metrics.json <<'EOF'
{
  "title": "AI Stack - AI Metrics",
  "uid": "ai-metrics",
  "panels": [...]
}
EOF
```

**Add to monitoring.nix:**
```nix
services.grafana.provision.dashboards.settings.providers = [
  {
    name = "AI Metrics";
    options.path = ./dashboards/ai-metrics.json;
  }
];
```

#### 1.1.3: Real-Time Metrics Dashboard

**Create:** `dashboard/frontend/src/pages/MetricsLive.tsx`

**Features:**
- Live token usage counter (updates every second)
- Quality score real-time chart
- Cost meter (running total)
- Free agent usage percentage
- Recent requests list with quality scores

**Backend Endpoint:**
- `GET /metrics/live` → WebSocket or SSE for real-time updates
- Returns: current token/s, cost/s, quality avg, free agent %

#### 1.1.4: Custom Textfile Metrics

**Create:** `scripts/observability/collect-ai-custom-metrics.sh`

```bash
#!/usr/bin/env bash
# Collect AI-specific metrics for Prometheus textfile collector

METRICS_FILE="/var/lib/node_exporter/textfile_collector/ai_custom.prom"

# Model file sizes
llama_model_size=$(stat -f%z ~/.local/share/models/*.gguf 2>/dev/null || echo 0)
embedding_model_size=$(stat -f%z ~/.local/share/models/embed/*.gguf 2>/dev/null || echo 0)

# Lesson count
lesson_count=$(find ai-stack/lessons -name "*.md" 2>/dev/null | wc -l)

# Skill count
skill_count=$(curl -sS http://127.0.0.1:8003/control/ai-coordinator/skills 2>/dev/null | jq -r '.skill_count // 0')

# Pattern library size
pattern_count=$(scripts/ai/aq-patterns stats --format json 2>/dev/null | jq -r '.total_patterns // 0')

cat > "$METRICS_FILE" <<EOF
# HELP ai_model_file_bytes Model file size in bytes
# TYPE ai_model_file_bytes gauge
ai_model_file_bytes{model="llama"} $llama_model_size
ai_model_file_bytes{model="embedding"} $embedding_model_size

# HELP ai_lesson_count Total number of lessons
# TYPE ai_lesson_count gauge
ai_lesson_count $lesson_count

# HELP ai_skill_count Total number of skills
# TYPE ai_skill_count gauge
ai_skill_count $skill_count

# HELP ai_pattern_library_size Pattern library size
# TYPE ai_pattern_library_size gauge
ai_pattern_library_size $pattern_count
EOF
```

**Systemd Timer:**
```nix
systemd.timers.ai-custom-metrics = {
  wantedBy = [ "timers.target" ];
  timerConfig = {
    OnBootSec = "1min";
    OnUnitActiveSec = "5min";
  };
};

systemd.services.ai-custom-metrics = {
  script = "${pkgs.bash}/bin/bash ${./scripts/observability/collect-ai-custom-metrics.sh}";
  serviceConfig.Type = "oneshot";
};
```

---

## Batch 1.2: Automated Anomaly Detection

**Objective:** Implement automated detection and alerting for performance and quality degradation.

**Status:** pending

### Tasks

#### 1.2.1: Statistical Anomaly Detection

**Create:** `ai-stack/observability/anomaly_detector.py`

```python
from prometheus_api_client import PrometheusConnect
import numpy as np
from typing import List, Dict, Any

class AnomalyDetector:
    def __init__(self, prometheus_url: str = "http://127.0.0.1:9090"):
        self.prom = PrometheusConnect(url=prometheus_url)
        self.baselines = {}

    def establish_baseline(self, metric: str, window: str = "7d"):
        """Establish statistical baseline for a metric."""
        data = self.prom.custom_query_range(
            query=metric,
            start_time=f"-{window}",
            end_time="now",
            step="5m"
        )
        values = [float(point[1]) for result in data for point in result["values"]]

        self.baselines[metric] = {
            "mean": np.mean(values),
            "std": np.std(values),
            "p95": np.percentile(values, 95),
            "p99": np.percentile(values, 99)
        }

    def detect_anomaly(self, metric: str, current_value: float, threshold: float = 3.0) -> Dict[str, Any]:
        """Detect anomaly using z-score."""
        if metric not in self.baselines:
            self.establish_baseline(metric)

        baseline = self.baselines[metric]
        z_score = (current_value - baseline["mean"]) / (baseline["std"] + 1e-9)

        is_anomaly = abs(z_score) > threshold

        return {
            "is_anomaly": is_anomaly,
            "z_score": z_score,
            "current_value": current_value,
            "baseline_mean": baseline["mean"],
            "baseline_std": baseline["std"],
            "severity": "critical" if abs(z_score) > 5 else "warning" if abs(z_score) > 3 else "normal"
        }

    def check_metrics(self) -> List[Dict[str, Any]]:
        """Check all monitored metrics for anomalies."""
        metrics_to_monitor = [
            "rate(hybrid_requests_total[5m])",
            "histogram_quantile(0.95, rate(hybrid_request_latency_seconds_bucket[5m]))",
            "sum(rate(hybrid_token_usage_total[5m]))",
            "hybrid_delegation_success_rate",
            "hybrid_hint_quality_score"
        ]

        anomalies = []
        for metric in metrics_to_monitor:
            result = self.prom.custom_query(query=metric)
            if result:
                value = float(result[0]["value"][1])
                anomaly_result = self.detect_anomaly(metric, value)
                if anomaly_result["is_anomaly"]:
                    anomaly_result["metric"] = metric
                    anomalies.append(anomaly_result)

        return anomalies
```

**Integration:**
- [ ] Create systemd service for continuous monitoring
- [ ] Add alert generation on anomaly detection
- [ ] Integrate with notification system (email, Slack, etc.)

#### 1.2.2: Prometheus Alert Rules

**Create:** `nix/modules/services/prometheus-alerts.nix`

```nix
{ config, ... }:
{
  services.prometheus.rules = [
    ''
      groups:
        - name: ai_stack_alerts
          interval: 30s
          rules:
            # High error rate
            - alert: HighErrorRate
              expr: rate(hybrid_request_errors_total[5m]) > 0.05
              for: 2m
              labels:
                severity: warning
              annotations:
                summary: "High error rate detected"
                description: "Error rate is {{ $value }} errors/sec"

            # High latency
            - alert: HighLatency
              expr: histogram_quantile(0.95, rate(hybrid_request_latency_seconds_bucket[5m])) > 5.0
              for: 3m
              labels:
                severity: warning
              annotations:
                summary: "High request latency detected"
                description: "P95 latency is {{ $value }} seconds"

            # Low quality scores
            - alert: LowHintQuality
              expr: avg_over_time(hybrid_hint_quality_score[10m]) < 0.6
              for: 5m
              labels:
                severity: warning
              annotations:
                summary: "Low hint quality detected"
                description: "Average hint quality is {{ $value }}"

            # Low delegation success
            - alert: LowDelegationSuccess
              expr: hybrid_delegation_success_rate < 0.8
              for: 5m
              labels:
                severity: critical
              annotations:
                summary: "Low delegation success rate"
                description: "Delegation success rate is {{ $value }}"

            # High token cost
            - alert: HighTokenCost
              expr: rate(hybrid_token_cost_usd_total[1h]) > 1.0
              for: 10m
              labels:
                severity: warning
              annotations:
                summary: "High token cost detected"
                description: "Token cost is ${{ $value }}/hour"

            # Memory usage high
            - alert: HighMemoryUsage
              expr: hybrid_process_memory_bytes > 4e9
              for: 5m
              labels:
                severity: warning
              annotations:
                summary: "High memory usage"
                description: "Memory usage is {{ $value | humanize }}B"
    ''
  ];
}
```

#### 1.2.3: Auto-Remediation Triggers

**Create:** `scripts/observability/auto-remediate.sh`

```bash
#!/usr/bin/env bash
# Auto-remediation for common issues

ISSUE_TYPE="$1"

case "$ISSUE_TYPE" in
  high_memory)
    echo "Restarting hybrid-coordinator to free memory..."
    sudo systemctl restart ai-hybrid-coordinator.service
    ;;

  high_error_rate)
    echo "Clearing caches and restarting services..."
    redis-cli FLUSHDB
    sudo systemctl restart ai-hybrid-coordinator.service
    ;;

  low_quality)
    echo "Refreshing hint patterns and quality models..."
    scripts/ai/aq-patterns extract --min-occurrences 5
    sudo systemctl reload ai-hybrid-coordinator.service
    ;;

  *)
    echo "Unknown issue type: $ISSUE_TYPE"
    exit 1
    ;;
esac
```

**Alertmanager Integration:**
```yaml
receivers:
  - name: 'auto-remediate'
    webhook_configs:
      - url: 'http://127.0.0.1:9093/webhook'
        send_resolved: true

route:
  receiver: 'auto-remediate'
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  routes:
    - match:
        severity: critical
      receiver: 'auto-remediate'
```

---

## Batch 1.3: Performance Profiling & Bottleneck Detection

**Objective:** Continuous performance profiling with automatic bottleneck identification.

**Status:** pending

### Tasks

#### 1.3.1: Continuous Profiling

**Use:** `py-spy` for Python services

```bash
# Install
nix-shell -p py-spy

# Profile hybrid-coordinator
sudo py-spy record --pid $(pgrep -f hybrid-coordinator) --output profile.svg --duration 60

# Convert to flamegraph
py-spy top --pid $(pgrep -f hybrid-coordinator)
```

**Systemd Service:**
```nix
systemd.services.ai-profiling = {
  description = "AI Stack Continuous Profiling";
  script = ''
    while true; do
      ${pkgs.py-spy}/bin/py-spy record \
        --pid $(${pkgs.procps}/bin/pgrep -f hybrid-coordinator) \
        --output /var/lib/profiling/profile-$(date +%s).svg \
        --duration 300
      sleep 3600  # Profile every hour
    done
  '';
  wantedBy = [ "multi-user.target" ];
};
```

#### 1.3.2: Bottleneck Detection

**Create:** `ai-stack/observability/bottleneck_detector.py`

```python
import json
from pathlib import Path
from typing import List, Dict, Any

def analyze_profile(profile_file: Path) -> Dict[str, Any]:
    """Analyze flamegraph data to identify bottlenecks."""
    # Parse SVG flamegraph or use py-spy JSON output
    # Identify:
    # - Functions consuming >10% CPU time
    # - Blocking I/O operations
    # - Lock contention
    # - Memory allocation hotspots

    bottlenecks = []

    # Example: Parse py-spy JSON output
    with open(profile_file) as f:
        data = json.load(f)

    for frame in data.get("frames", []):
        if frame.get("cpu_percent", 0) > 10:
            bottlenecks.append({
                "function": frame["name"],
                "cpu_percent": frame["cpu_percent"],
                "line": frame.get("line"),
                "file": frame.get("filename")
            })

    return {
        "bottlenecks": sorted(bottlenecks, key=lambda x: x["cpu_percent"], reverse=True),
        "total_cpu_time": sum(b["cpu_percent"] for b in bottlenecks)
    }

def generate_optimization_recommendations(bottlenecks: List[Dict]) -> List[str]:
    """Generate actionable optimization recommendations."""
    recommendations = []

    for bottleneck in bottlenecks[:5]:  # Top 5
        func = bottleneck["function"]
        cpu = bottleneck["cpu_percent"]

        if "json.loads" in func or "json.dumps" in func:
            recommendations.append(f"Use orjson instead of json for {cpu:.1f}% speedup")

        if "requests." in func:
            recommendations.append(f"Use httpx with connection pooling for {cpu:.1f}% improvement")

        if "embedding" in func.lower():
            recommendations.append(f"Batch embedding calls to reduce {cpu:.1f}% overhead")

        if "database" in func.lower() or "query" in func.lower():
            recommendations.append(f"Add database query caching for {cpu:.1f}% reduction")

    return recommendations
```

#### 1.3.3: A/B Testing Framework

**Create:** `ai-stack/observability/ab_testing.py`

```python
import random
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

@dataclass
class ABTest:
    name: str
    variant_a: str
    variant_b: str
    split_ratio: float = 0.5
    started_at: datetime = None

class ABTestManager:
    def __init__(self):
        self.active_tests: Dict[str, ABTest] = {}
        self.results: Dict[str, Dict[str, Any]] = {}

    def create_test(self, name: str, variant_a: str, variant_b: str, split_ratio: float = 0.5):
        """Create a new A/B test."""
        self.active_tests[name] = ABTest(
            name=name,
            variant_a=variant_a,
            variant_b=variant_b,
            split_ratio=split_ratio,
            started_at=datetime.now()
        )

    def assign_variant(self, test_name: str, user_id: Optional[str] = None) -> str:
        """Assign a variant to a user."""
        test = self.active_tests.get(test_name)
        if not test:
            return None

        # Consistent assignment based on user_id hash
        if user_id:
            hash_val = hash(user_id)
            if hash_val % 100 < (test.split_ratio * 100):
                return test.variant_a
            return test.variant_b

        # Random assignment
        return test.variant_a if random.random() < test.split_ratio else test.variant_b

    def record_result(self, test_name: str, variant: str, metric: str, value: float):
        """Record A/B test result."""
        if test_name not in self.results:
            self.results[test_name] = {
                "variant_a": [],
                "variant_b": []
            }

        self.results[test_name][variant].append({
            "metric": metric,
            "value": value,
            "timestamp": datetime.now().isoformat()
        })

    def analyze_test(self, test_name: str) -> Dict[str, Any]:
        """Analyze A/B test results with statistical significance."""
        results = self.results.get(test_name, {})

        # Calculate statistics for each variant
        # Use t-test for significance
        from scipy import stats

        variant_a_values = [r["value"] for r in results.get("variant_a", [])]
        variant_b_values = [r["value"] for r in results.get("variant_b", [])]

        if not variant_a_values or not variant_b_values:
            return {"error": "Insufficient data"}

        t_stat, p_value = stats.ttest_ind(variant_a_values, variant_b_values)

        return {
            "variant_a_mean": sum(variant_a_values) / len(variant_a_values),
            "variant_b_mean": sum(variant_b_values) / len(variant_b_values),
            "t_statistic": t_stat,
            "p_value": p_value,
            "significant": p_value < 0.05,
            "winner": "variant_a" if sum(variant_a_values) > sum(variant_b_values) else "variant_b"
        }
```

---

## Validation Checklist

### Batch 1.1
- [ ] All AI-specific metrics instrumented
- [ ] Grafana dashboard shows real-time token usage
- [ ] Cost tracking operational
- [ ] Quality metrics visible
- [ ] Custom metrics collected

### Batch 1.2
- [ ] Anomaly detection running
- [ ] Alert rules configured
- [ ] Auto-remediation tested
- [ ] Alerts firing correctly
- [ ] Notification system working

### Batch 1.3
- [ ] Profiling service running
- [ ] Bottleneck reports generated
- [ ] Optimization recommendations generated
- [ ] A/B testing framework operational
- [ ] Performance improvements validated

---

## Success Metrics

| Metric | Target | Validation |
|--------|--------|------------|
| Metrics coverage | 100% of endpoints | Check Grafana dashboards |
| Alert response time | <5 minutes | Test alert triggers |
| Anomaly detection accuracy | >90% | Review false positive rate |
| Profiling overhead | <5% | Compare with/without profiling |
| Dashboard load time | <2 seconds | Measure page load |

---

## Next Steps

1. Begin Batch 1.1 implementation
2. Test AI-specific metrics on staging
3. Deploy Grafana dashboards
4. Validate metrics collection
5. Move to Batch 1.2
