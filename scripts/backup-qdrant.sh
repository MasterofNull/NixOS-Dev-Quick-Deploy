#!/usr/bin/env bash
# Qdrant Vector Database Automated Backup Script
# Supports collection snapshots, verification, and restoration

set -euo pipefail

# Configuration
BACKUP_DIR="${BACKUP_DIR:-/var/backups/qdrant}"
QDRANT_HOST="${QDRANT_HOST:-localhost}"
QDRANT_PORT="${QDRANT_PORT:-6333}"
QDRANT_API_KEY="${QDRANT_API_KEY:-}"
CURL_TIMEOUT="${CURL_TIMEOUT:-30}"
CURL_CONNECT_TIMEOUT="${CURL_CONNECT_TIMEOUT:-5}"

RETENTION_DAYS="${RETENTION_DAYS:-7}"
RETENTION_WEEKS="${RETENTION_WEEKS:-4}"
RETENTION_MONTHS="${RETENTION_MONTHS:-12}"

VERIFY_BACKUP="${VERIFY_BACKUP:-true}"

# Prometheus metrics file
METRICS_FILE="${METRICS_FILE:-/var/lib/node_exporter/textfile_collector/qdrant_backup.prom}"

# Logging
LOG_FILE="${LOG_FILE:-/var/log/qdrant-backup.log}"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE" >&2
}

error() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $*" | tee -a "$LOG_FILE" >&2
}

# Setup directories
setup_directories() {
    mkdir -p "$BACKUP_DIR"/{daily,weekly,monthly}
    mkdir -p "$(dirname "$METRICS_FILE")"
    log "Backup directories created"
}

# Build curl command with optional API key
qdrant_curl() {
    local method="$1"
    local path="$2"
    shift 2

    local api_header=()
    if [[ -n "${QDRANT_API_KEY:-}" ]]; then
        api_header=(-H "api-key: $QDRANT_API_KEY")
    fi

    curl -s --max-time "${CURL_TIMEOUT}" \
        --connect-timeout "${CURL_CONNECT_TIMEOUT}" \
        -X "$method" \
        "${api_header[@]}" \
        "http://${QDRANT_HOST}:${QDRANT_PORT}${path}" \
        "$@"
}

# Get list of collections
get_collections() {
    qdrant_curl GET "/collections" | jq -r '.result.collections[].name' 2>/dev/null || echo ""
}

# Create snapshot for a collection
create_snapshot() {
    local collection="$1"
    log "Creating snapshot for collection: $collection"

    local response=$(qdrant_curl POST "/collections/$collection/snapshots")
    local snapshot_name=$(echo "$response" | jq -r '.result.name' 2>/dev/null)

    if [[ -z "$snapshot_name" || "$snapshot_name" == "null" ]]; then
        error "Failed to create snapshot for $collection"
        error "Response: $response"
        return 1
    fi

    log "✓ Snapshot created: $snapshot_name"
    echo "$snapshot_name"
}

# Download snapshot
download_snapshot() {
    local collection="$1"
    local snapshot_name="$2"
    local output_file="$3"

    log "Downloading snapshot: $snapshot_name"

    local tmp_root="${TMPDIR:-/${TMP_FALLBACK:-tmp}}"
    local http_code_file="${tmp_root}/qdrant_http_code"

    if ! qdrant_curl GET "/collections/$collection/snapshots/$snapshot_name" \
        -o "$output_file" \
        -w "%{http_code}" > "$http_code_file"; then
        error "Failed to download snapshot"
        return 1
    fi

    local http_code=$(cat "$http_code_file")
    if [[ "$http_code" != "200" ]]; then
        error "HTTP error $http_code downloading snapshot"
        rm -f "$output_file"
        return 1
    fi

    local size=$(stat -f%z "$output_file" 2>/dev/null || stat -c%s "$output_file")
    log "✓ Snapshot downloaded: $(numfmt --to=iec-i --suffix=B $size)"
}

# Delete snapshot from Qdrant
delete_snapshot() {
    local collection="$1"
    local snapshot_name="$2"

    log "Deleting remote snapshot: $snapshot_name"
    qdrant_curl DELETE "/collections/$collection/snapshots/$snapshot_name" > /dev/null
}

