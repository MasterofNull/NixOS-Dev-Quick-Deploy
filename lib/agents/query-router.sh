#!/usr/bin/env bash
# lib/agents/query-router.sh
# Phase 4.2: Query Routing System
#
# Routes operator queries to appropriate agent based on:
# - Query analysis and classification
# - Agent capability matching
# - Load balancing across agents
# - Fallback routing strategies
#
# Supports:
# - Deployment queries (status, history, failures)
# - Troubleshooting queries (errors, performance)
# - Configuration queries (validation, optimization)
# - Learning queries (patterns, recommendations)

set -euo pipefail

# Logging utilities
log_debug() { [[ "${DEBUG:-0}" == "1" ]] && printf '[DEBUG] %s\n' "$*" >&2 || true; }
log_info() { printf '[INFO] %s\n' "$*" >&2; }
log_warn() { printf '[WARN] %s\n' "$*" >&2; }
log_error() { printf '[ERROR] %s\n' "$*" >&2; }

# Query type classifications
readonly QUERY_TYPE_DEPLOYMENT="deployment"
readonly QUERY_TYPE_TROUBLESHOOTING="troubleshooting"
readonly QUERY_TYPE_CONFIGURATION="configuration"
readonly QUERY_TYPE_LEARNING="learning"
readonly QUERY_TYPE_UNKNOWN="unknown"

# Agent tiers for routing
readonly AGENT_TIER_LOCAL="local"
readonly AGENT_TIER_SPECIALIZED="specialized"
readonly AGENT_TIER_ORCHESTRATOR="orchestrator"

# Query complexity levels
readonly COMPLEXITY_SIMPLE="simple"
readonly COMPLEXITY_MEDIUM="medium"
readonly COMPLEXITY_HIGH="high"

# Database for routing metrics
ROUTING_METRICS_DB="${ROUTING_METRICS_DB:-${HOME}/.cache/nixos-ai-stack/routing-metrics.db}"

# Initialize routing metrics database
init_routing_metrics_db() {
    local db_dir
    db_dir="$(dirname "${ROUTING_METRICS_DB}")"
    mkdir -p "${db_dir}"

    # Use SQLite if available, otherwise use JSON
    if command -v sqlite3 &>/dev/null; then
        sqlite3 "${ROUTING_METRICS_DB}" <<'SQL' 2>/dev/null || true
            CREATE TABLE IF NOT EXISTS routing_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                query_hash TEXT,
                query_type TEXT,
                complexity TEXT,
                routed_agent TEXT,
                execution_time_ms INTEGER,
                success BOOLEAN,
                result_quality REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS agent_performance (
                agent_name TEXT PRIMARY KEY,
                total_queries INTEGER DEFAULT 0,
                successful_queries INTEGER DEFAULT 0,
                avg_execution_time_ms REAL DEFAULT 0.0,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_routing_timestamp ON routing_decisions(timestamp);
            CREATE INDEX IF NOT EXISTS idx_routing_type ON routing_decisions(query_type);
            CREATE INDEX IF NOT EXISTS idx_routing_agent ON routing_decisions(routed_agent);
SQL
    fi
}

# Classify query type based on content analysis
classify_query_type() {
    local query="$1"
    local query_lower
    query_lower="$(tr '[:upper:]' '[:lower:]' <<< "${query}")"

    # Deployment queries
    if grep -qE "(deploy|deployment|status|running|active|rollback|upgrade|install|uninstall)" <<< "${query_lower}"; then
        echo "${QUERY_TYPE_DEPLOYMENT}"
        return 0
    fi

    # Troubleshooting queries
    if grep -qE "(debug|error|fail|problem|issue|crash|hang|timeout|performance|slow)" <<< "${query_lower}"; then
        echo "${QUERY_TYPE_TROUBLESHOOTING}"
        return 0
    fi

    # Configuration queries
    if grep -qE "(config|configuration|setting|parameter|option|validate|optimize|tune)" <<< "${query_lower}"; then
        echo "${QUERY_TYPE_CONFIGURATION}"
        return 0
    fi

    # Learning queries
    if grep -qE "(learn|pattern|hint|recommendation|improve|best practice|example)" <<< "${query_lower}"; then
        echo "${QUERY_TYPE_LEARNING}"
        return 0
    fi

    echo "${QUERY_TYPE_UNKNOWN}"
}

# Assess query complexity
assess_query_complexity() {
    local query="$1"
    local word_count
    word_count="$(wc -w <<< "${query}")"

    # High complexity: long queries with technical terms
    if (( word_count > 50 )); then
        if grep -qE "(architecture|design|strategy|tradeoff|multi|distributed|cluster)" <<< "${query}"; then
            echo "${COMPLEXITY_HIGH}"
            return 0
        fi
    fi

    # Medium complexity: moderate length with some complexity
    if (( word_count > 20 )); then
        echo "${COMPLEXITY_MEDIUM}"
        return 0
    fi

    # Simple: short, direct queries
    echo "${COMPLEXITY_SIMPLE}"
}

# Calculate query similarity hash for deduplication
compute_query_hash() {
    local query="$1"
    echo -n "${query}" | sha256sum | awk '{print $1}' | cut -c1-16
}

# Get agent capability based on query type
get_agent_for_query_type() {
    local query_type="$1"
    local complexity="$2"

    case "${query_type}" in
        "${QUERY_TYPE_DEPLOYMENT}")
            # Deployment queries route to deployment-specialized agent
            case "${complexity}" in
                "${COMPLEXITY_HIGH}")
                    echo "claude-opus"  # Complex deployments need orchestrator
                    ;;
                "${COMPLEXITY_MEDIUM}")
                    echo "deployment-specialist"
                    ;;
                *)
                    echo "local-llm"
                    ;;
            esac
            ;;
        "${QUERY_TYPE_TROUBLESHOOTING}")
            # Troubleshooting queries route to debugging agent
            case "${complexity}" in
                "${COMPLEXITY_HIGH}")
                    echo "claude-opus"
                    ;;
                *)
                    echo "troubleshooting-specialist"
                    ;;
            esac
            ;;
        "${QUERY_TYPE_CONFIGURATION}")
            # Configuration queries route to config expert
            case "${complexity}" in
                "${COMPLEXITY_HIGH}")
                    echo "claude-sonnet"
                    ;;
                *)
                    echo "config-validator"
                    ;;
            esac
            ;;
        "${QUERY_TYPE_LEARNING}")
            # Learning queries route to learning system
            echo "learning-engine"
            ;;
        *)
            # Unknown queries fallback to general purpose agent
            case "${complexity}" in
                "${COMPLEXITY_HIGH}")
                    echo "claude-opus"
                    ;;
                "${COMPLEXITY_MEDIUM}")
                    echo "claude-sonnet"
                    ;;
                *)
                    echo "local-llm"
                    ;;
            esac
            ;;
    esac
}

