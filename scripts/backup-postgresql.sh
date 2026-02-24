#!/usr/bin/env bash
# PostgreSQL Automated Backup Script
# Supports full dumps, incremental WAL archiving, and point-in-time recovery

set -euo pipefail

# Configuration
BACKUP_DIR="${BACKUP_DIR:-/var/backups/postgresql}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-${POSTGRES_PORT}}"
DB_NAME="${DB_NAME:-aidb}"
DB_USER="${DB_USER:-aidb}"
PGPASSWORD="${DB_PASSWORD:-aidb_password}"
export PGPASSWORD

RETENTION_DAYS="${RETENTION_DAYS:-7}"
RETENTION_WEEKS="${RETENTION_WEEKS:-4}"
RETENTION_MONTHS="${RETENTION_MONTHS:-12}"

COMPRESSION="${COMPRESSION:-gzip}"  # gzip, zstd, or none
ENCRYPTION="${ENCRYPTION:-false}"
ENCRYPTION_KEY="${ENCRYPTION_KEY:-}"

BACKUP_TYPE="${BACKUP_TYPE:-full}"  # full or incremental
VERIFY_BACKUP="${VERIFY_BACKUP:-true}"

# Prometheus metrics file
METRICS_FILE="${METRICS_FILE:-/var/lib/node_exporter/textfile_collector/postgres_backup.prom}"

# Logging
LOG_FILE="${LOG_FILE:-/var/log/postgresql-backup.log}"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

error() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $*" | tee -a "$LOG_FILE" >&2
}

# Create backup directory structure
setup_directories() {
    mkdir -p "$BACKUP_DIR"/{daily,weekly,monthly,wal}
    mkdir -p "$(dirname "$METRICS_FILE")"
    log "Backup directories created"
}

# Generate backup filename with timestamp
get_backup_filename() {
    local type="$1"
    local timestamp=$(date +%Y%m%d-%H%M%S)
    local filename="${DB_NAME}-${type}-${timestamp}"

    case "$COMPRESSION" in
        gzip)
            filename="${filename}.sql.gz"
            ;;
        zstd)
            filename="${filename}.sql.zst"
            ;;
        none)
            filename="${filename}.sql"
            ;;
    esac

    if [[ "$ENCRYPTION" == "true" ]]; then
        filename="${filename}.enc"
    fi

    echo "$filename"
}

# Perform full database backup
backup_full() {
    log "Starting full backup of $DB_NAME"

    local backup_file="$BACKUP_DIR/daily/$(get_backup_filename full)"
    local temp_file="${backup_file}.tmp"

    local start_time=$(date +%s)

    # pg_dump with optimal settings
    if ! pg_dump \
        --host="$DB_HOST" \
        --port="$DB_PORT" \
        --username="$DB_USER" \
        --dbname="$DB_NAME" \
        --format=plain \
        --no-owner \
        --no-acl \
        --verbose \
        --file=- 2>>"$LOG_FILE" | compress_and_encrypt > "$temp_file"; then
        error "pg_dump failed"
        rm -f "$temp_file"
        return 1
    fi

    mv "$temp_file" "$backup_file"

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    local size=$(stat -f%z "$backup_file" 2>/dev/null || stat -c%s "$backup_file")

    log "Full backup completed: $backup_file"
    log "  Size: $(numfmt --to=iec-i --suffix=B $size)"
    log "  Duration: ${duration}s"

    # Verify backup
    if [[ "$VERIFY_BACKUP" == "true" ]]; then
        verify_backup "$backup_file"
    fi

    # Update metrics
    update_metrics "full" "$backup_file" "$duration" "$size" "success"

    echo "$backup_file"
}

# Compress and optionally encrypt backup (reads stdin, writes stdout)
compress_and_encrypt() {
    if [[ "$ENCRYPTION" == "true" ]] && [[ -z "${ENCRYPTION_KEY:-}" ]]; then
        error "Encryption enabled but no key provided"
        return 1
    fi

    # Compression stage
    case "$COMPRESSION" in
        gzip) gzip -9 ;;
        zstd) zstd -19 -T0 ;;
        *)    cat ;;
    esac | {
        # Encryption stage
        if [[ "$ENCRYPTION" == "true" ]]; then
            openssl enc -aes-256-cbc -salt -pbkdf2 -pass "pass:${ENCRYPTION_KEY}"
        else
            cat
        fi
    }
}

