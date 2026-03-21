#!/usr/bin/env bash
# lib/deploy/auto-enable-features.sh
# Phase 4.5: Auto-Enable Features
#
# Automatic feature detection and enabling based on system capabilities
# No manual intervention required - features auto-enable when appropriate

set -euo pipefail

# Source common utilities if available
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

if [[ -f "${ROOT_DIR}/lib/logging.sh" ]]; then
    source "${ROOT_DIR}/lib/logging.sh"
else
    log() { echo "[auto-enable] $*"; }
    warn() { echo "[warning] $*" >&2; }
    error() { echo "[error] $*" >&2; }
fi

# Feature state tracking
declare -A ENABLED_FEATURES
declare -A SKIPPED_FEATURES
declare -A FEATURE_REASONS

# Detect system capabilities
detect_cpu_cores() {
    nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo "1"
}

detect_total_ram_gb() {
    local ram_kb
    if [[ -f /proc/meminfo ]]; then
        ram_kb=$(awk '/MemTotal/ {print $2}' /proc/meminfo)
        echo "$((ram_kb / 1024 / 1024))"
    else
        echo "0"
    fi
}

detect_gpu_available() {
    # Check for NVIDIA GPU
    if command -v nvidia-smi &>/dev/null; then
        if nvidia-smi &>/dev/null; then
            echo "nvidia"
            return 0
        fi
    fi

    # Check for AMD GPU
    if command -v rocm-smi &>/dev/null; then
        echo "amd"
        return 0
    fi

    # Check for Intel GPU
    if [[ -d /sys/class/drm ]] && ls /sys/class/drm/card*/device/vendor 2>/dev/null | xargs cat 2>/dev/null | grep -q "0x8086"; then
        echo "intel"
        return 0
    fi

    echo "none"
    return 1
}

detect_vulkan_support() {
    if command -v vulkaninfo &>/dev/null; then
        if vulkaninfo --summary &>/dev/null; then
            return 0
        fi
    fi
    return 1
}

detect_llama_model() {
    local model_dir="/var/lib/llama-cpp/models"
    local model_file="${model_dir}/llama.gguf"

    if [[ -f "${model_file}" ]]; then
        # Try to detect model family from filename or metadata
        if grep -q "qwen" <<< "${model_file,,}"; then
            echo "qwen"
        elif grep -q "deepseek" <<< "${model_file,,}"; then
            echo "deepseek"
        else
            echo "unknown"
        fi
    else
        echo "none"
    fi
}

# Auto-enable core features (Category A - already enabled by default)
enable_core_features() {
    log "Enabling core features (Category A)..."

    local core_features=(
        "AI_CONTEXT_COMPRESSION_ENABLED"
        "AI_HARNESS_ENABLED"
        "AI_MEMORY_ENABLED"
        "AI_TREE_SEARCH_ENABLED"
        "AI_HARNESS_EVAL_ENABLED"
        "AI_CAPABILITY_DISCOVERY_ENABLED"
        "AI_PROMPT_CACHE_POLICY_ENABLED"
        "AI_TASK_CLASSIFICATION_ENABLED"
        "AI_WEB_RESEARCH_ENABLED"
        "AI_BROWSER_RESEARCH_ENABLED"
        "AI_HINT_FEEDBACK_DB_ENABLED"
        "AI_HINT_BANDIT_ENABLED"
        "CONTINUOUS_LEARNING_ENABLED"
        "OPTIMIZATION_PROPOSALS_ENABLED"
        "OPTIMIZATION_PROPOSAL_SUBMISSION_ENABLED"
        "RATE_LIMIT_ENABLED"
        "OTEL_TRACING_ENABLED"
        "TELEMETRY_ENABLED"
        "AI_TOOL_SECURITY_AUDIT_ENABLED"
    )

    for feature in "${core_features[@]}"; do
        # Set to true if not already set
        if [[ -z "${!feature:-}" ]]; then
            export "${feature}=true"
        fi
        ENABLED_FEATURES["${feature}"]="true"
        FEATURE_REASONS["${feature}"]="Core feature - always enabled"
    done

    log "Enabled ${#core_features[@]} core features"
}

