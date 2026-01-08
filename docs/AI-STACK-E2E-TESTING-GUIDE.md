# AI Stack End-to-End Testing Guide

**Created**: January 2, 2026
**Purpose**: Comprehensive testing framework for validating all AI stack features and workflows

## Overview

This testing framework exercises every component of the AI stack in a real-world scenario, ensuring:
- All services are communicating correctly
- Data flows properly between components
- Telemetry and monitoring systems are working
- Database and dashboard are recording events
- Continuous learning and pattern extraction are functional

## Test Scenario: Auto-Commit Feature

The test simulates adding a new "auto-commit" feature to the AI workflow, which:
1. **Stores requirements** in Qdrant vector database
2. **Queries LLM** (llama.cpp) for implementation plan
3. **Extracts patterns** via hybrid-coordinator
4. **Records telemetry** in Postgres database
5. **Enables continuous learning** from the interaction
6. **Monitors via dashboard** for visibility

This comprehensive scenario touches **all major components**.

## Components Tested

### Core Infrastructure ✅
1. **Qdrant** - Vector database for semantic search
   - Health check
   - Collection integrity
   - Vector storage/retrieval
   - Context augmentation

2. **llama.cpp** - Local LLM inference
   - Health check
   - Model availability
   - Chat completions API
   - Response quality

3. **PostgreSQL** - Relational database
   - Connection health
   - Telemetry table existence
   - Event storage
   - Query performance

4. **Redis** - Caching layer
   - Connection health
   - Read/write operations
   - TTL handling

### MCP Servers ✅
5. **AIDB MCP** - Context API and telemetry
   - Health endpoint
   - Telemetry event recording
   - API responsiveness

6. **Hybrid Coordinator** - Learning and federation
   - Health endpoint
   - Qdrant integration
   - Context storage
   - Pattern extraction
   - Collection management

7. **NixOS Docs MCP** - Documentation knowledge base
   - Health endpoint
   - Cache functionality

### Monitoring ✅
8. **Dashboard** - Event visualization
   - Backend API health
   - Database access
   - Recent event visibility

### Data Flows ✅
9. **End-to-End Workflows**
   - Feature request → Qdrant storage
   - LLM query → Response generation
   - Pattern extraction → Skills storage
   - Telemetry → Database persistence
   - Cross-system data consistency

## Stack Gym Task List (Senior Dev Validation Run)

**Goal:** Prove the full AI stack works end-to-end with measurable outcomes.

### Tasks
- [ ] Start the AI stack and confirm all core services are healthy.
- [ ] Run the end-to-end test script.
- [ ] Analyze the results and confirm database + vector storage visibility.
- [ ] Record the run summary (timestamp, pass/fail, key metrics).

### Success Metrics
- **Service health:** `./scripts/ai-stack-health.sh` reports all core services healthy.
- **E2E test:** `./scripts/ai-stack-e2e-test.sh` exits with code `0`.
- **Artifacts:** Test results JSON exists under `~/.local/share/nixos-ai-stack/test-results/`.
- **Telemetry:** `./scripts/analyze-test-results.sh` reports event recording + Qdrant checks passing.
- **Regression signal:** No new errors in `./scripts/ai-stack-manage.sh logs` during the run.

## Usage

### Running the Full Test

```bash
# Run complete end-to-end test
./scripts/ai-stack-e2e-test.sh

# This will:
# - Test all services
# - Store results in ~/.local/share/nixos-ai-stack/test-results/
# - Generate JSON report
# - Store results in database
# - Exit with code 0 (success) or 1 (failure)
```

### Analyzing Results

```bash
# Analyze most recent test run
./scripts/analyze-test-results.sh

# Analyze specific test run
./scripts/analyze-test-results.sh test-20260102-200134

# This will:
# - Check database event recording
# - Verify Qdrant collections
# - Test dashboard visibility
# - Identify integration gaps
# - Provide actionable fixes
```

### Test Output

