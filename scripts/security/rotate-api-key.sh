#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MANAGER="${ROOT_DIR}/scripts/governance/manage-secrets.sh"
HOST_NAME=""
SERVICE=""

service_to_secret() {
  case "${1:-}" in
    stack|"")
      echo ""
      ;;
    aidb) echo "aidb_api_key" ;;
    hybrid|hybrid-coordinator|coordinator) echo "hybrid_coordinator_api_key" ;;
    embeddings) echo "embeddings_api_key" ;;
    aider|aider-wrapper) echo "aider_wrapper_api_key" ;;
    nixos-docs|docs) echo "nixos_docs_api_key" ;;
    remote|openrouter|remote-llm) echo "remote_llm_api_key" ;;
    *)
      echo "Unknown service '${1}'. Expected one of: stack, aidb, hybrid, embeddings, aider-wrapper, nixos-docs, remote-llm." >&2
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
      shift
      ;;
    --help)
      echo "Usage: $0 [--service SERVICE_NAME] [--host HOST_NAME]"
      echo ""
      echo "Rotate one API key in the external SOPS bundle."
      echo "Use --service stack only to print guidance for full rotation."
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

if [[ -z "${SERVICE}" || "${SERVICE}" == "stack" ]]; then
  echo "Rotating all API keys is handled declaratively. Run:" >&2
  echo "  ${MANAGER} ${manager_args[*]} init --include-optional --force" >&2
  exit 0
fi

secret_name="$(service_to_secret "${SERVICE}")"
echo "scripts/security/rotate-api-key.sh is a compatibility shim over scripts/governance/manage-secrets.sh." >&2
exec "${MANAGER}" "${manager_args[@]}" set "${secret_name}" --generate
