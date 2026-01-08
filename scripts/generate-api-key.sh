#!/usr/bin/env bash
set -euo pipefail

# Generate API keys for AI stack services
# Usage:
#   ./generate-api-key.sh                    # Generate master stack_api_key
#   ./generate-api-key.sh --service aidb     # Generate service-specific key

SECRETS_DIR="${SECRETS_DIR:-$(pwd)/ai-stack/compose/secrets}"
SERVICE=""

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --service)
      SERVICE="$2"
      shift 2
      ;;
    --help)
      echo "Usage: $0 [--service SERVICE_NAME]"
      echo "  --service  Generate key for specific service (aidb, embeddings, hybrid, nixos-docs)"
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

mkdir -p "${SECRETS_DIR}"

# Determine key file name
if [[ -n "${SERVICE}" ]]; then
  KEY_FILE="${SECRETS_DIR}/${SERVICE}_api_key"
else
  KEY_FILE="${SECRETS_DIR}/stack_api_key"
fi

if [[ -f "${KEY_FILE}" ]]; then
  echo "⚠️  API key already exists at ${KEY_FILE}" >&2
  echo "To rotate this key, use: ./scripts/rotate-api-key.sh --service ${SERVICE:-stack}" >&2
  exit 0
fi

# Generate secure random key
umask 077
openssl rand -hex 32 > "${KEY_FILE}"
chmod 0400 "${KEY_FILE}"  # Read-only for owner

echo "✅ Generated API key at ${KEY_FILE}"
echo "   Permissions: $(stat -c %a "${KEY_FILE}") (owner read-only)"

# Log key generation for audit trail
if [[ -d "${SECRETS_DIR}/../audit" ]] || mkdir -p "${SECRETS_DIR}/../audit"; then
  echo "$(date -Iseconds) | GENERATE | ${KEY_FILE##*/} | $(whoami)" >> "${SECRETS_DIR}/../audit/api-keys.log"
fi
