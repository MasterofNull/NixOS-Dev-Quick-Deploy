#!/usr/bin/env bash
# Report to Database Library
# Part of: NixOS-Dev-Quick-Deploy
# Purpose: Store deployment reports in PostgreSQL instead of cluttering repo with markdown files

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Database connection from environment or defaults
DB_HOST="${POSTGRES_HOST:-localhost}"
DB_PORT="${POSTGRES_PORT}"
DB_NAME="${POSTGRES_DB:-mcp}"
DB_USER="${POSTGRES_USER:-mcp}"
DB_PASSWORD_FILE="${POSTGRES_PASSWORD_FILE:-/run/secrets/postgres_password}"
DB_PASSWORD=""
if [[ -f "$DB_PASSWORD_FILE" ]]; then
    DB_PASSWORD=$(<"$DB_PASSWORD_FILE")
fi

# Report types
REPORT_TYPE_DEPLOYMENT="deployment"
REPORT_TYPE_FIX="fix"
REPORT_TYPE_UPGRADE="upgrade"
REPORT_TYPE_ERROR="error"
REPORT_TYPE_DEBUG="debug"
REPORT_TYPE_SUMMARY="summary"
REPORT_TYPE_SESSION="session"

# Check if psql is available
check_database_available() {
    if ! command -v psql >/dev/null 2>&1; then
        return 1
    fi

    # Try to connect
    if ! PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1" >/dev/null 2>&1; then
        return 1
    fi

    return 0
}

# Store report in database
# Usage: store_report TITLE CONTENT TYPE [METADATA_JSON]
store_report() {
    local title="$1"
    local content="$2"
    local report_type="${3:-$REPORT_TYPE_SESSION}"
    local metadata_json="${4:-{}}"

    if ! check_database_available; then
        # Fallback to file if database not available
        echo "⚠ Database not available, saving report to file as fallback"
        fallback_to_file "$title" "$content" "$report_type"
        return 1
    fi

    # Add automatic metadata
    local full_metadata=$(cat <<EOF
{
    "report_type": "$report_type",
    "created_by": "nixos-quick-deploy",
    "script_version": "$(git rev-parse HEAD 2>/dev/null || echo 'unknown')",
    "hostname": "$(hostname)",
    "timestamp": "$(date -Iseconds)",
    "user_metadata": $metadata_json
}
EOF
)

    # Insert into database
    PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<SQL
INSERT INTO deployment_reports (
    title,
    content,
    report_type,
    metadata,
    created_at
) VALUES (
    '$title',
    \$CONTENT\$
$content
\$CONTENT\$,
    '$report_type',
    '$full_metadata'::jsonb,
    NOW()
);
SQL

    if [ $? -eq 0 ]; then
        echo "✓ Report stored in database: $title"
        return 0
    else
        echo "✗ Failed to store report in database, falling back to file"
        fallback_to_file "$title" "$content" "$report_type"
        return 1
    fi
}

# Fallback: Save to file if database not available
fallback_to_file() {
    local title="$1"
    local content="$2"
    local report_type="$3"

    local report_dir="${PROJECT_ROOT}/.reports/${report_type}"
    mkdir -p "$report_dir"

    local filename=$(echo "$title" | sed 's/[^a-zA-Z0-9-]/-/g' | tr '[:upper:]' '[:lower:]')
    local filepath="${report_dir}/${filename}-$(date +%Y%m%d-%H%M%S).md"

    cat > "$filepath" <<EOF
# $title

**Type**: $report_type
**Created**: $(date -Iseconds)
**Hostname**: $(hostname)

---

$content
EOF

    echo "✓ Report saved to file: $filepath"
    echo "  (This should be moved to database when available)"
}

# Store deployment report
# Usage: store_deployment_report TITLE CONTENT [METADATA_JSON]
store_deployment_report() {
    store_report "$1" "$2" "$REPORT_TYPE_DEPLOYMENT" "${3:-{}}"
}

# Store fix report
# Usage: store_fix_report TITLE CONTENT ISSUE_FIXED [METADATA_JSON]
store_fix_report() {
    local title="$1"
    local content="$2"
    local issue_fixed="$3"
    local metadata="${4:-{}}"

    # Add issue to metadata
    local enhanced_metadata=$(echo "$metadata" | jq ". + {\"issue_fixed\": \"$issue_fixed\"}" 2>/dev/null || echo "{\"issue_fixed\": \"$issue_fixed\"}")

    store_report "$title" "$content" "$REPORT_TYPE_FIX" "$enhanced_metadata"
}

# Store upgrade report
# Usage: store_upgrade_report TITLE CONTENT FROM_VERSION TO_VERSION [METADATA_JSON]
store_upgrade_report() {
    local title="$1"
    local content="$2"
    local from_version="$3"
    local to_version="$4"
    local metadata="${5:-{}}"

    local enhanced_metadata=$(echo "$metadata" | jq ". + {\"from_version\": \"$from_version\", \"to_version\": \"$to_version\"}" 2>/dev/null || echo "{\"from_version\": \"$from_version\", \"to_version\": \"$to_version\"}")

    store_report "$title" "$content" "$REPORT_TYPE_UPGRADE" "$enhanced_metadata"
}

