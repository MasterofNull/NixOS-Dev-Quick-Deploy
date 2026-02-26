#!/usr/bin/env bash
#
# Centralized Settings - Tunable parameters for all subsystems
# Purpose: Single source of truth for timeouts, retries, validation, and resource limits
# Version: 6.1.0
#
# Override any setting via environment variables before sourcing this file.
# Example: DEPLOY_API_TIMEOUT=120 ./nixos-quick-deploy.sh
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

: "${DEPLOY_API_TIMEOUT:=60}"           # Deployment API requests
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
# AI Stack Runtime Resource Settings
# ============================================================================
# Resource governance defaults for AI stack workflows.
# ============================================================================

: "${AI_STACK_NAMESPACE:=ai-stack}"
: "${BACKUPS_NAMESPACE:=backups}"
: "${LOGGING_NAMESPACE:=logging}"

# Default container resource requests
: "${AI_STACK_DEFAULT_CPU_REQUEST:=100m}"
: "${AI_STACK_DEFAULT_MEM_REQUEST:=128Mi}"

# Default container resource limits
: "${AI_STACK_DEFAULT_CPU_LIMIT:=500m}"
: "${AI_STACK_DEFAULT_MEM_LIMIT:=512Mi}"

# Maximum per-container limits (enforced by LimitRange)
: "${AI_STACK_MAX_CPU_LIMIT:=4}"
: "${AI_STACK_MAX_MEM_LIMIT:=8Gi}"

# Namespace-wide quotas (enforced by ResourceQuota)
: "${AI_STACK_QUOTA_CPU:=8}"
: "${AI_STACK_QUOTA_MEM:=16Gi}"
: "${AI_STACK_QUOTA_PODS:=30}"

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
# Ports and endpoints for AI stack services.
# Override to match your host-level declarative port registry.
# ============================================================================

: "${QDRANT_PORT:=6333}"
: "${QDRANT_GRPC_PORT:=6334}"
: "${LLAMA_CPP_PORT:=8080}"
: "${OPEN_WEBUI_PORT:=3001}"
: "${POSTGRES_PORT:=5432}"
: "${REDIS_PORT:=6379}"
: "${GRAFANA_PORT:=3000}"
: "${PROMETHEUS_PORT:=9090}"
: "${AIDB_PORT:=8002}"
: "${HYBRID_COORDINATOR_PORT:=8003}"
: "${MINDSDB_PORT:=47334}"
: "${EMBEDDINGS_PORT:=8081}"
: "${SWITCHBOARD_PORT:=8085}"
: "${AIDER_WRAPPER_PORT:=8090}"
: "${NIXOS_DOCS_PORT:=8096}"
: "${DASHBOARD_API_PORT:=8889}"
: "${NETDATA_PORT:=19999}"
: "${DASHBOARD_PORT:=8888}"
: "${OLLAMA_PORT:=11434}"
: "${GITEA_PORT:=3003}"
: "${REDISINSIGHT_PORT:=5540}"
: "${ANTHROPIC_PROXY_PORT:=8094}"
: "${CONTAINER_ENGINE_PORT:=8095}"
: "${RALPH_PORT:=8004}"