# Backup single collection
backup_collection() {
    local collection="$1"
    local backup_subdir="$2"

    log "Backing up collection: $collection"

    local timestamp=$(date +%Y%m%d-%H%M%S)
    local backup_file="$BACKUP_DIR/$backup_subdir/${collection}-${timestamp}.snapshot"
    local temp_file="${backup_file}.tmp"

    local start_time=$(date +%s)

    # Create snapshot
    local snapshot_name=$(create_snapshot "$collection")
    if [[ -z "$snapshot_name" ]]; then
        return 1
    fi

    # Download snapshot
    if ! download_snapshot "$collection" "$snapshot_name" "$temp_file"; then
        delete_snapshot "$collection" "$snapshot_name" || true
        return 1
    fi

    # Delete remote snapshot (keep only local copy)
    delete_snapshot "$collection" "$snapshot_name"

    # Move to final location
    mv "$temp_file" "$backup_file"

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    local size=$(stat -f%z "$backup_file" 2>/dev/null || stat -c%s "$backup_file")

    log "✓ Backup completed: $backup_file"
    log "  Size: $(numfmt --to=iec-i --suffix=B $size)"
    log "  Duration: ${duration}s"

    # Verify backup
    if [[ "$VERIFY_BACKUP" == "true" ]]; then
        verify_backup "$backup_file"
    fi

    # Update metrics
    update_metrics "$collection" "$backup_file" "$duration" "$size" "success"

    echo "$backup_file"
}

# Backup all collections
backup_all() {
    log "Starting backup of all Qdrant collections"

    local collections=$(get_collections)
    if [[ -z "$collections" ]]; then
        error "No collections found or cannot connect to Qdrant"
        return 1
    fi

    local success_count=0
    local fail_count=0

    for collection in $collections; do
        if backup_collection "$collection" "daily"; then
            ((success_count++))
        else
            ((fail_count++))
        fi
    done

    log "Backup summary: $success_count succeeded, $fail_count failed"

    if [[ $fail_count -gt 0 ]]; then
        return 1
    fi
}

# Verify backup integrity
verify_backup() {
    local backup_file="$1"
    log "Verifying backup: $backup_file"

    # Check if file is a valid tar archive (Qdrant snapshots may be tar or tar.gz)
    if ! tar -tf "$backup_file" > /dev/null 2>&1; then
        if ! tar -tzf "$backup_file" > /dev/null 2>&1; then
            error "Backup verification failed: not a valid tar archive"
            update_metrics "verification" "$backup_file" 0 0 "failed"
            return 1
        fi
    fi

    # Check if contains expected files
    local tar_list
    if tar_list=$(tar -tf "$backup_file" 2>/dev/null); then
        :
    elif tar_list=$(tar -tzf "$backup_file" 2>/dev/null); then
        :
    else
        error "Backup verification failed: cannot list snapshot contents"
        update_metrics "verification" "$backup_file" 0 0 "failed"
        return 1
    fi

    if ! echo "$tar_list" | grep -q "collection.json\|segments"; then
        error "Backup verification failed: missing collection data"
        update_metrics "verification" "$backup_file" 0 0 "failed"
        return 1
    fi

    log "✓ Backup verified successfully"
    update_metrics "verification" "$backup_file" 0 0 "success"
}

# Restore collection from backup
restore_collection() {
    local backup_file="$1"
    local target_collection="${2:-}"

    if [[ ! -f "$backup_file" ]]; then
        error "Backup file not found: $backup_file"
        return 1
    fi

    # Extract collection name from backup filename if not specified
    if [[ -z "$target_collection" ]]; then
        target_collection=$(basename "$backup_file" | sed 's/-[0-9]\{8\}-[0-9]\{6\}\.snapshot$//')
        log "Target collection: $target_collection (auto-detected)"
    fi

    log "Restoring collection: $target_collection"
    log "From backup: $backup_file"

    # Upload snapshot to Qdrant
    local snapshot_name=$(basename "$backup_file")

    log "Uploading snapshot to Qdrant..."
    local tmp_root="${TMPDIR:-/${TMP_FALLBACK:-tmp}}"
    local http_code_file="${tmp_root}/qdrant_http_code"

    if ! qdrant_curl PUT "/collections/$target_collection/snapshots/upload" \
        -F "snapshot=@$backup_file" \
        -w "%{http_code}" > "$http_code_file" 2>>"$LOG_FILE"; then
        error "Failed to upload snapshot"
        return 1
    fi

    local http_code=$(cat "$http_code_file")
    if [[ "$http_code" != "200" && "$http_code" != "201" ]]; then
        error "HTTP error $http_code uploading snapshot"
        return 1
    fi

    log "✓ Collection restored successfully"
    log "  Collection: $target_collection"
}

