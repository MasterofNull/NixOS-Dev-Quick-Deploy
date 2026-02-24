# End-to-End Telemetry Flow Verification

## Ralph → Hybrid → AIDB Telemetry Flow Validation

This document provides procedures for verifying the complete telemetry flow from Ralph Wiggum through Hybrid Coordinator to AIDB.

### Telemetry Flow Architecture

#### Data Flow Path
```
Ralph Wiggum Loop → Hybrid Coordinator → AIDB MCP Server → PostgreSQL/Redis/Qdrant
      ↓                    ↓                    ↓                ↓
Telemetry Events → Learning Pipeline → Telemetry Processing → Storage & Analysis
```

#### Component Roles
1. **Ralph Wiggum**: Generates task completion and iteration telemetry
2. **Hybrid Coordinator**: Processes and forwards telemetry, extracts patterns
3. **AIDB**: Stores and analyzes telemetry, provides query interface

### Telemetry Event Schema

#### Ralph Wiggum Events
```json
{
  "event": "task_completed",
  "task_id": "uuid",
  "prompt": "string",
  "backend": "string",
  "iterations_used": "integer",
  "max_iterations_allowed": "integer",
  "status": "success|failure|cancelled",
  "start_time": "ISO8601",
  "end_time": "ISO8601",
  "duration_seconds": "float",
  "adaptive_limit_used": "integer",
  "complexity_score": "float",
  "history_adjustment": "float",
  "task": {
    "type": "string",
    "complexity": "simple|default|complex",
    "estimated_iterations": "integer"
  },
  "timestamp": "ISO8601"
}
```

#### Hybrid Coordinator Events
```json
{
  "event_type": "interaction_recorded",
  "source": "ralph-wiggum",
  "interaction_id": "uuid",
  "query": "string",
  "response": "string",
  "input_tokens": "integer",
  "output_tokens": "integer",
  "processing_time_ms": "float",
  "value_score": "float",
  "collections_used": ["array of strings"],
  "llm_used": "local|remote",
  "model": "string",
  "cache_hit": "boolean",
  "rag_hits": "integer",
  "tokens_saved": "integer",
  "metadata": {
    "ralph_task_id": "uuid",
    "backend_used": "string",
    "iterations_used": "integer"
  },
  "timestamp": "ISO8601"
}
```

#### AIDB Telemetry Events
```json
{
  "source": "hybrid-coordinator",
  "event_type": "query_processed",
  "llm_used": "local|remote",
  "tokens_saved": "integer",
  "rag_hits": "integer",
  "collections_used": ["array of strings"],
  "model": "string",
  "latency_ms": "float",
  "cache_hit": "boolean",
  "metadata": {
    "query": "string",
    "response_length": "integer",
    "processing_stage": "string"
  },
  "created_at": "ISO8601"
}
```

### Verification Procedures

#### 1. Manual Telemetry Test
Execute a complete flow to verify telemetry:

```bash
# Step 1: Submit a task to Ralph Wiggum
TASK_ID=$(curl -s -X POST http://ralph-wiggum:8098/tasks \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $(cat /run/secrets/ralph-wiggum-api-key)" \
  -d '{
    "prompt": "Test telemetry flow verification",
    "backend": "aider",
    "max_iterations": 5
  }' | jq -r '.task_id')

echo "Submitted task: $TASK_ID"

# Step 2: Wait for task completion
while true; do
  STATUS=$(curl -s -H "X-API-Key: $(cat /run/secrets/ralph-wiggum-api-key)" \
    "http://ralph-wiggum:8098/tasks/$TASK_ID" | jq -r '.status')
  
  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
    echo "Task $TASK_ID completed with status: $STATUS"
    break
  fi
  
  sleep 2
done

# Step 3: Verify telemetry in Hybrid Coordinator
echo "Checking Hybrid Coordinator telemetry..."
curl -s -H "X-API-Key: $(cat /run/secrets/hybrid-coordinator-api-key)" \
  "http://hybrid-coordinator:8092/telemetry/summary"

# Step 4: Verify telemetry in AIDB
echo "Checking AIDB telemetry..."
curl -s -H "X-API-Key: $(cat /run/secrets/aidb-api-key)" \
  "http://aidb:8091/telemetry/summary"
```

