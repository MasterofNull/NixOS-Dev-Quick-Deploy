#!/usr/bin/env bash
#
# P6-OPS-001: Telemetry Rotation Script
# Rotates and compresses old telemetry files to prevent disk space issues
#
# Usage:
#   ./scripts/rotate-telemetry.sh           # Rotate telemetry files
#   ./scripts/rotate-telemetry.sh --dry-run # Preview what would be done
#

set -euo pipefail

# Configuration
TELEMETRY_DIR="${TELEMETRY_DIR:-$HOME/.local/share/nixos-ai-stack/telemetry}"
KEEP_DAYS="${KEEP_DAYS:-30}"           # Keep files for 30 days
COMPRESS_DAYS="${COMPRESS_DAYS:-7}"    # Compress files older than 7 days
DRY_RUN="${1:-}"                        # --dry-run flag

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging
log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

# Check if dry run
is_dry_run() {
    [[ "$DRY_RUN" == "--dry-run" ]]
}

# Main rotation logic
main() {
    log_info "Telemetry Rotation Script"
    log_info "Telemetry directory: $TELEMETRY_DIR"
    log_info "Keep days: $KEEP_DAYS"
    log_info "Compress days: $COMPRESS_DAYS"

    if is_dry_run; then
        log_warn "DRY RUN MODE - No changes will be made"
    fi
    echo

    # Check if telemetry directory exists
    if [[ ! -d "$TELEMETRY_DIR" ]]; then
        log_error "Telemetry directory not found: $TELEMETRY_DIR"
        exit 1
    fi

    # Find telemetry files
    log_info "Scanning for telemetry files..."
    local file_count=0
    local compressed_count=0
    local deleted_count=0
    local total_size=0
    local freed_size=0

    # Process each telemetry file
    while IFS= read -r -d '' file; do
        ((file_count++))

        local file_size
        file_size=$(du -h "$file" | cut -f1)
        local file_age_days
        file_age_days=$(find "$file" -mtime +0 -printf '%Ad\n' 2>/dev/null || echo "0")

        # Calculate size in bytes for statistics
        local size_bytes
        size_bytes=$(stat -c%s "$file" 2>/dev/null || echo "0")
        total_size=$((total_size + size_bytes))

        # Delete files older than KEEP_DAYS
        if [[ $file_age_days -gt $KEEP_DAYS ]]; then
            log_info "🗑️  Deleting old file (${file_age_days}d): $(basename "$file") ($file_size)"

            if ! is_dry_run; then
                rm "$file"
            fi

            ((deleted_count++))
            freed_size=$((freed_size + size_bytes))
            continue
        fi

        # Compress files older than COMPRESS_DAYS (if not already compressed)
        if [[ $file_age_days -gt $COMPRESS_DAYS ]] && [[ ! "$file" =~ \.gz$ ]]; then
            log_info "📦 Compressing file (${file_age_days}d): $(basename "$file") ($file_size)"

            if ! is_dry_run; then
                gzip "$file"
            fi

            ((compressed_count++))
        fi

    done < <(find "$TELEMETRY_DIR" -name "*.jsonl" -o -name "*.jsonl.gz" -print0)

    # Summary
    echo
    log_info "Summary"
    log_info "  Files processed: $file_count"
    log_info "  Files compressed: $compressed_count"
    log_info "  Files deleted: $deleted_count"
    log_info "  Total size: $(numfmt --to=iec $total_size 2>/dev/null || echo "${total_size} bytes")"

    if [[ $freed_size -gt 0 ]]; then
        log_info "  Space freed: $(numfmt --to=iec $freed_size 2>/dev/null || echo "${freed_size} bytes")"
    fi

    # Current disk usage
    echo
    log_info "Current telemetry disk usage:"
    du -h "$TELEMETRY_DIR" 2>/dev/null || log_warn "Could not calculate disk usage"

    # List remaining files
    echo
    log_info "Remaining telemetry files:"
    local remaining_files
    remaining_files=$(find "$TELEMETRY_DIR" -name "*.jsonl" -o -name "*.jsonl.gz" | wc -l)

    if [[ $remaining_files -eq 0 ]]; then
        log_info "  No telemetry files remaining"
    else
        find "$TELEMETRY_DIR" -name "*.jsonl" -o -name "*.jsonl.gz" | while read -r file; do
            local age
            age=$(stat -c %Y "$file")
            local now
            now=$(date +%s)
            local days_old=$(( (now - age) / 86400 ))
            local size
            size=$(du -h "$file" | cut -f1)

            printf "  %-40s %3dd  %8s\n" "$(basename "$file")" "$days_old" "$size"
        done
    fi

    echo
    if is_dry_run; then
        log_warn "DRY RUN COMPLETE - Run without --dry-run to apply changes"
    else
        log_info "✅ Rotation complete"
    fi
}

# Run main function
main
