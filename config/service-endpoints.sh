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

# Load port definitions from settings.sh if not already loaded
if [[ -z "${AI_STACK_NAMESPACE:-}" ]]; then
    _SE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    # shellcheck source=config/settings.sh
    [[ -f "${_SE_DIR}/settings.sh" ]] && source "${_SE_DIR}/settings.sh"
    unset _SE_DIR
fi

# ============================================================================
# Service Host - defaults to localhost for NodePort/port-forward access
# Override SERVICE_HOST for remote or ingress-based access
# ============================================================================

: "${SERVICE_HOST:=localhost}"

# ============================================================================
# Full Service URLs (built from host + port)
# Override individual URLs to point at specific endpoints
# ============================================================================

: "${AIDB_URL:=http://${SERVICE_HOST}:${AIDB_PORT:-8091}}"
: "${HYBRID_URL:=http://${SERVICE_HOST}:${HYBRID_COORDINATOR_PORT:-8092}}"
: "${QDRANT_URL:=http://${SERVICE_HOST}:${QDRANT_PORT:-6333}}"
: "${LLAMA_URL:=http://${SERVICE_HOST}:${LLAMA_CPP_PORT:-8080}}"
: "${OPEN_WEBUI_URL:=http://${SERVICE_HOST}:${OPEN_WEBUI_PORT:-3001}}"
: "${GRAFANA_URL:=http://${SERVICE_HOST}:${GRAFANA_PORT:-3000}}"
: "${PROMETHEUS_URL:=http://${SERVICE_HOST}:${PROMETHEUS_PORT:-9090}}"
: "${RALPH_URL:=http://${SERVICE_HOST}:${RALPH_PORT:-8098}}"
: "${MINDSDB_URL:=http://${SERVICE_HOST}:${MINDSDB_PORT:-47334}}"
: "${DASHBOARD_API_URL:=http://${SERVICE_HOST}:${DASHBOARD_API_PORT:-8889}}"
: "${DASHBOARD_URL:=http://${SERVICE_HOST}:${DASHBOARD_PORT:-8888}}"
: "${EMBEDDINGS_URL:=http://${SERVICE_HOST}:${EMBEDDINGS_PORT:-8081}}"
: "${NETDATA_URL:=http://${SERVICE_HOST}:${NETDATA_PORT:-19999}}"
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

# ============================================================================
# K3s In-Cluster Service URLs
# When running inside K3s, services can be reached via cluster DNS.
# These are used by the dashboard-api pod and other in-cluster workloads.
# ============================================================================

: "${K3S_AIDB_SVC:=http://aidb.${AI_STACK_NAMESPACE:-ai-stack}.svc:8091}"
: "${K3S_HYBRID_SVC:=http://hybrid-coordinator.${AI_STACK_NAMESPACE:-ai-stack}.svc:8092}"
: "${K3S_QDRANT_SVC:=http://qdrant.${AI_STACK_NAMESPACE:-ai-stack}.svc:6333}"
: "${K3S_LLAMA_SVC:=http://llama-cpp.${AI_STACK_NAMESPACE:-ai-stack}.svc:8080}"
: "${K3S_GRAFANA_SVC:=http://grafana.${AI_STACK_NAMESPACE:-ai-stack}.svc:3000}"
: "${K3S_PROMETHEUS_SVC:=http://prometheus.${AI_STACK_NAMESPACE:-ai-stack}.svc:9090}"
: "${K3S_RALPH_SVC:=http://ralph-wiggum.${AI_STACK_NAMESPACE:-ai-stack}.svc:8098}"
: "${K3S_NGINX_SVC:=https://nginx.${AI_STACK_NAMESPACE:-ai-stack}.svc:443}"
