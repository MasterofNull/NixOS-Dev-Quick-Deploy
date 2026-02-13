#!/usr/bin/env bash
# Backup Restore Drill (Postgres + Qdrant)
# Safe by default: prints planned commands unless --execute is provided.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

POSTGRES_BACKUP_DIR="${POSTGRES_BACKUP_DIR:-/var/backups/postgresql}"
QDRANT_BACKUP_DIR="${QDRANT_BACKUP_DIR:-/var/backups/qdrant}"

DB_NAME="${DB_NAME:-aidb}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-aidb}"

QDRANT_HOST="${QDRANT_HOST:-localhost}"
QDRANT_PORT="${QDRANT_PORT:-6333}"

CURL_TIMEOUT="${CURL_TIMEOUT:-10}"
CURL_CONNECT_TIMEOUT="${CURL_CONNECT_TIMEOUT:-3}"

EXECUTE=false
CLEANUP=false
POSTGRES_ONLY=false
QDRANT_ONLY=false

usage() {
  cat <<USAGE
Usage: $0 [--execute] [--cleanup] [--postgres-only|--qdrant-only]

Defaults to dry-run (prints commands without executing).

Options:
  --execute        Perform restore drill (creates temp DB/collection)
  --cleanup        Drop temp DB/collection after verification
  --postgres-only  Only run PostgreSQL restore drill
  --qdrant-only    Only run Qdrant restore drill
USAGE
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "ERROR: Required command not found: $1" >&2
    exit 1
  fi
}

find_latest_backup() {
  local dir="$1"
  local pattern="$2"
  ls -t "$dir"/daily/$pattern "$dir"/weekly/$pattern "$dir"/monthly/$pattern 2>/dev/null | head -1
}

run_or_echo() {
  if [[ "$EXECUTE" == "true" ]]; then
    "$@"
  else
    echo "+ $*"
  fi
}

timestamp="$(date +%Y%m%d-%H%M%S)"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --execute) EXECUTE=true ;;
    --cleanup) CLEANUP=true ;;
    --postgres-only) POSTGRES_ONLY=true ;;
    --qdrant-only) QDRANT_ONLY=true ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
  shift
done

if [[ "$POSTGRES_ONLY" == "true" && "$QDRANT_ONLY" == "true" ]]; then
  echo "ERROR: Choose only one of --postgres-only or --qdrant-only" >&2
  exit 1
fi

if [[ "$POSTGRES_ONLY" != "true" && "$QDRANT_ONLY" != "true" ]]; then
  POSTGRES_ONLY=false
  QDRANT_ONLY=false
fi

echo "== Backup Restore Drill =="
echo "Mode: $([[ "$EXECUTE" == "true" ]] && echo "EXECUTE" || echo "DRY-RUN")"
echo "Cleanup: $([[ "$CLEANUP" == "true" ]] && echo "ENABLED" || echo "DISABLED")"
echo ""

if [[ "$QDRANT_ONLY" != "true" ]]; then
  require_cmd psql
fi
if [[ "$POSTGRES_ONLY" != "true" ]]; then
  require_cmd curl
  require_cmd jq
fi

if [[ "$QDRANT_ONLY" != "true" ]]; then
  postgres_backup=$(find_latest_backup "$POSTGRES_BACKUP_DIR" "${DB_NAME}-*.sql*")
  if [[ -z "$postgres_backup" ]]; then
    echo "ERROR: No PostgreSQL backups found in ${POSTGRES_BACKUP_DIR}" >&2
    exit 1
  fi

  target_db="${DB_NAME}_restore_${timestamp}"
  echo "Postgres backup: $postgres_backup"
  echo "Target DB: $target_db"

  run_or_echo "${PROJECT_ROOT}/scripts/backup-postgresql.sh" restore "$postgres_backup" "$target_db"

  if [[ "$EXECUTE" == "true" ]]; then
    echo "Verifying Postgres restore..."
    table_count=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$target_db" -c "\\dt" 2>/dev/null | grep -c "^[[:space:]]*public" || echo "0")
    if [[ "$table_count" -gt 0 ]]; then
      echo "✓ Postgres restore verified (tables found: ${table_count})"
    else
      echo "⚠ Postgres restore completed but no tables detected; verify manually."
    fi
  fi

  if [[ "$EXECUTE" == "true" && "$CLEANUP" == "true" ]]; then
    echo "Cleaning up Postgres restore DB: $target_db"
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c "DROP DATABASE IF EXISTS ${target_db};" >/dev/null
  fi

  echo ""
fi

if [[ "$POSTGRES_ONLY" != "true" ]]; then
  qdrant_backup=$(find_latest_backup "$QDRANT_BACKUP_DIR" "*.snapshot")
  if [[ -z "$qdrant_backup" ]]; then
    echo "ERROR: No Qdrant backups found in ${QDRANT_BACKUP_DIR}" >&2
    exit 1
  fi

  base_collection=$(basename "$qdrant_backup" | sed -E 's/-[0-9]{8}-[0-9]{6}\\.snapshot$//')
  target_collection="${base_collection}_restore_${timestamp}"
  echo "Qdrant backup: $qdrant_backup"
  echo "Target collection: $target_collection"

  run_or_echo "${PROJECT_ROOT}/scripts/backup-qdrant.sh" restore "$qdrant_backup" "$target_collection"

  if [[ "$EXECUTE" == "true" ]]; then
    echo "Verifying Qdrant restore..."
    collection_info=$(curl -s --max-time "$CURL_TIMEOUT" --connect-timeout "$CURL_CONNECT_TIMEOUT" \
      "http://${QDRANT_HOST}:${QDRANT_PORT}/collections/${target_collection}" 2>/dev/null || echo "")
    points_count=$(echo "$collection_info" | jq -r '.result.points_count // 0' 2>/dev/null || echo "0")
    if [[ "$points_count" -gt 0 ]]; then
      echo "✓ Qdrant restore verified (points: ${points_count})"
    else
      echo "⚠ Qdrant restore completed but no points detected; verify manually."
    fi
  fi

  if [[ "$EXECUTE" == "true" && "$CLEANUP" == "true" ]]; then
    echo "Cleaning up Qdrant collection: $target_collection"
    curl -s --max-time "$CURL_TIMEOUT" --connect-timeout "$CURL_CONNECT_TIMEOUT" \
      -X DELETE "http://${QDRANT_HOST}:${QDRANT_PORT}/collections/${target_collection}" >/dev/null || true
  fi
fi

echo ""
echo "Restore drill complete."
