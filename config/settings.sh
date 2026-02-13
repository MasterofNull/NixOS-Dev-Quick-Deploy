#!/usr/bin/env bash
#
# Centralized Settings - Tunable parameters for all subsystems
# Purpose: Single source of truth for timeouts, retries, validation, and resource limits
# Version: 6.1.0
#
# Override any setting via environment variables before sourcing this file.
# Example: KUBECTL_TIMEOUT=120 ./nixos-quick-deploy.sh
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
#
# Required Libraries:
#   - None (loaded before libraries)
#
# Exports:
#   - Timeout, retry, validation, and resource settings
#
# ============================================================================

# ============================================================================
# Timeout Settings (seconds)
# ============================================================================
# These control how long we wait before killing external commands.
# Set higher values on slow hardware or unreliable networks.
# ============================================================================

: "${KUBECTL_TIMEOUT:=60}"              # kubectl API requests
: "${CURL_TIMEOUT:=10}"                 # curl total transfer time
: "${CURL_CONNECT_TIMEOUT:=5}"          # curl TCP connect phase
: "${NIXOS_REBUILD_TIMEOUT:=3600}"      # nixos-rebuild switch (1 hour)
: "${HOME_MANAGER_TIMEOUT:=1800}"       # home-manager switch (30 min)
: "${GENERIC_TIMEOUT:=120}"             # fallback for unclassified commands

# ============================================================================
# Retry / Backoff Settings
# ============================================================================
# Exponential backoff: delay doubles each attempt (with jitter).
# Circuit breaker opens after THRESHOLD consecutive failures.
# ============================================================================

: "${MAX_RETRY_ATTEMPTS:=3}"            # Max retries before giving up
: "${RETRY_BASE_DELAY:=2}"             # Initial delay between retries (seconds)
: "${RETRY_MAX_DELAY:=60}"             # Cap on backoff delay (seconds)
: "${CIRCUIT_BREAKER_THRESHOLD:=5}"     # Consecutive failures to trip breaker

# ============================================================================
# Input Validation Settings
# ============================================================================

: "${MIN_PASSWORD_LENGTH:=12}"          # Minimum password length for generated creds

# ============================================================================
# K3s / Kubernetes Settings
# ============================================================================
# Resource governance for the AI stack namespace.
# These are applied via LimitRange and ResourceQuota objects.
# ============================================================================

: "${AI_STACK_NAMESPACE:=ai-stack}"
: "${BACKUPS_NAMESPACE:=backups}"
: "${LOGGING_NAMESPACE:=logging}"
: "${K3S_AI_NAMESPACE:=${AI_STACK_NAMESPACE}}"
: "${K3S_KUBECONFIG:=/etc/rancher/k3s/k3s.yaml}"

# Default container resource requests
: "${K3S_DEFAULT_CPU_REQUEST:=100m}"
: "${K3S_DEFAULT_MEM_REQUEST:=128Mi}"

# Default container resource limits
: "${K3S_DEFAULT_CPU_LIMIT:=500m}"
: "${K3S_DEFAULT_MEM_LIMIT:=512Mi}"

# Maximum per-container limits (enforced by LimitRange)
: "${K3S_MAX_CPU_LIMIT:=4}"
: "${K3S_MAX_MEM_LIMIT:=8Gi}"

# Namespace-wide quotas (enforced by ResourceQuota)
: "${K3S_QUOTA_CPU:=8}"
: "${K3S_QUOTA_MEM:=16Gi}"
: "${K3S_QUOTA_PODS:=30}"

# ============================================================================
# Disk Space Requirements (GB)
# ============================================================================

: "${REQUIRED_DISK_SPACE_GB:=50}"

# ============================================================================
# Logging Defaults
# ============================================================================
# LOG_DIR, LOG_FILE, and LOG_LEVEL are set in the main script before
# libraries load. These serve as fallbacks when sourced in isolation.
# ============================================================================

: "${LOG_LEVEL:=INFO}"
: "${LOG_FORMAT:=json}"             # plain | json
: "${LOG_COMPONENT:=nixos-quick-deploy}"

# ============================================================================
# AI Stack Paths
# ============================================================================

: "${AI_STACK_CONFIG_DIR:=${HOME}/.config/nixos-ai-stack}"
: "${AI_STACK_ENV_FILE:=${AI_STACK_CONFIG_DIR}/.env}"

# ============================================================================
# NPM AI Tooling Versions (Pinned)
# ============================================================================

: "${OPEN_SKILLS_VERSION:=1.5.0}"

# ============================================================================
# Network / Service URLs
# ============================================================================
# Ports and endpoints for the K3s AI stack services.
# Override to match custom NodePort or Ingress configurations.
# ============================================================================

: "${QDRANT_PORT:=6333}"
: "${QDRANT_GRPC_PORT:=6334}"
: "${LLAMA_CPP_PORT:=8080}"
: "${OPEN_WEBUI_PORT:=3001}"
: "${POSTGRES_PORT:=5432}"
: "${REDIS_PORT:=6379}"
: "${GRAFANA_PORT:=3000}"
: "${PROMETHEUS_PORT:=9090}"
: "${AIDB_PORT:=8091}"
: "${HYBRID_COORDINATOR_PORT:=8092}"
: "${MINDSDB_PORT:=47334}"
: "${EMBEDDINGS_PORT:=8081}"
: "${DASHBOARD_API_PORT:=8889}"
: "${NETDATA_PORT:=19999}"
: "${DASHBOARD_PORT:=8888}"
: "${OLLAMA_PORT:=11434}"
: "${GITEA_PORT:=3003}"
: "${REDISINSIGHT_PORT:=5540}"
: "${ANTHROPIC_PROXY_PORT:=8094}"
: "${CONTAINER_ENGINE_PORT:=8095}"
