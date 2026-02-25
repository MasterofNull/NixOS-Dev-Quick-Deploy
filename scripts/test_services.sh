#!/usr/bin/env bash
#
# Quick health probe for the public NixOS-Dev-Quick-Deploy services.
# Runs the detailed system health check and pings the key HTTP endpoints
# exposed by the trimmed llama.cpp stack.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
HEALTH_SCRIPT="$REPO_ROOT/scripts/system-health-check.sh"
# shellcheck source=../config/service-endpoints.sh
source "$REPO_ROOT/config/service-endpoints.sh"

AIDB_BASE_URL="${AIDB_BASE_URL:-${AIDB_URL}}"
LLAMA_CPP_BASE_URL="${LLAMA_CPP_BASE_URL:-${LLAMA_URL}}"
REDISINSIGHT_BASE_URL="${REDISINSIGHT_BASE_URL:-${REDISINSIGHT_URL}}"
SWITCHBOARD_BASE_URL="${SWITCHBOARD_BASE_URL:-${SWITCHBOARD_URL}}"

run_health_check=true
fail=0

usage() {
    cat <<EOF
Usage: $(basename "$0") [--skip-health-check]

Options:
  --skip-health-check    Do not run scripts/system-health-check.sh
  -h, --help             Show this message
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --skip-health-check)
            run_health_check=false
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage
            exit 1
            ;;
    esac
done

if $run_health_check; then
    if [[ ! -x "$HEALTH_SCRIPT" ]]; then
        echo "Health check script not found at $HEALTH_SCRIPT" >&2
        exit 1
    fi
    echo "🩺 Running system-health-check --detailed"
    "$HEALTH_SCRIPT" --detailed
fi

check_required_endpoint() {
    local name="$1"
    local url="$2"
    if curl -fs --max-time 5 "$url" >/dev/null 2>&1; then
        printf '✅ %s reachable (%s)\n' "$name" "$url"
    else
        printf '❌ %s unreachable (%s)\n' "$name" "$url"
        fail=1
    fi
}

check_json_equals() {
    local name="$1"
    local url="$2"
    local jq_expr="$3"
    local expected="$4"
    local value=""

    if ! command -v jq >/dev/null 2>&1; then
        printf '❌ jq required for JSON assertion: %s\n' "$name"
        fail=1
        return
    fi

    value="$(curl -fsS --max-time 5 "$url" 2>/dev/null | jq -r "$jq_expr" 2>/dev/null || true)"
    if [[ "$value" == "$expected" ]]; then
        printf '✅ %s (%s=%s)\n' "$name" "$jq_expr" "$expected"
    else
        printf '❌ %s expected %s=%s, got=%s (%s)\n' "$name" "$jq_expr" "$expected" "${value:-unknown}" "$url"
        fail=1
    fi
}

unit_declared() {
    local unit="$1"
    systemctl list-unit-files --type=service --type=target 2>/dev/null | awk '{print $1}' | grep -qx "$unit" \
      || systemctl list-units --all --type=service --type=target 2>/dev/null | awk '{print $1}' | grep -qx "$unit"
}

echo
echo "🌐 Endpoint probes"
check_required_endpoint "AIDB MCP" "${AIDB_BASE_URL%/}/health"
check_json_equals "AIDB MCP status" "${AIDB_BASE_URL%/}/health" '.status' 'ok'
llama_cpp_base="${LLAMA_CPP_BASE_URL%/}"
llama_cpp_base="${llama_cpp_base%/api/v1}"
check_required_endpoint "llama.cpp" "${llama_cpp_base}/health"
check_json_equals "llama.cpp status" "${llama_cpp_base}/health" '.status' 'ok'

if unit_declared "redisinsight.service"; then
    check_required_endpoint "RedisInsight" "${REDISINSIGHT_BASE_URL%/}"
else
    printf 'ℹ️  RedisInsight not declared as a systemd unit; skipping endpoint gate.\n'
fi

if unit_declared "ai-switchboard.service"; then
    check_required_endpoint "AI Switchboard" "${SWITCHBOARD_BASE_URL%/}/health"
    check_json_equals "AI Switchboard status" "${SWITCHBOARD_BASE_URL%/}/health" '.status' 'ok'
else
    printf 'ℹ️  AI Switchboard not declared as a systemd unit; skipping endpoint gate.\n'
fi

if [[ $fail -ne 0 ]]; then
    echo
    echo "Service functionality checks failed." >&2
    exit 1
fi

echo
echo "Service functionality checks passed."
