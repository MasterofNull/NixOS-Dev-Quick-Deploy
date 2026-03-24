#!/usr/bin/env bash
# Reconcile hosted GitHub code scanning by exporting, reporting residuals, removing stale analyses, and exporting again.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APPLY=false
SHOW_SUMMARY=true
REF="refs/heads/main"
WAIT_FOR_IDLE=true
IDLE_TIMEOUT_SECONDS=900
IDLE_POLL_SECONDS=15
SETTLE_SECONDS=0

usage() {
  cat <<'EOF'
Usage: scripts/security/reconcile-github-code-scanning.sh [options]

Reconcile hosted GitHub code scanning after a workflow run by:
1. exporting the current backlog snapshot,
2. reporting residual open categories versus current workflow categories,
3. deleting stale deletable analyses whose categories no longer exist,
4. exporting a fresh snapshot again,
5. printing summary, residuals, and delta output.

Options:
  --ref git-ref       Limit reconciliation to one ref (default: refs/heads/main)
  --apply       Delete stale analyses instead of dry-run only
  --no-wait-for-idle  Do not wait for in-flight security workflow runs to finish
  --idle-timeout s    Maximum seconds to wait for workflow idleness (default: 900)
  --idle-poll s       Poll interval while waiting for workflow idleness (default: 15)
  --settle-seconds s  Sleep before post-cleanup export to allow GitHub reconciliation
  --no-summary  Skip summary and delta output
  -h, --help    Show this help text
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ref)
      REF="${2:?missing value for --ref}"
      shift 2
      ;;
    --apply)
      APPLY=true
      shift
      ;;
    --no-wait-for-idle)
      WAIT_FOR_IDLE=false
      shift
      ;;
    --idle-timeout)
      IDLE_TIMEOUT_SECONDS="${2:?missing value for --idle-timeout}"
      shift 2
      ;;
    --idle-poll)
      IDLE_POLL_SECONDS="${2:?missing value for --idle-poll}"
      shift 2
      ;;
    --settle-seconds)
      SETTLE_SECONDS="${2:?missing value for --settle-seconds}"
      shift 2
      ;;
    --no-summary)
      SHOW_SUMMARY=false
      shift
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

require_cmd bash
require_cmd gh
require_cmd jq
require_cmd date

branch_name="${REF#refs/heads/}"

wait_for_idle() {
  local deadline current_runs
  deadline=$(( $(date +%s) + IDLE_TIMEOUT_SECONDS ))

  while (( $(date +%s) < deadline )); do
    current_runs="$(
      gh run list \
        --workflow "security.yml" \
        --branch "${branch_name}" \
        --limit 20 \
        --json databaseId,status,event \
        --jq '
          map(select(
            (.event == "push" or .event == "workflow_dispatch")
            and (.status == "in_progress" or .status == "queued" or .status == "waiting" or .status == "requested" or .status == "pending")
          ))
        '
    )"

    if [[ "$(jq 'length' <<<"${current_runs}")" == "0" ]]; then
      return 0
    fi

    echo "Waiting for hosted security workflow idleness on ${branch_name}"
    jq -r '.[] | "  run \(.databaseId): status=\(.status) event=\(.event)"' <<<"${current_runs}"
    sleep "${IDLE_POLL_SECONDS}"
  done

  echo "Timed out waiting for hosted security workflow idleness on ${branch_name}" >&2
  return 1
}

if [[ "${WAIT_FOR_IDLE}" == true ]]; then
  wait_for_idle
fi

echo "Exporting pre-reconciliation snapshot"
bash "${ROOT_DIR}/scripts/security/export-github-code-scanning-alerts.sh"

echo "Reporting pre-reconciliation residual categories"
bash "${ROOT_DIR}/scripts/security/report-github-code-scanning-residuals.sh" --ref "${REF}"

cleanup_args=()
if [[ "${APPLY}" == true ]]; then
  cleanup_args+=(--apply)
fi

echo "Reconciling stale analyses"
bash "${ROOT_DIR}/scripts/security/cleanup-stale-code-scanning-analyses.sh" --ref "${REF}" "${cleanup_args[@]}"

if (( SETTLE_SECONDS > 0 )); then
  echo "Waiting ${SETTLE_SECONDS}s for GitHub alert reconciliation"
  sleep "${SETTLE_SECONDS}"
fi

echo "Exporting post-reconciliation snapshot"
bash "${ROOT_DIR}/scripts/security/export-github-code-scanning-alerts.sh"

if [[ "${SHOW_SUMMARY}" == true ]]; then
  bash "${ROOT_DIR}/scripts/security/summarize-github-code-scanning-alerts.sh"
  bash "${ROOT_DIR}/scripts/security/report-github-code-scanning-residuals.sh" --ref "${REF}"
  bash "${ROOT_DIR}/scripts/security/compare-github-code-scanning-alerts.sh"
fi
