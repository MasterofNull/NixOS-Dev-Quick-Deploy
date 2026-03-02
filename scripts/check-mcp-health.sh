#!/usr/bin/env bash
# check-mcp-health.sh — Phase 1.5.1
# Verify all HTTP-based MCP servers respond to /health within the timeout.
# Exits 0 only when every required service is healthy.
#
# Usage:
#   scripts/check-mcp-health.sh              # check all required services
#   scripts/check-mcp-health.sh --timeout 30 # override per-service timeout (default 10s)
#
# Service dependency tiers:
#   REQUIRED  — MCP servers that must be healthy for the AI stack to function
#   INFRA     — Infrastructure that required servers depend on
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../config/service-endpoints.sh
source "${SCRIPT_DIR}/../config/service-endpoints.sh"

TIMEOUT=10
CHECK_OPTIONAL=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --timeout)  TIMEOUT="$2"; shift 2 ;;
    --optional) CHECK_OPTIONAL=true; shift ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

PASS=0
FAIL=0

# ── Colour helpers ────────────────────────────────────────────────────────────
if [[ -t 1 ]]; then
  GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[0;33m'; RESET='\033[0m'
else
  GREEN=''; RED=''; YELLOW=''; RESET=''
fi

check_http() {
  local tier="$1"   # REQUIRED | OPTIONAL | INFRA
  local label="$2"
  local url="$3"
  local required_tier="${4:-REQUIRED}"  # unused, kept for symmetry

  local http_code
  http_code=$(curl -sS -o /dev/null -w "%{http_code}" \
    --max-time "$TIMEOUT" --connect-timeout 3 "$url" 2>/dev/null || echo "000")

  if [[ "$http_code" =~ ^2 ]]; then
    printf "${GREEN}PASS${RESET}  [%-8s] %s\n" "$tier" "$label"
    (( PASS++ )) || true
  else
    printf "${RED}FAIL${RESET}  [%-8s] %s (HTTP %s — expected 2xx at %s)\n" \
      "$tier" "$label" "$http_code" "$url"
    (( FAIL++ )) || true
  fi
}

check_tcp() {
  local tier="$1"
  local label="$2"
  local host="$3"
  local port="$4"

  if timeout "$TIMEOUT" bash -c ">/dev/tcp/${host}/${port}" 2>/dev/null; then
    printf "${GREEN}PASS${RESET}  [%-8s] %s (%s:%s)\n" "$tier" "$label" "$host" "$port"
    (( PASS++ )) || true
  else
    printf "${RED}FAIL${RESET}  [%-8s] %s (TCP %s:%s unreachable)\n" \
      "$tier" "$label" "$host" "$port"
    (( FAIL++ )) || true
  fi
}

url_port() {
  local url="$1"
  # shellcheck disable=SC2001
  sed -E 's#^[a-zA-Z]+://[^:/]+:([0-9]+).*$#\1#' <<<"$url"
}

# ── Infrastructure dependencies ───────────────────────────────────────────────
echo "── Infrastructure ───────────────────────────────────────────"
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT}"
check_tcp "INFRA" "Redis" "$REDIS_HOST" "$REDIS_PORT"

QDRANT_HOST="${SERVICE_HOST}"
QDRANT_PORT="${QDRANT_PORT}"
check_tcp "INFRA" "Qdrant" "$QDRANT_HOST" "$QDRANT_PORT"
QDRANT_HEALTH_URL="http://${QDRANT_HOST}:${QDRANT_PORT}/healthz"
check_http "INFRA" "Qdrant HTTP API     (:${QDRANT_PORT})" "$QDRANT_HEALTH_URL"

POSTGRES_HOST="${POSTGRES_HOST}"
POSTGRES_PORT="${POSTGRES_PORT}"
check_tcp "INFRA" "PostgreSQL" "$POSTGRES_HOST" "$POSTGRES_PORT"

# ── Core HTTP MCP servers ─────────────────────────────────────────────────────
echo "── Core MCP Servers ─────────────────────────────────────────"
check_http "REQUIRED" "embeddings-service  (:$(url_port "${EMBEDDINGS_URL}"))" "${EMBEDDINGS_URL%/}/health"
check_http "REQUIRED" "aidb                (:$(url_port "${AIDB_URL}"))" "${AIDB_URL%/}/health"
check_http "REQUIRED" "hybrid-coordinator  (:$(url_port "${HYBRID_URL}"))" "${HYBRID_URL%/}/health"
check_http "REQUIRED" "ralph-wiggum        (:$(url_port "${RALPH_URL}"))" "${RALPH_URL%/}/health"
check_http "REQUIRED" "switchboard         (:$(url_port "${SWITCHBOARD_URL}"))" "${SWITCHBOARD_URL%/}/health"
check_http "REQUIRED" "aider-wrapper       (:$(url_port "${AIDER_URL}"))" "${AIDER_URL%/}/health"
check_http "REQUIRED" "nixos-docs          (:$(url_port "${NIXOS_DOCS_URL}"))" "${NIXOS_DOCS_URL%/}/health"

# ── LLM backend ───────────────────────────────────────────────────────────────
echo "── LLM Backends ─────────────────────────────────────────────"
LLAMA_URL="${LLAMA_CPP_URL}"
check_http "REQUIRED" "llama-cpp inference (:$(url_port "${LLAMA_URL}"))" "${LLAMA_URL%/}/health"

LLAMA_EMBED_URL="${LLAMA_CPP_EMBED_URL}"
check_http "REQUIRED" "llama-cpp embedding (:$(url_port "${LLAMA_EMBED_URL}"))" "${LLAMA_EMBED_URL%/}/health"

# ── Summary ───────────────────────────────────────────────────────────────────
echo "─────────────────────────────────────────────────────────────"
printf "Result: %d passed, %d failed\n" "$PASS" "$FAIL"

if [[ $FAIL -gt 0 ]]; then
  echo "One or more MCP health checks failed." >&2
  exit 1
fi

echo "All required MCP services are healthy."

# ── Optional services (only checked with --optional flag) ─────────────────────
if [[ "$CHECK_OPTIONAL" == "true" ]]; then
  echo ""
  echo "── Optional Services ──────────────────────────────────────"
  check_http "OPTIONAL" "open-webui          (:$(url_port "${OPEN_WEBUI_URL}"))" "${OPEN_WEBUI_URL%/}/health"
  check_http "OPTIONAL" "grafana             (:$(url_port "${GRAFANA_URL}"))" "${GRAFANA_URL%/}/api/health"
  check_http "OPTIONAL" "prometheus          (:$(url_port "${PROMETHEUS_URL}"))" "${PROMETHEUS_URL%/}/-/healthy"
  check_http "OPTIONAL" "dashboard-api       (:$(url_port "${DASHBOARD_API_URL}"))" "${DASHBOARD_API_URL%/}/api/health"
  # Note: mindsdb, netdata, gitea, redisinsight are not deployed by default
  # Uncomment below if you have these services configured
  # check_http "OPTIONAL" "mindsdb             (:$(url_port "${MINDSDB_URL}"))" "${MINDSDB_URL%/}/api/util/ping"
  # check_http "OPTIONAL" "netdata             (:$(url_port "${NETDATA_URL}"))" "${NETDATA_URL%/}/api/v1/info"
  # check_http "OPTIONAL" "gitea               (:$(url_port "${GITEA_URL}"))" "${GITEA_URL%/}/api/v1/version"
  # check_http "OPTIONAL" "redisinsight        (:$(url_port "${REDISINSIGHT_URL}"))" "${REDISINSIGHT_URL%/}/api/v1"
  
  echo "─────────────────────────────────────────────────────────────"
  printf "Optional: %d passed, %d failed\n" "$PASS" "$FAIL"
fi