# Conditionally enable performance features (Category D)
enable_conditional_features() {
    log "Evaluating conditional features (Category D)..."

    local cpu_cores=$(detect_cpu_cores)
    local ram_gb=$(detect_total_ram_gb)
    local gpu_type=$(detect_gpu_available || echo "none")
    local model_family=$(detect_llama_model)
    local has_vulkan=$(detect_vulkan_support && echo "true" || echo "false")

    log "System capabilities:"
    log "  - CPU cores: ${cpu_cores}"
    log "  - RAM: ${ram_gb} GB"
    log "  - GPU: ${gpu_type}"
    log "  - Vulkan: ${has_vulkan}"
    log "  - Model: ${model_family}"

    # AI_SPECULATIVE_DECODING_ENABLED
    # Requires: Qwen/DeepSeek model + 16GB+ RAM + GPU acceleration
    if [[ "${model_family}" =~ ^(qwen|deepseek)$ ]] && \
       [[ "${ram_gb}" -ge 16 ]] && \
       [[ "${gpu_type}" != "none" || "${has_vulkan}" == "true" ]]; then
        export AI_SPECULATIVE_DECODING_ENABLED="true"
        ENABLED_FEATURES["AI_SPECULATIVE_DECODING_ENABLED"]="true"
        FEATURE_REASONS["AI_SPECULATIVE_DECODING_ENABLED"]="Auto-enabled: ${model_family} model + ${ram_gb}GB RAM + ${gpu_type} GPU"
        log "✓ Enabled AI_SPECULATIVE_DECODING_ENABLED"
    else
        SKIPPED_FEATURES["AI_SPECULATIVE_DECODING_ENABLED"]="true"
        FEATURE_REASONS["AI_SPECULATIVE_DECODING_ENABLED"]="Requires Qwen/DeepSeek model + 16GB+ RAM + GPU"
        log "✗ Skipped AI_SPECULATIVE_DECODING_ENABLED (insufficient resources)"
    fi

    # AI_LLM_EXPANSION_ENABLED
    # Requires: 4+ CPU cores + opt-in flag
    local expansion_opt_in="${AI_LLM_EXPANSION_OPT_IN:-false}"
    if [[ "${cpu_cores}" -ge 4 ]] && [[ "${expansion_opt_in}" == "true" ]]; then
        export AI_LLM_EXPANSION_ENABLED="true"
        ENABLED_FEATURES["AI_LLM_EXPANSION_ENABLED"]="true"
        FEATURE_REASONS["AI_LLM_EXPANSION_ENABLED"]="Auto-enabled: ${cpu_cores} cores + user opt-in"
        log "✓ Enabled AI_LLM_EXPANSION_ENABLED"
    else
        SKIPPED_FEATURES["AI_LLM_EXPANSION_ENABLED"]="true"
        if [[ "${cpu_cores}" -lt 4 ]]; then
            FEATURE_REASONS["AI_LLM_EXPANSION_ENABLED"]="Requires 4+ CPU cores (have ${cpu_cores})"
        else
            FEATURE_REASONS["AI_LLM_EXPANSION_ENABLED"]="Requires opt-in via AI_LLM_EXPANSION_OPT_IN=true"
        fi
        log "✗ Skipped AI_LLM_EXPANSION_ENABLED (${FEATURE_REASONS["AI_LLM_EXPANSION_ENABLED"]})"
    fi

    # AI_CROSS_ENCODER_ENABLED
    # Requires: High-precision opt-in + sufficient resources
    local cross_encoder_opt_in="${AI_CROSS_ENCODER_OPT_IN:-false}"
    if [[ "${cross_encoder_opt_in}" == "true" ]] && [[ "${ram_gb}" -ge 8 ]]; then
        export AI_CROSS_ENCODER_ENABLED="true"
        ENABLED_FEATURES["AI_CROSS_ENCODER_ENABLED"]="true"
        FEATURE_REASONS["AI_CROSS_ENCODER_ENABLED"]="Auto-enabled: user opt-in + ${ram_gb}GB RAM"
        log "✓ Enabled AI_CROSS_ENCODER_ENABLED"
    else
        SKIPPED_FEATURES["AI_CROSS_ENCODER_ENABLED"]="true"
        FEATURE_REASONS["AI_CROSS_ENCODER_ENABLED"]="Requires opt-in via AI_CROSS_ENCODER_OPT_IN=true + 8GB+ RAM"
        log "✗ Skipped AI_CROSS_ENCODER_ENABLED (opt-in required)"
    fi
}

# Ensure experimental features stay disabled (Category B)
ensure_experimental_disabled() {
    log "Ensuring experimental features remain disabled (Category B)..."

    local experimental_features=(
        "QUERY_EXPANSION_ENABLED"
        "REMOTE_LLM_FEEDBACK_ENABLED"
        "MULTI_TURN_QUERY_EXPANSION"
        "PATTERN_EXTRACTION_ENABLED"
    )

    for feature in "${experimental_features[@]}"; do
        # Only set to false if not explicitly overridden
        if [[ -z "${!feature:-}" ]]; then
            export "${feature}=false"
        fi
        SKIPPED_FEATURES["${feature}"]="true"
        FEATURE_REASONS["${feature}"]="Experimental - manual opt-in required"
    done

    log "Kept ${#experimental_features[@]} experimental features disabled"
}

