#!/usr/bin/env bash
# Build a non-destructive secrets rotation readiness/impact report.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MANAGER="${ROOT_DIR}/scripts/governance/manage-secrets.sh"
OUTPUT_DIR="${AI_SECURITY_AUDIT_DIR:-${HOME}/.local/share/nixos-ai-stack/security}"
REPORT_PATH="${SECRETS_ROTATION_PLAN_REPORT_PATH:-${OUTPUT_DIR}/latest-secrets-rotation-plan.json}"
HOST_NAME=""
STATUS_JSON=""

usage() {
  cat <<'EOF'
Usage: scripts/security/secrets-rotation-plan.sh [--host HOST] [--status-json PATH] [--output PATH]

Build a non-destructive secrets rotation readiness/impact report from the
declarative manage-secrets inventory.
EOF
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 2
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      HOST_NAME="${2:?missing value for --host}"
      shift 2
      ;;
    --status-json)
      STATUS_JSON="${2:?missing value for --status-json}"
      shift 2
      ;;
    --output)
      REPORT_PATH="${2:?missing value for --output}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

require_cmd jq

if [[ -z "${STATUS_JSON}" ]]; then
  [[ -x "${MANAGER}" ]] || { echo "Missing ${MANAGER}" >&2; exit 1; }
  tmp_status="$(mktemp)"
  trap 'rm -f "${tmp_status}"' EXIT
  manager_args=()
  if [[ -n "${HOST_NAME}" ]]; then
    manager_args+=(--host "${HOST_NAME}")
  fi
  "${MANAGER}" "${manager_args[@]}" status --format json > "${tmp_status}"
  STATUS_JSON="${tmp_status}"
fi

mkdir -p "$(dirname "${REPORT_PATH}")"

jq '
  def restart_groups(name):
    if name == "hybrid_coordinator_api_key" then ["ai-hybrid-coordinator.service", "command-center-dashboard-api.service", "switchboard", "workflow clients"]
    elif name == "aidb_api_key" then ["ai-aidb.service", "ai-ralph-wiggum.service", "command-center-dashboard-api.service"]
    elif name == "embeddings_api_key" then ["ai-embeddings.service", "ai-hybrid-coordinator.service"]
    elif name == "postgres_password" then ["postgresql.service", "ai-aidb.service", "ai-hybrid-coordinator.service", "command-center-dashboard-api.service", "meta-optimization"]
    elif name == "redis_password" then ["redis service consumers", "nixos-docs"]
    elif name == "aider_wrapper_api_key" then ["ai-aider-wrapper.service", "ai-hybrid-coordinator.service"]
    elif name == "nixos_docs_api_key" then ["ai-nixos-docs.service"]
    elif name == "remote_llm_api_key" then ["switchboard remote routing", "hybrid remote delegation"]
    else []
    end;
  def rotation_command(name; host):
    if host != null and host != "" then
      ("./scripts/governance/manage-secrets.sh --host " + host + " set " + name + " --generate")
    else
      ("./scripts/governance/manage-secrets.sh set " + name + " --generate")
    end;
  {
    generated_at: (now | todateiso8601),
    host: .host,
    bundle: .bundle,
    age_key_file: .age_key_file,
    local_override: .local_override,
    rotation_ready: (.core_ready and (.bundle != null) and (.age_key_file != null) and (.local_override != null)),
    core_ready: .core_ready,
    all_managed_ready: .all_managed_ready,
    missing_by_scope: .missing_by_scope,
    summary: {
      total_managed_secrets: (.secrets | length),
      present_secrets: ([.secrets[] | select(.present == true)] | length),
      missing_secrets: ([.secrets[] | select(.present != true)] | length),
      core_missing: (.missing_by_scope.core | length),
      optional_missing: (.missing_by_scope.optional | length),
      remote_missing: (.missing_by_scope.remote | length)
    },
    secrets: [
      .secrets[]
      | . + {
          restart_groups: restart_groups(.name),
          rotation_command: rotation_command(.name; .host),
          disruption: (
            if (.name == "postgres_password" or .name == "hybrid_coordinator_api_key" or .name == "aidb_api_key") then "high"
            elif (.name == "embeddings_api_key" or .name == "aider_wrapper_api_key") then "medium"
            else "low"
            end
          )
        }
    ],
    next_steps: (
      .next_steps + [
        "Generate a rotation plan before mutating any secret values.",
        "Rotate one secret at a time and validate affected services after each change."
      ]
    )
  }
' "${STATUS_JSON}" > "${REPORT_PATH}"

echo "Secrets rotation plan report written: ${REPORT_PATH}"