#### 2. Automated Verification Script
Create a script to verify the complete flow:

```bash
#!/bin/bash
# scripts/verify-telemetry-flow.sh

set -e

echo "Starting end-to-end telemetry flow verification..."

# Configuration
RALPH_URL=${RALPH_URL:-"http://ralph-wiggum:8098"}
HYBRID_URL=${HYBRID_URL:-"http://hybrid-coordinator:8092"}
AIDB_URL=${AIDB_URL:-"http://aidb:8091"}

# Get API keys
RALPH_API_KEY=$(cat /run/secrets/ralph-wiggum-api-key 2>/dev/null || echo "")
HYBRID_API_KEY=$(cat /run/secrets/hybrid-coordinator-api-key 2>/dev/null || echo "")
AIDB_API_KEY=$(cat /run/secrets/aidb-api-key 2>/dev/null || echo "")

# Headers
RALPH_HEADER=""
HYBRID_HEADER=""
AIDB_HEADER=""

if [ ! -z "$RALPH_API_KEY" ]; then
  RALPH_HEADER="-H X-API-Key: $RALPH_API_KEY"
fi
if [ ! -z "$HYBRID_API_KEY" ]; then
  HYBRID_HEADER="-H X-API-Key: $HYBRID_API_KEY"
fi
if [ ! -z "$AIDB_API_KEY" ]; then
  AIDB_HEADER="-H X-API-Key: $AIDB_API_KEY"
fi

# Get telemetry counts before test
echo "Getting initial telemetry counts..."
INITIAL_RALPH_EVENTS=$(curl -s $RALPH_HEADER "$RALPH_URL/stats" | jq -r '.total_tasks_submitted // 0')
INITIAL_HYBRID_EVENTS=$(curl -s $HYBRID_HEADER "$HYBRID_URL/telemetry/summary" | jq -r '.total_events // 0')
INITIAL_AIDB_EVENTS=$(curl -s $AIDB_HEADER "$AIDB_URL/telemetry/summary" | jq -r '.total_events // 0')

echo "Initial counts - Ralph: $INITIAL_RALPH_EVENTS, Hybrid: $INITIAL_HYBRID_EVENTS, AIDB: $INITIAL_AIDB_EVENTS"

# Submit a test task
TEST_PROMPT="Telemetry verification test $(date +%s)"
TASK_ID=$(curl -s -X POST $RALPH_HEADER "$RALPH_URL/tasks" \
  -H "Content-Type: application/json" \
  -d "{\"prompt\": \"$TEST_PROMPT\", \"backend\": \"aider\", \"max_iterations\": 2}" | jq -r '.task_id')

if [ "$TASK_ID" = "null" ] || [ -z "$TASK_ID" ]; then
  echo "❌ Failed to submit task to Ralph Wiggum"
  exit 1
fi

echo "Submitted test task: $TASK_ID"

# Wait for task completion (with timeout)
TIMEOUT=60
ELAPSED=0
while [ $ELAPSED -lt $TIMEOUT ]; do
  TASK_STATUS=$(curl -s $RALPH_HEADER "$RALPH_URL/tasks/$TASK_ID" | jq -r '.status')
  
  if [ "$TASK_STATUS" = "completed" ] || [ "$TASK_STATUS" = "failed" ]; then
    echo "Task $TASK_ID reached final state: $TASK_STATUS"
    break
  fi
  
  sleep 2
  ELAPSED=$((ELAPSED + 2))
done

if [ $ELAPSED -ge $TIMEOUT ]; then
  echo "⚠️ Task $TASK_ID did not complete within timeout, continuing with verification..."
fi

# Wait a bit more for telemetry to propagate
sleep 5

# Get telemetry counts after test
FINAL_RALPH_EVENTS=$(curl -s $RALPH_HEADER "$RALPH_URL/stats" | jq -r '.total_tasks_submitted // 0')
FINAL_HYBRID_EVENTS=$(curl -s $HYBRID_HEADER "$HYBRID_URL/telemetry/summary" | jq -r '.total_events // 0')
FINAL_AIDB_EVENTS=$(curl -s $AIDB_HEADER "$AIDB_URL/telemetry/summary" | jq -r '.total_events // 0')

echo "Final counts - Ralph: $FINAL_RALPH_EVENTS, Hybrid: $FINAL_HYBRID_EVENTS, AIDB: $FINAL_AIDB_EVENTS"

# Verify flow
SUCCESS=true

if [ $FINAL_RALPH_EVENTS -le $INITIAL_RALPH_EVENTS ]; then
  echo "❌ Ralph events did not increase"
  SUCCESS=false
else
  echo "✅ Ralph events increased ($INITIAL_RALPH_EVENTS → $FINAL_RALPH_EVENTS)"
fi

if [ $FINAL_HYBRID_EVENTS -le $INITIAL_HYBRID_EVENTS ]; then
  echo "❌ Hybrid events did not increase"
  SUCCESS=false
else
  echo "✅ Hybrid events increased ($INITIAL_HYBRID_EVENTS → $FINAL_HYBRID_EVENTS)"
fi

if [ $FINAL_AIDB_EVENTS -le $INITIAL_AIDB_EVENTS ]; then
  echo "❌ AIDB events did not increase"
  SUCCESS=false
else
  echo "✅ AIDB events increased ($INITIAL_AIDB_EVENTS → $FINAL_AIDB_EVENTS)"
fi

if [ "$SUCCESS" = true ]; then
  echo "🎉 End-to-end telemetry flow verification PASSED"
  echo "Telemetry successfully flowed from Ralph → Hybrid → AIDB"
else
  echo "💥 End-to-end telemetry flow verification FAILED"
  exit 1
fi

# Additional verification: Check for specific event patterns
echo "Checking for specific telemetry patterns..."

# Look for events related to our test task
RALPH_TASK_FOUND=$(curl -s $RALPH_HEADER "$RALPH_URL/stats" | jq -r ".recent_tasks[]?.task_id" | grep -c "$TASK_ID" || echo "0")

if [ "$RALPH_TASK_FOUND" -gt 0 ]; then
  echo "✅ Found test task in Ralph statistics"
else
  echo "⚠️ Test task not found in Ralph statistics (may be expected for quick tasks)"
fi

echo "Telemetry flow verification completed successfully!"
```

