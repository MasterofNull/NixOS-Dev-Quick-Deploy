#!/usr/bin/env bash
#
# Validate centralized deployment configuration.
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

ENV_FILE=""

usage() {
  cat <<'EOF'
Usage: ./scripts/validate-config-settings.sh [options]

Options:
  --env-file PATH   Source additional environment overrides from PATH
  -h, --help        Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file)
      ENV_FILE="${2:?missing value for --env-file}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -n "$ENV_FILE" ]]; then
  [[ -f "$ENV_FILE" ]] || {
    echo "ERROR: env file not found: $ENV_FILE" >&2
    exit 1
  }
  # shellcheck source=/dev/null
  source "$ENV_FILE"
fi

# Base settings first.
# shellcheck source=/dev/null
source "${PROJECT_ROOT}/config/settings.sh"
# shellcheck source=/dev/null
source "${PROJECT_ROOT}/lib/error-codes.sh"
# logging.sh is optional in this standalone validator; avoid hard failure if
# logging dependencies or environment assumptions differ in CI shells.
if [[ -f "${PROJECT_ROOT}/lib/logging.sh" ]]; then
  # shellcheck source=/dev/null
  source "${PROJECT_ROOT}/lib/logging.sh" || true
fi

# Minimal fallbacks when called outside the full deploy script.
if ! declare -F print_error >/dev/null 2>&1; then
  print_error() { printf 'ERROR: %s\n' "$*" >&2; }
fi

if ! declare -F print_info >/dev/null 2>&1; then
  print_info() { printf '%s\n' "$*"; }
fi

if ! declare -F log_error >/dev/null 2>&1; then
  log_error() { printf 'ERROR: %s\n' "$*" >&2; }
fi

# shellcheck source=/dev/null
source "${PROJECT_ROOT}/lib/validation-input.sh"

if ! validate_config_settings; then
  print_error "Configuration validation failed."
  exit "${ERR_CONFIG_INVALID:-30}"
fi

printf 'Configuration validation passed.\n'