# Store error report
# Usage: store_error_report TITLE ERROR_MESSAGE STACK_TRACE [METADATA_JSON]
store_error_report() {
    local title="$1"
    local error_message="$2"
    local stack_trace="$3"
    local metadata="${4:-{}}"

    local content=$(cat <<EOF
## Error

$error_message

## Stack Trace

\`\`\`
$stack_trace
\`\`\`
EOF
)

    local enhanced_metadata=$(echo "$metadata" | jq ". + {\"error\": \"$error_message\"}" 2>/dev/null || echo "{\"error\": \"$error_message\"}")

    store_report "$title" "$content" "$REPORT_TYPE_ERROR" "$enhanced_metadata"
}

# Retrieve reports from database
# Usage: get_reports [TYPE] [LIMIT] [OFFSET]
get_reports() {
    local report_type="${1:-}"
    local limit="${2:-10}"
    local offset="${3:-0}"

    if ! check_database_available; then
        echo "✗ Database not available"
        return 1
    fi

    local where_clause=""
    if [ -n "$report_type" ]; then
        where_clause="WHERE report_type = '$report_type'"
    fi

    PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<SQL
SELECT
    id,
    title,
    report_type,
    created_at,
    LENGTH(content) as content_length
FROM deployment_reports
$where_clause
ORDER BY created_at DESC
LIMIT $limit OFFSET $offset;
SQL
}

# Get report by ID
# Usage: get_report_by_id REPORT_ID
get_report_by_id() {
    local report_id="$1"

    if ! check_database_available; then
        echo "✗ Database not available"
        return 1
    fi

    PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<SQL
SELECT
    id,
    title,
    content,
    report_type,
    metadata,
    created_at
FROM deployment_reports
WHERE id = $report_id;
SQL
}

# Search reports by keyword
# Usage: search_reports KEYWORD [LIMIT]
search_reports() {
    local keyword="$1"
    local limit="${2:-10}"

    if ! check_database_available; then
        echo "✗ Database not available"
        return 1
    fi

    PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<SQL
SELECT
    id,
    title,
    report_type,
    created_at,
    ts_rank(to_tsvector('english', title || ' ' || content), plainto_tsquery('english', '$keyword')) as rank
FROM deployment_reports
WHERE to_tsvector('english', title || ' ' || content) @@ plainto_tsquery('english', '$keyword')
ORDER BY rank DESC, created_at DESC
LIMIT $limit;
SQL
}

# Clean up old reports
# Usage: cleanup_old_reports DAYS_TO_KEEP [REPORT_TYPE]
cleanup_old_reports() {
    local days="${1:-90}"
    local report_type="${2:-}"

    if ! check_database_available; then
        echo "✗ Database not available"
        return 1
    fi

    local where_clause="WHERE created_at < NOW() - INTERVAL '$days days'"
    if [ -n "$report_type" ]; then
        where_clause="$where_clause AND report_type = '$report_type'"
    fi

    echo "🧹 Cleaning up reports older than $days days..."

    PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<SQL
DELETE FROM deployment_reports
$where_clause
RETURNING id, title, created_at;
SQL
}

# Export report to markdown file
# Usage: export_report_to_file REPORT_ID OUTPUT_FILE
export_report_to_file() {
    local report_id="$1"
    local output_file="$2"

    if ! check_database_available; then
        echo "✗ Database not available"
        return 1
    fi

    PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -A <<SQL > "$output_file"
SELECT content FROM deployment_reports WHERE id = $report_id;
SQL

    echo "✓ Report exported to: $output_file"
}

# Migrate existing markdown files to database
# Usage: migrate_markdown_to_database MARKDOWN_FILE REPORT_TYPE
migrate_markdown_to_database() {
    local file="$1"
    local report_type="${2:-$REPORT_TYPE_SESSION}"

    if [ ! -f "$file" ]; then
        echo "✗ File not found: $file"
        return 1
    fi

    local title=$(basename "$file" .md | sed 's/-/ /g' | sed 's/\b\(.\)/\u\1/g')
    local content=$(cat "$file")

    # Extract metadata from filename if possible
    local metadata="{}"
    if [[ "$file" =~ ([0-9]{4}-[0-9]{2}-[0-9]{2}) ]]; then
        local date="${BASH_REMATCH[1]}"
        metadata=$(echo "$metadata" | jq ". + {\"original_date\": \"$date\"}" 2>/dev/null || echo "{\"original_date\": \"$date\"}")
    fi

    metadata=$(echo "$metadata" | jq ". + {\"original_file\": \"$file\", \"migrated\": true}" 2>/dev/null || echo "{\"original_file\": \"$file\", \"migrated\": true}")

    if store_report "$title" "$content" "$report_type" "$metadata"; then
        echo "✓ Migrated: $file"
        echo "  To remove file: rm \"$file\""
        return 0
    else
        echo "✗ Failed to migrate: $file"
        return 1
    fi
}
