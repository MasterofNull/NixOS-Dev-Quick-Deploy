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

run_health_check=true

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
    "$HEALTH_SCRIPT" --detailed || true
fi

check_endpoint() {
    local name="$1"
    local url="$2"
    if curl -fs --max-time 5 "$url" >/dev/null 2>&1; then
        printf '✅ %s reachable (%s)\n' "$name" "$url"
    else
        printf '⚠️  %s unreachable (%s)\n' "$name" "$url"
    fi
}

echo "\n🌐 Endpoint probes"
check_endpoint "AIDB MCP" "${AIDB_BASE_URL%/}/health"
llama_cpp_base="${LLAMA_CPP_BASE_URL%/}"
llama_cpp_base="${llama_cpp_base%/api/v1}"
check_endpoint "llama.cpp" "${llama_cpp_base}/health"
check_endpoint "RedisInsight" "${REDISINSIGHT_BASE_URL%/}"

echo "\nDone. Review warnings above if any checks failed."