# Check agent availability and load
check_agent_availability() {
    local agent="$1"
    local agent_endpoint

    case "${agent}" in
        "local-llm")
            agent_endpoint="${LOCAL_LLM_ENDPOINT:-http://localhost:8080}"
            ;;
        "deployment-specialist"|"troubleshooting-specialist"|"config-validator")
            agent_endpoint="${HYBRID_COORDINATOR_ENDPOINT:-http://localhost:8003}"
            ;;
        "learning-engine")
            agent_endpoint="${HYBRID_COORDINATOR_ENDPOINT:-http://localhost:8003}"
            ;;
        "claude-sonnet"|"claude-opus")
            agent_endpoint="${HYBRID_COORDINATOR_ENDPOINT:-http://localhost:8003}"
            ;;
        *)
            return 1
            ;;
    esac

    # Quick health check
    if timeout 2 curl -sf "${agent_endpoint}/health" >/dev/null 2>&1; then
        return 0
    else
        log_warn "Agent ${agent} unavailable at ${agent_endpoint}"
        return 1
    fi
}

# Fallback routing strategy
get_fallback_agent() {
    local original_agent="$1"
    local complexity="$2"

    case "${original_agent}" in
        "claude-opus")
            # Opus → Sonnet → Local
            echo "claude-sonnet"
            ;;
        "claude-sonnet")
            # Sonnet → Specialist → Local
            echo "deployment-specialist"
            ;;
        "deployment-specialist"|"troubleshooting-specialist"|"config-validator")
            # Specialist → Local
            echo "local-llm"
            ;;
        *)
            echo ""
            ;;
    esac
}

# Record routing decision for metrics
record_routing_decision() {
    local query_hash="$1"
    local query_type="$2"
    local complexity="$3"
    local agent="$4"
    local execution_time_ms="${5:-0}"
    local success="${6:-true}"
    local quality_score="${7:-0.5}"

    # Try SQLite first
    if command -v sqlite3 &>/dev/null && [[ -f "${ROUTING_METRICS_DB}" ]]; then
        sqlite3 "${ROUTING_METRICS_DB}" <<SQL 2>/dev/null || true
            INSERT INTO routing_decisions
            (query_hash, query_type, complexity, routed_agent, execution_time_ms, success, result_quality)
            VALUES ('${query_hash}', '${query_type}', '${complexity}', '${agent}', ${execution_time_ms}, ${success}, ${quality_score});
SQL
    fi

    log_debug "Recorded routing: query_type=${query_type}, agent=${agent}, execution_time=${execution_time_ms}ms, quality=${quality_score}"
}