```
Test Results Location:
~/.local/share/nixos-ai-stack/test-results/
├── test-YYYYMMDD-HHMMSS.log          # Full execution log
├── test-YYYYMMDD-HHMMSS-report.json  # JSON summary
├── test-YYYYMMDD-HHMMSS-llm-response.json  # LLM output
└── test-YYYYMMDD-HHMMSS-feature-request.json  # Test input
```

## Test Phases

### Phase 1: Pre-flight Checks (7 tests)
Verifies all services are running and healthy:
- ✅ Qdrant health
- ✅ llama.cpp health
- ✅ PostgreSQL connection
- ✅ Redis connection
- ✅ AIDB MCP health
- ✅ Hybrid Coordinator health + collections
- ✅ NixOS Docs MCP health

### Phase 2: Real-World Feature Test (4 tests)
Simulates actual AI workflow:
- ✅ Store feature request in Qdrant
- ✅ Query LLM for implementation plan
- ✅ Store plan as coding pattern
- ✅ Retrieve similar patterns (context augmentation)

### Phase 3: Telemetry and Learning (4 tests)
Tests data persistence and learning:
- ✅ Send telemetry event to AIDB
- ✅ Verify event in Postgres database
- ✅ Verify Redis caching
- ✅ Check continuous learning daemon

### Phase 4: Dashboard Monitoring (2 tests)
Validates monitoring infrastructure:
- ✅ Dashboard backend accessibility
- ✅ Event visibility in dashboard

### Phase 5: Data Consistency (2 tests)
Cross-system validation:
- ✅ Qdrant collection integrity
- ✅ Event count consistency across systems

**Total: 19 comprehensive tests**

## Expected Results

### ✅ All Tests Passing (100%)
```
Tests Passed: 19
Tests Failed: 0
Total Tests: 19
Pass Rate: 100%

✅ ALL TESTS PASSED - AI Stack is fully functional!
```

### 🟡 Partial Success (80-99%)
```
Tests Passed: 17
Tests Failed: 2
Pass Rate: 89%

Some tests failed - system partially functional
```

Common partial failures:
- Dashboard not running (optional component)
- Some Qdrant collections empty (new installation)
- Continuous learning endpoint not implemented

**Action**: Review specific failures, system still usable

### 🔴 Major Issues (<80%)
```
Tests Passed: 10
Tests Failed: 9
Pass Rate: 52%

Pass rate below 80% - immediate attention required
```

Common critical failures:
- Services not responding
- Database connection failures
- Telemetry pipeline broken

**Action**: Run analysis script for detailed diagnostics

## Interpreting Test Results

### JSON Report Format
```json
{
  "test_run_id": "test-20260102-200134",
  "timestamp": "2026-01-02T20:01:34-08:00",
  "summary": {
    "total_tests": 19,
    "passed": 17,
    "failed": 2,
    "pass_rate": 89
  },
  "failed_tests": [
    "Dashboard backend: Service not running",
    "Continuous learning daemon: Endpoint not available"
  ],
  "components_tested": [...]
}
```

### Database Storage
Test results are automatically stored in Postgres:
```sql
SELECT * FROM test_runs ORDER BY timestamp DESC LIMIT 5;
```

This allows tracking test trends over time.

## Common Issues and Fixes

### Issue: Telemetry Events Not in Database
**Symptom**: Test passes but `analyze-test-results.sh` shows 0 events

**Diagnosis**:
```bash
podman logs local-ai-aidb | grep -i telemetry
podman logs local-ai-aidb | grep -i postgres
```

**Fix**:
```bash
# Create telemetry table if missing
PGPASSWORD="change_me_in_production" psql -h localhost -U mcp -d mcp << EOF
CREATE TABLE IF NOT EXISTS telemetry_events (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(255),
    timestamp TIMESTAMP DEFAULT NOW(),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
EOF

# Restart AIDB
podman restart local-ai-aidb
```

### Issue: Qdrant Collections Empty
**Symptom**: `points_count: 0` for all collections

**Diagnosis**: New installation, no data yet

**Fix**: Not an error - collections will fill up during normal use

**Optional**: Initialize with sample data:
```bash
curl -X POST http://localhost:8092/api/collections/init
```

### Issue: Hybrid Coordinator Not Responding
**Symptom**: Health check fails, timeout errors

