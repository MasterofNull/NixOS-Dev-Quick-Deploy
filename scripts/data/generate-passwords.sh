#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MANAGER="${ROOT_DIR}/scripts/governance/manage-secrets.sh"
HOST_NAME=""
FORCE=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      HOST_NAME="$2"
      shift 2
      ;;
    --force)
      FORCE=true
      shift
      ;;
    --help)
      echo "Usage: $0 [--host HOST_NAME] [--force]"
      echo ""
      echo "Generate or rotate the SOPS-backed password secrets used by the local AI stack."
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

if [[ ! -x "${MANAGER}" ]]; then
  echo "Missing secrets manager wrapper: ${MANAGER}" >&2
  exit 1
fi

manager_args=()
if [[ -n "${HOST_NAME}" ]]; then
  manager_args+=(--host "${HOST_NAME}")
fi

echo "scripts/data/generate-passwords.sh is a compatibility shim over scripts/governance/manage-secrets.sh." >&2
"${MANAGER}" "${manager_args[@]}" set postgres_password --generate
"${MANAGER}" "${manager_args[@]}" set redis_password --generate

if [[ "${FORCE}" == true ]]; then
  echo "Password secrets rotated in the external SOPS bundle." >&2
else
  echo "Password secrets ensured in the external SOPS bundle." >&2
fi
