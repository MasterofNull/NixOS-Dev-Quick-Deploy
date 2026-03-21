#!/usr/bin/env bash
# lib/agents/improvement-tracker.sh
# Phase 4.2: Continuous Improvement Tracker
#
# Tracks quality metrics, detects regressions, and measures improvements over time.
#
# Features:
# - Quality metrics collection (success rate, response time)
# - Improvement trend analysis
# - Regression detection with alerts
# - Performance benchmarking
# - Dashboard reporting
# - Alert on quality degradation

set -euo pipefail

# Logging utilities
log_debug() { [[ "${DEBUG:-0}" == "1" ]] && printf '[DEBUG] %s\n' "$*" >&2 || true; }
log_info() { printf '[INFO] %s\n' "$*" >&2; }
log_warn() { printf '[WARN] %s\n' "$*" >&2; }
log_error() { printf '[ERROR] %s\n' "$*" >&2; }

# Metrics configuration
METRICS_DB="${METRICS_DB:-${HOME}/.cache/nixos-ai-stack/improvement-metrics.json}"
METRICS_HISTORY="${METRICS_HISTORY:-${HOME}/.cache/nixos-ai-stack/metrics-history.jsonl}"
BASELINE_METRICS="${BASELINE_METRICS:-${HOME}/.cache/nixos-ai-stack/baseline-metrics.json}"

# Thresholds for alerts
REGRESSION_THRESHOLD="${REGRESSION_THRESHOLD:-5}"  # % point drop triggers alert
QUALITY_IMPROVEMENT_TARGET="${QUALITY_IMPROVEMENT_TARGET:-20}"  # % improvement target
MIN_QUERIES_FOR_VALID_METRIC="${MIN_QUERIES_FOR_VALID_METRIC:-10}"

# Initialize metrics database
init_metrics_db() {
    local db_dir
    db_dir="$(dirname "${METRICS_DB}")"
    mkdir -p "${db_dir}"

    # Create empty database file if it doesn't exist
    if [[ ! -f "${METRICS_DB}" ]]; then
        cat > "${METRICS_DB}" <<'EOF'
{
  "schema_version": 1,
  "created_at": "2026-03-20T00:00:00Z",
  "baseline": {
    "query_success_rate": 0.0,
    "avg_response_time_ms": 0,
    "agent_selection_accuracy": 0.0,
    "pattern_coverage": 0.0,
    "learning_effectiveness": 0.0
  },
  "current": {
    "query_success_rate": 0.0,
    "avg_response_time_ms": 0,
    "agent_selection_accuracy": 0.0,
    "pattern_coverage": 0.0,
    "learning_effectiveness": 0.0
  },
  "history": []
}
EOF
        log_info "Initialized metrics database"
    fi

    # Create baseline if it doesn't exist
    if [[ ! -f "${BASELINE_METRICS}" ]]; then
        mkdir -p "$(dirname "${BASELINE_METRICS}")"
        cat > "${BASELINE_METRICS}" <<'EOF'
{
  "timestamp": "2026-03-20T00:00:00Z",
  "query_success_rate": 0.5,
  "avg_response_time_ms": 1000,
  "agent_selection_accuracy": 0.7,
  "pattern_coverage": 0.1,
  "learning_effectiveness": 0.0,
  "total_queries": 0
}
EOF
    fi
}

