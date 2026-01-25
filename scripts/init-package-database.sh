#!/usr/bin/env sh
#
# Initialize Package Versions Database
# Populates PostgreSQL with package tracking information
#

set -e

POSTGRES_HOST=${POSTGRES_HOST:-postgres}
POSTGRES_PORT=${POSTGRES_PORT:-5432}
POSTGRES_DB=${POSTGRES_DB:-mcp}
POSTGRES_USER=${POSTGRES_USER:-mcp}

info() { echo "\033[0;34mℹ\033[0m $1"; }
success() { echo "\033[0;32m✓\033[0m $1"; }
error() { echo "\033[0;31m✗\033[0m $1"; }

info "Initializing package versions database..."

# Check if running in container or host
if [ -f /.dockerenv ] || [ -f /run/.containerenv ]; then
    PSQL_CMD="psql"
else
    PSQL_CMD="podman exec -i local-ai-postgres psql"
fi

# Load schema
info "Creating package_versions schema..."
cat ai-stack/sql/package_versions_schema.sql | $PSQL_CMD -U "$POSTGRES_USER" -d "$POSTGRES_DB" 2>&1 | grep -v "already exists" || true

success "Database schema created"

# Query summary
info "Package update summary:"
echo "SELECT * FROM get_update_summary();" | $PSQL_CMD -U "$POSTGRES_USER" -d "$POSTGRES_DB"

info "Packages needing updates:"
echo "SELECT package_name, container_name, current_version, latest_version, action_needed FROM packages_needing_updates LIMIT 10;" | \
    $PSQL_CMD -U "$POSTGRES_USER" -d "$POSTGRES_DB"

success "Package database initialized!"