**Diagnosis**:
```bash
podman ps | grep hybrid-coordinator
podman logs local-ai-hybrid-coordinator | tail -50
```

**Fix**:
```bash
# Check if Qdrant dependency is healthy
curl http://localhost:6333/healthz

# Restart hybrid-coordinator
podman restart local-ai-hybrid-coordinator

# If still failing, check docker-compose.yml dependencies
```

### Issue: LLM Query Timeout
**Symptom**: Phase 2 test fails on LLM query

**Diagnosis**: Model loading slowly or not loaded

**Fix**:
```bash
# Check if model is loaded
curl http://localhost:8080/v1/models

# Check llama.cpp logs
podman logs local-ai-llama-cpp | tail -50

# Increase timeout in test script (line ~146)
# Change: --max-time 30
# To: --max-time 60
```

## Integration with Deployment

### Run During NixOS Quick Deploy
Add to `scripts/start-ai-stack-and-dashboard.sh`:
```bash
# After stack starts successfully
if [ "$stack_started" = true ]; then
    info "Running AI stack validation tests..."
    "${PROJECT_ROOT}/scripts/ai-stack-e2e-test.sh" || \
        warn "Some validation tests failed - review test results"
fi
```

### Automated Monitoring
Set up periodic testing:
```bash
# Add to crontab
0 */6 * * * /path/to/scripts/ai-stack-e2e-test.sh >> /var/log/ai-stack-tests.log 2>&1
```

This runs tests every 6 hours and logs results.

## Advanced Usage

### Custom Test Scenarios
Modify the test to add your own scenarios:
```bash
# Edit scripts/ai-stack-e2e-test.sh
# Add new test phases after Phase 5

# Example: Test MindsDB integration
test_start "MindsDB ML predictions"
MINDSDB_RESULT=$(curl -sf --max-time 10 http://localhost:47334/api/sql/query \
  -d "SELECT * FROM mindsdb.models" 2>&1)
if echo "$MINDSDB_RESULT" | grep -q "data"; then
    test_pass "MindsDB query"
else
    test_fail "MindsDB query" "API error"
fi
```

### Continuous Integration
Use in CI/CD pipelines:
```yaml
# .github/workflows/ai-stack-test.yml
- name: Test AI Stack
  run: |
    ./scripts/ai-stack-e2e-test.sh
    EXIT_CODE=$?
    ./scripts/analyze-test-results.sh
    exit $EXIT_CODE
```

## Metrics and KPIs

Track these metrics over time:
- **Pass Rate**: Should stay > 95%
- **Test Duration**: Should be < 2 minutes for full suite
- **Event Recording Rate**: 100% of telemetry events should reach database
- **Collection Health**: All Qdrant collections should have > 0 points after first week

## Troubleshooting

### Test Hangs or Times Out
```bash
# Kill hanging test
pkill -f ai-stack-e2e-test.sh

# Check what's hanging
podman ps --format "{{.Names}}\t{{.Status}}"

# Look for containers in "starting" state for >5 minutes
```

### Test Results Not Saved
```bash
# Check directory permissions
ls -la ~/.local/share/nixos-ai-stack/test-results/

# Create if missing
mkdir -p ~/.local/share/nixos-ai-stack/test-results
chmod 755 ~/.local/share/nixos-ai-stack/test-results
```

### Database Connection Fails
```bash
# Verify Postgres is running
podman ps | grep postgres

# Test connection manually
PGPASSWORD="change_me_in_production" psql -h localhost -U mcp -d mcp -c "SELECT 1;"

# Check firewall
sudo firewall-cmd --list-ports | grep 5432
```

## Future Enhancements

- [ ] Performance benchmarking (latency, throughput)
- [ ] Load testing (concurrent requests)
- [ ] Failure injection testing (chaos engineering)
- [ ] Multi-model testing (different LLMs)
- [ ] Integration with Prometheus/Grafana
- [ ] Automated regression detection
- [ ] Test coverage reporting

---

**Status**: Production Ready ✅
**Last Updated**: January 2, 2026
**Maintainer**: NixOS Quick Deploy AI Stack Team