# Record a metric snapshot
record_metric_snapshot() {
    local success_rate="${1:-0.5}"
    local response_time="${2:-1000}"
    local agent_accuracy="${3:-0.7}"
    local pattern_coverage="${4:-0.1}"
    local learning_effectiveness="${5:-0.0}"
    local query_count="${6:-0}"

    [[ -f "${METRICS_DB}" ]] || init_metrics_db

    # Create metric entry
    local timestamp
    timestamp="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"

    cat >> "${METRICS_HISTORY}" <<EOF
{"timestamp":"${timestamp}","success_rate":${success_rate},"response_time_ms":${response_time},"agent_accuracy":${agent_accuracy},"pattern_coverage":${pattern_coverage},"learning_effectiveness":${learning_effectiveness},"query_count":${query_count}}
EOF

    # Update current metrics in database
    if command -v jq &>/dev/null; then
        local temp_db
        temp_db="$(mktemp)"
        jq \
          --arg ts "${timestamp}" \
          --argjson sr "${success_rate}" \
          --argjson rt "${response_time}" \
          --argjson aa "${agent_accuracy}" \
          --argjson pc "${pattern_coverage}" \
          --argjson le "${learning_effectiveness}" \
          '.current = {
            "timestamp": $ts,
            "query_success_rate": $sr,
            "avg_response_time_ms": $rt,
            "agent_selection_accuracy": $aa,
            "pattern_coverage": $pc,
            "learning_effectiveness": $le
          }' "${METRICS_DB}" > "${temp_db}"
        mv "${temp_db}" "${METRICS_DB}"
    fi

    log_debug "Recorded metric snapshot: success_rate=${success_rate}, response_time=${response_time}ms"
}

# Detect regressions
detect_regressions() {
    local current_success_rate="${1:-0.5}"

    [[ -f "${BASELINE_METRICS}" ]] || return 1

    if ! command -v jq &>/dev/null; then
        log_warn "jq not available, regression detection skipped"
        return 1
    fi

    local baseline_success_rate
    baseline_success_rate="$(jq -r '.query_success_rate' "${BASELINE_METRICS}" 2>/dev/null || echo "0.5")"

    # Calculate regression
    local regression_points
    regression_points=$(awk "BEGIN {printf \"%.1f\", (${baseline_success_rate} - ${current_success_rate}) * 100}")

    # Check if regression exceeds threshold
    local exceeded
    exceeded=$(awk "BEGIN {print (${regression_points} > ${REGRESSION_THRESHOLD}) ? 1 : 0}")

    if [[ "${exceeded}" == "1" ]]; then
        log_error "REGRESSION DETECTED: Success rate dropped by ${regression_points}% (threshold: ${REGRESSION_THRESHOLD}%)"
        return 0  # Regression detected
    else
        log_info "No regression detected (dropped ${regression_points}%, threshold: ${REGRESSION_THRESHOLD}%)"
        return 1  # No regression
    fi
}

# Analyze improvement trends
analyze_improvement_trends() {
    [[ -f "${METRICS_HISTORY}" ]] || { echo "No metrics history available"; return 1; }

    if ! command -v jq &>/dev/null; then
        log_warn "jq not available, trend analysis skipped"
        return 1
    fi

    # Read last 100 snapshots
    local recent_metrics
    recent_metrics="$(tail -100 "${METRICS_HISTORY}" 2>/dev/null || echo "")"

    if [[ -z "${recent_metrics}" ]]; then
        echo "Insufficient metrics history for analysis"
        return 1
    fi

    # Calculate moving average
    local count=0
    local success_sum=0.0
    local time_sum=0.0

    while IFS= read -r line; do
        success_sum=$(awk -v s="${success_sum}" -v val="$(echo "${line}" | jq -r '.success_rate')" 'BEGIN {print s + val}')
        time_sum=$(awk -v s="${time_sum}" -v val="$(echo "${line}" | jq -r '.response_time_ms')" 'BEGIN {print s + val}')
        count=$((count + 1))
    done <<< "${recent_metrics}"

    if [[ ${count} -lt ${MIN_QUERIES_FOR_VALID_METRIC} ]]; then
        echo "Insufficient data points for trend analysis (${count}/${MIN_QUERIES_FOR_VALID_METRIC})"
        return 1
    fi

    local avg_success
    local avg_time
    avg_success=$(awk "BEGIN {printf \"%.3f\", ${success_sum} / ${count}}")
    avg_time=$(awk "BEGIN {printf \"%.1f\", ${time_sum} / ${count}}")

    # Read baseline
    local baseline_success
    baseline_success="$(jq -r '.query_success_rate' "${BASELINE_METRICS}" 2>/dev/null || echo "0.5")"

    # Calculate improvement percentage
    local improvement
    improvement=$(awk "BEGIN {printf \"%.1f\", (${avg_success} - ${baseline_success}) * 100}")

    cat <<EOF
{
  "analysis_type": "improvement_trends",
  "data_points": ${count},
  "current_avg_success_rate": ${avg_success},
  "current_avg_response_time_ms": ${avg_time},
  "baseline_success_rate": ${baseline_success},
  "improvement_percentage": ${improvement},
  "trending": "$(awk "BEGIN {print (${avg_success} > ${baseline_success}) ? \"up\" : \"down"}")
}
EOF
}

