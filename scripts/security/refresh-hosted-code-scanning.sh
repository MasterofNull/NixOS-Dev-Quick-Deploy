#!/usr/bin/env bash
# Dispatch the hosted security workflow, wait for completion, and refresh local alert exports.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORKFLOW_FILE="security.yml"
REF="$(git -C "${ROOT_DIR}" rev-parse --abbrev-ref HEAD)"
WAIT_FOR_RUN=true
TIMEOUT_SECONDS=1800
POLL_INTERVAL=10

usage() {
  cat <<'EOF'
Usage: scripts/security/refresh-hosted-code-scanning.sh [options]

Dispatches the GitHub Actions security workflow for the current branch, optionally
waits for completion, then refreshes the local code-scanning export and summary.

Options:
  --ref branch         Git ref to dispatch (default: current branch)
  --no-wait            Dispatch only; do not wait for workflow completion
  --timeout seconds    Maximum wait time when --wait is enabled (default: 1800)
  --poll seconds       Poll interval while locating the new workflow run (default: 10)
  -h, --help           Show this help text
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ref)
      REF="${2:?missing value for --ref}"
      shift 2
      ;;
    --no-wait)
      WAIT_FOR_RUN=false
      shift
      ;;
    --timeout)
      TIMEOUT_SECONDS="${2:?missing value for --timeout}"
      shift 2
      ;;
    --poll)
      POLL_INTERVAL="${2:?missing value for --poll}"
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

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 2
  }
}

require_cmd gh
require_cmd jq
require_cmd date

gh auth status >/dev/null

head_sha="$(git -C "${ROOT_DIR}" rev-parse "${REF}")"
started_epoch="$(date +%s)"

echo "Dispatching ${WORKFLOW_FILE} on ref ${REF} (${head_sha})"
gh workflow run "${WORKFLOW_FILE}" --ref "${REF}"

if [[ "${WAIT_FOR_RUN}" != true ]]; then
  echo "Workflow dispatched. Refresh export later with:"
  echo "  bash scripts/security/export-github-code-scanning-alerts.sh"
  exit 0
fi

run_id=""
deadline=$((started_epoch + TIMEOUT_SECONDS))
while (( "$(date +%s)" < deadline )); do
  run_id="$(
    gh run list \
      --workflow "${WORKFLOW_FILE}" \
      --branch "${REF}" \
      --limit 20 \
      --json databaseId,headSha,event,status,createdAt \
      --jq '
        map(select(.event == "workflow_dispatch" and .headSha == "'"${head_sha}"'"))
        | sort_by(.createdAt)
        | reverse
        | .[0].databaseId // empty
      '
  )"
  if [[ -n "${run_id}" ]]; then
    break
  fi
  sleep "${POLL_INTERVAL}"
done

[[ -n "${run_id}" ]] || {
  echo "Timed out locating dispatched workflow run for ${WORKFLOW_FILE} on ${REF}" >&2
  exit 1
}

echo "Watching workflow run ${run_id}"
gh run watch "${run_id}" --exit-status

echo "Refreshing local hosted backlog export"
bash "${ROOT_DIR}/scripts/security/export-github-code-scanning-alerts.sh"
bash "${ROOT_DIR}/scripts/security/summarize-github-code-scanning-alerts.sh"