#### 3. Continuous Monitoring
Set up continuous monitoring of the telemetry flow:

```bash
#!/bin/bash
# scripts/monitor-telemetry-flow.sh

# Continuously monitor the telemetry flow
while true; do
  # Check if all services are reachable
  RALPH_HEALTH=$(curl -sf http://ralph-wiggum:8098/health | jq -r '.status' 2>/dev/null || echo "unreachable")
  HYBRID_HEALTH=$(curl -sf http://hybrid-coordinator:8092/health | jq -r '.status' 2>/dev/null || echo "unreachable")
  AIDB_HEALTH=$(curl -sf http://aidb:8091/health | jq -r '.status' 2>/dev/null || echo "unreachable")
  
  if [ "$RALPH_HEALTH" != "healthy" ] || [ "$HYBRID_HEALTH" != "healthy" ] || [ "$AIDB_HEALTH" != "healthy" ]; then
    echo "$(date): Service health issue - Ralph: $RALPH_HEALTH, Hybrid: $HYBRID_HEALTH, AIDB: $AIDB_HEALTH"
  fi
  
  # Check telemetry event rates
  RALPH_RATE=$(curl -s http://ralph-wiggum:8098/stats 2>/dev/null | jq -r '.tasks_per_minute // 0' 2>/dev/null || echo "0")
  HYBRID_RATE=$(curl -s http://hybrid-coordinator:8092/telemetry/summary 2>/dev/null | jq -r '.events_per_minute // 0' 2>/dev/null || echo "0")
  AIDB_RATE=$(curl -s http://aidb:8091/telemetry/summary 2>/dev/null | jq -r '.events_per_minute // 0' 2>/dev/null || echo "0")
  
  # Log rates
  echo "$(date): Event rates - Ralph: $RALPH_RATE/min, Hybrid: $HYBRID_RATE/min, AIDB: $AIDB_RATE/min"
  
  # Check for flow disruptions
  if (( $(echo "$RALPH_RATE > 0" | bc -l) )) && (( $(echo "$HYBRID_RATE == 0" | bc -l) )); then
    echo "$(date): ALERT - Ralph generating events but Hybrid not receiving them"
  fi
  
  if (( $(echo "$HYBRID_RATE > 0" | bc -l) )) && (( $(echo "$AIDB_RATE == 0" | bc -l) )); then
    echo "$(date): ALERT - Hybrid generating events but AIDB not receiving them"
  fi
  
  sleep 30
done
```

