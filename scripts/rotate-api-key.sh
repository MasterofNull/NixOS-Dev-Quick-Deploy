#!/usr/bin/env bash
set -euo pipefail

# Rotate API keys for AI stack services
# Usage:
#   ./rotate-api-key.sh --service aidb     # Rotate service-specific key
#   ./rotate-api-key.sh                    # Rotate master stack_api_key

SECRETS_DIR="${SECRETS_DIR:-$(pwd)/ai-stack/kubernetes/secrets/generated}"
SERVICE=""
FORCE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --service)
      SERVICE="$2"
      shift 2
      ;;
    --force)
      FORCE=true
      shift
      ;;
    --help)
      echo "Usage: $0 [--service SERVICE_NAME] [--force]"
      echo "  --service  Rotate key for specific service (aidb, embeddings, hybrid, nixos-docs)"
      echo "  --force    Skip confirmation prompt"
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

# Determine key file name
if [[ -n "${SERVICE}" ]]; then
  KEY_FILE="${SECRETS_DIR}/${SERVICE}_api_key"
  SERVICE_NAME="${SERVICE}"
else
  KEY_FILE="${SECRETS_DIR}/stack_api_key"
  SERVICE_NAME="stack (all services)"
fi

if [[ ! -f "${KEY_FILE}" ]]; then
  echo "❌ API key does not exist at ${KEY_FILE}" >&2
  echo "   Generate it first with: ./scripts/generate-api-key.sh ${SERVICE:+--service ${SERVICE}}" >&2
  exit 1
fi

# Confirmation
if [[ "${FORCE}" != "true" ]]; then
  echo "⚠️  WARNING: Key rotation will require restarting services!"
  echo "   Affected: ${SERVICE_NAME}"
  read -rp "Continue? (y/N): " confirm
  if [[ ! "${confirm}" =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
  fi
fi

# Backup old key
BACKUP_DIR="${SECRETS_DIR}/backups"
mkdir -p "${BACKUP_DIR}"
BACKUP_FILE="${BACKUP_DIR}/$(basename "${KEY_FILE}").$(date +%Y%m%d_%H%M%S).bak"
cp "${KEY_FILE}" "${BACKUP_FILE}"
chmod 0400 "${BACKUP_FILE}"
echo "📦 Backed up old key to: ${BACKUP_FILE}"

# Generate new key
umask 077
openssl rand -hex 32 > "${KEY_FILE}"
chmod 0400 "${KEY_FILE}"

echo "✅ Rotated API key: ${KEY_FILE}"
echo "   Permissions: $(stat -c %a "${KEY_FILE}") (owner read-only)"

# Log rotation for audit trail
if [[ -d "${SECRETS_DIR}/../audit" ]] || mkdir -p "${SECRETS_DIR}/../audit"; then
  echo "$(date -Iseconds) | ROTATE | ${KEY_FILE##*/} | $(whoami) | backup=${BACKUP_FILE}" >> "${SECRETS_DIR}/../audit/api-keys.log"
fi

# Instructions for next steps
echo ""
echo "📝 Next steps:"
if [[ -n "${SERVICE}" ]]; then
  echo "   1. Restart service: kubectl rollout restart deploy -n ai-stack ${SERVICE}"
  echo "   2. Verify health: curl -H 'X-API-Key: \$(cat ${KEY_FILE})' https://localhost:8443/${SERVICE}/health"
else
  echo "   1. Restart all services: kubectl rollout restart deploy -n ai-stack --all"
  echo "   2. Verify health: ./scripts/system-health-check.sh"
fi
echo ""
echo "   Backup retained for 90 days at: ${BACKUP_FILE}"
