#!/usr/bin/env bash
#
# Generate NixOS configurations with help from the AI-Optimizer AIDB MCP server.
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Options:
  -d, --description TEXT   Description of what to configure (required)
  -t, --template FILE      Optional template/config used as additional context
  -o, --output FILE        Write generated config to file instead of stdout
  -r, --review             Run AI review on the generated configuration
  -h, --help               Show this help message
EOF
}

# Provide lightweight logging helpers if the deployment libraries were not sourced.
if ! declare -f log_info >/dev/null 2>&1; then
    log_info()    { printf '[INFO] %s\n' "$*"; }
    log_warning() { printf '[WARN] %s\n' "$*" >&2; }
    log_error()   { printf '[ERROR] %s\n' "$*" >&2; }
    log_success() { printf '[ OK ] %s\n' "$*"; }
fi

if [[ ! -f "${SCRIPT_DIR}/lib/ai-optimizer.sh" ]]; then
    log_error "lib/ai-optimizer.sh not found. Please run from the repository root."
    exit 1
fi

# shellcheck source=/dev/null
source "${SCRIPT_DIR}/lib/ai-optimizer.sh"

DESCRIPTION=""
TEMPLATE_PATH=""
OUTPUT_PATH=""
REVIEW=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        -d|--description)
            DESCRIPTION="$2"
            shift 2
            ;;
        -t|--template)
            TEMPLATE_PATH="$2"
            shift 2
            ;;
        -o|--output)
            OUTPUT_PATH="$2"
            shift 2
            ;;
        -r|--review)
            REVIEW=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

if [[ -z "$DESCRIPTION" ]]; then
    log_error "A description is required."
    usage
    exit 1
fi

if [[ -n "$TEMPLATE_PATH" && ! -f "$TEMPLATE_PATH" ]]; then
    log_error "Template file not found: $TEMPLATE_PATH"
    exit 1
fi

if ! ai_check_availability; then
    log_error "AI-Optimizer is not available at ${AIDB_BASE_URL}. Start the AIDB MCP stack and retry."
    exit 1
fi

CONTEXT=""
if [[ -n "$TEMPLATE_PATH" ]]; then
    CONTEXT="$(cat "$TEMPLATE_PATH")"
fi

log_info "Generating configuration with AI-Optimizer..."
if ! GENERATED_CONTENT="$(ai_generate_nix_config "$DESCRIPTION" "$CONTEXT")"; then
    log_error "Failed to generate configuration. Check AI-Optimizer logs for details."
    exit 1
fi

if $REVIEW; then
    tmpfile="$(mktemp)"
    trap 'rm -f "$tmpfile"' EXIT
    printf '%s\n' "$GENERATED_CONTENT" > "$tmpfile"
    log_info "Reviewing generated configuration..."
    if ai_review_config "$tmpfile"; then
        log_success "AI review complete."
    else
        log_warning "AI review failed."
    fi
fi

if [[ -n "$OUTPUT_PATH" ]]; then
    printf '%s\n' "$GENERATED_CONTENT" > "$OUTPUT_PATH"
    log_success "Configuration written to ${OUTPUT_PATH}"
else
    printf '%s\n' "$GENERATED_CONTENT"
fi
