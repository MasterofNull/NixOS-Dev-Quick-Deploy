#!/usr/bin/env bash
#
# Service Endpoints - Centralized URL definitions for all AI stack services
# Purpose: Single source of truth for service URLs used by dashboard scripts
# Version: 1.0.0
#
# Source this file from any script that needs service URLs.
# All values are overridable via environment variables.
#
# ============================================================================

# Load port definitions from settings.sh when endpoint ports are not initialized.
# AI_STACK_NAMESPACE may be exported without individual port vars, so key off
# required port env vars instead of namespace presence.
if [[ -z "${LLAMA_CPP_PORT:-}" || -z "${AIDB_PORT:-}" || -z "${SWITCHBOARD_PORT:-}" ]]; then
    _SE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    # shellcheck source=config/settings.sh
    [[ -f "${_SE_DIR}/settings.sh" ]] && source "${_SE_DIR}/settings.sh"
    unset _SE_DIR
fi

# ============================================================================
# Service Host - defaults to localhost for host-local services
# Override SERVICE_HOST for remote access
# ============================================================================

: "${SERVICE_HOST:=localhost}"

# ============================================================================
# Full Service URLs (built from host + port)
# Override individual URLs to point at specific endpoints
# ============================================================================

: "${AIDB_URL:=http://${SERVICE_HOST}:${AIDB_PORT:-8002}}"
: "${HYBRID_URL:=http://${SERVICE_HOST}:${HYBRID_COORDINATOR_PORT:-8003}}"
: "${QDRANT_URL:=http://${SERVICE_HOST}:${QDRANT_PORT:-6333}}"
: "${LLAMA_URL:=http://${SERVICE_HOST}:${LLAMA_CPP_PORT:-8080}}"
: "${OPEN_WEBUI_URL:=http://${SERVICE_HOST}:${OPEN_WEBUI_PORT:-3001}}"
: "${GRAFANA_URL:=http://${SERVICE_HOST}:${GRAFANA_PORT:-3000}}"
: "${PROMETHEUS_URL:=http://${SERVICE_HOST}:${PROMETHEUS_PORT:-9090}}"
: "${RALPH_URL:=http://${SERVICE_HOST}:${RALPH_PORT:-8004}}"
: "${MINDSDB_URL:=http://${SERVICE_HOST}:${MINDSDB_PORT:-47334}}"
: "${DASHBOARD_API_URL:=http://${SERVICE_HOST}:${DASHBOARD_API_PORT:-8889}}"
: "${DASHBOARD_URL:=http://${SERVICE_HOST}:${DASHBOARD_PORT:-8888}}"
: "${EMBEDDINGS_URL:=http://${SERVICE_HOST}:${EMBEDDINGS_PORT:-8081}}"
: "${SWITCHBOARD_URL:=http://${SERVICE_HOST}:${SWITCHBOARD_PORT:-8085}}"
: "${AIDER_WRAPPER_URL:=http://${SERVICE_HOST}:${AIDER_WRAPPER_PORT:-8090}}"
: "${NETDATA_URL:=http://${SERVICE_HOST}:${NETDATA_PORT:-19999}}"
: "${NIXOS_DOCS_URL:=http://${SERVICE_HOST}:${NIXOS_DOCS_PORT:-8096}}"
: "${OLLAMA_URL:=http://${SERVICE_HOST}:${OLLAMA_PORT:-11434}}"
: "${GITEA_URL:=http://${SERVICE_HOST}:${GITEA_PORT:-3003}}"
: "${REDISINSIGHT_URL:=http://${SERVICE_HOST}:${REDISINSIGHT_PORT:-5540}}"
: "${ANTHROPIC_PROXY_URL:=http://${SERVICE_HOST}:${ANTHROPIC_PROXY_PORT:-8094}}"
: "${CONTAINER_ENGINE_URL:=http://${SERVICE_HOST}:${CONTAINER_ENGINE_PORT:-8095}}"
: "${NGINX_HTTPS_PORT:=8443}"
: "${NGINX_HTTPS_URL:=https://${SERVICE_HOST}:${NGINX_HTTPS_PORT}}"

# Database connection strings (used by exec-based health checks)
: "${POSTGRES_HOST:=${SERVICE_HOST}}"
: "${REDIS_HOST:=${SERVICE_HOST}}"

# Backward-compatible aliases for older scripts.
: "${LLAMA_CPP_URL:=${LLAMA_URL}}"
: "${LLAMA_CPP_EMBED_URL:=${EMBEDDINGS_URL}}"
: "${AIDER_URL:=${AIDER_WRAPPER_URL}}"

# In-cluster DNS endpoints were intentionally removed.
# Host-mode declarative runtime is authoritative; use localhost URLs above.