# Decompress and optionally decrypt backup (reads file, writes stdout)
decompress_and_decrypt() {
    local backup_file="$1"

    # Decryption stage (reads file)
    if [[ "$backup_file" == *.enc ]]; then
        if [[ -z "${ENCRYPTION_KEY:-}" ]]; then
            error "Backup is encrypted but no key provided"
            return 1
        fi
        openssl enc -aes-256-cbc -d -pbkdf2 -pass "pass:${ENCRYPTION_KEY}" < "$backup_file"
    else
        cat < "$backup_file"
    fi | {
        # Decompression stage
        if [[ "$backup_file" == *.gz* ]]; then
            gunzip
        elif [[ "$backup_file" == *.zst* ]]; then
            zstd -d
        else
            cat
        fi
    }
}

# Verify backup integrity
verify_backup() {
    local backup_file="$1"
    log "Verifying backup: $backup_file"

    # Test decompression/decryption
    if ! decompress_and_decrypt "$backup_file" | head -n 1 > /dev/null; then
        error "Backup verification failed: cannot decompress/decrypt"
        update_metrics "verification" "$backup_file" 0 0 "failed"
        return 1
    fi

    # Test SQL syntax (first 100 lines)
    if ! decompress_and_decrypt "$backup_file" | head -n 100 | grep -q "CREATE TABLE\|INSERT INTO\|PostgreSQL database dump"; then
        error "Backup verification failed: invalid SQL content"
        update_metrics "verification" "$backup_file" 0 0 "failed"
        return 1
    fi

    log "✓ Backup verified successfully"
    update_metrics "verification" "$backup_file" 0 0 "success"
}

# Archive WAL files for point-in-time recovery
archive_wal() {
    log "Archiving WAL files"

    # Get WAL files from PostgreSQL data directory
    local wal_dir="${PG_DATA_DIR:-/var/lib/postgresql/data}/pg_wal"
    local archive_dir="$BACKUP_DIR/wal"

    if [[ ! -d "$wal_dir" ]]; then
        log "WAL directory not found, skipping WAL archiving"
        return 0
    fi

    # Archive completed WAL segments
    find "$wal_dir" -type f -name "*.ready" | while read ready_file; do
        local wal_file=$(basename "$ready_file" .ready)
        local wal_path="$wal_dir/$wal_file"
        local archive_path="$archive_dir/${wal_file}.gz"

        if [[ -f "$wal_path" ]]; then
            gzip -c "$wal_path" > "$archive_path"
            log "Archived WAL: $wal_file"
        fi
    done
}

# Rotate backups according to retention policy
rotate_backups() {
    log "Rotating backups (retention: ${RETENTION_DAYS}d/${RETENTION_WEEKS}w/${RETENTION_MONTHS}m)"

    # Promote daily to weekly (keep last backup of each week)
    local last_weekly=$(date -d "1 week ago" +%Y%m%d)
    find "$BACKUP_DIR/daily" -type f -name "${DB_NAME}-*" -mtime +7 | while read backup; do
        local backup_date=$(basename "$backup" | grep -oP '\d{8}' | head -1)
        if [[ "$backup_date" -ge "$last_weekly" ]]; then
            mv "$backup" "$BACKUP_DIR/weekly/"
            log "Promoted to weekly: $(basename $backup)"
        fi
    done

    # Promote weekly to monthly (keep last backup of each month)
    local last_monthly=$(date -d "1 month ago" +%Y%m%d)
    find "$BACKUP_DIR/weekly" -type f -name "${DB_NAME}-*" -mtime +30 | while read backup; do
        local backup_date=$(basename "$backup" | grep -oP '\d{8}' | head -1)
        if [[ "$backup_date" -ge "$last_monthly" ]]; then
            mv "$backup" "$BACKUP_DIR/monthly/"
            log "Promoted to monthly: $(basename $backup)"
        fi
    done

    # Delete old backups
    find "$BACKUP_DIR/daily" -type f -mtime +$RETENTION_DAYS -delete
    find "$BACKUP_DIR/weekly" -type f -mtime +$((RETENTION_WEEKS * 7)) -delete
    find "$BACKUP_DIR/monthly" -type f -mtime +$((RETENTION_MONTHS * 30)) -delete

    # Clean old WAL files (keep 7 days)
    find "$BACKUP_DIR/wal" -type f -mtime +7 -delete

    log "Backup rotation complete"
}

