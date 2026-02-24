#!/usr/bin/env bash
# Analyze AI Stack Test Results and Identify Gaps
# Compares expected events with actual database/dashboard entries
# Provides actionable fixes for any mismatches

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_RESULTS_DIR="${HOME}/.local/share/nixos-ai-stack/test-results"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info() { echo -e "${BLUE}ℹ${NC} $1"; }
success() { echo -e "${GREEN}✓${NC} $1"; }
warning() { echo -e "${YELLOW}⚠${NC} $1"; }
error() { echo -e "${RED}✗${NC} $1"; }

# Get latest test run or specific run ID
TEST_RUN_ID="${1:-$(ls -t "$TEST_RESULTS_DIR" | grep "^test-" | grep ".json" | head -1 | sed 's/-report.json$//')}"

if [ -z "$TEST_RUN_ID" ]; then
    error "No test runs found in $TEST_RESULTS_DIR"
    exit 1
fi

REPORT_FILE="${TEST_RESULTS_DIR}/${TEST_RUN_ID}-report.json"
if [ ! -f "$REPORT_FILE" ]; then
    error "Report file not found: $REPORT_FILE"
    exit 1
fi

info "Analyzing test run: $TEST_RUN_ID"
info "Report: $REPORT_FILE"
echo ""

# Parse report
TESTS_PASSED=$(jq -r '.summary.passed' "$REPORT_FILE")
TESTS_FAILED=$(jq -r '.summary.failed' "$REPORT_FILE")
PASS_RATE=$(jq -r '.summary.pass_rate' "$REPORT_FILE")

info "Test Summary:"
info "  Passed: $TESTS_PASSED"
info "  Failed: $TESTS_FAILED"
info "  Pass Rate: ${PASS_RATE}%"
echo ""

# ============================================================================
# Analysis 1: Check Database Event Recording
# ============================================================================
info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
info "Analysis 1: Database Event Recording"
info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check if telemetry table exists
TABLE_EXISTS=$(PGPASSWORD="${POSTGRES_PASSWORD:-change_me_in_production}" psql -h localhost -U "${POSTGRES_USER:-mcp}" -d "${POSTGRES_DB:-mcp}" -t -c "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'telemetry_events');" 2>/dev/null | tr -d ' ' || echo "f")

if [ "$TABLE_EXISTS" = "t" ]; then
    success "Telemetry table exists in database"

    # Count events for this test run
    EVENT_COUNT=$(PGPASSWORD="${POSTGRES_PASSWORD:-change_me_in_production}" psql -h localhost -U "${POSTGRES_USER:-mcp}" -d "${POSTGRES_DB:-mcp}" -t -c "SELECT COUNT(*) FROM telemetry_events WHERE metadata->>'test_run_id' = '$TEST_RUN_ID';" 2>/dev/null | tr -d ' ' || echo "0")

    if [ "$EVENT_COUNT" -gt 0 ]; then
        success "Found $EVENT_COUNT events for test run in database"
    else
        warning "No events found for test run in database"
        warning "  Possible causes:"
        warning "    1. AIDB telemetry endpoint not working"
        warning "    2. Database connection issues"
        warning "    3. Events not being persisted"
        echo ""
        warning "  Fix: Check AIDB logs:"
        echo "    kubectl logs -n ai-stack deploy/aidb | grep -i telemetry"
    fi