# Get routing metrics
get_routing_metrics() {
    local output_format="${1:-text}"

    if ! command -v sqlite3 &>/dev/null || [[ ! -f "${ROUTING_METRICS_DB}" ]]; then
        if [[ "${output_format}" == "json" ]]; then
            echo '{"error":"routing metrics not available","format":"json"}'
        else
            echo "Routing metrics not available (SQLite required)"
        fi
        return 1
    fi

    if [[ "${output_format}" == "json" ]]; then
        sqlite3 "${ROUTING_METRICS_DB}" <<SQL 2>/dev/null || echo '{}'
            SELECT json_object(
                'total_queries', COUNT(*),
                'by_type', json_group_object(query_type, COUNT(*)),
                'by_agent', json_group_object(routed_agent, COUNT(*)),
                'success_rate', CAST(SUM(CASE WHEN success THEN 1 ELSE 0 END) AS REAL) / COUNT(*) * 100,
                'avg_execution_time_ms', AVG(execution_time_ms),
                'avg_quality_score', AVG(result_quality)
            ) FROM routing_decisions;
SQL
    else
        sqlite3 "${ROUTING_METRICS_DB}" <<SQL 2>/dev/null || true
            SELECT 'Total Queries:', COUNT(*) FROM routing_decisions;
            SELECT 'Query Types:' FROM routing_decisions LIMIT 1;
            SELECT '  ' || query_type || ': ' || COUNT(*) FROM routing_decisions GROUP BY query_type;
            SELECT 'Agent Distribution:' FROM routing_decisions LIMIT 1;
            SELECT '  ' || routed_agent || ': ' || COUNT(*) FROM routing_decisions GROUP BY routed_agent;
SQL
    fi
}

# Main routing function
route_query() {
    local query="$1"
    local context="${2:-}"
    local prefer_agent="${3:-}"

    [[ -n "${query}" ]] || { log_error "route_query: query is required"; return 1; }

    # Initialize metrics database if needed
    [[ -d "$(dirname "${ROUTING_METRICS_DB}")" ]] || init_routing_metrics_db

    # Step 1: Classify query
    local query_type
    query_type="$(classify_query_type "${query}")"
    log_debug "Query classified as: ${query_type}"

    # Step 2: Assess complexity
    local complexity
    complexity="$(assess_query_complexity "${query}")"
    log_debug "Query complexity: ${complexity}"

    # Step 3: Compute query hash for deduplication
    local query_hash
    query_hash="$(compute_query_hash "${query}")"

    # Step 4: Select initial agent
    local agent="${prefer_agent}"
    if [[ -z "${agent}" ]]; then
        agent="$(get_agent_for_query_type "${query_type}" "${complexity}")"
    fi
    log_debug "Selected agent: ${agent}"

    # Step 5: Check availability with fallback
    local attempts=0
    local max_attempts=3
    while (( attempts < max_attempts )); do
        if check_agent_availability "${agent}"; then
            log_info "Agent ${agent} is available"

            # Return routing decision
            cat <<JSON
{
  "agent": "${agent}",
  "query_type": "${query_type}",
  "complexity": "${complexity}",
  "query_hash": "${query_hash}",
  "context": ${context:-null},
  "routable": true
}
JSON
            return 0
        fi

        # Try fallback
        local fallback
        fallback="$(get_fallback_agent "${agent}" "${complexity}")"
        if [[ -z "${fallback}" ]]; then
            log_error "No fallback available for ${agent}"
            break
        fi

        log_warn "Agent ${agent} unavailable, trying fallback: ${fallback}"
        agent="${fallback}"
        attempts=$((attempts + 1))
    done

    # All agents exhausted
    log_error "Unable to route query: no available agents"
    cat <<JSON
{
  "agent": "",
  "query_type": "${query_type}",
  "complexity": "${complexity}",
  "query_hash": "${query_hash}",
  "context": ${context:-null},
  "routable": false,
  "error": "no available agents"
}
JSON
    return 1
}

# Export functions for sourcing
export -f classify_query_type
export -f assess_query_complexity
export -f compute_query_hash
export -f get_agent_for_query_type
export -f check_agent_availability
export -f get_fallback_agent
export -f record_routing_decision
export -f get_routing_metrics
export -f route_query
export -f init_routing_metrics_db