# Update Prometheus metrics
update_metrics() {
    local backup_type="$1"
    local backup_file="$2"
    local duration="$3"
    local size="$4"
    local status="$5"

    local timestamp=$(date +%s)

    cat > "$METRICS_FILE" <<EOF
# HELP postgres_backup_last_success_timestamp Unix timestamp of last successful backup
# TYPE postgres_backup_last_success_timestamp gauge
postgres_backup_last_success_timestamp{database="$DB_NAME",type="$backup_type"} $timestamp

# HELP postgres_backup_duration_seconds Duration of last backup in seconds
# TYPE postgres_backup_duration_seconds gauge
postgres_backup_duration_seconds{database="$DB_NAME",type="$backup_type"} $duration

# HELP postgres_backup_size_bytes Size of last backup in bytes
# TYPE postgres_backup_size_bytes gauge
postgres_backup_size_bytes{database="$DB_NAME",type="$backup_type"} $size

# HELP postgres_backup_status Status of last backup (1=success, 0=failure)
# TYPE postgres_backup_status gauge
postgres_backup_status{database="$DB_NAME",type="$backup_type"} $([ "$status" == "success" ] && echo 1 || echo 0)

# HELP postgres_backup_total Total number of backups performed
# TYPE postgres_backup_total counter
postgres_backup_total{database="$DB_NAME",type="$backup_type",status="$status"} 1
EOF
}

# List available backups
list_backups() {
    echo "Available backups for $DB_NAME:"
    echo ""
    echo "DAILY:"
    ls -lh "$BACKUP_DIR/daily/${DB_NAME}"* 2>/dev/null || echo "  (none)"
    echo ""
    echo "WEEKLY:"
    ls -lh "$BACKUP_DIR/weekly/${DB_NAME}"* 2>/dev/null || echo "  (none)"
    echo ""
    echo "MONTHLY:"
    ls -lh "$BACKUP_DIR/monthly/${DB_NAME}"* 2>/dev/null || echo "  (none)"
}

# Restore from backup
restore_backup() {
    local backup_file="$1"
    local target_db="${2:-${DB_NAME}_restore}"

    if [[ ! -f "$backup_file" ]]; then
        error "Backup file not found: $backup_file"
        return 1
    fi

    log "Restoring from backup: $backup_file"
    log "Target database: $target_db"

    # Create target database
    log "Creating database: $target_db"
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres <<EOF
DROP DATABASE IF EXISTS $target_db;
CREATE DATABASE $target_db;
EOF

    # Restore backup
    log "Restoring data..."
    if ! decompress_and_decrypt "$backup_file" | \
        psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$target_db" > /dev/null 2>>"$LOG_FILE"; then
        error "Restore failed"
        return 1
    fi

    log "✓ Restore completed successfully"
    log "  Database: $target_db"
    log "  To use: psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $target_db"
}

# Main execution
main() {
    local command="${1:-backup}"

    setup_directories

    case "$command" in
        backup)
            backup_full
            archive_wal
            rotate_backups
            ;;
        list)
            list_backups
            ;;
        restore)
            if [[ -z "${2:-}" ]]; then
                error "Usage: $0 restore <backup_file> [target_db]"
                exit 1
            fi
            restore_backup "$2" "${3:-}"
            ;;
        verify)
            if [[ -z "${2:-}" ]]; then
                error "Usage: $0 verify <backup_file>"
                exit 1
            fi
            verify_backup "$2"
            ;;
        *)
            echo "Usage: $0 {backup|list|restore|verify}"
            echo ""
            echo "Commands:"
            echo "  backup              - Perform full backup"
            echo "  list                - List available backups"
            echo "  restore <file> [db] - Restore from backup"
            echo "  verify <file>       - Verify backup integrity"
            echo ""
            echo "Environment variables:"
            echo "  BACKUP_DIR          - Backup directory (default: /var/backups/postgresql)"
            echo "  DB_HOST             - Database host (default: localhost)"
            echo "  DB_PORT             - Database port (default: POSTGRES_PORT)"
            echo "  DB_NAME             - Database name (default: aidb)"
            echo "  DB_USER             - Database user (default: aidb)"
            echo "  DB_PASSWORD         - Database password"
            echo "  RETENTION_DAYS      - Daily retention (default: 7)"
            echo "  RETENTION_WEEKS     - Weekly retention (default: 4)"
            echo "  RETENTION_MONTHS    - Monthly retention (default: 12)"
            echo "  COMPRESSION         - Compression: gzip|zstd|none (default: gzip)"
            echo "  ENCRYPTION          - Enable encryption: true|false (default: false)"
            echo "  ENCRYPTION_KEY      - Encryption passphrase"
            exit 1
            ;;
    esac
}

main "$@"