### Prometheus Monitoring

#### Telemetry Flow Metrics
Add these metrics to monitor the flow:

```yaml
# File: ai-stack/monitoring/prometheus/rules/telemetry-flow.yml
groups:
- name: telemetry.flow
  rules:
  - alert: TelemetryFlowDisrupted
    expr: |
      (
        rate(raph_tasks_completed_total[5m]) > 0
      ) and (
        rate(hybrid_telemetry_events_total[5m]) == 0
      ) and (
        rate(aidb_telemetry_events_total[5m]) == 0
      )
    for: 2m
    labels:
      severity: critical
    annotations:
      summary: "Telemetry flow disruption detected"
      description: "Ralph is completing tasks but telemetry is not flowing to Hybrid/AIDB"

  - alert: TelemetryFlowLatencyHigh
    expr: |
      histogram_quantile(0.95, rate(telemetry_processing_duration_seconds_bucket[5m])) > 30
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High telemetry processing latency"
      description: "95th percentile telemetry processing time is {{ $value }}s, above 30s threshold"

  - alert: TelemetryEventLoss
    expr: |
      (
        increase(raph_tasks_completed_total[10m])
      ) > (
        increase(aidb_telemetry_events_total[10m]) * 1.1
      )
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "Potential telemetry event loss"
      description: "More tasks completed than telemetry events recorded, suggesting event loss"
```

### Troubleshooting Telemetry Issues

#### Common Issues and Solutions

1. **No Events Flowing**:
   - Check service connectivity
   - Verify API keys and authentication
   - Review service logs

2. **Delayed Events**:
   - Check network connectivity
   - Verify buffer sizes
   - Review processing performance

3. **Event Loss**:
   - Check buffer overflow
   - Verify storage capacity
   - Review error handling

#### Diagnostic Commands
```bash
# Check Ralph Wiggum events
kubectl logs -n ai-stack deployment/ralph-wiggum | grep -i telemetry

# Check Hybrid Coordinator events
kubectl logs -n ai-stack deployment/hybrid-coordinator | grep -i telemetry

# Check AIDB events
kubectl logs -n ai-stack deployment/aidb | grep -i telemetry

# Verify event counts
curl -H "X-API-Key: $API_KEY" http://aidb:8091/telemetry/summary | jq '.'

# Check PostgreSQL telemetry table
kubectl exec -n ai-stack deployment/postgres -- psql -U mcp -d mcp -c "SELECT COUNT(*) FROM telemetry_events;"
```

This provides comprehensive verification for the end-to-end telemetry flow.