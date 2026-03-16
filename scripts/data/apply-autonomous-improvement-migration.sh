#!/usr/bin/env bash
# Apply autonomous improvement database migration
# Usage: ./apply-autonomous-improvement-migration.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Load service endpoints
if [[ -f "${REPO_ROOT}/config/service-endpoints.sh" ]]; then
    # shellcheck source=../../config/service-endpoints.sh
    source "${REPO_ROOT}/config/service-endpoints.sh"
fi

: "${POSTGRES_HOST:=127.0.0.1}"
: "${POSTGRES_PORT:=5432}"
: "${POSTGRES_USER:=aidb}"
: "${POSTGRES_DB:=aidb}"

MIGRATION_FILE="${REPO_ROOT}/ai-stack/postgres/migrations/006_autonomous_improvement.sql"

if [[ ! -f "$MIGRATION_FILE" ]]; then
    echo "❌ Migration file not found: $MIGRATION_FILE" >&2
    exit 1
fi

# Check if password is available
if [[ -z "${POSTGRES_PASSWORD:-}" ]]; then
    if [[ -r "/run/secrets/postgres_password" ]]; then
        export PGPASSWORD="$(tr -d '[:space:]' < /run/secrets/postgres_password)"
    else
        echo "⚠️  POSTGRES_PASSWORD not set and /run/secrets/postgres_password not readable"
        echo "   Attempting connection without password (may fail)"
    fi
else
    export PGPASSWORD="$POSTGRES_PASSWORD"
fi

echo "🔧 Applying autonomous improvement migration..."
echo "   Host: $POSTGRES_HOST:$POSTGRES_PORT"
echo "   Database: $POSTGRES_DB"
echo "   User: $POSTGRES_USER"
echo "   Migration: $MIGRATION_FILE"
echo ""

# Apply migration
if psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f "$MIGRATION_FILE"; then
    echo ""
    echo "✅ Migration applied successfully"
    echo ""
    echo "Created tables:"
    echo "  - improvement_cycles"
    echo "  - trigger_events"
    echo "  - experiment_results_history"
    echo "  - system_metrics_timeseries (TimescaleDB hypertable)"
    echo "  - design_decisions"
    echo "  - metric_trends"
    echo "  - optimization_hypotheses"
    echo "  - improvement_recommendations"
    echo ""
    echo "Created views:"
    echo "  - active_improvement_cycles"
    echo "  - recent_experiments"
    echo "  - top_recommendations"
    echo "  - system_health_summary"
    echo ""
    echo "Next steps:"
    echo "  1. Create trigger engine: ai-stack/autonomous-improvement/trigger_engine.py"
    echo "  2. Create trend database module: ai-stack/autonomous-improvement/trend_database.py"
    echo "  3. Start autonomous improvement daemon"
else
    echo ""
    echo "❌ Migration failed" >&2
    echo "   Check PostgreSQL logs for details"
    exit 1
fi
