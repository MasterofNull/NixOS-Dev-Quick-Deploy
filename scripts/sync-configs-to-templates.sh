#!/usr/bin/env bash
# Sync validated user configs to templates
# Auto-sync mechanism for template propagation
# Author: Claude Code (Vibe Coding System)
# Date: 2025-12-31

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TEMPLATES_DIR="${PROJECT_ROOT}/templates"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}✓${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}⚠${NC} $*"
}

log_error() {
    echo -e "${RED}✗${NC} $*"
}

# Sync a single config file
sync_config() {
    local source="$1"
    local dest="$2"
    local source_expanded="${source/#\~/$HOME}"

    if [[ ! -f "$source_expanded" ]]; then
        log_warn "Source file not found: $source"
        return 1
    fi

    # Validate JSON if applicable
    if [[ "$source_expanded" =~ \.json$ ]]; then
        if ! jq empty "$source_expanded" 2>/dev/null; then
            log_error "Invalid JSON in $source"
            return 1
        fi
    fi

    # Create destination directory
    mkdir -p "$(dirname "$dest")"

    # Backup existing template
    if [[ -f "$dest" ]]; then
        cp "$dest" "${dest}.backup"
        log_info "Backed up existing template: ${dest}.backup"
    fi

    # Copy file
    cp "$source_expanded" "$dest"

    # Add sync metadata to JSON files
    if [[ "$dest" =~ \.json$ ]]; then
        local temp_file="${dest}.tmp"
        jq ". + {\"_sync_metadata\": {\"synced_at\": \"$(date -Iseconds)\", \"source\": \"$source\"}}" \
            "$dest" > "$temp_file"
        mv "$temp_file" "$dest"
    fi

    log_info "Synced: $source → $(basename "$dest")"
    return 0
}

# Check for hardcoded secrets in files
check_secrets() {
    local file="$1"

    local secret_patterns=(
        "password.*=.*[^_PASSWORD]"
        "api_key.*=.*[^_KEY]"
        "token.*=.*[^_TOKEN]"
        "secret.*=.*[^_SECRET]"
    )

    local found_secrets=0

    for pattern in "${secret_patterns[@]}"; do
        if grep -iE "$pattern" "$file" >/dev/null 2>&1; then
            log_warn "Possible hardcoded secret detected in $file (pattern: $pattern)"
            ((found_secrets++))
        fi
    done

    return $found_secrets
}

# Main sync process
main() {
    echo "====================================="
    echo "  Config → Template Auto-Sync"
    echo "====================================="
    echo ""

    local errors=0
    local warnings=0
    local synced=0

    # VSCode settings
    if sync_config \
        "~/.config/VSCodium/User/settings.json" \
        "${TEMPLATES_DIR}/vscode/settings.json"; then
        ((synced++))
        if check_secrets "${TEMPLATES_DIR}/vscode/settings.json"; then
            ((warnings++))
        fi
    else
        ((errors++))
    fi

    # Continue config
    if sync_config \
        "~/.continue/config.json" \
        "${TEMPLATES_DIR}/vscode/continue/config.json"; then
        ((synced++))
        if check_secrets "${TEMPLATES_DIR}/vscode/continue/config.json"; then
            ((warnings++))
        fi
    else
        ((errors++))
    fi

    # Claude Code MCP config
    if sync_config \
        "~/.claude-code/mcp_servers.json" \
        "${TEMPLATES_DIR}/vscode/claude-code/mcp_servers.json"; then
        ((synced++))
        if check_secrets "${TEMPLATES_DIR}/vscode/claude-code/mcp_servers.json"; then
            ((warnings++))
        fi
    else
        ((errors++))
    fi

    # AI Stack .env (example only, not actual .env with secrets)
    if [[ -f "${HOME}/.config/nixos-ai-stack/.env" ]]; then
        # Don't sync actual .env, only update .env.example with new keys
        log_info "Skipping .env sync (contains secrets), .env.example should be updated manually"
    fi

    echo ""
    echo "====================================="
    echo "  Sync Summary"
    echo "====================================="
    echo "Synced:   $synced file(s)"
    echo "Errors:   $errors error(s)"
    echo "Warnings: $warnings warning(s)"
    echo ""

    if (( errors > 0 )); then
        log_error "Sync completed with errors"
        return 1
    elif (( warnings > 0 )); then
        log_warn "Sync completed with warnings (review secrets)"
        return 0
    else
        log_info "Sync completed successfully"
        return 0
    fi
}

# Run main function
main "$@"