else
    error "Telemetry table does not exist!"
    error "  Fix: Create the table manually:"
    echo ""
    cat << 'EOF'
    PGPASSWORD="change_me_in_production" psql -h localhost -U mcp -d mcp << EOSQL
    CREATE TABLE IF NOT EXISTS telemetry_events (
        id SERIAL PRIMARY KEY,
        event_type VARCHAR(255),
        timestamp TIMESTAMP DEFAULT NOW(),
        metadata JSONB,
        created_at TIMESTAMP DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_telemetry_type ON telemetry_events(event_type);
    CREATE INDEX IF NOT EXISTS idx_telemetry_metadata ON telemetry_events USING GIN(metadata);
    EOSQL
EOF
    echo ""
fi

echo ""

# ============================================================================
# Analysis 2: Check Qdrant Vector Storage
# ============================================================================
info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
info "Analysis 2: Qdrant Vector Storage"
info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check each collection
for collection in interaction-history skills-patterns codebase-context error-solutions best-practices; do
    COLLECTION_INFO=$(curl -sf --max-time 5 "http://${SERVICE_HOST:-localhost}:6333/collections/$collection" 2>&1 || echo "FAILED")

    if echo "$COLLECTION_INFO" | grep -q "points_count"; then
        POINT_COUNT=$(echo "$COLLECTION_INFO" | grep -o '"points_count":[0-9]*' | grep -o '[0-9]*')

        if [ "$POINT_COUNT" -gt 0 ]; then
            success "Collection '$collection': $POINT_COUNT points"
        else
            warning "Collection '$collection' is empty"
            warning "  This may be expected for new installations"
        fi
    else
        error "Collection '$collection' not accessible"
        error "  Fix: Recreate collection via hybrid-coordinator:"
        echo "    curl -X POST http://${SERVICE_HOST:-localhost}:8092/api/collections/init"
    fi
done

echo ""

# ============================================================================
# Analysis 3: Dashboard Visibility
# ============================================================================
info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
info "Analysis 3: Dashboard Event Visibility"
info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check if dashboard backend is running
DASHBOARD_RUNNING=$(curl -sf --max-time 3 http://${SERVICE_HOST:-localhost}:8889/api/metrics/system >/dev/null 2>&1 && echo "true" || echo "false")

if [ "$DASHBOARD_RUNNING" = "true" ]; then
    success "Dashboard backend is running"

    # Check recent events visible to dashboard
    RECENT_EVENTS=$(PGPASSWORD="${POSTGRES_PASSWORD:-change_me_in_production}" psql -h localhost -U "${POSTGRES_USER:-mcp}" -d "${POSTGRES_DB:-mcp}" -t -c "SELECT COUNT(*) FROM telemetry_events WHERE created_at > NOW() - INTERVAL '10 minutes';" 2>/dev/null | tr -d ' ' || echo "0")

    if [ "$RECENT_EVENTS" -gt 0 ]; then
        success "Dashboard can access $RECENT_EVENTS recent events"
    else
        warning "No recent events visible to dashboard"
        warning "  Possible causes:"
        warning "    1. Events not being written to database"
        warning "    2. Dashboard query time range too narrow"
        warning "    3. Database permissions issue"
    fi
else
    warning "Dashboard backend not running"
    info "  To start dashboard:"
    echo "    systemctl --user start dashboard-server.service"
    echo "    OR"
    echo "    cd $SCRIPT_DIR/../dashboard/backend && uvicorn api.main:app --host 0.0.0.0 --port 8889"
fi

echo ""

# ============================================================================
# Analysis 4: Component Integration Gaps
# ============================================================================
info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
info "Analysis 4: Component Integration Gaps"
info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Test data flow: AIDB → Postgres
info "Testing: AIDB → Postgres data flow"
TEST_EVENT='{"event_type":"integration_test","test":"aidb_to_postgres","timestamp":"'$(date -Iseconds)'"}'
AIDB_RESPONSE=$(curl -sf --max-time 5 -X POST http://${SERVICE_HOST:-localhost}:8091/api/telemetry/event \
  -H "Content-Type: application/json" \
  -d "$TEST_EVENT" 2>&1 || echo "FAILED")

if echo "$AIDB_RESPONSE" | grep -q "success\|recorded"; then
    sleep 2  # Allow time for write
    VERIFY_COUNT=$(PGPASSWORD="${POSTGRES_PASSWORD:-change_me_in_production}" psql -h localhost -U "${POSTGRES_USER:-mcp}" -d "${POSTGRES_DB:-mcp}" -t -c "SELECT COUNT(*) FROM telemetry_events WHERE event_type = 'integration_test' AND created_at > NOW() - INTERVAL '10 seconds';" 2>/dev/null | tr -d ' ' || echo "0")

    if [ "$VERIFY_COUNT" -gt 0 ]; then
        success "AIDB → Postgres: Working ($VERIFY_COUNT events written)"
    else
        error "AIDB → Postgres: BROKEN"
        error "  Events sent to AIDB but not appearing in Postgres"
        error "  Fix: Check AIDB database connection configuration"
        echo "    kubectl logs -n ai-stack deploy/aidb | grep -i postgres"
    fi
else
    error "AIDB API not responding to telemetry requests"
    error "  Fix: Check if AIDB is running and healthy"
    echo "    kubectl get pods -n ai-stack | grep aidb"
    echo "    curl http://${SERVICE_HOST:-localhost}:8091/health"
fi

echo ""

# Test data flow: Hybrid Coordinator → Qdrant
info "Testing: Hybrid Coordinator → Qdrant data flow"
TEST_CONTEXT='{"collection":"interaction-history","text":"Integration test context","metadata":{"test":"true"}}'
HYBRID_RESPONSE=$(curl -sf --max-time 5 -X POST http://${SERVICE_HOST:-localhost}:8092/api/context/add \
  -H "Content-Type: application/json" \
  -d "$TEST_CONTEXT" 2>&1 || echo "FAILED")

if echo "$HYBRID_RESPONSE" | grep -q "success\|id"; then
    success "Hybrid Coordinator → Qdrant: Working"
else
    error "Hybrid Coordinator → Qdrant: BROKEN"
    error "  Fix: Check hybrid-coordinator logs and Qdrant connection"
    echo "    kubectl logs -n ai-stack deploy/hybrid-coordinator | grep -i qdrant"
fi

echo ""

# ============================================================================
# Recommendations
# ============================================================================
info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
info "Recommendations"
info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ "$TESTS_FAILED" -gt 0 ]; then
    warning "Failed tests found. Review the following:"
    jq -r '.failed_tests[]' "$REPORT_FILE" 2>/dev/null | while read -r failure; do
        echo "  • $failure"
    done
    echo ""
fi

if [ "$PASS_RATE" -lt 80 ]; then
    error "Pass rate below 80% - immediate attention required"
    echo ""
    info "Common fixes:"
    echo "  1. Restart failed deployments:"
    echo "     kubectl rollout restart deploy -n ai-stack aidb hybrid-coordinator"
    echo ""
    echo "  2. Check deployment logs:"
    echo "     kubectl logs -n ai-stack deploy/aidb"
    echo "     kubectl logs -n ai-stack deploy/hybrid-coordinator"
    echo ""
    echo "  3. Verify database schema:"
    echo "     psql -h localhost -U mcp -d mcp -c '\dt'"
    echo ""
    echo "  4. Reset Qdrant collections:"
    echo "     curl -X POST http://${SERVICE_HOST:-localhost}:8092/api/collections/reset"
elif [ "$PASS_RATE" -lt 100 ]; then
    warning "Some tests failed - system partially functional"
    info "Review specific failures and apply targeted fixes"
else
    success "All tests passed! AI stack is fully functional"
fi

echo ""
success "Analysis complete. Review recommendations above."
