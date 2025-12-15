#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SQL_FILE="${SQL_FILE:-$REPO_ROOT/docs/sql/aidb-timeseries-schema.sql}"
PSQL_BIN="${PSQL_BIN:-psql}"
POSTGRES_DSN="${AIDB_POSTGRES_DSN:-postgres://mcp:change_me@localhost:5432/mcp}"

usage() {
    cat <<EOF
Usage: $(basename "$0") [--dsn DSN] [--schema FILE]

Options:
  --dsn DSN        PostgreSQL DSN (default: $POSTGRES_DSN)
  --schema FILE    Path to SQL file (default: $SQL_FILE)
  -h, --help       Show this help message
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dsn)
            POSTGRES_DSN="$2"
            shift 2
            ;;
        --schema)
            SQL_FILE="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage
            exit 1
            ;;
    esac
done

if ! command -v "$PSQL_BIN" >/dev/null 2>&1; then
    echo "psql binary ('$PSQL_BIN') not found" >&2
    exit 1
fi

if [[ ! -f "$SQL_FILE" ]]; then
    echo "Schema file not found: $SQL_FILE" >&2
    exit 1
fi

echo "📦 Applying schema from $SQL_FILE"
"$PSQL_BIN" "$POSTGRES_DSN" -v ON_ERROR_STOP=1 -f "$SQL_FILE"
echo "✅ Schema applied"