# Validate required dependencies
validate_dependencies() {
    log "Validating feature dependencies..."

    local validation_errors=0

    # AI_HINT_FEEDBACK_DB_ENABLED requires PostgreSQL
    if [[ "${AI_HINT_FEEDBACK_DB_ENABLED:-true}" == "true" ]]; then
        if ! systemctl is-active postgresql &>/dev/null; then
            warn "AI_HINT_FEEDBACK_DB_ENABLED requires PostgreSQL"
            if [[ "${AI_STRICT_VALIDATION:-false}" == "true" ]]; then
                ((validation_errors++))
            fi
        fi
    fi

    # AI_MEMORY_ENABLED requires Qdrant
    if [[ "${AI_MEMORY_ENABLED:-true}" == "true" ]]; then
        if ! systemctl is-active qdrant &>/dev/null; then
            warn "AI_MEMORY_ENABLED requires Qdrant service"
            if [[ "${AI_STRICT_VALIDATION:-false}" == "true" ]]; then
                ((validation_errors++))
            fi
        fi
    fi

    # OTEL_TRACING_ENABLED should have exporter endpoint
    if [[ "${OTEL_TRACING_ENABLED:-true}" == "true" ]]; then
        if [[ -z "${OTEL_EXPORTER_OTLP_ENDPOINT:-}" ]] && [[ "${AI_STRICT_ENV:-false}" == "true" ]]; then
            warn "OTEL_TRACING_ENABLED set but OTEL_EXPORTER_OTLP_ENDPOINT not configured"
        fi
    fi

    if [[ "${validation_errors}" -gt 0 ]]; then
        error "Found ${validation_errors} validation errors (strict mode enabled)"
        return 1
    fi

    log "Dependency validation complete"
    return 0
}

# Generate feature status report
generate_status_report() {
    local report_file="${1:-/tmp/auto-enable-report.txt}"

    {
        echo "=== Auto-Enable Feature Report ==="
        echo "Generated: $(date --iso-8601=seconds)"
        echo ""

        echo "System Capabilities:"
        echo "  CPU Cores: $(detect_cpu_cores)"
        echo "  RAM: $(detect_total_ram_gb) GB"
        echo "  GPU: $(detect_gpu_available || echo "none")"
        echo "  Vulkan: $(detect_vulkan_support && echo "yes" || echo "no")"
        echo "  Model: $(detect_llama_model)"
        echo ""

        echo "Enabled Features (${#ENABLED_FEATURES[@]}):"
        for feature in "${!ENABLED_FEATURES[@]}"; do
            echo "  ✓ ${feature}"
            echo "      ${FEATURE_REASONS[${feature}]}"
        done
        echo ""

        echo "Skipped Features (${#SKIPPED_FEATURES[@]}):"
        for feature in "${!SKIPPED_FEATURES[@]}"; do
            echo "  ✗ ${feature}"
            echo "      ${FEATURE_REASONS[${feature}]}"
        done
        echo ""

        echo "=== End Report ==="
    } > "${report_file}"

    log "Feature status report: ${report_file}"
}

# Print status summary
print_summary() {
    log ""
    log "=== Feature Auto-Enable Summary ==="
    log "Enabled features: ${#ENABLED_FEATURES[@]}"
    log "Skipped features: ${#SKIPPED_FEATURES[@]}"
    log ""
}

# Main execution
main() {
    log "Starting automatic feature enabling..."
    log ""

    # Enable core features (Category A)
    enable_core_features

    # Enable conditional features (Category D)
    enable_conditional_features

    # Ensure experimental features stay disabled (Category B)
    ensure_experimental_disabled

    # Validate dependencies
    if ! validate_dependencies; then
        if [[ "${AI_STRICT_VALIDATION:-false}" == "true" ]]; then
            error "Dependency validation failed in strict mode"
            return 1
        else
            warn "Dependency validation warnings (non-strict mode)"
        fi
    fi

    # Generate report
    local report_file="${AUTO_ENABLE_REPORT:-/tmp/auto-enable-report.txt}"
    generate_status_report "${report_file}"

    # Print summary
    print_summary

    log "Auto-enable complete"
    return 0
}

# Export feature enable function for sourcing
auto_enable_features() {
    main "$@"
}

# Run if executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
