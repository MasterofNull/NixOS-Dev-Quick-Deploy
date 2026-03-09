#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MANAGER="${ROOT_DIR}/scripts/governance/manage-secrets.sh"
HOST_NAME=""
SERVICE=""
FORCE=false

service_to_secret() {
  case "${1:-}" in
    aidb) echo "aidb_api_key" ;;
    hybrid|hybrid-coordinator|coordinator) echo "hybrid_coordinator_api_key" ;;
    embeddings) echo "embeddings_api_key" ;;
    aider|aider-wrapper) echo "aider_wrapper_api_key" ;;
    nixos-docs|docs) echo "nixos_docs_api_key" ;;
    remote|openrouter|remote-llm) echo "remote_llm_api_key" ;;
    "")
      echo ""
      ;;
    *)
      echo "Unknown service '${1}'. Expected one of: aidb, hybrid, embeddings, aider-wrapper, nixos-docs, remote-llm." >&2
      return 1
      ;;
  esac
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --service)
      SERVICE="$2"
      shift 2
      ;;
    --host)
      HOST_NAME="$2"
      shift 2
      ;;
    --force)
      FORCE=true
      shift
      ;;
    --help)
      echo "Usage: $0 [--service SERVICE_NAME]"
      echo "       $0 --service SERVICE_NAME [--host HOST_NAME] [--force]"
      echo ""
      echo "Generate or rotate a service API key inside the external SOPS bundle."
      echo "This is a compatibility shim over scripts/governance/manage-secrets.sh."
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

if [[ -z "${SERVICE}" ]]; then
  if [[ "${FORCE}" == true ]]; then
    echo "Refusing to rotate all API keys via ${0}. Use ${MANAGER} init --include-optional --force explicitly." >&2
    exit 2
  fi
  exec "${MANAGER}" "${manager_args[@]}" init --include-optional
fi

secret_name="$(service_to_secret "${SERVICE}")"
set_args=(set "${secret_name}" --generate)
exec "${MANAGER}" "${manager_args[@]}" "${set_args[@]}"
