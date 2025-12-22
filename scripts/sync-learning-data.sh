#!/usr/bin/env bash
# Sync Learning Data from Runtime to Repo
# Extracts high-value patterns for federation
#
# Usage: bash scripts/sync-learning-data.sh
#
# This script:
# 1. Extracts high-value patterns (score >= 0.7) from runtime telemetry
# 2. Syncs fine-tuning dataset
# 3. Creates telemetry snapshots
# 4. Updates repo for federation

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
RUNTIME_DATA="${AI_STACK_DATA:-$HOME/.local/share/nixos-ai-stack}"
REPO_DATA="$REPO_ROOT/data"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }

# Check if jq is available
if ! command -v jq >/dev/null 2>&1; then
    log_warning "jq not found, pattern extraction will be skipped"
    HAS_JQ=false
else
    HAS_JQ=true
fi

# ==============================================================================
# Extract High-Value Patterns
# ==============================================================================
extract_patterns() {
    log_info "Extracting high-value patterns..."

    local source="$RUNTIME_DATA/telemetry/hybrid-events.jsonl"
    local dest_skills="$REPO_DATA/patterns/skills-patterns.jsonl"
    local dest_errors="$REPO_DATA/patterns/error-solutions.jsonl"
    local count=0

    if [[ ! -f "$source" ]]; then
        log_warning "No telemetry found at $source"
        return
    fi

    if [[ "$HAS_JQ" == "false" ]]; then
        log_warning "Skipping pattern extraction (jq not available)"
        return
    fi

    # Extract skills patterns (value_score >= 0.7)
    if jq -c 'select(.value_score >= 0.7 and .pattern_extracted == true)' "$source" >> "$dest_skills" 2>/dev/null; then
        # Deduplicate based on pattern_id or content hash
        sort -u "$dest_skills" -o "$dest_skills"
        count=$(wc -l < "$dest_skills" 2>/dev/null || echo 0)
        log_success "Extracted $count skills patterns"
    fi

    # Extract error solutions
    if jq -c 'select(.error_type != null and .solution != null and .confidence_score >= 0.7)' "$source" >> "$dest_errors" 2>/dev/null; then
        sort -u "$dest_errors" -o "$dest_errors"
        local error_count=$(wc -l < "$dest_errors" 2>/dev/null || echo 0)
        log_success "Extracted $error_count error solutions"
    fi
}

# ==============================================================================
# Sync Fine-Tuning Dataset
# ==============================================================================
sync_finetuning() {
    log_info "Syncing fine-tuning dataset..."

    local source="$RUNTIME_DATA/fine-tuning/dataset.jsonl"
    local dest="$REPO_DATA/fine-tuning/dataset.jsonl"
    local snapshot_dir="$REPO_DATA/fine-tuning/snapshots"

    if [[ ! -f "$source" ]]; then
        log_warning "No fine-tuning dataset found at $source"
        return
    fi

    # Copy to repo
    cp "$source" "$dest"

    # Create versioned snapshot
    local version=$(date +%Y-%m-%d)
    cp "$source" "$snapshot_dir/${version}.jsonl"

    # Update latest symlink
    ln -sf "${version}.jsonl" "$snapshot_dir/latest.jsonl"

    local lines=$(wc -l < "$dest" 2>/dev/null || echo 0)
    log_success "Synced fine-tuning dataset ($lines samples)"

    # Keep only last 5 snapshots
    ls -t "$snapshot_dir"/*.jsonl 2>/dev/null | grep -v latest | tail -n +6 | xargs rm -f 2>/dev/null || true
}

# ==============================================================================
# Create Telemetry Snapshot
# ==============================================================================
snapshot_telemetry() {
    log_info "Creating telemetry snapshot..."

    local source="$RUNTIME_DATA/telemetry/hybrid-events.jsonl"
    local dest="$REPO_DATA/telemetry/snapshots/$(date +%Y-%m-%d).jsonl"

    if [[ ! -f "$source" ]]; then
        log_warning "No telemetry found at $source"
        return
    fi

    if [[ "$HAS_JQ" == "false" ]]; then
        log_warning "Skipping telemetry snapshot (jq not available)"
        return
    fi

    # Last 1000 high-value events only (to keep size manageable)
    jq -c 'select(.value_score >= 0.7)' "$source" 2>/dev/null | tail -1000 > "$dest" || {
        log_warning "Failed to create telemetry snapshot"
        return
    }

    local lines=$(wc -l < "$dest" 2>/dev/null || echo 0)
    log_success "Created telemetry snapshot ($lines events)"

    # Keep only last 30 days of snapshots
    find "$REPO_DATA/telemetry/snapshots" -name "*.jsonl" -mtime +30 -delete 2>/dev/null || true
}

# ==============================================================================
# Update Metrics
# ==============================================================================
update_metrics() {
    log_info "Updating federation metrics..."

    local metrics_file="$REPO_DATA/metrics/monthly/$(date +%Y-%m).json"
    local patterns_count=$(wc -l < "$REPO_DATA/patterns/skills-patterns.jsonl" 2>/dev/null || echo 0)
    local finetuning_count=$(wc -l < "$REPO_DATA/fine-tuning/dataset.jsonl" 2>/dev/null || echo 0)

    cat > "$metrics_file" <<EOF
{
  "timestamp": "$(date -Iseconds)",
  "month": "$(date +%Y-%m)",
  "federation": {
    "patterns_total": $patterns_count,
    "fine_tuning_samples": $finetuning_count,
    "last_sync": "$(date -Iseconds)"
  }
}
EOF

    log_success "Updated federation metrics"
}

# ==============================================================================
# Main Execution
# ==============================================================================
main() {
    log_info "Starting learning data sync..."
    echo

    # Ensure directories exist
    mkdir -p "$REPO_DATA"/{patterns,fine-tuning/snapshots,telemetry/snapshots,metrics/monthly}

    # Run sync operations
    extract_patterns
    sync_finetuning
    snapshot_telemetry
    update_metrics

    echo
    log_success "✅ Learning data sync complete!"
    echo
    log_info "Next steps:"
    echo "  1. Review extracted patterns in data/patterns/"
    echo "  2. Commit to git: git add data/ && git commit -m 'Sync learned patterns'"
    echo "  3. Push to share: git push"
    echo
}

main "$@"