# Rotate backups according to retention policy
rotate_backups() {
    log "Rotating backups (retention: ${RETENTION_DAYS}d/${RETENTION_WEEKS}w/${RETENTION_MONTHS}m)"

    # Promote daily to weekly
    find "$BACKUP_DIR/daily" -type f -name "*.snapshot" -mtime +7 | while read backup; do
        mv "$backup" "$BACKUP_DIR/weekly/"
        log "Promoted to weekly: $(basename $backup)"
    done

    # Promote weekly to monthly
    find "$BACKUP_DIR/weekly" -type f -name "*.snapshot" -mtime +30 | while read backup; do
        mv "$backup" "$BACKUP_DIR/monthly/"
        log "Promoted to monthly: $(basename $backup)"
    done

    # Delete old backups
    find "$BACKUP_DIR/daily" -type f -mtime +$RETENTION_DAYS -delete
    find "$BACKUP_DIR/weekly" -type f -mtime +$((RETENTION_WEEKS * 7)) -delete
    find "$BACKUP_DIR/monthly" -type f -mtime +$((RETENTION_MONTHS * 30)) -delete

    log "Backup rotation complete"
}

# Update Prometheus metrics
update_metrics() {
    local collection="$1"
    local backup_file="$2"
    local duration="$3"
    local size="$4"
    local status="$5"

    local timestamp=$(date +%s)

    cat >> "$METRICS_FILE" <<EOF
# HELP qdrant_backup_last_success_timestamp Unix timestamp of last successful backup
# TYPE qdrant_backup_last_success_timestamp gauge
qdrant_backup_last_success_timestamp{collection="$collection"} $timestamp

# HELP qdrant_backup_duration_seconds Duration of last backup in seconds
# TYPE qdrant_backup_duration_seconds gauge
qdrant_backup_duration_seconds{collection="$collection"} $duration

# HELP qdrant_backup_size_bytes Size of last backup in bytes
# TYPE qdrant_backup_size_bytes gauge
qdrant_backup_size_bytes{collection="$collection"} $size

# HELP qdrant_backup_status Status of last backup (1=success, 0=failure)
# TYPE qdrant_backup_status gauge
qdrant_backup_status{collection="$collection"} $([ "$status" == "success" ] && echo 1 || echo 0)
EOF
}

# List available backups
list_backups() {
    echo "Available Qdrant backups:"
    echo ""
    echo "DAILY:"
    ls -lh "$BACKUP_DIR/daily"/*.snapshot 2>/dev/null || echo "  (none)"
    echo ""
    echo "WEEKLY:"
    ls -lh "$BACKUP_DIR/weekly"/*.snapshot 2>/dev/null || echo "  (none)"
    echo ""
    echo "MONTHLY:"
    ls -lh "$BACKUP_DIR/monthly"/*.snapshot 2>/dev/null || echo "  (none)"
}

# List collections in Qdrant
list_collections() {
    echo "Collections in Qdrant:"
    local collections=$(get_collections)
    if [[ -z "$collections" ]]; then
        echo "  (none or cannot connect)"
    else
        echo "$collections" | while read collection; do
            # Get collection info
            local info=$(qdrant_curl GET "/collections/$collection")
            local vectors_count=$(echo "$info" | jq -r '.result.vectors_count // 0')
            local points_count=$(echo "$info" | jq -r '.result.points_count // 0')
            echo "  $collection: $points_count points, $vectors_count vectors"
        done
    fi
}

# Main execution
main() {
    local command="${1:-backup}"

    setup_directories

    case "$command" in
        backup)
            if [[ -n "${2:-}" ]]; then
                # Backup specific collection
                backup_collection "$2" "daily"
            else
                # Backup all collections
                backup_all
            fi
            rotate_backups
            ;;
        list)
            list_backups
            ;;
        list-collections)
            list_collections
            ;;
        restore)
            if [[ -z "${2:-}" ]]; then
                error "Usage: $0 restore <backup_file> [target_collection]"
                exit 1
            fi
            restore_collection "$2" "${3:-}"
            ;;
        verify)
            if [[ -z "${2:-}" ]]; then
                error "Usage: $0 verify <backup_file>"
                exit 1
            fi
            verify_backup "$2"
            ;;
        *)
            echo "Usage: $0 {backup|list|list-collections|restore|verify}"
            echo ""
            echo "Commands:"
            echo "  backup [collection]       - Backup all or specific collection"
            echo "  list                      - List available backups"
            echo "  list-collections          - List collections in Qdrant"
            echo "  restore <file> [coll]     - Restore from backup"
            echo "  verify <file>             - Verify backup integrity"
            echo ""
            echo "Environment variables:"
            echo "  BACKUP_DIR          - Backup directory (default: /var/backups/qdrant)"
            echo "  QDRANT_HOST         - Qdrant host (default: localhost)"
            echo "  QDRANT_PORT         - Qdrant port (default: 6333)"
            echo "  QDRANT_API_KEY      - Qdrant API key (optional)"
            echo "  RETENTION_DAYS      - Daily retention (default: 7)"
            echo "  RETENTION_WEEKS     - Weekly retention (default: 4)"
            echo "  RETENTION_MONTHS    - Monthly retention (default: 12)"
            exit 1
            ;;
    esac
}

main "$@"