# Get quality metrics
get_quality_metrics() {
    [[ -f "${METRICS_DB}" ]] || init_metrics_db

    if ! command -v jq &>/dev/null; then
        log_warn "jq not available"
        cat "${METRICS_DB}"
        return 0
    fi

    jq '.current' "${METRICS_DB}" 2>/dev/null || echo "{}"
}

# Compare with baseline
compare_with_baseline() {
    [[ -f "${METRICS_DB}" ]] || init_metrics_db
    [[ -f "${BASELINE_METRICS}" ]] || return 1

    if ! command -v jq &>/dev/null; then
        log_warn "jq not available"
        return 1
    fi

    local current_success
    local baseline_success
    current_success="$(jq -r '.current.query_success_rate // 0' "${METRICS_DB}")"
    baseline_success="$(jq -r '.query_success_rate' "${BASELINE_METRICS}")"

    local improvement
    improvement=$(awk "BEGIN {printf \"%.1f\", (${current_success} - ${baseline_success}) * 100}")

    cat <<EOF
{
  "comparison_type": "baseline_comparison",
  "baseline_success_rate": ${baseline_success},
  "current_success_rate": ${current_success},
  "improvement_percentage": ${improvement},
  "target_improvement": ${QUALITY_IMPROVEMENT_TARGET},
  "target_achieved": $(awk "BEGIN {print (${improvement} >= ${QUALITY_IMPROVEMENT_TARGET}) ? \"true\" : \"false"}")
}
EOF
}

# Set new baseline
set_baseline() {
    local success_rate="${1:-0.5}"
    local response_time="${2:-1000}"
    local agent_accuracy="${3:-0.7}"
    local pattern_coverage="${4:-0.1}"
    local learning_effectiveness="${5:-0.0}"

    local timestamp
    timestamp="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"

    cat > "${BASELINE_METRICS}" <<EOF
{
  "timestamp": "${timestamp}",
  "query_success_rate": ${success_rate},
  "avg_response_time_ms": ${response_time},
  "agent_selection_accuracy": ${agent_accuracy},
  "pattern_coverage": ${pattern_coverage},
  "learning_effectiveness": ${learning_effectiveness}
}
EOF

    log_info "Baseline set: success_rate=${success_rate}, response_time=${response_time}ms"
}

# Generate quality report
generate_quality_report() {
    local output_file="${1:-}"

    [[ -f "${METRICS_DB}" ]] || init_metrics_db

    local report
    report="{
  \"report_type\": \"quality_improvement\",
  \"generated_at\": \"$(date -u +'%Y-%m-%dT%H:%M:%SZ')\","

    # Add current metrics
    if [[ -f "${METRICS_DB}" ]] && command -v jq &>/dev/null; then
        report="${report}
  \"current_metrics\": $(jq '.current' "${METRICS_DB}"),
  \"baseline_metrics\": $(jq '.' "${BASELINE_METRICS}"),
  \"comparison\": $(compare_with_baseline),"
    fi

    # Add trends
    if [[ -f "${METRICS_HISTORY}" ]]; then
        report="${report}
  \"trends\": $(analyze_improvement_trends),"
    fi

    # Add status
    report="${report}
  \"status\": \"operational\"
}"

    if [[ -n "${output_file}" ]]; then
        echo "${report}" > "${output_file}"
        log_info "Report written to ${output_file}"
    else
        echo "${report}"
    fi
}

# Export functions for sourcing
export -f init_metrics_db
export -f record_metric_snapshot
export -f detect_regressions
export -f analyze_improvement_trends
export -f get_quality_metrics
export -f compare_with_baseline
export -f set_baseline
export -f generate_quality_report
