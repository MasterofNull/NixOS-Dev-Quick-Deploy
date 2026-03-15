#!/usr/bin/env bash
#
# Dashboard Notification Helper
# Sends deployment progress updates to dashboard API

# Dashboard API URL (configurable via environment)
DASHBOARD_API_URL="${DASHBOARD_API_URL:-http://localhost:8005}"
DEPLOYMENT_ID="${DEPLOYMENT_ID:-}"

# Check if dashboard integration is enabled
DASHBOARD_ENABLED="${DASHBOARD_ENABLED:-true}"

# Logging
log_debug() {
  [[ "${VERBOSE:-0}" == "1" ]] && echo "[dashboard-notify] $*" >&2
}

log_error() {
  echo "[dashboard-notify] ERROR: $*" >&2
}

# ============================================================================
# Dashboard API Functions
# ============================================================================

dashboard_api_call() {
  local endpoint="$1"
  local method="${2:-POST}"
  local data="${3:-}"

  if [[ "${DASHBOARD_ENABLED}" != "true" ]]; then
    log_debug "Dashboard integration disabled"
    return 0
  fi

  local url="${DASHBOARD_API_URL}/api${endpoint}"

  log_debug "${method} ${url}"

  if [[ -n "$data" ]]; then
    curl -fsS -X "${method}" \
      -H "Content-Type: application/json" \
      -d "$data" \
      "$url" 2>/dev/null || {
      log_debug "Dashboard API call failed (dashboard may not be running)"
      return 0  # Don't fail the deployment if dashboard is down
    }
  else
    curl -fsS -X "${method}" "$url" 2>/dev/null || {
      log_debug "Dashboard API call failed (dashboard may not be running)"
      return 0
    }
  fi
}

# Start deployment tracking
notify_deployment_start() {
  local command="$1"
  local user="${2:-${USER:-system}}"

  # Generate deployment ID if not set
  if [[ -z "$DEPLOYMENT_ID" ]]; then
    DEPLOYMENT_ID="deploy-$(date +%Y%m%d-%H%M%S)-$$"
    export DEPLOYMENT_ID
  fi

  log_debug "Starting deployment tracking: ${DEPLOYMENT_ID}"

  dashboard_api_call \
    "/deployments/start?deployment_id=${DEPLOYMENT_ID}&command=${command}&user=${user}" \
    "POST"

  # Save deployment ID for child processes
  echo "${DEPLOYMENT_ID}" > /tmp/deploy-id.txt 2>/dev/null || true
}

# Update deployment progress
notify_deployment_progress() {
  local progress="$1"
  local message="$2"
  local log_line="${3:-}"

  # Get deployment ID from environment or file
  if [[ -z "$DEPLOYMENT_ID" ]]; then
    DEPLOYMENT_ID=$(cat /tmp/deploy-id.txt 2>/dev/null || echo "")
  fi

  if [[ -z "$DEPLOYMENT_ID" ]]; then
    log_debug "No deployment ID, skipping progress update"
    return 0
  fi

  log_debug "Progress ${progress}%: ${message}"

  local json_data
  if [[ -n "$log_line" ]]; then
    # Escape JSON special characters
    log_line=$(echo "$log_line" | sed 's/"/\\"/g' | sed "s/'/\\'/g")
    json_data="{\"progress\": ${progress}, \"message\": \"${message}\", \"log\": \"${log_line}\"}"
  else
    json_data="{\"progress\": ${progress}, \"message\": \"${message}\"}"
  fi

  dashboard_api_call \
    "/deployments/${DEPLOYMENT_ID}/progress" \
    "POST" \
    "$json_data"
}

# Complete deployment
notify_deployment_complete() {
  local success="${1:-true}"
  local message="${2:-Deployment completed}"

  # Get deployment ID from environment or file
  if [[ -z "$DEPLOYMENT_ID" ]]; then
    DEPLOYMENT_ID=$(cat /tmp/deploy-id.txt 2>/dev/null || echo "")
  fi

  if [[ -z "$DEPLOYMENT_ID" ]]; then
    log_debug "No deployment ID, skipping completion notification"
    return 0
  fi

  log_debug "Completing deployment: ${DEPLOYMENT_ID} (success=${success})"

  local json_data="{\"success\": ${success}, \"message\": \"${message}\"}"

  dashboard_api_call \
    "/deployments/${DEPLOYMENT_ID}/complete" \
    "POST" \
    "$json_data"

  # Cleanup
  rm -f /tmp/deploy-id.txt 2>/dev/null || true
}

# ============================================================================
# Main CLI Interface
# ============================================================================

show_help() {
  cat <<EOF
Usage: dashboard-notify.sh COMMAND [OPTIONS]

Send deployment progress updates to dashboard API.

COMMANDS:
  start COMMAND [USER]        Start deployment tracking
  progress PERCENT MESSAGE    Update progress (0-100)
  log MESSAGE                 Send log message
  complete [SUCCESS] [MSG]    Complete deployment (SUCCESS: true/false)

ENVIRONMENT VARIABLES:
  DASHBOARD_API_URL           Dashboard API URL (default: http://localhost:8005)
  DASHBOARD_ENABLED           Enable dashboard integration (default: true)
  DEPLOYMENT_ID               Deployment tracking ID (auto-generated if not set)

EXAMPLES:
  dashboard-notify.sh start "deploy system"
  dashboard-notify.sh progress 25 "Validating configuration"
  dashboard-notify.sh log "Building system configuration"
  dashboard-notify.sh complete true "Deployment successful"
  dashboard-notify.sh complete false "Deployment failed"
EOF
}

# Main command dispatcher
case "${1:-}" in
  start)
    shift
    notify_deployment_start "$@"
    ;;
  progress)
    shift
    notify_deployment_progress "$@"
    ;;
  log)
    shift
    notify_deployment_progress "${DEPLOYMENT_PROGRESS:-0}" "$1" "$1"
    ;;
  complete)
    shift
    notify_deployment_complete "$@"
    ;;
  help|--help|-h)
    show_help
    ;;
  *)
    echo "Error: Unknown command: ${1:-}" >&2
    echo "" >&2
    show_help >&2
    exit 1
    ;;
esac
